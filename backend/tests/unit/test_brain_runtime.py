from datetime import datetime

from app.services.brain_runtime import (
    RunLedgerArtifact,
    apply_run_ledger_artifact,
    infer_run_ledger_target_route,
    validate_runtime_document,
)


def test_validate_runtime_document_accepts_run_ledger_target_contract() -> None:
    result = validate_runtime_document(
        "run_ledger",
        """# Autonomy Run Ledger

## Latest Run
- Slice: Batch 101 signal review
- Outcome: Verified
- Verification: cmd /c npm run type-check
- Remaining Risk: Release mapping still pending
- Next Step: Connect audit packet 900 to release center
- Target Surface: audit_packet
- Target ID: 900
- Target Route: /bos/console?auditPacketId=900

## Recent Runs
- 2026-04-16 12:00 | Batch 101 signal review | Verified | Added explicit target contract | signal_lab | 101 | /bos/signal-lab?batchId=101
""",
    )

    assert result.is_valid is True
    assert result.invalid_lines == []


def test_validate_runtime_document_rejects_run_ledger_without_target_contract() -> None:
    result = validate_runtime_document(
        "run_ledger",
        """# Autonomy Run Ledger

## Latest Run
- Slice: Batch 101 signal review
- Outcome: Verified
- Verification: cmd /c npm run type-check
- Remaining Risk: Release mapping still pending
- Next Step: Connect audit packet 900 to release center

## Recent Runs
- 2026-04-16 12:00 | Batch 101 signal review | Verified | Added explicit target contract
""",
    )

    assert result.is_valid is False
    assert "Latest Run must include '- Target Surface: ...'" in result.invalid_lines
    assert "Latest Run must include '- Target ID: ...'" in result.invalid_lines
    assert "Latest Run must include '- Target Route: ...'" in result.invalid_lines


def test_infer_run_ledger_target_route_uses_surface_contract() -> None:
    assert infer_run_ledger_target_route("signal_lab", "101", None) == "/bos/signal-lab?batchId=101"
    assert infer_run_ledger_target_route("audit_packet", "900", None) == "/bos/console?auditPacketId=900"
    assert infer_run_ledger_target_route("brain", None, None) == "/bos/brain"


def test_apply_run_ledger_artifact_updates_latest_and_recent_runs() -> None:
    content = """# Autonomy Run Ledger

## Latest Run
- Slice: Older slice
- Outcome: Verified
- Verification: tests
- Remaining Risk: older risk
- Next Step: older step
- Target Surface: brain
- Target ID:
- Target Route: /bos/brain

## Recent Runs
- 2026-04-16 10:00+08:00 | Older slice | Verified | older step | brain |  | /bos/brain
"""
    artifact = RunLedgerArtifact(
        slice="Batch 101 signal review",
        outcome="Verified",
        verification="cmd /c npm run type-check",
        remaining_risk="Release mapping still pending",
        next_step="Connect audit packet 900 to release center",
        target_surface="audit_packet",
        target_id="900",
    )

    updated = apply_run_ledger_artifact(
        content,
        artifact,
        when=datetime.fromisoformat("2026-04-16T16:45:00+08:00"),
    )

    assert "- Slice: Batch 101 signal review" in updated
    assert "- Target Surface: audit_packet" in updated
    assert "- Target ID: 900" in updated
    assert "- Target Route: /bos/console?auditPacketId=900" in updated
    assert (
        "- 2026-04-16 16:45+08:00 | Batch 101 signal review | Verified | Connect audit packet 900 to release center | audit_packet | 900 | /bos/console?auditPacketId=900"
        in updated
    )
