"""
BOS Pipeline v9.0 — Webhook Delivery Tasks

Reliable webhook delivery with retries and circuit breaker.
"""

import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional

import httpx
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

# Circuit breaker: max consecutive failures before disabling webhook
MAX_CONSECUTIVE_FAILURES = 10
DELIVERY_TIMEOUT_SECONDS = 30


@shared_task(
    name="app.tasks.webhook.deliver_webhook",
    bind=True,
    max_retries=5,
    default_retry_delay=30,
    soft_time_limit=60,
    time_limit=90,
    rate_limit="60/m",
)
def deliver_webhook(
    self,
    webhook_id: int,
    event: str,
    payload: Dict[str, Any],
    url: str,
    secret: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Deliver a single webhook with retry logic."""
    logger.info(f"Delivering webhook {webhook_id}: event={event}, url={url}")

    delivery_payload = {
        "event": event,
        "timestamp": time.time(),
        "delivery_attempt": self.request.retries + 1,
        "data": payload,
    }

    payload_bytes = json.dumps(delivery_payload, default=str).encode("utf-8")

    # Compute HMAC signature
    request_headers = {
        "Content-Type": "application/json",
        "User-Agent": "BOS-Pipeline/9.0 Webhook",
        "X-BOS-Event": event,
        "X-BOS-Delivery-ID": self.request.id or "unknown",
    }

    if secret:
        sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
        request_headers["X-BOS-Signature-256"] = f"sha256={sig}"

    if headers:
        request_headers.update(headers)

    try:
        with httpx.Client(timeout=DELIVERY_TIMEOUT_SECONDS) as client:
            response = client.post(url, content=payload_bytes, headers=request_headers)

        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"Webhook {webhook_id} delivered: status={response.status_code}")
            _update_webhook_status(webhook_id, success=True)
            return {
                "status": "delivered",
                "status_code": response.status_code,
                "attempt": self.request.retries + 1,
            }
        else:
            logger.warning(f"Webhook {webhook_id} failed: status={response.status_code}")
            _update_webhook_status(webhook_id, success=False)
            raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")

    except httpx.TimeoutException as exc:
        logger.warning(f"Webhook {webhook_id} timeout: {exc}")
        _update_webhook_status(webhook_id, success=False)
        self.retry(exc=exc, countdown=min(30 * (2**self.request.retries), 600))

    except Exception as exc:
        logger.error(f"Webhook {webhook_id} error: {exc}")
        _update_webhook_status(webhook_id, success=False)
        self.retry(exc=exc, countdown=min(30 * (2**self.request.retries), 600))


@shared_task(name="app.tasks.webhook.deliver_pending")
def deliver_pending() -> Dict[str, Any]:
    """Periodic task: retry any pending webhook deliveries."""
    logger.info("Checking for pending webhook deliveries...")
    # In production, query a webhook_deliveries table for pending items
    return {"status": "checked", "pending": 0}


def _update_webhook_status(webhook_id: int, success: bool):
    """Update webhook last_triggered and failure_count."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.config import get_settings
    from app.models import Webhook
    from datetime import datetime, timezone

    settings = get_settings()
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
    engine = create_engine(sync_url, pool_pre_ping=True)

    try:
        with Session(engine) as session:
            webhook = session.get(Webhook, webhook_id)
            if webhook:
                webhook.last_triggered = datetime.now(timezone.utc)
                if success:
                    webhook.failure_count = 0
                else:
                    webhook.failure_count = (webhook.failure_count or 0) + 1
                    if webhook.failure_count >= MAX_CONSECUTIVE_FAILURES:
                        webhook.is_active = False
                        logger.warning(f"Webhook {webhook_id} disabled after {MAX_CONSECUTIVE_FAILURES} failures")
                session.commit()
    except Exception as e:
        logger.error(f"Failed to update webhook status: {e}")
