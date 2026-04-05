"""
BOS Pipeline v9.0 �� Routers Package

Registers all API routers with the FastAPI application.
"""

from fastapi import APIRouter

from app.routers import (
    admin,
    anomaly,
    api_keys,
    audit,
    auth,
    batches,
    bayesian,
    billing,
    calibration,
    calculations,
    controller,
    dashboard,
    did,
    energy,
    export,
    feature_flags,
    flight,
    forecast,
    gdpr,
    ghg,
    health,
    lca,
    mass_balance,
    risk,
    sensitivity,
    ser,
    simulation,
    species,
    tea,
    tenants,
    twin,
    users,
    water,
    webhooks,
    websocket_router,
)

api_router = APIRouter()

# ���� Public / infrastructure ����
api_router.include_router(health.router, prefix="/health", tags=["Health"])

# ���� Auth ����
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# ���� Core CRUD ����
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["Tenants"])
api_router.include_router(batches.router, prefix="/batches", tags=["Batches"])
api_router.include_router(calculations.router, prefix="/calculations", tags=["Calculations"])

# ���� Engine endpoints ����
api_router.include_router(ser.router, prefix="/ser", tags=["SER Engine"])
api_router.include_router(simulation.router, prefix="/simulation", tags=["Monte Carlo"])
api_router.include_router(ghg.router, prefix="/ghg", tags=["GHG Balance"])
api_router.include_router(water.router, prefix="/water", tags=["Water Footprint"])
api_router.include_router(energy.router, prefix="/energy", tags=["Energy Balance"])
api_router.include_router(tea.router, prefix="/tea", tags=["TEA"])
api_router.include_router(lca.router, prefix="/lca", tags=["LCA"])
api_router.include_router(risk.router, prefix="/risk", tags=["Risk Assessment"])
api_router.include_router(flight.router, prefix="/flight-envelope", tags=["Flight Envelope"])
api_router.include_router(calibration.router, prefix="/calibration", tags=["GP Calibration"])
api_router.include_router(anomaly.router, prefix="/anomaly", tags=["Anomaly Detection"])
api_router.include_router(sensitivity.router, prefix="/sensitivity", tags=["Sensitivity Analysis"])
api_router.include_router(did.router, prefix="/did", tags=["Causal Inference"])
api_router.include_router(bayesian.router, prefix="/bayesian", tags=["Bayesian A/B"])
api_router.include_router(forecast.router, prefix="/forecast", tags=["Forecasting"])
api_router.include_router(mass_balance.router, prefix="/mass-balance", tags=["Mass Balance"])
api_router.include_router(controller.router, prefix="/controller", tags=["PID Controller"])
api_router.include_router(species.router, prefix="/species", tags=["Species Database"])

# ���� Digital twin ����
api_router.include_router(twin.router, prefix="/twin", tags=["Digital Twin"])
api_router.include_router(twin.router, prefix="/twins", tags=["Digital Twin"])

# ���� Platform management ����
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(export.router, prefix="/export", tags=["Export"])
api_router.include_router(billing.router, prefix="/billing", tags=["Billing"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["API Keys"])
api_router.include_router(gdpr.router, prefix="/gdpr", tags=["GDPR"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit Log"])
api_router.include_router(feature_flags.router, prefix="/feature-flags", tags=["Feature Flags"])

# ���� WebSocket ����
api_router.include_router(websocket_router.router, tags=["WebSocket"])
