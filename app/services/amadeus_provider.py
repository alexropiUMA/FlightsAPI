from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import List, Optional

from amadeus import Client, ResponseError

from app.schemas import FlightOffer, FlightSearchRequest, FlightSegment, PurchaseLink
from app.services.flight_provider import FlightProvider, ProviderError


class AmadeusFlightProvider(FlightProvider):
    """Provider backed by the Amadeus Self-Service APIs."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        currency: str = "EUR",
        max_results: int = 10,
    ) -> None:
        self.currency = currency
        self.max_results = max_results
        self.client = Client(
            client_id=client_id,
            client_secret=client_secret,
        )

    @classmethod
    def from_env(cls, client_id: Optional[str], client_secret: Optional[str]) -> "AmadeusFlightProvider":
        if not client_id or not client_secret:
            raise ProviderError("amadeus", "Credenciales de Amadeus incompletas")
        return cls(client_id=client_id, client_secret=client_secret)

    async def search_round_trip(self, request: FlightSearchRequest) -> List[FlightOffer]:
        try:
            response = await asyncio.to_thread(
                self.client.shopping.flight_offers_search.get,
                originLocationCode=request.origin,
                destinationLocationCode=request.destination,
                departureDate=request.departure_date.isoformat(),
                returnDate=request.return_date.isoformat(),
                adults=1,
                currencyCode=self.currency,
                max=self.max_results,
            )
        except ResponseError as exc:  # pragma: no cover - transport error surfaced to caller
            status = getattr(exc, "response", None)
            status_code = getattr(status, "status_code", None)
            result = getattr(status, "result", None)
            message = f"Amadeus error {status_code or ''}: {result or exc}"
            raise ProviderError("amadeus", message) from exc

        try:
            data = response.data
        except ResponseError as exc:  # pragma: no cover - transport error surfaced to caller
            status = getattr(exc, "response", None)
            status_code = getattr(status, "status_code", None)
            result = getattr(status, "result", None)
            message = f"Amadeus error {status_code or ''}: {result or exc}"
            raise ProviderError("amadeus", message) from exc

        offers: List[FlightOffer] = []
        for offer in data:
            try:
                total_price = float(offer["price"]["total"])
                currency = offer["price"]["currency"]
                itineraries = offer.get("itineraries", [])
                segments = self._build_segments(itineraries)
            except (KeyError, TypeError, ValueError) as exc:
                continue  # skip malformed offers

            preferred_stop_matched = self._matches_preferred_stop(segments, request.preferred_stop)
            if request.max_layover_hours is not None and not self._within_layover_limits(segments, request.max_layover_hours):
                continue

            airline = self._first_marketing_carrier(itineraries) or "Desconocida"
            purchase_links = self._build_purchase_links(request)

            offers.append(
                FlightOffer(
                    provider="amadeus",
                    airline=airline,
                    currency=currency,
                    total_price=total_price,
                    segments=segments,
                    preferred_stop_matched=preferred_stop_matched,
                    purchase_links=purchase_links,
                )
            )

        return offers

    def _build_segments(self, itineraries: list) -> List[FlightSegment]:
        segments: List[FlightSegment] = []
        for itinerary in itineraries:
            for idx, segment in enumerate(itinerary.get("segments", [])):
                departure = segment.get("departure", {})
                arrival = segment.get("arrival", {})
                departure_time = departure.get("at")
                arrival_time = arrival.get("at")
                layover_hours: Optional[float] = None

                if idx + 1 < len(itinerary.get("segments", [])):
                    next_departure = itinerary["segments"][idx + 1].get("departure", {}).get("at")
                    layover_hours = self._compute_layover_hours(arrival_time, next_departure)

                segments.append(
                    FlightSegment(
                        origin=departure.get("iataCode"),
                        destination=arrival.get("iataCode"),
                        departure_time=departure_time,
                        arrival_time=arrival_time,
                        layover_hours=layover_hours,
                    )
                )
        return segments

    def _compute_layover_hours(self, arrival: Optional[str], next_departure: Optional[str]) -> Optional[float]:
        if not arrival or not next_departure:
            return None
        try:
            arrival_dt = datetime.fromisoformat(arrival).astimezone(timezone.utc)
            next_dep_dt = datetime.fromisoformat(next_departure).astimezone(timezone.utc)
            delta = next_dep_dt - arrival_dt
            return max(delta.total_seconds() / 3600, 0)
        except ValueError:
            return None

    def _within_layover_limits(self, segments: List[FlightSegment], max_hours: float) -> bool:
        for seg in segments:
            if seg.layover_hours is not None and seg.layover_hours > max_hours:
                return False
        return True

    def _matches_preferred_stop(self, segments: List[FlightSegment], preferred_stop: Optional[str]) -> bool:
        if not preferred_stop:
            return True
        target = preferred_stop.upper()
        return any(seg.destination == target for seg in segments[:-1])

    def _first_marketing_carrier(self, itineraries: list) -> Optional[str]:
        for itinerary in itineraries:
            for segment in itinerary.get("segments", []):
                carrier = segment.get("carrierCode") or segment.get("marketingCarrier")
                if carrier:
                    return carrier
        return None

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
