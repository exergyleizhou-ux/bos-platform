"""
Staged reference-ingestion service.

Phase 1 stores parsed documents and promoted campaign candidates outside the
curated production reference constants, preserving a clear fallback/rollback
boundary.
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.schemas.reference_ingestion import (
    ReferenceIngestionCampaignCandidate,
    ReferenceIngestionStagedItem,
)
from app.services.mineru_parser_service import MinerUParserService


SPECIES_NORMALIZATION = {
    "tenebrio molitor": "MW",
    "yellow mealworm": "MW",
    "mealworm": "MW",
    "protaetia brevitarsis": "PB",
    "white-spotted flower chafer": "PB",
    "chafer grub": "PB",
    "hermetia illucens": "BSF",
    "black soldier fly": "BSF",
    "bsf": "BSF",
}

FEEDSTOCK_NORMALIZATION = {
    "distillers grains": "distillers_grains",
    "distillery grains": "distillers_grains",
    "brewery spent grains": "brewery_spent_grains",
    "beer lees": "brewery_spent_grains",
    "straw-sludge": "straw_sludge_blend",
    "straw sludge": "straw_sludge_blend",
    "washed kitchen waste": "washed_kitchen_waste",
    "kitchen waste": "washed_kitchen_waste",
    "sewage sludge": "sewage_sludge",
    "traditional chinese medicine residue": "tcm_residue",
    "tcm residue": "tcm_residue",
}

PARAMETER_PATTERNS = {
    "ser": [r"\bser\b"],
    "d_prime": [r"\bd[_\s-]?prime\b", r"\bd'\b"],
    "g_prime": [r"\bg[_\s-]?prime\b", r"\bg'\b"],
    "delta_delta_ser": [r"\bdelta[_\s-]?delta[_\s-]?ser\b"],
    "kernel_target_moisture_pct": [r"\bkernel[_\s-]?target[_\s-]?moisture[_\s-]?pct\b"],
    "kernel_temperature_c": [r"\bkernel[_\s-]?temperature[_\s-]?c\b"],
    "audit_window_h": [r"\baudit[_\s-]?window[_\s-]?h\b"],
    "dose_nominal_bu_per_kg": [r"\bdose[_\s-]?nominal[_\s-]?bu[_\s-]?per[_\s-]?kg\b"],
}

OUTPUT_PATTERNS = {
    "best_single_stage_ser": [r"\bbest[_\s-]?single[_\s-]?stage[_\s-]?ser\b"],
    "signal_api_cellulase_uplift_pct": [r"\bsignal[_\s-]?api[_\s-]?cellulase[_\s-]?uplift[_\s-]?pct\b"],
}


class ReferenceIngestionService:
    def __init__(
        self,
        *,
        storage_root: Path | None = None,
        parser_service: MinerUParserService | None = None,
        promotion_enabled: bool | None = None,
    ) -> None:
        settings = get_settings()
        self.storage_root = storage_root or Path(settings.BOS_REFERENCE_INGESTION_STORAGE_DIR)
        self.parser_service = parser_service or MinerUParserService(
            command=settings.BOS_MINERU_COMMAND,
            timeout_seconds=settings.BOS_MINERU_TIMEOUT_SECONDS,
            extra_args=settings.BOS_MINERU_EXTRA_ARGS,
        )
        self.promotion_enabled = (
            settings.BOS_REFERENCE_INGESTION_PROMOTION_ENABLED
            if promotion_enabled is None
            else promotion_enabled
        )

    def parse_document(
        self,
        *,
        tenant_id: int,
        filename: str,
        content: bytes,
        source_title: str | None,
        source_type: str = "pdf",
        source_owner: str | None = None,
        license_note: str | None = None,
        region: str | None = None,
        units: dict[str, str] | None = None,
        ingestion_mode: str = "manual_review_first",
        human_review_required: bool = True,
    ) -> ReferenceIngestionStagedItem:
        item_id = f"refing_{uuid.uuid4().hex[:12]}"
        tenant_root = self._tenant_root(tenant_id)
        raw_dir = tenant_root / "raw" / item_id
        raw_dir.mkdir(parents=True, exist_ok=True)

        safe_name = self._safe_filename(filename or "source.pdf")
        source_path = raw_dir / safe_name
        source_path.write_bytes(content)

        parser_result = self.parser_service.parse_pdf(source_path, raw_dir)
        staged = self._normalize_to_staged_item(
            tenant_id=tenant_id,
            item_id=item_id,
            source_title=source_title or Path(filename).stem or "Untitled source",
            source_type=source_type,
            source_owner=source_owner,
            license_note=license_note,
            region=region,
            units=units or {},
            ingestion_mode=ingestion_mode,
            human_review_required=human_review_required,
            markdown=parser_result.markdown,
            json_payload=parser_result.json_payload,
            parser_metadata=parser_result.metadata.model_copy(update={"source_file_path": str(source_path)}),
        )
        self._write_staged_item(staged)
        return staged

    def list_staged_items(self, tenant_id: int) -> list[ReferenceIngestionStagedItem]:
        staging_dir = self._tenant_root(tenant_id) / "staging"
        if not staging_dir.exists():
            return []
        items = [
            ReferenceIngestionStagedItem.model_validate_json(path.read_text(encoding="utf-8"))
            for path in staging_dir.glob("*.json")
        ]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    def get_staged_item(self, tenant_id: int, item_id: str) -> ReferenceIngestionStagedItem | None:
        path = self._staged_item_path(tenant_id, item_id)
        if not path.exists():
            return None
        return ReferenceIngestionStagedItem.model_validate_json(path.read_text(encoding="utf-8"))

    def promote_to_campaign(
        self,
        *,
        tenant_id: int,
        item_id: str,
        notes: str | None = None,
    ) -> tuple[ReferenceIngestionStagedItem, ReferenceIngestionCampaignCandidate] | None:
        if not self.promotion_enabled:
            raise ValueError("reference_ingestion_promotion_disabled")

        staged = self.get_staged_item(tenant_id, item_id)
        if staged is None:
            return None
        self._validate_promotable(staged)

        campaign = self._staged_item_to_campaign(staged, notes=notes)
        promoted = self.list_promoted_campaigns(tenant_id)
        by_key = {item["key"]: item for item in promoted}
        by_key[campaign.key] = campaign.model_dump(mode="json")
        self._promoted_campaigns_path(tenant_id).parent.mkdir(parents=True, exist_ok=True)
        self._promoted_campaigns_path(tenant_id).write_text(
            json.dumps(list(by_key.values()), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        now = datetime.now(UTC)
        updated = staged.model_copy(
            update={
                "status": "promoted",
                "promoted_campaign_key": campaign.key,
                "updated_at": now,
            }
        )
        self._write_staged_item(updated)
        return updated, campaign

    def list_promoted_campaigns(self, tenant_id: int) -> list[dict[str, Any]]:
        path = self._promoted_campaigns_path(tenant_id)
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []

    def get_promoted_campaign(self, tenant_id: int, campaign_key: str) -> dict[str, Any] | None:
        for campaign in self.list_promoted_campaigns(tenant_id):
            if campaign.get("key") == campaign_key:
                return campaign
        return None

    def get_health(self, tenant_id: int) -> dict[str, Any]:
        import shutil as _shutil

        return {
            "parser_name": "mineru",
            "parser_command": self.parser_service.command,
            "parser_available": _shutil.which(self.parser_service.command) is not None,
            "parser_extra_args": self.parser_service.extra_args,
            "promotion_enabled": self.promotion_enabled,
            "storage_root": str(self.storage_root),
            "staged_count": len(self.list_staged_items(tenant_id)),
            "promoted_count": len(self.list_promoted_campaigns(tenant_id)),
            "rollback_mode": "staging_only" if not self.promotion_enabled else "promotion_explicit",
        }

    def _normalize_to_staged_item(
        self,
        *,
        tenant_id: int,
        item_id: str,
        source_title: str,
        source_type: str,
        source_owner: str | None,
        license_note: str | None,
        region: str | None,
        units: dict[str, str],
        ingestion_mode: str,
        human_review_required: bool,
        markdown: str,
        json_payload: dict[str, Any],
        parser_metadata,
    ) -> ReferenceIngestionStagedItem:
        text = f"{source_title}\n{markdown}\n{json.dumps(json_payload, ensure_ascii=False)}"
        species_chain = self._normalize_mentions(text, SPECIES_NORMALIZATION)
        feedstocks = self._normalize_mentions(text, FEEDSTOCK_NORMALIZATION)
        key_parameters = self._extract_key_parameters(text)
        observed_outputs = self._extract_observed_outputs(text)
        source_anchor = self._extract_source_anchor(text, source_title)
        evidence_level = self._infer_evidence_level(text)
        campaign_type = self._infer_campaign_type(text)
        references = self._extract_references(text, source_title)
        summary = self._extract_summary(markdown, source_title, species_chain, feedstocks)
        field_count = sum(
            1
            for value in [species_chain, feedstocks, evidence_level, campaign_type, summary, key_parameters, observed_outputs, references]
            if value
        )
        now = datetime.now(UTC)

        return ReferenceIngestionStagedItem(
            id=item_id,
            tenant_id=tenant_id,
            source_title=source_title,
            source_anchor=source_anchor,
            source_type=source_type,
            source_owner=source_owner,
            license_note=license_note,
            region=region,
            units=units,
            ingestion_mode=ingestion_mode,  # type: ignore[arg-type]
            human_review_required=human_review_required,
            species_chain=species_chain,
            feedstocks=feedstocks,
            evidence_level=evidence_level,
            campaign_type=campaign_type,
            summary=summary,
            key_parameters=key_parameters,
            observed_outputs=observed_outputs,
            references=references,
            parser_metadata=parser_metadata.model_copy(update={"extracted_field_count": field_count}),
            status="staged",
            promoted_campaign_key=None,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _normalize_mentions(text: str, mapping: dict[str, str]) -> list[str]:
        lowered = re.sub(r"[-_]+", " ", text.lower())
        values: list[str] = []
        for needle, canonical in mapping.items():
            if needle in lowered and canonical not in values:
                values.append(canonical)
        return values

    @staticmethod
    def _extract_key_parameters(text: str) -> dict[str, Any]:
        parameters: dict[str, Any] = {}
        for key, aliases in PARAMETER_PATTERNS.items():
            for alias in aliases:
                match = re.search(rf"{alias}\s*(?:=|:)\s*(-?\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
                if match:
                    parameters[key] = float(match.group(1))
                    break

        cn_match = re.search(
            r"(?:initial[_\s-]?cn[_\s-]?range|c/n)\s*(?:=|:)?\s*(\d+(?:\.\d+)?)\s*(?:-|to|,)\s*(\d+(?:\.\d+)?)",
            text,
            flags=re.IGNORECASE,
        )
        if cn_match:
            parameters["initial_cn_range"] = [float(cn_match.group(1)), float(cn_match.group(2))]
        return parameters

    @staticmethod
    def _extract_observed_outputs(text: str) -> dict[str, Any]:
        outputs: dict[str, Any] = {}
        for key, aliases in OUTPUT_PATTERNS.items():
            for alias in aliases:
                match = re.search(rf"{alias}\s*(?:=|:)\s*(-?\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
                if match:
                    outputs[key] = float(match.group(1))
                    break

        classification = re.search(r"\bclassification\s*(?:=|:)\s*([A-Z0-9_ -]{3,60})", text, flags=re.IGNORECASE)
        if classification:
            outputs["classification"] = classification.group(1).strip().replace(" ", "_").upper()
        return outputs

    @staticmethod
    def _extract_source_anchor(text: str, source_title: str) -> str:
        match = re.search(r"\bsource[_\s-]?anchor\s*(?:=|:)\s*([^\n\r]{3,160})", text, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            value = re.split(
                r"\s+(?:ser|d[_\s-]?prime|g[_\s-]?prime|best[_\s-]?single[_\s-]?stage|signal[_\s-]?api|reference|doi)\s*(?:=|:)",
                value,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip()
            return value
        for label in ("supplementary note", "methods", "results", "abstract", "table", "figure"):
            if label in text.lower():
                return f"{source_title} / {label.title()}"
        return f"{source_title} / parsed staging"

    @staticmethod
    def _infer_evidence_level(text: str) -> str:
        lowered = text.lower()
        if "manuscript_core" in lowered or "core validation" in lowered:
            return "manuscript_core"
        if "manuscript_mechanistic" in lowered or "portability" in lowered:
            return "manuscript_mechanistic"
        if "manuscript_analytical" in lowered or "heavy metal" in lowered or "analytical" in lowered:
            return "manuscript_analytical"
        if "pilot" in lowered:
            return "manuscript_pilot"
        return "manuscript_campaign"

    @staticmethod
    def _infer_campaign_type(text: str) -> str:
        lowered = text.lower()
        if "core validation" in lowered:
            return "core_validation"
        if "portability" in lowered:
            return "portability_audit"
        if "heavy metal" in lowered or "analytical" in lowered:
            return "safety_context"
        if "compatibility" in lowered:
            return "compatibility_screen"
        if "sludge" in lowered or "risk" in lowered:
            return "risk_control_screen"
        return "document_ingestion"

    @staticmethod
    def _extract_references(text: str, source_title: str) -> list[str]:
        references = [f"Parsed source: {source_title}"]
        for match in re.findall(r"\bdoi\s*[: ]\s*([10]\.[^\s,;]+/[^\s,;]+)", text, flags=re.IGNORECASE):
            ref = f"DOI:{match}"
            if ref not in references:
                references.append(ref)
        for line in text.splitlines():
            if line.lower().startswith(("reference:", "references:")):
                value = line.split(":", 1)[1].strip()
                if value and value not in references:
                    references.append(value)
        return references[:8]

    @staticmethod
    def _extract_summary(markdown: str, source_title: str, species_chain: list[str], feedstocks: list[str]) -> str:
        for line in markdown.splitlines():
            stripped = line.strip().strip("# ")
            if len(stripped) >= 20 and not stripped.lower().startswith(("source_anchor", "reference:")):
                return stripped[:500]
        parts = [source_title]
        if species_chain:
            parts.append(f"species={','.join(species_chain)}")
        if feedstocks:
            parts.append(f"feedstocks={','.join(feedstocks)}")
        return " / ".join(parts)

    def _staged_item_to_campaign(
        self,
        staged: ReferenceIngestionStagedItem,
        *,
        notes: str | None,
    ) -> ReferenceIngestionCampaignCandidate:
        key_base = self._slugify(staged.source_title) or staged.id
        key = f"staged_{key_base}_{staged.id[-6:]}"
        references = list(staged.references)
        if notes:
            references.append(f"Promotion note: {notes}")
        return ReferenceIngestionCampaignCandidate(
            key=key,
            title=staged.source_title,
            species_chain=staged.species_chain,
            feedstocks=staged.feedstocks,
            campaign_type=staged.campaign_type,
            evidence_level=staged.evidence_level,
            summary=staged.summary,
            key_parameters=staged.key_parameters,
            observed_outputs=staged.observed_outputs,
            source_anchor=staged.source_anchor,
            references=references,
            staging_meta={
                "staged_item_id": staged.id,
                "parser": staged.parser_metadata.parser_name,
                "execution_mode": staged.parser_metadata.execution_mode,
                "source_owner": staged.source_owner,
                "license_note": staged.license_note,
                "region": staged.region,
                "units": staged.units,
                "ingestion_mode": staged.ingestion_mode,
                "human_review_required": staged.human_review_required,
                "promoted_at": datetime.now(UTC).isoformat(),
                "promotion_status": "promoted",
            },
        )

    @staticmethod
    def _validate_promotable(staged: ReferenceIngestionStagedItem) -> None:
        if staged.status == "failed":
            raise ValueError("staged_item_failed")
        if not staged.source_anchor.strip():
            raise ValueError("source_anchor_required")
        if staged.parser_metadata.extracted_field_count < 5:
            raise ValueError("at_least_five_bos_fields_required")
        if not staged.species_chain:
            raise ValueError("species_chain_required")
        if not staged.feedstocks:
            raise ValueError("feedstocks_required")

    def _write_staged_item(self, item: ReferenceIngestionStagedItem) -> None:
        path = self._staged_item_path(item.tenant_id, item.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item.model_dump_json(indent=2), encoding="utf-8")

    def _tenant_root(self, tenant_id: int) -> Path:
        return self.storage_root / f"tenant-{tenant_id}"

    def _staged_item_path(self, tenant_id: int, item_id: str) -> Path:
        return self._tenant_root(tenant_id) / "staging" / f"{item_id}.json"

    def _promoted_campaigns_path(self, tenant_id: int) -> Path:
        return self._tenant_root(tenant_id) / "promoted" / "campaigns.json"

    @staticmethod
    def _safe_filename(filename: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
        return cleaned or "source.pdf"

    @staticmethod
    def _slugify(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:80]

    def reset_tenant_storage(self, tenant_id: int) -> None:
        tenant_root = self._tenant_root(tenant_id)
        if tenant_root.exists():
            shutil.rmtree(tenant_root)


reference_ingestion_service = ReferenceIngestionService()
