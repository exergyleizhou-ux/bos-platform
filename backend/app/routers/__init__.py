"""
BOS Pipeline v9.0 routers package.

Registers all API routers with the FastAPI application.

Phase 0.5 (2026-05-16): 13 operational routers moved to ``_legacy/`` and
mounted with ``deprecated=True``. URL prefixes are unchanged so existing
frontend callers keep working; only OpenAPI metadata is affected.
"""

from fastapi import APIRouter

from app.routers import (
    anomaly,
    assistant,
    audit,
    auth,
    batches,
    bayesian,
    bos,
    bos_kernels,
    calculations,
    calibration,
    code,
    compliance,
    controller,
    dashboard,
    did,
    energy,
    evidence,
    export,
    feature_flags,
    final_actions,
    feedstocks,
    flight,
    forecast,
    ghg,
    health,
    lca,
    mass_balance,
    mc,
    release_packets,
    risk,
    relay,
    sensitivity,
    ser,
    sfi,
    simulation,
    simulation_lab,
    species,
    sustainability_kernel,
    tea,
    twin,
    water,
    websocket_router,
)
from app.routers._legacy import (
    admin,
    api_keys,
    billing,
    external_sources,
    gdpr,
    governance,
    manuscript_references,
    media,
    reference_ingestion,
    tenants,
    users,
    webhooks,
    wechat,
)

api_router = APIRouter()

# Public and infrastructure
api_router.include_router(health.router, prefix="/health", tags=["Health"])

# Authentication
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Core CRUD
api_router.include_router(
    users.router, prefix="/users", tags=["legacy-users"], deprecated=True,
)
api_router.include_router(
    tenants.router, prefix="/tenants", tags=["legacy-tenants"], deprecated=True,
)
api_router.include_router(batches.router, prefix="/batches", tags=["Batches"])
api_router.include_router(calculations.router, prefix="/calculations", tags=["Calculations"])
api_router.include_router(bos.router, tags=["BOS"])
api_router.include_router(assistant.router, tags=["Assistant"])
api_router.include_router(evidence.router, tags=["Evidence"])
api_router.include_router(release_packets.router, tags=["Release Packets"])
api_router.include_router(final_actions.router, tags=["Final Actions"])
api_router.include_router(
    governance.router, tags=["legacy-governance"], deprecated=True,
)
api_router.include_router(compliance.router, tags=["Compliance"])
api_router.include_router(sustainability_kernel.router, tags=["Sustainability"])
api_router.include_router(bos_kernels.router, tags=["BOS Kernels"])
api_router.include_router(code.router)

# Engine endpoints
api_router.include_router(ser.router, prefix="/ser", tags=["SER Engine"])
api_router.include_router(simulation.router, prefix="/simulation", tags=["Monte Carlo"])
api_router.include_router(ghg.router, prefix="/ghg", tags=["GHG Balance"])
api_router.include_router(water.router, prefix="/water", tags=["Water Footprint"])
api_router.include_router(energy.router, prefix="/energy", tags=["Energy Balance"])
api_router.include_router(tea.router, prefix="/tea", tags=["TEA"])
api_router.include_router(lca.router, prefix="/lca", tags=["LCA"])
api_router.include_router(risk.router, prefix="/risk", tags=["Risk Assessment"])
api_router.include_router(flight.router, prefix="/flight-envelope", tags=["Flight Envelope"])
api_router.include_router(sfi.router, prefix="/sfi", tags=["SFI (Phase A)"])
api_router.include_router(relay.router, prefix="/relay", tags=["Relay (Phase A)"])
api_router.include_router(mc.router, prefix="/mc", tags=["MC (Phase A)"])
api_router.include_router(calibration.router, prefix="/calibration", tags=["GP Calibration"])
api_router.include_router(anomaly.router, prefix="/anomaly", tags=["Anomaly Detection"])
api_router.include_router(sensitivity.router, prefix="/sensitivity", tags=["Sensitivity Analysis"])
api_router.include_router(did.router, prefix="/did", tags=["Causal Inference"])
api_router.include_router(bayesian.router, prefix="/bayesian", tags=["Bayesian A/B"])
api_router.include_router(forecast.router, prefix="/forecast", tags=["Forecasting"])
api_router.include_router(mass_balance.router, prefix="/mass-balance", tags=["Mass Balance"])
api_router.include_router(controller.router, prefix="/controller", tags=["PID Controller"])
api_router.include_router(species.router, prefix="/species", tags=["Species Database"])
api_router.include_router(feedstocks.router, prefix="/feedstocks", tags=["Feedstock Database"])
api_router.include_router(
    manuscript_references.router,
    prefix="/references",
    tags=["legacy-manuscript-references"],
    deprecated=True,
)
api_router.include_router(
    reference_ingestion.router,
    prefix="/references/ingestion",
    tags=["legacy-reference-ingestion"],
    deprecated=True,
)
api_router.include_router(
    external_sources.router,
    prefix="/external-sources",
    tags=["legacy-external-sources"],
    deprecated=True,
)
api_router.include_router(simulation_lab.router, prefix="/bos/simulation-lab", tags=["BOS Simulation Lab"])

# Digital twin
api_router.include_router(twin.router, prefix="/twin", tags=["Digital Twin"])
api_router.include_router(twin.router, prefix="/twins", tags=["Digital Twin"])

# Platform management
api_router.include_router(
    admin.router, prefix="/admin", tags=["legacy-admin"], deprecated=True,
)
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(export.router, prefix="/export", tags=["Export"])
api_router.include_router(
    billing.router, prefix="/billing", tags=["legacy-billing"], deprecated=True,
)
api_router.include_router(
    webhooks.router, prefix="/webhooks", tags=["legacy-webhooks"], deprecated=True,
)
api_router.include_router(
    api_keys.router, prefix="/api-keys", tags=["legacy-api-keys"], deprecated=True,
)
api_router.include_router(
    gdpr.router, prefix="/gdpr", tags=["legacy-gdpr"], deprecated=True,
)
api_router.include_router(audit.router, prefix="/audit", tags=["Audit Log"])
api_router.include_router(feature_flags.router, prefix="/feature-flags", tags=["Feature Flags"])
api_router.include_router(media.router, tags=["legacy-media"], deprecated=True)
api_router.include_router(wechat.router, tags=["legacy-wechat"], deprecated=True)

# WebSocket
api_router.include_router(websocket_router.router, tags=["WebSocket"])
