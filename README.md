# FlightsAPI

API ligera en FastAPI para monitorizar vuelos Málaga (AGP) → Quito (UIO) con preferencia de escala en Madrid (MAD) y alertas cuando las tarifas bajan del umbral de 1000 €.

## Características
- **Ventanas de fechas preconfiguradas**: 1 julio–20 julio, 1 julio–21 julio, 1 julio–19 julio, 1 julio–18 julio, 30 junio–19 julio, 30 junio–20 julio, 30 junio–18 julio.
- **Filtro de escala**: se privilegia Madrid y se limita el tiempo de escala a 5 h en el proveedor de ejemplo.
- **Monitor de precios**: tarea de fondo que revisa periódicamente (por defecto cada 15 minutos) y genera alertas cuando el mejor precio está por debajo de 1000 €.
- **Proveedor simulado**: `MockFlightProvider` devuelve resultados deterministas para facilitar pruebas locales. Puedes sustituirlo por un proveedor real integrando APIs externas.

## Requisitos
- Python 3.11+

Instala dependencias:

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
- `/search`: POST con un cuerpo `FlightSearchRequest` para lanzar búsquedas ad-hoc.

Las variables de entorno permiten ajustar el comportamiento:

- `PRICE_THRESHOLD`: umbral de alerta (por defecto 1000).
- `CHECK_INTERVAL_MINUTES`: minutos entre ejecuciones del monitor (por defecto 15; ideal para Raspberry Pi 4B).
- `EMAIL_RECIPIENTS`: lista separada por comas de destinatarios para alertas (por defecto `alexropi00@gmail.com`).
- `EMAIL_SENDER`: dirección del remitente de los correos.
- `SMTP_HOST` / `SMTP_PORT`: host y puerto SMTP (por defecto `smtp.gmail.com:587`).
- `SMTP_USERNAME` / `SMTP_PASSWORD`: credenciales para autenticarte en SMTP (requeridas para enviar email).

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

# Ajusta el intervalo (15 minutos por defecto)
export CHECK_INTERVAL_MINUTES=15

# Lanza el servicio
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Para mantenerlo en ejecución tras cerrar la terminal puedes usar `tmux`, `screen` o un servicio `systemd`. El monitor comprobará cada 15 minutos las combinaciones indicadas y enviará correo cuando el precio caiga por debajo del umbral.

## Personalización del proveedor

El proveedor actual (`MockFlightProvider`) se encuentra en `app/services/mock_provider.py`. Para conectar con un servicio real, implementa `FlightProvider.search_round_trip` en un nuevo módulo y reemplaza la instancia creada en `app/main.py`.

## Notificaciones

`NotificationService` (en `app/services/notification.py`) registra las alertas en los logs. Amplíalo con email, SMS o push añadiendo la lógica en `send_price_alert`.
