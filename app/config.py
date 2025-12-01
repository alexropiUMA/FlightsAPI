from __future__ import annotations

import os
from datetime import date
from typing import List

from app.schemas import FlightSearchRequest

DEFAULT_ORIGIN = "AGP"  # Málaga
DEFAULT_DESTINATION = "UIO"  # Quito
DEFAULT_PREFERRED_STOP = "MAD"
DEFAULT_MAX_LAYOVER_HOURS = 5.0
DEFAULT_PRICE_THRESHOLD = float(os.getenv("PRICE_THRESHOLD", 1000))
DEFAULT_CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", 360))
LOCAL_TIMEZONE = os.getenv("LOCAL_TIMEZONE", "Europe/Madrid")

EMAIL_SENDER = os.getenv("EMAIL_SENDER", "alerts@example.com")
EMAIL_RECIPIENTS = [email.strip() for email in os.getenv("EMAIL_RECIPIENTS", "alexropi00@gmail.com").split(",") if email.strip()]
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_CONFIGURED = bool(SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD and EMAIL_SENDER)

AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID", "")
AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET", "")
AMADEUS_CONFIGURED = bool(AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET)


# Date windows requested by the user
TARGET_WINDOWS: List[FlightSearchRequest] = [
    FlightSearchRequest(origin=DEFAULT_ORIGIN, destination=DEFAULT_DESTINATION, departure_date=date(2026, 7, 1), return_date=date(2026, 7, 20), preferred_stop=DEFAULT_PREFERRED_STOP, max_layover_hours=DEFAULT_MAX_LAYOVER_HOURS),
    FlightSearchRequest(origin=DEFAULT_ORIGIN, destination=DEFAULT_DESTINATION, departure_date=date(2026, 7, 1), return_date=date(2026, 7, 21), preferred_stop=DEFAULT_PREFERRED_STOP, max_layover_hours=DEFAULT_MAX_LAYOVER_HOURS),
    FlightSearchRequest(origin=DEFAULT_ORIGIN, destination=DEFAULT_DESTINATION, departure_date=date(2026, 7, 1), return_date=date(2026, 7, 19), preferred_stop=DEFAULT_PREFERRED_STOP, max_layover_hours=DEFAULT_MAX_LAYOVER_HOURS),
    FlightSearchRequest(origin=DEFAULT_ORIGIN, destination=DEFAULT_DESTINATION, departure_date=date(2026, 7, 1), return_date=date(2026, 7, 18), preferred_stop=DEFAULT_PREFERRED_STOP, max_layover_hours=DEFAULT_MAX_LAYOVER_HOURS),
    FlightSearchRequest(origin=DEFAULT_ORIGIN, destination=DEFAULT_DESTINATION, departure_date=date(2026, 6, 30), return_date=date(2026, 7, 19), preferred_stop=DEFAULT_PREFERRED_STOP, max_layover_hours=DEFAULT_MAX_LAYOVER_HOURS),
    FlightSearchRequest(origin=DEFAULT_ORIGIN, destination=DEFAULT_DESTINATION, departure_date=date(2026, 6, 30), return_date=date(2026, 7, 20), preferred_stop=DEFAULT_PREFERRED_STOP, max_layover_hours=DEFAULT_MAX_LAYOVER_HOURS),
    FlightSearchRequest(origin=DEFAULT_ORIGIN, destination=DEFAULT_DESTINATION, departure_date=date(2026, 6, 30), return_date=date(2026, 7, 18), preferred_stop=DEFAULT_PREFERRED_STOP, max_layover_hours=DEFAULT_MAX_LAYOVER_HOURS),
]
