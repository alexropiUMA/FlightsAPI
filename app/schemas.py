from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class FlightSegment(BaseModel):
    origin: str = Field(..., description="IATA code of the departure airport")
    destination: str = Field(..., description="IATA code of the arrival airport")
    departure_time: str = Field(..., description="Departure time in ISO 8601 format")
    arrival_time: str = Field(..., description="Arrival time in ISO 8601 format")
    layover_hours: Optional[float] = Field(None, description="Layover time after this segment, in hours")


class FlightOffer(BaseModel):
    provider: str
    currency: str
    total_price: float
    segments: List[FlightSegment]
    preferred_stop_matched: bool


class FlightSearchRequest(BaseModel):
    origin: str
    destination: str
    departure_date: date
    return_date: date
    preferred_stop: Optional[str] = None
    max_layover_hours: Optional[float] = None

    @validator("return_date")
    def validate_return_after_departure(cls, return_date: date, values: dict) -> date:
        departure_date: date | None = values.get("departure_date")
        if departure_date and return_date <= departure_date:
            raise ValueError("Return date must be after departure date")
        return return_date


class PriceAlert(BaseModel):
    window: FlightSearchRequest
    best_price: float
    below_threshold: bool
    message: str
