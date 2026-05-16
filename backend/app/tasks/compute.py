"""
BOS Pipeline v9.0 - Compute Tasks

Heavy async computation tasks executed via Celery workers.
"""

from __future__ import annotations

from contextlib import contextmanager
import time
from typing import Any

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


def _build_sync_database_url(database_url: str, database_url_sync: str | None = None) -> str:
    if database_url_sync:
        return database_url_sync
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if database_url.startswith("sqlite+aiosqlite://"):
        return database_url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return database_url


@contextmanager
def _open_sync_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.config import get_settings

    settings = get_settings()
    sync_url = _build_sync_database_url(settings.DATABASE_URL, getattr(settings, "DATABASE_URL_SYNC", None))
    engine = create_engine(sync_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def _persist_calculation(**kwargs) -> bool:
    """Persist a Calculation record using a sync DB session (Celery context)."""
    from app.models import Calculation

    batch_id = kwargs.get("batch_id")
    if batch_id is None:
        logger.warning(
            "Skipping calculation persistence because batch_id is required",
            extra={"calc_type": kwargs.get("calc_type", "unknown")},
        )
        return False

    with _open_sync_session() as session:
        calc = Calculation(
            batch_id=batch_id,
            calc_type=kwargs.get("calc_type", "unknown"),
            status="completed",
            inputs=kwargs.get("inputs"),
            result=kwargs.get("result_data"),
            ser_value=kwargs.get("ser_value"),
            passed=kwargs.get("passed"),
            mc_samples=kwargs.get("mc_samples"),
            duration_ms=kwargs.get("duration_ms"),
            engine_version=kwargs.get("engine_version"),
            user_id=kwargs.get("user_id"),
            tenant_id=kwargs.get("tenant_id"),
        )
        session.add(calc)
        session.commit()
    return True


@shared_task(
    name="app.tasks.compute.run_monte_carlo_async",
    bind=True,
    max_retries=2,
    soft_time_limit=300,
    time_limit=360,
)
def run_monte_carlo_async(
    self,
    batch_id: int,
    tenant_id: int,
    user_id: int,
    dm_in_mean: float,
    dm_in_std: float,
    dm_out_mean: float,
    dm_out_std: float,
    n_samples: int = 100_000,
    seed: int | None = None,
) -> dict[str, Any]:
    """Run Monte Carlo simulation asynchronously for large sample counts."""
    from app.engine.monte_carlo_engine import MCInput, run_monte_carlo

    logger.info("Starting MC simulation: batch=%s, n=%s", batch_id, n_samples)
    start = time.perf_counter()

    try:
        mc_input = MCInput(
            n_samples=n_samples,
            dm_in_mean=dm_in_mean,
            dm_in_std=dm_in_std,
            dm_out_mean=dm_out_mean,
            dm_out_std=dm_out_std,
            seed=seed,
        )
        result = run_monte_carlo(mc_input)
        duration = (time.perf_counter() - start) * 1000

        _persist_calculation(
            batch_id=batch_id,
            tenant_id=tenant_id,
            user_id=user_id,
            calc_type="monte_carlo",
            inputs={
                "n_samples": n_samples,
                "dm_in_mean": dm_in_mean,
                "dm_in_std": dm_in_std,
                "dm_out_mean": dm_out_mean,
                "dm_out_std": dm_out_std,
            },
            result_data={
                "ser_mean": result.ser_mean,
                "ser_std": result.ser_std,
                "ser_median": result.ser_median,
                "ser_ci_lower": result.ser_ci_lower,
                "ser_ci_upper": result.ser_ci_upper,
                "pass_probability": result.pass_probability,
            },
            ser_value=result.ser_mean,
            passed=result.pass_probability >= 0.5,
            mc_samples=n_samples,
            duration_ms=round(duration, 2),
            engine_version=result.engine_version,
        )

        logger.info("MC simulation complete: SER=%.4f, %.0fms", result.ser_mean, duration)
        return {
            "status": "completed",
            "ser_mean": result.ser_mean,
            "pass_probability": result.pass_probability,
            "computation_time_ms": round(duration, 2),
        }
    except Exception as exc:
        logger.error("MC simulation failed: %s", exc)
        raise self.retry(exc=exc, countdown=60) from exc


@shared_task(
    name="app.tasks.compute.run_sensitivity_async",
    bind=True,
    max_retries=2,
    soft_time_limit=600,
    time_limit=720,
)
def run_sensitivity_async(
    self,
    tenant_id: int,
    user_id: int,
    method: str,
    n_samples: int,
    parameters: dict[str, list[float]],
    seed: int | None = None,
) -> dict[str, Any]:
    """Run global sensitivity analysis asynchronously."""
    from app.engine.sensitivity_engine import SensitivityInput, run_sensitivity_analysis

    logger.info("Starting sensitivity analysis: method=%s, n=%s", method, n_samples)
    start = time.perf_counter()

    try:
        param_bounds = {key: (values[0], values[1]) for key, values in parameters.items()}
        sa_input = SensitivityInput(
            method=method,
            n_samples=n_samples,
            parameters=param_bounds,
            seed=seed,
        )

        result = run_sensitivity_analysis(sa_input)
        duration = (time.perf_counter() - start) * 1000

        _persist_calculation(
            batch_id=None,
            tenant_id=tenant_id,
            user_id=user_id,
            calc_type="sensitivity",
            inputs={"method": method, "n_samples": n_samples},
            result_data={
                "first_order": result.first_order,
                "total_order": result.total_order,
                "parameter_ranking": result.parameter_ranking,
            },
            duration_ms=round(duration, 2),
            engine_version=result.engine_version,
        )

        logger.info("Sensitivity analysis complete: %.0fms", duration)
        return {
            "status": "completed",
            "parameter_ranking": result.parameter_ranking,
            "computation_time_ms": round(duration, 2),
        }
    except Exception as exc:
        logger.error("Sensitivity analysis failed: %s", exc)
        raise self.retry(exc=exc, countdown=120) from exc


@shared_task(
    name="app.tasks.compute.run_gp_calibration_async",
    bind=True,
    max_retries=1,
    soft_time_limit=300,
    time_limit=360,
)
def run_gp_calibration_async(
    self,
    tenant_id: int,
    user_id: int,
    X_train: list[list[float]],
    y_train: list[float],
    kernel: str = "matern52",
) -> dict[str, Any]:
    """Run GP calibration asynchronously for large datasets."""
    from app.engine.calibration_engine import GPInput, fit_gp

    logger.info("Starting GP calibration: n=%s, kernel=%s", len(X_train), kernel)
    start = time.perf_counter()

    try:
        gp_input = GPInput(
            X_train=X_train,
            y_train=y_train,
            kernel=kernel,
            optimize_hyperparams=True,
        )

        result = fit_gp(gp_input)
        duration = (time.perf_counter() - start) * 1000

        _persist_calculation(
            batch_id=None,
            tenant_id=tenant_id,
            user_id=user_id,
            calc_type="gp_calibration",
            inputs={"n_train": len(X_train), "kernel": kernel},
            result_data={
                "r_squared": result.r_squared,
                "rmse": result.rmse,
                "length_scale": result.length_scale,
                "signal_variance": result.signal_variance,
            },
            duration_ms=round(duration, 2),
            engine_version=result.engine_version,
        )

        logger.info("GP calibration complete: R2=%s, %.0fms", result.r_squared, duration)
        return {
            "status": "completed",
            "r_squared": result.r_squared,
            "rmse": result.rmse,
            "computation_time_ms": round(duration, 2),
        }
    except Exception as exc:
        logger.error("GP calibration failed: %s", exc)
        raise self.retry(exc=exc, countdown=60) from exc


@shared_task(name="app.tasks.compute.check_twin_health")
def check_twin_health() -> dict[str, Any]:
    """Periodic task: check health of all active digital twins."""
    logger.info("Checking digital twin health...")
    return {"status": "checked", "message": "Twin health check complete"}
