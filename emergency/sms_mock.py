import logging

from django.conf import settings

from .models import MockSMSLog

logger = logging.getLogger(__name__)


def send_mock_sms(phone: str, message: str, related_request=None) -> MockSMSLog | None:
    if not getattr(settings, "SMS_MOCK_ENABLED", True):
        return None
    log = MockSMSLog.objects.create(
        recipient_phone=phone or "unknown",
        message=message,
        related_request=related_request,
    )
    logger.info("[MOCK SMS] to=%s | %s", phone, message[:200])
    return log
