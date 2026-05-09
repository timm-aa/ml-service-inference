from __future__ import annotations

from fastapi import FastAPI
from starlette_prometheus import PrometheusMiddleware, metrics

from app.api.routes import admin_loyalty, analytics, auth, billing, models_ml, predictions, users

app = FastAPI(
    title="ML Prediction Service",
    description="Asynchronous sklearn inference with credits billing and loyalty tiers.",
    version="1.0.0",
    openapi_tags=[
        {"name": "auth", "description": "Registration and JWT"},
        {"name": "users", "description": "Profile"},
        {"name": "models", "description": "Upload scikit-learn models"},
        {"name": "predictions", "description": "Async prediction jobs"},
        {"name": "billing", "description": "Credits balance and payment stub"},
        {"name": "analytics", "description": "Usage statistics"},
        {"name": "admin", "description": "Admin loyalty tier configuration"},
    ],
)

app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(models_ml.router)
app.include_router(predictions.router)
app.include_router(billing.router)
app.include_router(analytics.router)
app.include_router(admin_loyalty.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
