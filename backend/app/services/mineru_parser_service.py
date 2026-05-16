"""
MinerU parser boundary for staged reference ingestion.

The wrapper prefers a real `mineru` CLI when available. If MinerU is not
installed, it falls back to a conservative text extraction pass so the staging
pipeline remains reviewable and rollback-safe during phase 1.
"""

from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas.reference_ingestion import ReferenceParserMetadata


@dataclass
class MinerUParseResult:
    markdown: str
    json_payload: dict[str, Any]
    metadata: ReferenceParserMetadata


class MinerUParserService:
    def __init__(
        self,
        *,
        command: str = "mineru",
        timeout_seconds: int = 180,
        extra_args: str | None = "-b pipeline -m txt",
    ) -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds
        self.extra_args = extra_args or ""

    def parse_pdf(self, source_path: Path, output_dir: Path) -> MinerUParseResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        mineru_binary = shutil.which(self.command)

        if mineru_binary:
            try:
                return self._run_mineru(mineru_binary, source_path, output_dir)
            except subprocess.TimeoutExpired as exc:
                return self._fallback_parse(
                    source_path,
                    output_dir,
                    fallback_reason=f"mineru_timeout_after_{self.timeout_seconds}s",
                    warning_detail=self._trim_process_text(
                        "\n".join(str(part) for part in [exc.stdout, exc.stderr] if part)
                    ),
                )
            except subprocess.CalledProcessError as exc:
                return self._fallback_parse(
                    source_path,
                    output_dir,
                    fallback_reason=f"mineru_failed_exit_{exc.returncode}",
                    warning_detail=self._trim_process_text("\n".join([exc.stdout or "", exc.stderr or ""])),
                )
            except Exception as exc:  # pragma: no cover - exercised by runtime fallback.
                return self._fallback_parse(
                    source_path,
                    output_dir,
                    fallback_reason=f"mineru_failed:{exc.__class__.__name__}",
                    warning_detail=str(exc),
                )

        return self._fallback_parse(
            source_path,
            output_dir,
            fallback_reason="mineru_cli_not_found",
        )

    def _run_mineru(self, mineru_binary: str, source_path: Path, output_dir: Path) -> MinerUParseResult:
        completed = subprocess.run(
            [mineru_binary, "-p", str(source_path), "-o", str(output_dir), *shlex.split(self.extra_args)],
            check=True,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
        )

        markdown_path = self._find_first(output_dir, "*.md")
        json_path = self._find_first(output_dir, "*.json")
        markdown = markdown_path.read_text(encoding="utf-8") if markdown_path else completed.stdout
        json_payload = (
            json.loads(json_path.read_text(encoding="utf-8"))
            if json_path
            else {"stdout": completed.stdout, "stderr": completed.stderr}
        )

        raw_markdown_path = output_dir / "document.md"
        raw_json_path = output_dir / "document.json"
        raw_markdown_path.write_text(markdown, encoding="utf-8")
        raw_json_path.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False), encoding="utf-8")

        metadata = ReferenceParserMetadata(
            parser_name="mineru",
            parser_version=None,
            execution_mode="mineru_cli",
            raw_markdown_path=str(raw_markdown_path),
            raw_json_path=str(raw_json_path),
            source_file_path=str(source_path),
            warnings=[],
            fallback_reason=None,
            extracted_field_count=0,
            parsed_at=datetime.now(UTC),
        )
        return MinerUParseResult(markdown=markdown, json_payload=json_payload, metadata=metadata)

    def _fallback_parse(
        self,
        source_path: Path,
        output_dir: Path,
        *,
        fallback_reason: str,
        warning_detail: str | None = None,
    ) -> MinerUParseResult:
        raw_bytes = source_path.read_bytes()
        text, fallback_mode = self._extract_plain_text(raw_bytes)
        markdown = text if text.strip() else f"# {source_path.stem}\n\nNo extractable text found."
        json_payload = {
            "parser": "fallback_simple_pdf_text",
            "source_file": str(source_path),
            "blocks": [{"block_type": "Text", "text": markdown}],
        }
        raw_markdown_path = output_dir / "document.md"
        raw_json_path = output_dir / "document.json"
        raw_markdown_path.write_text(markdown, encoding="utf-8")
        raw_json_path.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False), encoding="utf-8")

        warnings = ["MinerU CLI unavailable or failed; used fallback parser for staging only."]
        if warning_detail:
            warnings.append(warning_detail)

        metadata = ReferenceParserMetadata(
            parser_name="mineru",
            parser_version=None,
            execution_mode=fallback_mode,
            raw_markdown_path=str(raw_markdown_path),
            raw_json_path=str(raw_json_path),
            source_file_path=str(source_path),
            warnings=warnings,
            fallback_reason=fallback_reason,
            extracted_field_count=0,
            parsed_at=datetime.now(UTC),
        )
        return MinerUParseResult(markdown=markdown, json_payload=json_payload, metadata=metadata)

    @staticmethod
    def _find_first(root: Path, pattern: str) -> Path | None:
        matches = sorted(root.rglob(pattern))
        return matches[0] if matches else None

    @staticmethod
    def _extract_plain_text(raw_bytes: bytes) -> tuple[str, str]:
        extracted = MinerUParserService._extract_with_pypdf(raw_bytes)
        if extracted.strip():
            return extracted, "fallback_pypdf_text"

        extracted = MinerUParserService._extract_with_pdfminer(raw_bytes)
        if extracted.strip():
            return extracted, "fallback_pdfminer_text"

        decoded = raw_bytes.decode("latin-1", errors="ignore")
        pdf_strings = re.findall(r"\(([^()]{2,})\)", decoded)
        if pdf_strings:
            return "\n".join(item.replace("\\(", "(").replace("\\)", ")") for item in pdf_strings), "fallback_regex_pdf_strings"

        printable_runs = re.findall(r"[A-Za-z0-9][A-Za-z0-9\s:;,_./%+\-'()]{20,}", decoded)
        return "\n".join(run.strip() for run in printable_runs[:80]), "fallback_regex_printable_runs"

    @staticmethod
    def _trim_process_text(value: str, limit: int = 1200) -> str:
        cleaned = re.sub(r"\s+", " ", value).strip()
        return cleaned[-limit:] if len(cleaned) > limit else cleaned

    @staticmethod
    def _extract_with_pypdf(raw_bytes: bytes) -> str:
        try:
            from io import BytesIO

            from pypdf import PdfReader

            reader = PdfReader(BytesIO(raw_bytes))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return ""

    @staticmethod
    def _extract_with_pdfminer(raw_bytes: bytes) -> str:
        try:
            from io import BytesIO

            from pdfminer.high_level import extract_text

            return extract_text(BytesIO(raw_bytes)) or ""
        except Exception:
            return ""
