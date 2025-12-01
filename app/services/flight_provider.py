from __future__ import annotations

import abc
from typing import List

from app.schemas import FlightOffer, FlightSearchRequest


class FlightProvider(abc.ABC):
    """Abstraction for flight search providers."""

    @abc.abstractmethod
    async def search_round_trip(self, request: FlightSearchRequest) -> List[FlightOffer]:
        """Return flight offers that match the request."""


class ProviderError(RuntimeError):
    """Raised when the provider cannot satisfy a request."""

    def __init__(self, provider: str, message: str):
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
