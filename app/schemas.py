from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class FlightSegment(BaseModel):
    origin: str = Field(..., description="IATA code of the departure airport")
    destination: str = Field(..., description="IATA code of the arrival airport")
    departure_time: str = Field(..., description="Departure time in ISO 8601 format")
    arrival_time: str = Field(..., description="Arrival time in ISO 8601 format")
    layover_hours: Optional[float] = Field(None, description="Layover time after this segment, in hours")


class PurchaseLink(BaseModel):
    name: str = Field(..., description="Label for the booking site")
    url: str = Field(..., description="Direct link to search or booking page")


class FlightOffer(BaseModel):
    provider: str
    airline: str
    currency: str
    total_price: float
    price_note: Optional[str] = Field(None, description="Clarifies how the price was quoted")
    segments: List[FlightSegment]
    preferred_stop_matched: bool
    purchase_links: List[PurchaseLink] = Field(default_factory=list)


class FlightSearchRequest(BaseModel):
    origin: str
    destination: str
    departure_date: date
    return_date: date
    preferred_stop: Optional[str] = None
    max_layover_hours: Optional[float] = None

    @model_validator(mode="after")
    def validate_return_after_departure(self) -> "FlightSearchRequest":
        if self.return_date <= self.departure_date:
            raise ValueError("Return date must be after departure date")
        return self


class PriceAlert(BaseModel):
    window: FlightSearchRequest
    best_price: float
    below_threshold: bool
    message: str


class MonitorStatus(BaseModel):
    status: str = Field(..., description="Short machine-readable status for the window (ok/error/empty/pending)")
    detail: str = Field(..., description="Human readable explanation of the latest check")
    checked_at: str = Field(..., description="ISO timestamp (config timezone) of the last attempt")
