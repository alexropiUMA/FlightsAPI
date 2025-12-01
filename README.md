# FlightsAPI

API ligera en FastAPI para monitorizar vuelos Málaga (AGP) → Quito (UIO) con preferencia de escala en Madrid (MAD) y alertas cuando las tarifas bajan del umbral de 1000 €.

## Características
- **Ventanas de fechas preconfiguradas**: 1 julio–20 julio, 1 julio–21 julio, 1 julio–19 julio, 1 julio–18 julio, 30 junio–19 julio, 30 junio–20 julio, 30 junio–18 julio (año 2026).
- **Filtro de escala**: se privilegia Madrid y se limita el tiempo de escala a 5 h.
- **Monitor de precios**: tarea de fondo que revisa periódicamente (por defecto cada 6 horas para no agotar las 1000 peticiones/mes) y genera alertas cuando el mejor precio está por debajo de 1000 €.
- **Proveedor Amadeus**: se consumen datos reales vía Amadeus Self-Service (obligatorio; sin credenciales no se ejecutan búsquedas).
- **Proveedor simulado**: disponible sólo para desarrollo (`MockFlightProvider`), pero no se usa automáticamente.
- **Enlaces rápidos de compra**: cada oferta incluye accesos a búsquedas en Google Flights, Skyscanner y Kayak para que compares precios reales.
- **Estado en vivo y motivos**: la UI muestra cada ventana de fechas (las 7 combinaciones) con el último estado: precios reales, ausencia de resultados, o errores/rate limit (429) reportados por Amadeus.

## Requisitos
- Python 3.9–3.13
- Zona horaria: en Windows instala `tzdata` (viene por defecto en Linux/macOS) para que `Europe/Madrid` funcione y las horas se muestren correctamente.

Instala dependencias (si vienes de una versión anterior, vuelve a instalar para recoger la actualización a Pydantic 2.x y Amadeus):

```bash
pip install -r requirements.txt
```

## Ejecución

```bash
uvicorn app.main:app --reload
```

- `/health`: estado básico de la API.
- `/targets`: devuelve las combinaciones de fechas configuradas.
- `/offers`: consulta el mejor precio almacenado por el monitor (si aún no hay datos, ejecuta una búsqueda rápida).
- `/status`: devuelve, para cada ventana, el último estado (ok, sin resultados, error/429) y los precios almacenados si existen.
- `/search`: POST con un cuerpo `FlightSearchRequest` para lanzar búsquedas ad-hoc.
- `/` (UI): panel web ligero con las ofertas, compañía aérea, formulario de búsqueda y actualizaciones en tiempo real vía SSE.

Las variables de entorno permiten ajustar el comportamiento:

- `PRICE_THRESHOLD`: umbral de alerta (por defecto 1000).
- `CHECK_INTERVAL_MINUTES`: minutos entre ejecuciones del monitor (por defecto 360 = 6 h, pensado para no agotar las 1000 peticiones mensuales).
- `AMADEUS_CLIENT_ID` / `AMADEUS_CLIENT_SECRET`: credenciales de Amadeus Self-Service. Sin ellas la API no lanzará búsquedas (sólo mostrará el estado en `/health`).
- `LOCAL_TIMEZONE`: zona horaria para mostrar horarios en la UI (por defecto `Europe/Madrid`, UTC+1 en verano).
- `EMAIL_RECIPIENTS`: lista separada por comas de destinatarios para alertas (por defecto `alexropi00@gmail.com`).
- `EMAIL_SENDER`: dirección del remitente de los correos.
- `SMTP_HOST` / `SMTP_PORT`: host y puerto SMTP (por defecto `smtp.gmail.com:587`).
- `SMTP_USERNAME` / `SMTP_PASSWORD`: credenciales para autenticarte en SMTP (requeridas para enviar email).

### Configurar alertas por correo (ejemplo con Gmail)

1. Crea o usa una contraseña de aplicación en tu cuenta de Gmail (no uses tu contraseña principal).
2. Exporta las variables antes de arrancar el servidor:

```bash
export SMTP_USERNAME="tu_correo@gmail.com"
export SMTP_PASSWORD="tu_contraseña_de_aplicación"
export EMAIL_SENDER="tu_correo@gmail.com"
export EMAIL_RECIPIENTS="alexropi00@gmail.com"
```

El endpoint `/health` devuelve `smtp_ready: yes` cuando detecta destinatarios y credenciales SMTP configuradas.

### Ejemplo de despliegue en Raspberry Pi 4B (4 GB)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configura tu SMTP (ejemplo con Gmail y app password)
export SMTP_USERNAME="tu_usuario@gmail.com"
export SMTP_PASSWORD="tu_app_password"
export EMAIL_SENDER="tu_usuario@gmail.com"
export EMAIL_RECIPIENTS="alexropi00@gmail.com"

# Ajusta el intervalo (6 horas por defecto para 1000 peticiones/mes)
export CHECK_INTERVAL_MINUTES=360

# Activa Amadeus (obligatorio para datos reales)
export AMADEUS_CLIENT_ID="tu_client_id"
export AMADEUS_CLIENT_SECRET="tu_client_secret"

# Lanza el servicio
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Para mantenerlo en ejecución tras cerrar la terminal puedes usar `tmux`, `screen` o un servicio `systemd`. El monitor comprobará cada 6 horas (por defecto) las combinaciones indicadas y enviará correo cuando el precio caiga por debajo del umbral.

## Personalización del proveedor

- **Amadeus**: si `AMADEUS_CLIENT_ID` y `AMADEUS_CLIENT_SECRET` están definidos, se usa `AmadeusFlightProvider` (`app/services/amadeus_provider.py`). Se solicitan hasta 10 resultados (`max=10`) con moneda EUR y se filtra por escala preferida y duración máxima de escala. Cada oferta incluye aerolínea, precio, divisa, segmentos con horarios y enlaces de compra rápidos. El precio mostrado usa `grandTotal` de Amadeus (importe total con impuestos); si no está disponible, se recurre a `total`.
- **Mock**: en ausencia de credenciales, `MockFlightProvider` (`app/services/mock_provider.py`) genera datos sintéticos (no provienen de ninguna API real) manteniendo la misma forma de los datos.

## Notificaciones

`NotificationService` (en `app/services/notification.py`) registra las alertas en los logs. Amplíalo con email, SMS o push añadiendo la lógica en `send_price_alert`.

## Diagnóstico: ¿por qué no veo las 7 ofertas?

- El monitor sigue consultando las 7 combinaciones, pero ahora **solo muestra datos reales de Amadeus**. Si un tramo no aparece es porque Amadeus devolvió 0 resultados (sin disponibilidad o caché reciente) o respondió con error.
- Visita `/status` o el panel en `/`: cada tarjeta enseña el último estado y la hora local. Si Amadeus limita por exceso de peticiones (429), lo verás indicado y el monitor reintentará según `CHECK_INTERVAL_MINUTES` (6 h por defecto).
- Los enlaces de compra (Google Flights, Skyscanner, Kayak) aparecen automáticamente en la tarjeta en cuanto llega una oferta real para ese rango de fechas.
