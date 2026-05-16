"""
Provider budget and quota governance for BOS Code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.config import get_settings
from app.models import CodeAgentRuntimeState

settings = get_settings()


@dataclass(slots=True)
class ProviderBudgetDecision:
    allowed: bool
    blocked_reason: str | None
    headline: str
    resume_at: datetime | None = None


class CodeProviderBudgetService:
    WINDOW_DURATION = timedelta(hours=1)

    @staticmethod
    def _as_utc(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    @classmethod
    def _window_metrics(cls, runtime: CodeAgentRuntimeState, *, now: datetime) -> dict:
        metrics = dict(runtime.runtime_metrics or {})
        started_at = cls._as_utc(metrics.get("provider_budget_window_started_at"))
        if started_at is None or now - started_at >= cls.WINDOW_DURATION:
            metrics["provider_budget_window_started_at"] = now.isoformat()
            metrics["provider_budget_request_count"] = 0
            metrics["provider_budget_estimated_cost"] = 0.0
        return metrics

    @classmethod
    def evaluate(cls, runtime: CodeAgentRuntimeState, *, now: datetime | None = None) -> ProviderBudgetDecision:
        now = now or datetime.now(UTC)
        metrics = cls._window_metrics(runtime, now=now)

        pause_until = cls._as_utc(metrics.get("provider_budget_pause_until"))
        if pause_until is not None and pause_until > now:
            return ProviderBudgetDecision(
                allowed=False,
                blocked_reason="provider_budget_paused",
                headline="Provider budget is cooling down before another autonomous turn can start.",
                resume_at=pause_until,
            )

        request_count = int(metrics.get("provider_budget_request_count", 0) or 0)
        estimated_cost = float(metrics.get("provider_budget_estimated_cost", 0.0) or 0.0)

        if request_count >= settings.BOS_CODE_PROVIDER_MAX_REQUESTS_PER_HOUR:
            return ProviderBudgetDecision(
                allowed=False,
                blocked_reason="provider_budget_paused",
                headline="Provider request budget is exhausted for the current hour.",
                resume_at=now + timedelta(seconds=settings.BOS_CODE_PROVIDER_BUDGET_COOLDOWN_SEC),
            )
        if estimated_cost >= settings.BOS_CODE_PROVIDER_MAX_ESTIMATED_COST_PER_HOUR:
            return ProviderBudgetDecision(
                allowed=False,
                blocked_reason="provider_budget_paused",
                headline="Provider cost budget is exhausted for the current hour.",
                resume_at=now + timedelta(seconds=settings.BOS_CODE_PROVIDER_BUDGET_COOLDOWN_SEC),
            )

        return ProviderBudgetDecision(
            allowed=True,
            blocked_reason=None,
            headline="Provider budget allows another autonomous turn.",
        )

    @classmethod
    def record_dispatch(
        cls,
        runtime: CodeAgentRuntimeState,
        *,
        estimated_cost: float | None,
        now: datetime | None = None,
    ) -> dict:
        now = now or datetime.now(UTC)
        metrics = cls._window_metrics(runtime, now=now)
        metrics["provider_budget_request_count"] = int(metrics.get("provider_budget_request_count", 0) or 0) + 1
        metrics["provider_budget_estimated_cost"] = float(metrics.get("provider_budget_estimated_cost", 0.0) or 0.0) + float(estimated_cost or 0.0)
        runtime.runtime_metrics = metrics
        return metrics

    @classmethod
    def record_pause(
        cls,
        runtime: CodeAgentRuntimeState,
        *,
        resume_at: datetime,
        now: datetime | None = None,
    ) -> dict:
        now = now or datetime.now(UTC)
        metrics = cls._window_metrics(runtime, now=now)
        metrics["provider_budget_pause_until"] = resume_at.isoformat()
        runtime.runtime_metrics = metrics
        return metrics

    @classmethod
    def clear_pause(cls, runtime: CodeAgentRuntimeState, *, now: datetime | None = None) -> dict:
        now = now or datetime.now(UTC)
        metrics = cls._window_metrics(runtime, now=now)
        metrics.pop("provider_budget_pause_until", None)
        runtime.runtime_metrics = metrics
        return metrics
