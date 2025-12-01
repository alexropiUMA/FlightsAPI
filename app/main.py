from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import AsyncGenerator, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse

from app import config
from app.schemas import FlightOffer, FlightSearchRequest, PriceAlert, MonitorStatus
from app.services.flight_provider import FlightProvider
from app.services.amadeus_provider import AmadeusFlightProvider, ProviderError
from app.services.notification import NotificationService

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FlightsAPI",
    description="Monitor de vuelos Málaga (AGP) -> Quito (UIO) con alerta de precios",
    version="0.1.0",
)


class AppState:
    def __init__(self, provider: FlightProvider, notifier: NotificationService):
        self.provider = provider
        self.notifier = notifier
        self.latest_offers: Dict[str, FlightOffer] = {}
        self.latest_updated_at: Dict[str, str] = {}
        self.latest_status: Dict[str, MonitorStatus] = {}
        self.target_windows: Dict[str, FlightSearchRequest] = {}
        self.monitor_task: Optional[asyncio.Task] = None
        self.subscribers: List[asyncio.Queue[str]] = []


state = AppState(
    provider=None,  # initialized on startup
    notifier=NotificationService(recipients=config.EMAIL_RECIPIENTS),
)


def local_zone() -> ZoneInfo:
    try:
        return ZoneInfo(config.LOCAL_TIMEZONE)
    except ZoneInfoNotFoundError:
        logger.warning(
            "Zona horaria %s no encontrada; usando UTC. Instala 'tzdata' en entornos Windows",
            config.LOCAL_TIMEZONE,
        )
        return ZoneInfo("UTC")


def window_key(request: FlightSearchRequest) -> str:
    return f"{request.departure_date}:{request.return_date}"


def seed_target_windows() -> None:
    for window in config.TARGET_WINDOWS:
        state.target_windows[window_key(window)] = window


def build_provider() -> FlightProvider:
    if not config.AMADEUS_CONFIGURED:
        raise ProviderError("amadeus", "Faltan credenciales: solo se permiten datos reales")
    logger.info("Usando proveedor Amadeus (solo datos reales)")
    return AmadeusFlightProvider.from_env(
        client_id=config.AMADEUS_CLIENT_ID,
        client_secret=config.AMADEUS_CLIENT_SECRET,
    )


async def monitor_prices():
    if state.provider is None:
        logger.error("Proveedor no inicializado; deteniendo monitor")
        return
    logger.info("Iniciando monitor de precios para %s combinaciones", len(config.TARGET_WINDOWS))
    while True:
        for window in config.TARGET_WINDOWS:
            normalized = normalize_request(window)
            key = window_key(normalized)
            record_status(key, "running", "Consultando Amadeus en tiempo real…")

            try:
                offers = await state.provider.search_round_trip(normalized)
            except ProviderError as exc:
                detail = classify_provider_error(str(exc))
                logger.error("%s (%s -> %s)", detail, normalized.origin, normalized.destination)
                record_status(key, "error", detail)
                continue

            if not offers:
                detail = (
                    "Amadeus devolvió 0 resultados para estas fechas. Puede ser falta de plazas "
                    "o un caché temporal tras una consulta reciente."
                )
                logger.info(
                    "%s (%s - %s)",
                    detail,
                    normalized.departure_date,
                    normalized.return_date,
                )
                record_status(key, "empty", detail)
                continue

            best_offer = min(offers, key=lambda offer: offer.total_price)
            record_offer(key, best_offer)
            record_status(
                key,
                "ok",
                f"{len(offers)} ofertas reales recibidas; mejor {best_offer.total_price:.2f} {best_offer.currency}",
            )

            below_threshold = best_offer.total_price <= config.DEFAULT_PRICE_THRESHOLD
            if below_threshold:
                alert = PriceAlert(
                    window=window,
                    best_price=best_offer.total_price,
                    below_threshold=below_threshold,
                    message=(
                        f"{window.origin}->{window.destination} {window.departure_date} - {window.return_date} "
                        f"por {best_offer.total_price}€"
                    ),
                )
                await state.notifier.send_price_alert(alert)
            else:
                logger.info(
                    "Mejor precio %s - %s: %.2f€ (umbral %.2f€)",
                    window.departure_date,
                    window.return_date,
                    best_offer.total_price,
                    config.DEFAULT_PRICE_THRESHOLD,
                )

        await asyncio.sleep(config.DEFAULT_CHECK_INTERVAL_MINUTES * 60)


