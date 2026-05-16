from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_script(name: str):
    script_path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = spec_from_file_location(name, script_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_generate_release_report_uses_review_gated_wording(monkeypatch, tmp_path):
    module = _load_script("generate_release_report")
    reports_dir = tmp_path / "reports"
    playwright_dir = reports_dir / "playwright-check"
    stabilize_dir = reports_dir / "stabilize-v9"
    playwright_dir.mkdir(parents=True)
    stabilize_dir.mkdir(parents=True)

    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(module, "PLAYWRIGHT_DIR", playwright_dir)
    monkeypatch.setattr(module, "STABILIZE_DIR", stabilize_dir)
    monkeypatch.setattr(module, "OUTPUT_PATH", reports_dir / "release-readiness-summary.md")
    monkeypatch.setattr(module, "MANIFEST_PATH", reports_dir / "release-readiness-summary.json")
    monkeypatch.setattr(module, "RC_MANIFEST_PATH", stabilize_dir / "BOS_V9_RC_MANIFEST.json")
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend" / "package.json").write_text('{"version":"9.0.0"}', encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "9.0.0"\n', encoding="utf-8")

    monkeypatch.setattr(module, "run_git", lambda *args: "test-ref")
    monkeypatch.setattr(
        module,
        "run_preflight",
        lambda: (
            "raw preflight output with old provider and port details",
            [
                module.CheckLine("PASS", "backend focused", "completed"),
                module.CheckLine("PASS", "OPENAI_API_KEY", "configured (sk-testsecret...)"),
                module.CheckLine("WARN", "port 8000", "already occupied"),
                module.CheckLine("WARN", "provider live smoke", "skipped locally"),
                module.CheckLine("FAIL", "frontend focused", "failed with exit code 1"),
            ],
        ),
    )
    for name in (
        "live-code-runtime-ui-actions.json",
        "live-bos-interface-smoke.json",
        "live-bos-mechanistic-smoke.json",
    ):
        (playwright_dir / name).write_text('{"finalUrl":"http://localhost","failingResponses":[]}', encoding="utf-8")
    (stabilize_dir / "provider-live-smoke.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "provider": "openai-team",
                "model": "gpt-5.5",
                "summary": "provider responded",
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                "blocked_reason": None,
                "response_contains_expected_marker": True,
            }
        ),
        encoding="utf-8",
    )

    assert module.main() == 0

    dossier = module.OUTPUT_PATH.read_text(encoding="utf-8")
    manifest = json.loads(module.MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["release_state"] == "review_required"
    assert manifest["candidate_evidence_state"] == "review_required"
    assert manifest["checks"][0]["status"] == "ready_for_review"
    assert manifest["checks"][1]["summary"] == "configured (masked)"
    assert manifest["checks"][2]["status"] == "review_required"
    assert manifest["review_required_items"] == ["frontend focused: failed with exit code 1"]
    assert manifest["local_validation_notes"] == [
        "port 8000: already occupied",
        "provider live smoke: skipped locally",
    ]
    assert manifest["recommended_next_action"] == (
        "Resolve release review_required items before stakeholder demos or pilot handoff."
    )
    assert "## Review Required Items" in dossier
    assert "## Local Validation Notes" in dossier
    assert "## Provider Live Smoke" in dossier
    assert manifest["provider_smoke_path"] == "reports/stabilize-v9/provider-live-smoke.json"
    assert manifest["artifacts"]["provider_live_smoke_json"] == "reports/stabilize-v9/provider-live-smoke.json"
    assert "ready_for_review" in dossier
    assert "review_required" in dossier
    assert "Raw Preflight Output" not in dossier
    assert "active" not in dossier.lower()
    assert "approved" not in dossier.lower()
    assert "blocked" not in dossier.lower()
    assert "compliant" not in dossier.lower()
    assert "sk-testsecret" not in dossier.lower()


def test_validate_release_report_rejects_missing_json_fields_and_bad_wording(tmp_path, monkeypatch):
    module = _load_script("validate_release_report")
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "DOSSIER_PATH", reports_dir / "release-readiness-summary.md")
    monkeypatch.setattr(module, "MANIFEST_PATH", reports_dir / "release-readiness-summary.json")

    module.DOSSIER_PATH.write_text(
        "# BOS Code Release Dossier\n\n"
        "## Release Metadata\n\n"
        "## Gate Summary\n\n"
        "## Key Artifacts\n\n"
        "## Review Required Items\n\n"
        "## Local Validation Notes\n\n"
        "## Provider Live Smoke\n\n"
        "## Recommended Next Action\n\n"
        "This dossier is approved and contains sk-testsecret.\n",
        encoding="utf-8",
    )
    module.MANIFEST_PATH.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-24T00:00:00Z",
                "release_state": "READY",
                "backend_version": "9.0.0",
                "frontend_version": "9.0.0",
                "git_branch": "main",
                "git_commit": "abc123",
                "preflight_pass_count": 1,
                "preflight_warn_count": 0,
                "preflight_fail_count": 0,
                "review_required_items": [],
                "local_validation_notes": [],
                "known_limitations": [],
                "recommended_next_action": "human approval required",
                "checks": [{"status": "PASS", "name": "backend", "summary": "completed"}],
                "artifacts": {"code_smoke_json": "reports/missing.json"},
                "report_path": "reports/release-readiness-summary.md",
                "code_smoke_path": "reports/missing.json",
                "bos_smoke_path": "reports/missing.json",
                "bos_mechanistic_smoke_path": "reports/missing.json",
                "provider_smoke_path": "reports/missing.json",
            }
        ),
        encoding="utf-8",
    )

    assert module.main() == 1


