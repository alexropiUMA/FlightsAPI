from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Dict, List, Optional

from fastapi import FastAPI

from app import config
from app.schemas import FlightOffer, FlightSearchRequest, PriceAlert
from app.services.flight_provider import FlightProvider
from app.services.mock_provider import MockFlightProvider
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
        self.monitor_task: Optional[asyncio.Task] = None


state = AppState(
    provider=MockFlightProvider(),
    notifier=NotificationService(recipients=config.EMAIL_RECIPIENTS),
)


async def monitor_prices():
    logger.info("Iniciando monitor de precios para %s combinaciones", len(config.TARGET_WINDOWS))
    while True:
        for window in config.TARGET_WINDOWS:
            offers = await state.provider.search_round_trip(window)
            if not offers:
                logger.info("Sin resultados para %s -> %s (%s-%s)", window.origin, window.destination, window.departure_date, window.return_date)
                continue

            best_offer = min(offers, key=lambda offer: offer.total_price)
            key = f"{window.departure_date}:{window.return_date}"
            state.latest_offers[key] = best_offer

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
    state.monitor_task = asyncio.create_task(monitor_prices())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    if state.monitor_task:
        state.monitor_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await state.monitor_task


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/targets", response_model=List[FlightSearchRequest])
async def list_targets() -> List[FlightSearchRequest]:
    return config.TARGET_WINDOWS


@app.get("/offers")
async def get_latest_offers() -> Dict[str, FlightOffer]:
    if not state.latest_offers:
        await monitor_once()
    return state.latest_offers


async def monitor_once() -> None:
    for window in config.TARGET_WINDOWS:
        offers = await state.provider.search_round_trip(window)
        if offers:
            best_offer = min(offers, key=lambda offer: offer.total_price)
            key = f"{window.departure_date}:{window.return_date}"
            state.latest_offers[key] = best_offer


@app.post("/search", response_model=List[FlightOffer])
async def search_custom(request: FlightSearchRequest) -> List[FlightOffer]:
    return await state.provider.search_round_trip(request)
