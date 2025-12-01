from __future__ import annotations

import logging
from typing import Iterable

from app.schemas import PriceAlert

logger = logging.getLogger(__name__)


class NotificationService:
    """Simple notification service placeholder.

    In production you could extend this class to integrate with email, SMS or push
    notifications. For now it logs alerts so they can be observed in the
    application output.
    """

    def __init__(self, recipients: Iterable[str] | None = None):
        self.recipients = list(recipients or [])

    async def send_price_alert(self, alert: PriceAlert) -> None:
        recipients = ", ".join(self.recipients) if self.recipients else "(sin destinatarios configurados)"
        logger.warning(
            "ALERTA DE PRECIO: %s | Mejor precio: %.2f€ | Umbral cumplido: %s | Destinatarios: %s",
            alert.message,
            alert.best_price,
            "sí" if alert.below_threshold else "no",
            recipients,
        )
