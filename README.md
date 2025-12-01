# FlightsAPI

API ligera en FastAPI para monitorizar vuelos Málaga (AGP) → Quito (UIO) con preferencia de escala en Madrid (MAD) y alertas cuando las tarifas bajan del umbral de 1000 €.

## Características
- **Ventanas de fechas preconfiguradas**: 1 julio–20 julio, 1 julio–21 julio, 1 julio–19 julio, 1 julio–18 julio, 30 junio–19 julio, 30 junio–20 julio, 30 junio–18 julio.
- **Filtro de escala**: se privilegia Madrid y se limita el tiempo de escala a 5 h en el proveedor de ejemplo.
- **Monitor de precios**: tarea de fondo que revisa periódicamente (por defecto cada 60 minutos) y genera alertas cuando el mejor precio está por debajo de 1000 €.
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
- `CHECK_INTERVAL_MINUTES`: minutos entre ejecuciones del monitor (por defecto 60).

## Personalización del proveedor

El proveedor actual (`MockFlightProvider`) se encuentra en `app/services/mock_provider.py`. Para conectar con un servicio real, implementa `FlightProvider.search_round_trip` en un nuevo módulo y reemplaza la instancia creada en `app/main.py`.

## Notificaciones

`NotificationService` (en `app/services/notification.py`) registra las alertas en los logs. Amplíalo con email, SMS o push añadiendo la lógica en `send_price_alert`.
