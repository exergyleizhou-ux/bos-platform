from app.tasks.compute import _build_sync_database_url, _persist_calculation


def test_build_sync_database_url_prefers_explicit_sync_url():
    assert (
        _build_sync_database_url(
            "postgresql+asyncpg://user:pass@localhost/db",
            "sqlite:///./override.db",
        )
        == "sqlite:///./override.db"
    )


def test_build_sync_database_url_converts_known_async_drivers():
    assert (
        _build_sync_database_url("postgresql+asyncpg://user:pass@localhost/db")
        == "postgresql+psycopg2://user:pass@localhost/db"
    )
    assert _build_sync_database_url("sqlite+aiosqlite:///./bos.db") == "sqlite:///./bos.db"


def test_persist_calculation_skips_records_without_batch_id():
    assert _persist_calculation(
        batch_id=None,
        calc_type="sensitivity",
        tenant_id=1,
        user_id=1,
    ) is False
