"""
BOS Pipeline v9.0 legacy seed data migration.

Revision ID: 002
Create Date: 2024-01-15 00:00:00.000000+00:00
"""

from alembic import op
from passlib.context import CryptContext

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO tenants (id, name, slug, plan, max_users, max_batches, max_calculations)
        VALUES (1, 'BOS Demo', 'bos-demo', 'pro', 50, 10000, 50000)
        ON CONFLICT (slug) DO NOTHING
        """
    )

    admin_password = pwd_context.hash("AdminPass123!")
    op.execute(
        f"""
        INSERT INTO users (id, username, hashed_password, full_name, email, role, tenant_id)
        VALUES (1, 'admin', '{admin_password}', 'System Administrator', 'admin@bos-pipeline.io', 'admin', 1)
        ON CONFLICT (username) DO NOTHING
        """
    )

    scientist_password = pwd_context.hash("SciPass123!")
    op.execute(
        f"""
        INSERT INTO users (id, username, hashed_password, full_name, email, role, tenant_id)
        VALUES (2, 'scientist', '{scientist_password}', 'Dr. Jane Smith', 'scientist@bos-pipeline.io', 'scientist', 1)
        ON CONFLICT (username) DO NOTHING
        """
    )

    operator_password = pwd_context.hash("OpPass123!")
    op.execute(
        f"""
        INSERT INTO users (id, username, hashed_password, full_name, email, role, tenant_id)
        VALUES (3, 'operator', '{operator_password}', 'John Operator', 'operator@bos-pipeline.io', 'operator', 1)
        ON CONFLICT (username) DO NOTHING
        """
    )

    sample_batches = [
        ("BATCH-2024-001", "BSF", "completed", 10.0, 2.3, 0.2300, 28.5, 68.0, "John Operator", "2024-01-10"),
        ("BATCH-2024-002", "BSF", "completed", 12.5, 2.8, 0.2240, 27.8, 72.0, "John Operator", "2024-01-15"),
        ("BATCH-2024-003", "BSF", "completed", 8.0, 1.6, 0.2000, 29.0, 65.0, "John Operator", "2024-01-20"),
        ("BATCH-2024-004", "BSF", "completed", 15.0, 3.6, 0.2400, 28.0, 70.0, "John Operator", "2024-01-25"),
        ("BATCH-2024-005", "BSF", "active", 11.0, 2.1, 0.1909, 28.2, 69.0, "John Operator", "2024-02-01"),
        ("BATCH-2024-006", "MW", "completed", 5.0, 0.8, 0.1600, 25.0, 75.0, "Dr. Jane Smith", "2024-01-12"),
        ("BATCH-2024-007", "MW", "completed", 6.0, 1.1, 0.1833, 24.5, 73.0, "Dr. Jane Smith", "2024-01-18"),
        ("BATCH-2024-008", "BSF", "completed", 20.0, 5.0, 0.2500, 28.3, 71.0, "John Operator", "2024-02-05"),
        ("BATCH-2024-009", "BSF", "logged", 9.5, 0.0, None, 27.5, 67.0, "John Operator", "2024-02-10"),
        ("BATCH-2024-010", "YMW", "completed", 3.0, 0.45, 0.1500, 26.0, 60.0, "Dr. Jane Smith", "2024-02-08"),
    ]

    for batch_id, species, status, dm_in, dm_out, score, temp, moist, operator, batch_date in sample_batches:
        score_sql = f"{score}" if score is not None else "NULL"
        op.execute(
            f"""
            INSERT INTO batches (
                batch_id, species, status, dm_in, dm_out, score,
                temperature, moisture, operator, batch_date, user_id, tenant_id
            )
            VALUES (
                '{batch_id}', '{species}', '{status}', {dm_in}, {dm_out}, {score_sql},
                {temp}, {moist}, '{operator}', '{batch_date}', 3, 1
            )
            """
        )

    op.execute("SELECT setval('tenants_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM tenants))")
    op.execute("SELECT setval('users_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM users))")
    op.execute("SELECT setval('batches_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM batches))")


def downgrade() -> None:
    op.execute("DELETE FROM batches WHERE tenant_id = 1 AND batch_id LIKE 'BATCH-2024-%'")
    op.execute("DELETE FROM users WHERE tenant_id = 1 AND username IN ('admin', 'scientist', 'operator')")
    op.execute("DELETE FROM tenants WHERE slug = 'bos-demo'")
