# Legacy Alembic Migrations

These migrations were moved out of `alembic/versions` on 2026-04-04 during stabilize-v9 work.

Reason:
- They created a second root chain (`001 -> 002`) that conflicted with the active chain (`001_initial -> 002_api_keys_webhooks -> 003_feature_flags -> 004_digital_twins`).
- The duplicate chain caused multiple Alembic heads and blocked `alembic upgrade head`.

Policy:
- Do not place these files back into `alembic/versions`.
- Keep them only for historical reference.
