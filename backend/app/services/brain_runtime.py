"""
Structured runtime-brain document helpers.

These documents are durable memory surfaces for the BOS autonomy loop. Keep
their schema explicit so operator-facing summaries and automated writers do not
silently drift into incompatible markdown.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re


RUNTIME_DOCUMENT_SPECS: dict[str, dict[str, object]] = {
    "project_brain": {
        "title": "Project Brain",
        "required_headings": [
            "Mission",
            "Current Focus",
            "Next Slices",
            "Stable Facts",
            "Constraints",
            "Known Good Commands",
            "Repeated Pitfalls",
        ],
    },
    "decision_journal": {
        "title": "Decision Journal",
        "required_headings": [
            "Recent Decisions",
            "Plan Changes",
        ],
    },
    "evolution_log": {
        "title": "Evolution Log",
        "required_headings": [
            "Active Heuristics",
            "Recent Learnings",
        ],
    },
    "run_ledger": {
        "title": "Autonomy Run Ledger",
        "required_headings": [
            "Latest Run",
            "Recent Runs",
        ],
    },
}

_H1_PATTERN = re.compile(r"^#\s+(.+?)\s*$")
_H2_PATTERN = re.compile(r"^##\s+(.+?)\s*$")
_BULLET_PATTERN = re.compile(r"^-\s+.+$")
_RUN_LEDGER_LATEST_RUN_FIELDS = (
    "slice",
    "outcome",
    "verification",
    "remaining risk",
    "next step",
    "target surface",
    "target id",
    "target route",
)
_RUN_LEDGER_LATEST_RUN_FIELD_LABELS = {
    "slice": "Slice",
    "outcome": "Outcome",
    "verification": "Verification",
    "remaining risk": "Remaining Risk",
    "next step": "Next Step",
    "target surface": "Target Surface",
    "target id": "Target ID",
    "target route": "Target Route",
}


@dataclass(slots=True)
class BrainRuntimeValidationResult:
    normalized_content: str
    missing_headings: list[str]
    unexpected_headings: list[str]
    duplicate_headings: list[str]
    out_of_order_headings: list[str]
    invalid_lines: list[str]

    @property
    def is_valid(self) -> bool:
        return not any(
            [
                self.missing_headings,
                self.unexpected_headings,
                self.duplicate_headings,
                self.out_of_order_headings,
                self.invalid_lines,
            ]
        )


@dataclass(slots=True)
class RunLedgerArtifact:
    slice: str
    outcome: str
    verification: str
    remaining_risk: str
    next_step: str
    target_surface: str
    target_id: str | None = None
    target_route: str | None = None


def get_runtime_document_spec(document_key: str) -> dict[str, object]:
    try:
        return RUNTIME_DOCUMENT_SPECS[document_key]
    except KeyError as exc:
        raise ValueError(f"Unknown runtime document key: {document_key}") from exc


def validate_runtime_document(document_key: str, content: str) -> BrainRuntimeValidationResult:
    spec = get_runtime_document_spec(document_key)
    expected_title = str(spec["title"])
    expected_headings = [str(item) for item in spec["required_headings"]]
    normalized = content.replace("\r\n", "\n").strip()
    lines = normalized.split("\n") if normalized else []

    missing_headings = list(expected_headings)
    unexpected_headings: list[str] = []
    duplicate_headings: list[str] = []
    out_of_order_headings: list[str] = []
    invalid_lines: list[str] = []
    seen_headings: list[str] = []
    section_lines: dict[str, list[str]] = {}
    current_section: str | None = None

    if not lines:
        invalid_lines.append("Document is empty.")
        return BrainRuntimeValidationResult(
            normalized_content=f"# {expected_title}\n",
            missing_headings=missing_headings,
            unexpected_headings=unexpected_headings,
            duplicate_headings=duplicate_headings,
            out_of_order_headings=out_of_order_headings,
            invalid_lines=invalid_lines,
        )

    title_match = _H1_PATTERN.match(lines[0].strip())
    if not title_match:
        invalid_lines.append(f"Line 1 must be '# {expected_title}'.")
    elif title_match.group(1).strip() != expected_title:
        invalid_lines.append(f"Document title must be '# {expected_title}'.")

    for index, raw_line in enumerate(lines[1:], start=2):
        stripped = raw_line.strip()
        if not stripped:
            continue

        heading_match = _H2_PATTERN.match(stripped)
        if heading_match:
            heading = heading_match.group(1).strip()
            if heading in seen_headings:
                duplicate_headings.append(heading)
            seen_headings.append(heading)
            current_section = heading
            if heading in missing_headings:
                missing_headings.remove(heading)
            else:
                unexpected_headings.append(heading)
            section_lines.setdefault(heading, [])
            continue

        if stripped.startswith("#"):
            invalid_lines.append(f"Line {index} uses an unsupported heading level: {stripped}")
            continue

        if current_section is None:
            invalid_lines.append(f"Line {index} must live under a '##' heading: {stripped}")
            continue

        if not _BULLET_PATTERN.match(stripped):
            invalid_lines.append(f"Line {index} must be a concise bullet: {stripped}")
            continue

        if current_section is not None:
            section_lines.setdefault(current_section, []).append(stripped)

    seen_required = [heading for heading in seen_headings if heading in expected_headings]
    if seen_required != expected_headings[: len(seen_required)]:
        out_of_order_headings.extend(seen_required)

    if document_key == "run_ledger":
        latest_run_lines = section_lines.get("Latest Run", [])
        latest_run_fields = {
            line[2:].split(":", 1)[0].strip().lower()
            for line in latest_run_lines
            if ":" in line[2:]
        }
        for field in _RUN_LEDGER_LATEST_RUN_FIELDS:
            if field not in latest_run_fields:
                invalid_lines.append(
                    f"Latest Run must include '- {_RUN_LEDGER_LATEST_RUN_FIELD_LABELS[field]}: ...'"
                )

    return BrainRuntimeValidationResult(
        normalized_content=normalized + "\n",
        missing_headings=missing_headings,
        unexpected_headings=unexpected_headings,
        duplicate_headings=duplicate_headings,
        out_of_order_headings=out_of_order_headings,
        invalid_lines=invalid_lines,
    )


def infer_run_ledger_target_route(
    target_surface: str | None,
    target_id: str | None,
    target_route: str | None,
) -> str | None:
    if target_route:
        return target_route
    if not target_surface:
        return None

    surface = target_surface.strip().lower()
    if surface == "signal_lab" and target_id:
        return f"/bos/signal-lab?batchId={target_id}"
    if surface == "batch" and target_id:
        return f"/batches/{target_id}"
    if surface == "audit_packet" and target_id:
        return f"/bos/console?auditPacketId={target_id}"
    if surface == "release":
        return "/release"
    if surface == "brain":
        return "/bos/brain"
    if surface == "orchestrator":
        return "/bos/orchestrator"
    return None


def format_run_ledger_latest_run(artifact: RunLedgerArtifact) -> list[str]:
    target_route = infer_run_ledger_target_route(
        artifact.target_surface,
        artifact.target_id,
        artifact.target_route,
    )
    return [
        f"- Slice: {artifact.slice}",
        f"- Outcome: {artifact.outcome}",
        f"- Verification: {artifact.verification}",
        f"- Remaining Risk: {artifact.remaining_risk}",
        f"- Next Step: {artifact.next_step}",
        f"- Target Surface: {artifact.target_surface}",
        f"- Target ID: {artifact.target_id or ''}",
        f"- Target Route: {target_route or ''}",
    ]


def format_run_ledger_recent_run(
    artifact: RunLedgerArtifact,
    *,
    when: datetime,
) -> str:
    target_route = infer_run_ledger_target_route(
        artifact.target_surface,
        artifact.target_id,
        artifact.target_route,
    )
    timestamp = when.isoformat(sep=" ", timespec="minutes")
    return " | ".join(
        [
            timestamp,
            artifact.slice,
            artifact.outcome,
            artifact.next_step,
            artifact.target_surface,
            artifact.target_id or "",
            target_route or "",
        ]
    )


def apply_run_ledger_artifact(
    content: str,
    artifact: RunLedgerArtifact,
    *,
    when: datetime,
    history_limit: int = 5,
) -> str:
    lines = format_run_ledger_latest_run(artifact)
    recent_entry = format_run_ledger_recent_run(artifact, when=when)
    parsed = validate_runtime_document("run_ledger", build_structured_runtime_document("run_ledger", content))
    normalized = parsed.normalized_content

    sections: dict[str, list[str]] = {"Latest Run": [], "Recent Runs": []}
    current_section: str | None = None
    for raw_line in normalized.splitlines():
        stripped = raw_line.strip()
        heading_match = _H2_PATTERN.match(stripped)
        if heading_match:
            current_section = heading_match.group(1).strip()
            sections.setdefault(current_section, [])
            continue
        if current_section in sections and _BULLET_PATTERN.match(stripped):
            sections[current_section].append(stripped)

    recent_runs = [item for item in sections.get("Recent Runs", []) if item != f"- {recent_entry}"]
    recent_runs.insert(0, f"- {recent_entry}")
    recent_runs = recent_runs[:history_limit]

    output = [
        "# Autonomy Run Ledger",
        "",
        "## Latest Run",
        "",
        *lines,
        "",
        "## Recent Runs",
        "",
        *recent_runs,
        "",
    ]
    return "\n".join(output)


def build_structured_runtime_document(documentKey: str, content: str) -> str:
    spec = get_runtime_document_spec(documentKey)
    parsed = content.replace("\r\n", "\n")
    section_map: dict[str, list[str]] = {}
    current_section: str | None = None
    for raw_line in parsed.splitlines():
        stripped = raw_line.strip()
        heading_match = _H2_PATTERN.match(stripped)
        if heading_match:
            current_section = heading_match.group(1).strip()
            section_map.setdefault(current_section, [])
            continue
        if current_section and _BULLET_PATTERN.match(stripped):
            section_map.setdefault(current_section, []).append(stripped)

    defaults: dict[str, list[str]] = {
        "Mission": ["- Record the durable mission of the project here."],
        "Current Focus": ["- Record the current highest-priority slice here."],
        "Next Slices": ["- Record the next 1-3 highest-value slices here."],
        "Stable Facts": ["- Record stable architecture and product truths here."],
        "Constraints": ["- Record hard limits, dependencies, and non-negotiables here."],
        "Known Good Commands": ["- Record the most reliable verification or run commands here."],
        "Repeated Pitfalls": ["- Record recurring traps or regressions here."],
        "Recent Decisions": ["- Record important planning and implementation decisions here."],
        "Plan Changes": ["- Record when the plan changed and why."],
        "Active Heuristics": ["- Record verified heuristics and routine improvements here."],
        "Recent Learnings": ["- Record short evidence-backed lessons from recent runs here."],
        "Latest Run": [
            "- Slice: Record the current slice here.",
            "- Outcome: Record the result here.",
            "- Verification: Record how it was verified here.",
            "- Remaining Risk: Record the remaining risk here.",
            "- Next Step: Record the next step here.",
            "- Target Surface: Record the destination surface key here.",
            "- Target ID: Record the destination entity id here when one exists.",
            "- Target Route: Record the deep-link route here.",
        ],
        "Recent Runs": ["- YYYY-MM-DD HH:MM | Slice | Outcome | Short note | targetSurface | targetId | targetRoute"],
    }

    lines = [f"# {spec['title']}", ""]
    for heading in [str(item) for item in spec["required_headings"]]:
        lines.append(f"## {heading}")
        lines.append("")
        payload = section_map.get(heading) or defaults.get(heading, ["- Fill this section."])
        lines.extend(payload)
        lines.append("")
    return "\n".join(lines).strip() + "\n"
