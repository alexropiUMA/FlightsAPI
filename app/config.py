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
DEFAULT_CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", 60))


# Date windows requested by the user
TARGET_WINDOWS: List[FlightSearchRequest] = [
    FlightSearchRequest(origin=DEFAULT_ORIGIN, destination=DEFAULT_DESTINATION, departure_date=date(2024, 7, 1), return_date=date(2024, 7, 20), preferred_stop=DEFAULT_PREFERRED_STOP, max_layover_hours=DEFAULT_MAX_LAYOVER_HOURS),
    FlightSearchRequest(origin=DEFAULT_ORIGIN, destination=DEFAULT_DESTINATION, departure_date=date(2024, 7, 1), return_date=date(2024, 7, 21), preferred_stop=DEFAULT_PREFERRED_STOP, max_layover_hours=DEFAULT_MAX_LAYOVER_HOURS),
    FlightSearchRequest(origin=DEFAULT_ORIGIN, destination=DEFAULT_DESTINATION, departure_date=date(2024, 7, 1), return_date=date(2024, 7, 19), preferred_stop=DEFAULT_PREFERRED_STOP, max_layover_hours=DEFAULT_MAX_LAYOVER_HOURS),
    FlightSearchRequest(origin=DEFAULT_ORIGIN, destination=DEFAULT_DESTINATION, departure_date=date(2024, 7, 1), return_date=date(2024, 7, 18), preferred_stop=DEFAULT_PREFERRED_STOP, max_layover_hours=DEFAULT_MAX_LAYOVER_HOURS),
    FlightSearchRequest(origin=DEFAULT_ORIGIN, destination=DEFAULT_DESTINATION, departure_date=date(2024, 6, 30), return_date=date(2024, 7, 19), preferred_stop=DEFAULT_PREFERRED_STOP, max_layover_hours=DEFAULT_MAX_LAYOVER_HOURS),
    FlightSearchRequest(origin=DEFAULT_ORIGIN, destination=DEFAULT_DESTINATION, departure_date=date(2024, 6, 30), return_date=date(2024, 7, 20), preferred_stop=DEFAULT_PREFERRED_STOP, max_layover_hours=DEFAULT_MAX_LAYOVER_HOURS),
    FlightSearchRequest(origin=DEFAULT_ORIGIN, destination=DEFAULT_DESTINATION, departure_date=date(2024, 6, 30), return_date=date(2024, 7, 18), preferred_stop=DEFAULT_PREFERRED_STOP, max_layover_hours=DEFAULT_MAX_LAYOVER_HOURS),
]