@app.on_event("startup")
async def on_startup() -> None:
    seed_target_windows()
    ensure_pending_statuses()
    try:
        state.provider = build_provider()
    except ProviderError as exc:
        logger.error("%s", exc)
        return

    state.monitor_task = asyncio.create_task(monitor_prices())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    if state.monitor_task:
        state.monitor_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await state.monitor_task


@app.get("/health")
async def health() -> Dict[str, str]:
    return {
        "status": "ok",
        "monitor_interval_minutes": str(config.DEFAULT_CHECK_INTERVAL_MINUTES),
        "smtp_ready": "yes" if (config.SMTP_CONFIGURED and config.EMAIL_RECIPIENTS) else "no",
        "provider": state.provider.__class__.__name__ if state.provider else "uninitialized",
        "amadeus_ready": "yes" if config.AMADEUS_CONFIGURED else "no",
    }


@app.get("/targets", response_model=List[FlightSearchRequest])
async def list_targets() -> List[FlightSearchRequest]:
    return config.TARGET_WINDOWS


@app.get("/offers")
async def get_latest_offers() -> Dict[str, FlightOffer]:
    if state.provider is None:
        raise HTTPException(status_code=503, detail="Proveedor Amadeus no configurado")
    if not state.latest_offers:
        await monitor_once()
    return state.latest_offers


@app.get("/status")
async def get_status_snapshot() -> Dict[str, Dict]:
    return {
        "windows": serialize_windows(),
        "offers": serialize_offers(),
        "statuses": serialize_statuses(),
    }


async def monitor_once() -> None:
    if state.provider is None:
        logger.error("Proveedor no inicializado; no se ejecuta búsqueda")
        return
    for window in config.TARGET_WINDOWS:
        normalized = normalize_request(window)
        key = window_key(normalized)
        try:
            offers = await state.provider.search_round_trip(normalized)
        except ProviderError as exc:
            record_status(key, "error", classify_provider_error(str(exc)))
            continue

        if offers:
            best_offer = min(offers, key=lambda offer: offer.total_price)
            record_offer(key, best_offer)
            record_status(key, "ok", f"{len(offers)} ofertas reales; mejor {best_offer.total_price:.2f} {best_offer.currency}")
        else:
            record_status(
                key,
                "empty",
                "Amadeus devolvió 0 resultados (sin disponibilidad o llamada reciente).",
            )


@app.post("/search", response_model=List[FlightOffer])
async def search_custom(request: FlightSearchRequest) -> List[FlightOffer]:
    normalized = normalize_request(request)
    if state.provider is None:
        raise HTTPException(status_code=503, detail="Proveedor Amadeus no configurado")
    key = window_key(normalized)
    state.target_windows[key] = normalized
    record_status(key, "running", "Búsqueda puntual solicitada (Amadeus)")
    try:
        offers = await state.provider.search_round_trip(normalized)
    except ProviderError as exc:
        detail = classify_provider_error(str(exc))
        record_status(key, "error", detail)
        raise HTTPException(status_code=503, detail=detail)

    if offers:
        best_offer = min(offers, key=lambda offer: offer.total_price)
        record_offer(key, best_offer)
        record_status(
            key,
            "ok",
            f"{len(offers)} ofertas reales; mejor {best_offer.total_price:.2f} {best_offer.currency}",
        )
    else:
        record_status(
            key,
            "empty",
            "Amadeus devolvió 0 resultados (sin disponibilidad o llamada reciente).",
        )
    return offers