def test_validate_release_report_accepts_required_manifest_and_smoke_jsons(tmp_path, monkeypatch):
    module = _load_script("validate_release_report")
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "DOSSIER_PATH", reports_dir / "release-readiness-summary.md")
    monkeypatch.setattr(module, "MANIFEST_PATH", reports_dir / "release-readiness-summary.json")

    module.DOSSIER_PATH.write_text(
        "# BOS Code Release Dossier\n\n"
        "## Release Metadata\n\n"
        "## Gate Summary\n\n"
        "## Key Artifacts\n\n"
        "## Review Required Items\n\n"
        "## Local Validation Notes\n\n"
        "## Provider Live Smoke\n\n"
        "## Safety Boundary\n\n"
        "## BOS v9 Target Scorecard\n\n"
        "## Recommended Next Action\n\n"
        "ready_for_review / review_required / human approval required\n",
        encoding="utf-8",
    )
    artifact_paths = {
        "release_dossier": "reports/release-readiness-summary.md",
        "release_manifest": "reports/release-readiness-summary.json",
        "bos_v9_rc_manifest": "reports/stabilize-v9/BOS_V9_RC_MANIFEST.json",
        "code_smoke_json": "reports/code.json",
        "code_smoke_png": "reports/code.png",
        "bos_smoke_json": "reports/bos.json",
        "bos_smoke_png": "reports/bos.png",
        "bos_mechanistic_smoke_json": "reports/mech.json",
        "bos_mechanistic_smoke_bos_png": "reports/mech-bos.png",
        "bos_mechanistic_smoke_packet_png": "reports/mech-packet.png",
        "bos_mechanistic_smoke_batch_png": "reports/mech-batch.png",
        "provider_live_smoke_json": "reports/provider.json",
        "release_reference_joint_smoke_json": "reports/release-reference.json",
        "frontend_build_entry": "frontend/dist/index.html",
    }
    for key in ("code_smoke_json", "bos_smoke_json", "bos_mechanistic_smoke_json"):
        (tmp_path / artifact_paths[key]).write_text(
            json.dumps({"finalUrl": "http://localhost", "failingResponses": []}),
            encoding="utf-8",
        )
    (tmp_path / artifact_paths["provider_live_smoke_json"]).write_text(
        json.dumps(
            {
                "status": "passed",
                "provider": "openai-team",
                "model": "gpt-5.5",
                "summary": "provider responded",
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                "blocked_reason": None,
                "response_contains_expected_marker": True,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / artifact_paths["release_reference_joint_smoke_json"]).write_text(
        json.dumps(
            {
                "passed": True,
                "checks": {"releaseCenterLoaded": True},
                "releaseDecisionAfter": "review_required",
                "modelVersionAfter": "ready_for_review",
                "finalActionDraftCount": 0,
                "finalActionAuditRecordCount": 0,
                "externalShareRecordCreated": False,
                "finalActionExecuteCalls": [],
                "failingResponses": [],
            }
        ),
        encoding="utf-8",
    )
    module.MANIFEST_PATH.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-24T00:00:00Z",
                "release_state": "review_required",
                "candidate_evidence_state": "ready_for_review",
                "backend_version": "9.0.0",
                "frontend_version": "9.0.0",
                "git_branch": "main",
                "git_commit": "abc123",
                "preflight_pass_count": 1,
                "preflight_warn_count": 0,
                "preflight_fail_count": 0,
                "review_required_items": [],
                "local_validation_notes": [],
                "known_limitations": [],
                "recommended_next_action": "human approval required",
                "checks": [{"status": "ready_for_review", "name": "backend", "summary": "completed"}],
                "artifacts": artifact_paths,
                "report_path": "reports/release-readiness-summary.md",
                "code_smoke_path": "reports/code.json",
                "bos_smoke_path": "reports/bos.json",
                "bos_mechanistic_smoke_path": "reports/mech.json",
                "provider_smoke_path": "reports/provider.json",
                "release_reference_smoke_path": "reports/release-reference.json",
                "release_reference_smoke_passed": True,
                "rc_manifest_path": "reports/stabilize-v9/BOS_V9_RC_MANIFEST.json",
                "bos_v9_target_progress_percent": 91,
                "bos_v9_target_scorecard": [
                    {"dimension": f"dimension_{index}", "score": 8, "target": 9, "evidence": "ready_for_review"}
                    for index in range(6)
                ],
                "safety_boundary": {
                    "release_decision": "review_required",
                    "model_version": "ready_for_review",
                    "final_action_draft_count": 0,
                    "final_action_audit_record_count": 0,
                    "external_share_record_created": False,
                    "final_action_execute_call_count": 0,
                    "validated_default_write_enabled": False,
                    "runtime_activation_enabled": False,
                    "hardware_execution_enabled": False,
                    "final_action_execution_enabled": False,
                },
            }
        ),
        encoding="utf-8",
    )

    assert module.main() == 0


