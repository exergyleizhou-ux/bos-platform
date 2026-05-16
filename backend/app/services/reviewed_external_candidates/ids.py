"""Stable identifier helpers for reviewed external candidate workflows."""

from __future__ import annotations

import uuid


def new_literature_review_draft_id() -> str:
    return f"LERD-{uuid.uuid4().hex[:16].upper()}"


def new_literature_value_promotion_request_id() -> str:
    return f"LVPR-{uuid.uuid4().hex[:16].upper()}"


def new_literature_value_promotion_approval_id() -> str:
    return f"LVPA-{uuid.uuid4().hex[:16].upper()}"


def new_literature_value_overlay_id() -> str:
    return f"LVO-{uuid.uuid4().hex[:16].upper()}"


def new_literature_value_runtime_activation_id() -> str:
    return f"LVRA-{uuid.uuid4().hex[:16].upper()}"


def new_literature_value_release_evidence_link_id() -> str:
    return f"LVREL-{uuid.uuid4().hex[:16].upper()}"


def new_literature_value_rollback_id() -> str:
    return f"LVRB-{uuid.uuid4().hex[:16].upper()}"