@app.get("/events/offers")
async def offers_stream() -> StreamingResponse:
    queue: asyncio.Queue[str] = asyncio.Queue()
    state.subscribers.append(queue)

    await queue.put(
        json.dumps(
            {
                "type": "snapshot",
                "offers": serialize_offers(),
                "statuses": serialize_statuses(),
                "windows": serialize_windows(),
            }
        )
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                payload = await queue.get()
                yield f"data: {payload}\n\n"
        except asyncio.CancelledError:
            logger.info("Cliente SSE desconectado")
        finally:
            if queue in state.subscribers:
                state.subscribers.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/", response_class=HTMLResponse)
async def home_page() -> HTMLResponse:
    return HTMLResponse(build_homepage())


def normalize_request(request: FlightSearchRequest) -> FlightSearchRequest:
    preferred_stop = (request.preferred_stop or config.DEFAULT_PREFERRED_STOP).upper()
    max_layover = request.max_layover_hours or config.DEFAULT_MAX_LAYOVER_HOURS
    return FlightSearchRequest(
        origin=request.origin,
        destination=request.destination,
        departure_date=request.departure_date,
        return_date=request.return_date,
        preferred_stop=preferred_stop,
        max_layover_hours=max_layover,
    )


def record_status(key: str, status: str, detail: str) -> None:
    state.latest_status[key] = MonitorStatus(
        status=status,
        detail=detail,
        checked_at=datetime.now(local_zone()).isoformat(),
    )
    broadcast_update("status")


def record_offer(key: str, offer: FlightOffer) -> None:
    state.latest_offers[key] = offer
    state.latest_updated_at[key] = datetime.now(local_zone()).isoformat()
    broadcast_update("offer")


def serialize_offers() -> Dict[str, Dict]:
    return {
        key: {**offer.model_dump(), "updated_at": state.latest_updated_at.get(key)}
        for key, offer in state.latest_offers.items()
    }


def serialize_statuses() -> Dict[str, Dict]:
    return {key: status.model_dump() for key, status in state.latest_status.items()}


def serialize_windows() -> Dict[str, Dict]:
    return {
        key: {
            "origin": window.origin,
            "destination": window.destination,
            "departure_date": str(window.departure_date),
            "return_date": str(window.return_date),
            "preferred_stop": window.preferred_stop,
            "max_layover_hours": window.max_layover_hours,
        }
        for key, window in state.target_windows.items()
    }


def broadcast_update(event_type: str) -> None:
    payload = json.dumps(
        {
            "type": event_type,
            "offers": serialize_offers(),
            "statuses": serialize_statuses(),
            "windows": serialize_windows(),
        }
    )
    for subscriber in list(state.subscribers):
        subscriber.put_nowait(payload)


def classify_provider_error(message: str) -> str:
    lowered = message.lower()
    if "429" in message or "too many" in lowered or "rate" in lowered:
        return (
            "Amadeus limitó la petición (429/Rate Limit). "
            f"El monitor reintenta cada {config.DEFAULT_CHECK_INTERVAL_MINUTES} minutos."
        )
    if "auth" in lowered or "token" in lowered:
        return "Amadeus rechazó las credenciales (revisa client id/secret)."
    return f"No se pudo recuperar precios reales de Amadeus: {message}"


def ensure_pending_statuses() -> None:
    for key in state.target_windows:
        if key not in state.latest_status:
            record_status(key, "pending", "Esperando primera consulta de Amadeus")


def build_homepage() -> str:
    return """
    <!DOCTYPE html>
    <html lang=\"es\">
    <head>
      <meta charset=\"UTF-8\" />
      <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
      <title>FlightsAPI - Monitor en vivo</title>
      <style>
        :root {
          color-scheme: light dark;
          --bg: #0b1220;
          --card: #111a2e;
          --accent: #4f9cf9;
          --text: #e8eefc;
          --muted: #8ea0c2;
          --success: #3dd598;
          --warning: #f0a500;
        }
        body {
          margin: 0;
          font-family: 'Inter', system-ui, -apple-system, sans-serif;
          background: radial-gradient(circle at 20% 20%, rgba(79,156,249,0.1), transparent 25%),
                      radial-gradient(circle at 80% 0%, rgba(61,213,152,0.12), transparent 20%),
                      var(--bg);
          color: var(--text);
          min-height: 100vh;
        }
        header {
          padding: 24px;
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }
        .title {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .pill {
          background: rgba(79,156,249,0.15);
          color: var(--accent);
          padding: 6px 12px;
          border-radius: 999px;
          font-weight: 600;
          letter-spacing: 0.3px;
        }
        main {
          padding: 0 24px 32px;
        }
        .grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
          gap: 16px;
        }
        .card {
          background: var(--card);
          border: 1px solid rgba(255,255,255,0.04);
          border-radius: 16px;
          padding: 18px;
          box-shadow: 0 10px 40px rgba(0,0,0,0.35);
          display: flex;
          flex-direction: column;
          gap: 10px;
          transition: border 0.2s ease, transform 0.2s ease;
        }
        .card:hover { border-color: rgba(79,156,249,0.45); transform: translateY(-2px); }
        .price {
          font-size: 28px;
          font-weight: 800;
        }
        .badge {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 6px 10px;
          border-radius: 10px;
          font-size: 12px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.4px;
          background: rgba(255,255,255,0.08);
          color: var(--muted);
        }
        .good { color: var(--success); background: rgba(61,213,152,0.12); }
        .warning { color: var(--warning); background: rgba(240,165,0,0.16); }
        .meta { display: flex; justify-content: space-between; color: var(--muted); font-size: 13px; }
        .segments { display: grid; gap: 6px; font-size: 14px; color: #d4ddf4; }
        .segment { display: flex; justify-content: space-between; align-items: center; }
        .small { color: var(--muted); font-size: 12px; }
        .links { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
        .link-btn { background: rgba(79,156,249,0.15); color: var(--text); padding: 8px 12px; border-radius: 10px; text-decoration: none; font-weight: 700; border: 1px solid rgba(79,156,249,0.35); }
        .link-btn:hover { border-color: rgba(61,213,152,0.6); color: var(--success); }
        .search-form { background: var(--card); padding: 16px; border-radius: 14px; margin-bottom: 16px; border:1px solid rgba(255,255,255,0.05); display:grid; gap:12px; grid-template-columns: repeat(auto-fit,minmax(180px,1fr)); }
        .search-form input { width: 100%; padding: 10px 12px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.08); background: rgba(0,0,0,0.15); color: var(--text); }
        .search-form button { grid-column: -1 / 1; padding: 12px 16px; border-radius: 12px; border: none; background: linear-gradient(90deg, #4f9cf9, #3dd598); color: #041024; font-weight: 800; cursor: pointer; }
        .toast { position: fixed; bottom: 16px; right: 16px; padding: 12px 16px; background: rgba(0,0,0,0.85); border-radius: 12px; border:1px solid rgba(255,255,255,0.08); color: var(--text); display:none; }
      </style>
    </head>
    <body>
      <header>
        <div class="title">
          <div class="pill">Málaga ➜ Quito</div>
          <div>
            <div style="font-size:22px;font-weight:800;">Ofertas en vivo</div>
            <div style="color:var(--muted);font-size:14px;">Datos reales (Amadeus) · Zona horaria {config.LOCAL_TIMEZONE}</div>
          </div>
        </div>
        <div id="connection" class="badge">⏳ Conectando</div>
      </header>
      <main>
        <form id="searchForm" class="search-form" onsubmit="runSearch(event)">
          <input name="origin" placeholder="Origen (IATA)" value="AGP" required />
          <input name="destination" placeholder="Destino (IATA)" value="UIO" required />
          <input name="departure_date" type="date" required />
          <input name="return_date" type="date" required />
          <input name="preferred_stop" placeholder="Escala preferida" value="MAD" />
          <input name="max_layover_hours" type="number" step="0.5" placeholder="Escala máx (h)" value="5" />
          <button type="submit">Buscar ahora</button>
        </form>
        <div class="grid" id="offersGrid"></div>
      </main>
      <div class="toast" id="toast"></div>
      <script>
        const grid = document.getElementById('offersGrid');
        const connection = document.getElementById('connection');
        const toast = document.getElementById('toast');
        const TIMEZONE = '{config.LOCAL_TIMEZONE}';

        const formatDateTime = (value) => value ? new Date(value).toLocaleString('es-ES', { timeZone: TIMEZONE }) : '—';
        const formatTime = (value) => value ? new Date(value).toLocaleTimeString('es-ES', { timeZone: TIMEZONE }) : '—';

        function showToast(text) {
          toast.textContent = text;
          toast.style.display = 'block';
          setTimeout(() => { toast.style.display = 'none'; }, 2500);
        }

        function renderOffers(payload) {
          const offers = payload.offers || {};
          const statuses = payload.statuses || {};
          const windows = payload.windows || {};
          const keys = [...new Set([...Object.keys(windows), ...Object.keys(statuses), ...Object.keys(offers)])];
          if (!keys.length) {
            grid.innerHTML = '<div class="card"><div class="price">Sin datos todavía</div><div class="small">Espera al primer ciclo del monitor…</div></div>';
            return;
          }

          grid.innerHTML = keys.map((key) => {
            const win = windows[key] || {};
            const offer = offers[key];
            const status = statuses[key] || { status: 'pending', detail: 'Esperando primera consulta', checked_at: null };
            const good = offer ? offer.total_price <= 1000 : false;
            const links = offer && (offer.purchase_links || []).map(link => `
              <a class="link-btn" href="${link.url}" target="_blank" rel="noopener noreferrer">${link.name}</a>
            `).join('') || '';
            const departure = win.departure_date || key.split(':')[0];
            const ret = win.return_date || key.split(':')[1];
            const badgeClass = status.status === 'ok' && good ? 'good' : (status.status === 'error' ? 'warning' : '');
            const badgeText = offer
              ? (good ? '✅ Bajo umbral' : '↗ Precio monitorizado')
              : (status.status === 'error' ? '⚠️ Error al obtener precios' : '⏳ Buscando en Amadeus');
            const segments = offer ? offer.segments.map(seg => `
              <div class="segment">
                <div>${seg.origin} → ${seg.destination}</div>
                <div class="small">${formatDateTime(seg.departure_time)} · ${seg.layover_hours ? seg.layover_hours + 'h escala' : ''}</div>
              </div>`).join('') : '<div class="small">Sin segmentos disponibles todavía</div>';

            return `
              <div class="card">
                <div class="meta">
                  <div><strong>${departure}</strong> → <strong>${ret}</strong></div>
                  <span class="badge ${badgeClass}">${badgeText}</span>
                </div>
                <div class="price">${offer ? `${offer.total_price.toFixed(2)} ${offer.currency} · ${offer.airline}` : 'Sin oferta disponible aún'}</div>
                <div class="small">${offer ? `Proveedor: ${offer.provider} · Escala preferida: ${offer.preferred_stop_matched ? 'sí' : 'no'}` : 'Esperando datos reales de Amadeus'}</div>
                <div class="segments">${segments}</div>
                <div class="links">${links || '<span class="small">En cuanto llegue una oferta verás aquí enlaces de compra (Google Flights, Skyscanner, Kayak).</span>'}</div>
                <div class="meta"><span class="small">Último estado</span><span class="small">${status.checked_at ? formatTime(status.checked_at) : '—'}</span></div>
                <div class="small">${status.detail || ''}</div>
              </div>
            `;
          }).join('');
        }

        async function checkHealth() {
          try {
            const res = await fetch('/health');
            const data = await res.json();
            if (data.amadeus_ready !== 'yes') {
              connection.textContent = '❌ Amadeus no configurado';
              connection.classList.remove('good');
            } else {
              connection.textContent = '🟢 Amadeus listo';
              connection.classList.add('good');
            }
          } catch (err) {
            connection.textContent = '⚠️ Sin conexión';
            connection.classList.remove('good');
          }
        }

        function connectSSE() {
          const es = new EventSource('/events/offers');
          es.onopen = () => { connection.textContent = '🟢 Tiempo real (Amadeus)'; connection.classList.add('good'); };
          es.onerror = () => { connection.textContent = '⚠️ Reconectando'; connection.classList.remove('good'); };
          es.onmessage = (event) => {
            if (!event.data) return;
            const payload = JSON.parse(event.data);
            if (['snapshot', 'offer', 'status'].includes(payload.type)) {
              renderOffers(payload);
              if (payload.type === 'offer') showToast('Nueva actualización recibida');
            }
          };
        }

        async function runSearch(event) {
          event.preventDefault();
          const form = new FormData(event.target);
          const body = Object.fromEntries(form.entries());
          body.max_layover_hours = body.max_layover_hours ? Number(body.max_layover_hours) : null;
          const res = await fetch('/search', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
          if (res.ok) {
            showToast('Búsqueda lanzada');
          } else {
            showToast('Error al buscar');
          }
        }

        renderOffers({ offers: {}, statuses: {}, windows: {} });
        checkHealth();
        connectSSE();
      </script>
    </body>
    </html>
    """
