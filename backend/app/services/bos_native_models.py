"""
BOS native model catalog for BSF and insect solid-waste operations.

This module turns frontier open models into first-class BOS capabilities:
- vision-led larval stage recognition
- insect instance segmentation
- multi-species detection and biosecurity
- time-series forecasting for decomposition and sensor traces
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from app.models import Batch, SignalBatch


CATALOG_VERIFIED_ON = date(2026, 4, 15).isoformat()


@dataclass(slots=True)
class NativeModelSource:
    label: str
    url: str
    provider: str


@dataclass(slots=True)
class NativeModelCapability:
    key: str
    name: str
    family: str
    frontier_window: str
    modality: str
    maturity: str
    primary_fit: str
    dialectical_role: str
    native_outputs: list[str]
    bos_touchpoints: list[str]
    operational_triggers: list[str]
    recommended_deployment: list[str]
    sources: list[NativeModelSource]


@dataclass(slots=True)
class NativeModelComposition:
    key: str
    title: str
    objective: str
    model_keys: list[str]
    why_it_matters: str
    native_outputs: list[str]
    bos_agents: list[str]


@dataclass(slots=True)
class NativeModelRecommendation:
    key: str
    title: str
    fit: str
    rationale: str
    model_keys: list[str]
    native_outputs: list[str]


def _catalog_models() -> list[NativeModelCapability]:
    return [
        NativeModelCapability(
            key="yolo11_dsconv",
            name="YOLO11-DSConv",
            family="BSF stage vision",
            frontier_window="2025",
            modality="vision",
            maturity="field-ready",
            primary_fit="BSF larval stage classification and harvest timing",
            dialectical_role="Fast discriminative detector for stage, density, and harvest-readiness signals.",
            native_outputs=[
                "larval_stage_class",
                "stage_confidence",
                "tray_density_index",
                "harvest_readiness_hint",
            ],
            bos_touchpoints=[
                "camera_ingest",
                "signal_compiler",
                "feed_agent",
                "harvest_agent",
            ],
            operational_triggers=[
                "需要判断小幼虫/大幼虫/预蛹",
                "需要边缘设备实时识别",
                "需要把虫态直接联动到喂料和收割",
            ],
            recommended_deployment=[
                "edge_gpu",
                "industrial_camera",
                "mobile_quality_check",
            ],
            sources=[
                NativeModelSource(
                    label="Zenodo weights + code",
                    url="https://zenodo.org/records/15044013",
                    provider="Zenodo",
                ),
                NativeModelSource(
                    label="Zenodo server app",
                    url="https://zenodo.org/records/15044077",
                    provider="Zenodo",
                ),
                NativeModelSource(
                    label="Zenodo mobile app",
                    url="https://zenodo.org/records/15044108",
                    provider="Zenodo",
                ),
            ],
        ),
        NativeModelCapability(
            key="insectsam",
            name="InsectSAM",
            family="Insect segmentation",
            frontier_window="2025",
            modality="vision",
            maturity="exploration-to-production bridge",
            primary_fit="Insect/body-waste segmentation in cluttered solid-waste scenes",
            dialectical_role="Complements detection by turning crowded insect heaps into measurable masks and coverage ratios.",
            native_outputs=[
                "active_body_area_ratio",
                "residual_waste_area_ratio",
                "instance_masks",
                "activity_heatmap",
            ],
            bos_touchpoints=[
                "camera_ingest",
                "decomposition_estimator",
                "vision_quality_agent",
            ],
            operational_triggers=[
                "需要区分虫体和垃圾背景",
                "需要估算活性面积或残渣面积",
                "画面遮挡复杂、单纯检测不够稳",
            ],
            recommended_deployment=[
                "gpu_batch_inference",
                "nightly_quality_pass",
                "label_assist_workstation",
            ],
            sources=[
                NativeModelSource(
                    label="Hugging Face model card",
                    url="https://huggingface.co/martintomov/InsectSAM",
                    provider="Hugging Face",
                )
            ],
        ),
        NativeModelCapability(
            key="insecta",
            name="Genius-Society/insecta",
            family="Multi-species insect detection",
            frontier_window="2026",
            modality="vision",
            maturity="expansion-ready",
            primary_fit="Mixed-insect monitoring and invasive-species alerting",
            dialectical_role="Extends BOS from BSF specialization to ecosystem and biosecurity awareness.",
            native_outputs=[
                "species_candidates",
                "species_confidence",
                "intrusion_alert",
                "mixed_colony_flag",
            ],
            bos_touchpoints=[
                "biosecurity_agent",
                "camera_ingest",
                "anomaly_engine",
            ],
            operational_triggers=[
                "需要监控非BSF虫种入侵",
                "需要混养或多物种监控",
                "需要生物多样性观察能力",
            ],
            recommended_deployment=[
                "cloud_gpu_review",
                "biosecurity_watchtower",
            ],
            sources=[
                NativeModelSource(
                    label="Hugging Face model card",
                    url="https://huggingface.co/Genius-Society/insecta",
                    provider="Hugging Face",
                )
            ],
        ),
        NativeModelCapability(
            key="timer_s1",
            name="Timer-S1",
            family="Foundation time-series forecasting",
            frontier_window="2025",
            modality="time-series",
            maturity="cloud-scale",
            primary_fit="Zero-shot forecasting for decomposition, climate, and gas/sensor trajectories",
            dialectical_role="Heavyweight forecaster for cross-sensor structure and 24-72h forward planning.",
            native_outputs=[
                "decomposition_rate_forecast",
                "sensor_forecast_24h",
                "sensor_forecast_72h",
                "growth_curve_projection",
            ],
            bos_touchpoints=[
                "forecast_engine",
                "digital_twin",
                "feed_agent",
                "environment_agent",
            ],
            operational_triggers=[
                "需要跨传感器零样本预测",
                "需要未来24-72小时分解/生长趋势",
                "需要更强的调度前瞻性",
            ],
            recommended_deployment=[
                "cloud_inference",
                "central_optimizer",
            ],
            sources=[
                NativeModelSource(
                    label="Hugging Face model card",
                    url="https://huggingface.co/bytedance-research/Timer-S1",
                    provider="Hugging Face",
                )
            ],
        ),
        NativeModelCapability(
            key="chronos_bolt",
            name="Chronos-Bolt",
            family="Lightweight time-series forecasting",
            frontier_window="2025-2026",
            modality="time-series",
            maturity="edge-ready",
            primary_fit="Fast, lighter fallback forecasting near the tray or gateway",
            dialectical_role="Acts as the efficient edge counterpart to Timer-S1 for continuous local control loops.",
            native_outputs=[
                "edge_decomposition_forecast",
                "edge_growth_forecast",
                "feed_setpoint_delta",
                "climate_setpoint_delta",
            ],
            bos_touchpoints=[
                "forecast_engine",
                "controller_engine",
                "feed_optimizer",
            ],
            operational_triggers=[
                "边缘侧需要更轻的时序推理",
                "需要作为Timer-S1的本地后备",
                "需要快速回路调参",
            ],
            recommended_deployment=[
                "edge_gateway",
                "local_controller",
            ],
            sources=[
                NativeModelSource(
                    label="Hugging Face model card",
                    url="https://huggingface.co/autogluon/chronos-bolt-small",
                    provider="Hugging Face",
                )
            ],
        ),
    ]


def _catalog_compositions() -> list[NativeModelComposition]:
    return [
        NativeModelComposition(
            key="vision_forecast_closed_loop",
            title="图像 + 预测闭环",
            objective="让 BOS 同时看见虫态、残渣和未来趋势，再反推喂料与环境动作。",
            model_keys=["yolo11_dsconv", "insectsam", "timer_s1", "chronos_bolt"],
            why_it_matters="YOLO11-DSConv给出阶段和密度，InsectSAM给出活性/残渣比例，Timer-S1负责中期预测，Chronos-Bolt负责边缘快速回路。",
            native_outputs=[
                "larval_stage_class",
                "active_body_area_ratio",
                "decomposition_rate_forecast",
                "feed_setpoint_delta",
            ],
            bos_agents=[
                "signal_compiler",
                "feed_agent",
                "environment_agent",
                "harvest_agent",
            ],
        ),
        NativeModelComposition(
            key="multispecies_biosecurity",
            title="多虫种监测 + 生物安防",
            objective="在BSF主场景之外，识别混养、杂虫入侵和异常生态事件。",
            model_keys=["insecta", "insectsam"],
            why_it_matters="insecta提供多物种识别，InsectSAM补足复杂背景下的区域和实例边界。",
            native_outputs=[
                "species_candidates",
                "intrusion_alert",
                "instance_masks",
            ],
            bos_agents=[
                "biosecurity_agent",
                "anomaly_engine",
            ],
        ),
        NativeModelComposition(
            key="bsf_growth_harvest_loop",
            title="BSF 生长-收割闭环",
            objective="围绕黑水虻单场景优先把阶段识别、增长预测、收割判断打通。",
            model_keys=["yolo11_dsconv", "timer_s1", "chronos_bolt"],
            why_it_matters="这是最短路径收益组合，先把虫态识别和未来生长/分解曲线接进调度与收割。",
            native_outputs=[
                "stage_confidence",
                "growth_curve_projection",
                "harvest_readiness_hint",
            ],
            bos_agents=[
                "signal_compiler",
                "harvest_agent",
                "feed_agent",
            ],
        ),
    ]


def _fit_label(*, high: bool) -> str:
    return "high" if high else "medium"


def _build_batch_recommendations(
    *,
    batch: Batch | None,
    signal_batch: SignalBatch | None,
) -> list[NativeModelRecommendation]:
    if batch is None:
        return [
            NativeModelRecommendation(
                key="vision_forecast_closed_loop",
                title="优先落地图像 + 预测闭环",
                fit="high",
                rationale="这是 BOS 在 BSF 固废场景里收益最高的起步组合，覆盖虫态识别、残渣估计、24-72h 分解预测与调度。",
                model_keys=["yolo11_dsconv", "insectsam", "timer_s1", "chronos_bolt"],
                native_outputs=[
                    "larval_stage_class",
                    "active_body_area_ratio",
                    "decomposition_rate_forecast",
                ],
            )
        ]

    species_upper = (batch.species or "").upper()
    is_bsf = "BSF" in species_upper or "BLACK SOLDIER" in species_upper
    has_sensor_context = any(
        value is not None
        for value in (batch.temperature, batch.moisture, batch.feed_rate, batch.density)
    )
    evidence_sparse = sum(
        value is not None
        for value in (
            batch.dm_in,
            batch.dm_out,
            batch.n_in,
            batch.n_larvae,
            batch.n_frass,
            batch.temperature,
            batch.moisture,
        )
    ) < 5
    missing_signal = signal_batch is None

    recommendations = [
        NativeModelRecommendation(
            key="bsf_growth_harvest_loop",
            title="BSF 生长与收割主回路",
            fit=_fit_label(high=is_bsf),
            rationale=(
                "当前批次是 BSF 主场景，YOLO11-DSConv 应作为虫态主引擎，联动 Timer-S1 / Chronos-Bolt 做收割与喂料前瞻。"
                if is_bsf
                else "即使不是纯 BSF 批次，这组能力也可提供基础阶段识别和增长预测。"
            ),
            model_keys=["yolo11_dsconv", "timer_s1", "chronos_bolt"],
            native_outputs=[
                "larval_stage_class",
                "growth_curve_projection",
                "harvest_readiness_hint",
            ],
        ),
        NativeModelRecommendation(
            key="vision_forecast_closed_loop",
            title="分解率与残渣闭环",
            fit=_fit_label(high=is_bsf and (has_sensor_context or missing_signal or evidence_sparse)),
            rationale=(
                "当前批次已有环境/工艺观测，但证据仍然偏稀，建议用 InsectSAM + 时序模型把视觉残渣和传感器趋势并到同一调度闭环。"
                if has_sensor_context or evidence_sparse
                else "如果后续补上相机和传感器，这会成为 BOS 最核心的闭环。"
            ),
            model_keys=["yolo11_dsconv", "insectsam", "timer_s1", "chronos_bolt"],
            native_outputs=[
                "active_body_area_ratio",
                "residual_waste_area_ratio",
                "decomposition_rate_forecast",
            ],
        ),
        NativeModelRecommendation(
            key="multispecies_biosecurity",
            title="混养监控与入侵预警",
            fit=_fit_label(high=not is_bsf),
            rationale=(
                "当前物种标签不是典型 BSF，建议尽早引入 insecta 做多虫种检测和生物安防。"
                if not is_bsf
                else "如果后续进入混养或外来虫风险更高的站点，可把 insecta 作为安防层补入。"
            ),
            model_keys=["insecta", "insectsam"],
            native_outputs=[
                "species_candidates",
                "intrusion_alert",
            ],
        ),
    ]

    return recommendations


def build_native_model_catalog(
    *,
    batch: Batch | None = None,
    signal_batch: SignalBatch | None = None,
) -> dict[str, Any]:
    models = _catalog_models()
    compositions = _catalog_compositions()
    recommendations = _build_batch_recommendations(batch=batch, signal_batch=signal_batch)

    rollout = [
        {
            "phase": "P1",
            "title": "虫态识别原生化",
            "objective": "先把 YOLO11-DSConv 接进相机链路，产出阶段、密度、收割提示。",
        },
        {
            "phase": "P2",
            "title": "分割与残渣估计",
            "objective": "引入 InsectSAM，把虫体活性面积和垃圾残留率送入分解估计层。",
        },
        {
            "phase": "P3",
            "title": "时序预测双保险",
            "objective": "云端用 Timer-S1，边缘用 Chronos-Bolt，形成24-72h预测与快速后备。",
        },
        {
            "phase": "P4",
            "title": "多虫种与生物安防",
            "objective": "在混养或入侵风险更高的站点接入 insecta。",
        },
    ]

    return {
        "catalog_version": "BOS-NATIVE-2026.04",
        "verified_on": CATALOG_VERIFIED_ON,
        "models": [
            {
                **asdict(model),
                "sources": [asdict(source) for source in model.sources],
            }
            for model in models
        ],
        "compositions": [asdict(item) for item in compositions],
        "recommendations": [asdict(item) for item in recommendations],
        "rollout": rollout,
    }


def build_native_model_embedding(
    *,
    batch: Batch | None = None,
    signal_batch: SignalBatch | None = None,
) -> dict[str, Any]:
    catalog = build_native_model_catalog(batch=batch, signal_batch=signal_batch)
    primary_recommendation = catalog["recommendations"][0] if catalog["recommendations"] else None
    return {
        "catalog_version": catalog["catalog_version"],
        "verified_on": catalog["verified_on"],
        "primary_recommendation": primary_recommendation,
        "recommendations": catalog["recommendations"],
        "compositions": catalog["compositions"],
        "model_keys": [item["key"] for item in catalog["models"]],
    }
