"""
BOS Pipeline v9.0 -Celery Tasks Package

Sub-modules:
- compute : Heavy computation tasks (MC, calibration, sensitivity)
- export : Data export generation
- webhook : Webhook delivery
- maintenance : Database cleanup, digest generation
"""

# Import task modules so Celery workers started in local Windows environments
# always register the concrete task names used by beat schedules.
from app.tasks import code_runtime, compute, export, maintenance, webhook  # noqa: F401