def test_ingest_go_live_packet_validates_artifacts_and_smoke_json(tmp_path, monkeypatch):
    module = _load_script("ingest_go_live_packet")
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    reports_dir = tmp_path / "reports" / "stabilize-v9"
    reports_dir.mkdir(parents=True)

    packet_path = reports_dir / "BOS_RELEASE_CENTER_GO_LIVE_PACKET_2026-04-24.md"
    manifest_path = tmp_path / "reports" / "release-readiness-summary.json"
    assistant_smoke_path = reports_dir / "assistant-release-browser-smoke-2026-04-24.json"
    provider_smoke_path = reports_dir / "provider-live-smoke.json"
    (tmp_path / "reports" / "release-readiness-summary.md").write_text("dossier", encoding="utf-8")
    assistant_smoke_path.write_text(
        json.dumps(
            {
                "passed": True,
                "releaseDecisionBefore": "review_required",
                "releaseDecisionAfter": "review_required",
                "checks": {key: True for key in module.REQUIRED_ASSISTANT_SMOKE_CHECKS},
            }
        ),
        encoding="utf-8",
    )
    provider_smoke_path.write_text(
        json.dumps(
            {
                "status": "passed",
                "provider": "openai-team",
                "model": "gpt-5.5",
                "summary": "provider responded",
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                "blocked_reason": None,
                "response_contains_expected_marker": True,
            }
        ),
        encoding="utf-8",
    )
    packet_path.write_text(
        "# Packet\n\n"
        "- Product path is verifiable: Assistant -> Simulation Lab -> appendix -> Release Center -> benchmark -> model governance -> knowledge relation.\n"
        "- Release decision before: `review_required`\n"
        "- Release decision after: `review_required`\n"
        "- Backend full, frontend full, build, report validation, and browser smoke all passed.\n"
        "- Dossier: `reports/release-readiness-summary.md`\n"
        "- Assistant browser smoke JSON: `reports/stabilize-v9/assistant-release-browser-smoke-2026-04-24.json`\n",
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "release_state": "review_required",
                "artifacts": {
                    "release_dossier": "reports/release-readiness-summary.md",
                    "provider_live_smoke_json": "reports/stabilize-v9/provider-live-smoke.json",
                },
            }
        ),
        encoding="utf-8",
    )

    ingest, failures = module.validate_packet(packet_path, manifest_path, require_provider_live=True)

    assert failures == []
    assert ingest["status"] == "passed"
    assert ingest["provider_live_status"] == "passed"
