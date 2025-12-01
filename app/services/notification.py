from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Iterable

from app import config
from app.schemas import PriceAlert

logger = logging.getLogger(__name__)


class NotificationService:
    """Notification service that logs and optionally envía correos SMTP."""

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

        if not self.recipients or not config.SMTP_HOST or not config.SMTP_USERNAME or not config.SMTP_PASSWORD:
            return

        message = EmailMessage()
        message["Subject"] = f"Alerta de vuelos {alert.window.origin}->{alert.window.destination}"
        message["From"] = config.EMAIL_SENDER
        message["To"] = ", ".join(self.recipients)
        message.set_content(
            (
                f"Se encontró una tarifa de {alert.best_price:.2f}€ para el rango "
                f"{alert.window.departure_date} - {alert.window.return_date}.\n"
                f"Ruta preferida: {alert.window.preferred_stop or 'sin preferencia'}.\n"
                "(Mensaje automático de FlightsAPI)."
            )
        )

        try:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as smtp:
                smtp.starttls()
                smtp.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
                smtp.send_message(message)
        except Exception:  # pragma: no cover - logged for observability
            logger.exception("No se pudo enviar el correo de alerta")
