from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import List

from app.schemas import FlightOffer, FlightSearchRequest, FlightSegment, PurchaseLink
from app.services.flight_provider import FlightProvider


class MockFlightProvider(FlightProvider):
    """Provider that generates deterministic fares for testing the workflow."""

    def __init__(self, base_price: float = 920.0, volatility: float = 120.0):
        self.base_price = base_price
        self.volatility = volatility
        self.airlines = [
            "Iberia",
            "LATAM",
            "Air Europa",
            "KLM",
            "Lufthansa",
        ]

    async def search_round_trip(self, request: FlightSearchRequest) -> List[FlightOffer]:
        distance_factor = 1.15  # Malaga -> Quito is long-haul; adjust base price
        days_to_return = (request.return_date - request.departure_date).days
        length_factor = 1 + max(days_to_return - 7, 0) * 0.01
        preferred_stop = request.preferred_stop or ""
        stop_match_bonus = -35 if preferred_stop else 0

        # Deterministic pseudo-variation based on date string hashes
        seed_value = sum(ord(c) for c in f"{request.departure_date}{request.return_date}")
        oscillation = math.sin(seed_value) * self.volatility
        total_price = max(450.0, self.base_price * distance_factor * length_factor + oscillation + stop_match_bonus)

        airline = self.airlines[seed_value % len(self.airlines)]

        layover = min(request.max_layover_hours or 3.0, 5.0)
        departure_time = datetime.combine(request.departure_date, datetime.min.time()) + timedelta(hours=8)
        return_time = datetime.combine(request.return_date, datetime.min.time()) + timedelta(hours=14)

        segments = [
            FlightSegment(
                origin=request.origin,
                destination=preferred_stop or "MAD",
                departure_time=departure_time.isoformat(),
                arrival_time=(departure_time + timedelta(hours=2.5)).isoformat(),
                layover_hours=layover,
            ),
            FlightSegment(
                origin=preferred_stop or "MAD",
                destination=request.destination,
                departure_time=(departure_time + timedelta(hours=2.5 + layover)).isoformat(),
                arrival_time=(departure_time + timedelta(hours=2.5 + layover + 11)).isoformat(),
            ),
            FlightSegment(
                origin=request.destination,
                destination=preferred_stop or "MAD",
                departure_time=return_time.isoformat(),
                arrival_time=(return_time + timedelta(hours=10.5)).isoformat(),
                layover_hours=layover,
            ),
            FlightSegment(
                origin=preferred_stop or "MAD",
                destination=request.origin,
                departure_time=(return_time + timedelta(hours=10.5 + layover)).isoformat(),
                arrival_time=(return_time + timedelta(hours=10.5 + layover + 2.5)).isoformat(),
            ),
        ]

        purchase_links = self._build_purchase_links(request)

        offer = FlightOffer(
            provider="mock",
            airline=airline,
            currency="EUR",
            total_price=round(total_price, 2),
            segments=segments,
            preferred_stop_matched=True,
            purchase_links=purchase_links,
        )

        return [offer]

    def _build_purchase_links(self, request: FlightSearchRequest) -> list[PurchaseLink]:
        dep = request.departure_date.strftime("%Y%m%d")
        ret = request.return_date.strftime("%Y%m%d")
        base_query = f"{request.origin}/{request.destination}/{dep}/{ret}"
        return [
            PurchaseLink(
                name="Google Flights",
                url=(
                    "https://www.google.com/travel/flights?q="
                    f"Flights%20from%20{request.origin}%20to%20{request.destination}%20on%20{request.departure_date}"
                    f"%20return%20{request.return_date}"
                ),
            ),
            PurchaseLink(
                name="Skyscanner",
                url=f"https://www.skyscanner.es/transporte/vuelos/{base_query}/",
            ),
            PurchaseLink(
                name="Kayak",
                url=(
                    "https://www.kayak.es/flights/"
                    f"{request.origin}-{request.destination}/{request.departure_date}/{request.return_date}?fs=stops=0,1"
                ),
            ),
        ]
