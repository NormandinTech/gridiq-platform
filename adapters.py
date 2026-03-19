"""
GridIQ Platform — Main Application
FastAPI app with CORS, middleware, startup/shutdown hooks, and all routes mounted.
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from backend.api.routes import router
from backend.core.config import settings
from backend.core.event_bus import EventType, get_event_bus

# ── Logging setup ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("gridiq")


# ── Lifespan (startup + shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info(f"  {settings.app_name} v{settings.app_version}")
    logger.info(f"  Environment : {settings.app_env}")
    logger.info(f"  API prefix  : {settings.api_prefix}")
    logger.info("=" * 60)

    # Start telemetry simulator in dev mode
    if settings.simulate_telemetry and settings.is_development:
        import asyncio
        from scripts.simulate_telemetry import TelemetrySimulator
        sim = TelemetrySimulator()
        task = asyncio.create_task(sim.run())
        logger.info("[Simulator] Telemetry simulation started")

    yield

    logger.info("GridIQ shutting down...")


# ── App factory ────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "GridIQ Platform API — AI-driven grid orchestration, digital twins, "
            "renewable integration, and OT/IT cybersecurity for electric utilities."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # ── Routes ───────────────────────────────────────────────────────────────
    app.include_router(router, prefix=settings.api_prefix)

    # Vegetation module
    from backend.vegetation.routes import veg_router
    app.include_router(veg_router, prefix=settings.api_prefix)

    # Asset intelligence module
    from backend.assets.routes import asset_router
    app.include_router(asset_router, prefix=settings.api_prefix)

    # Sensor management module
    from backend.sensors.routes import sensor_router
    app.include_router(sensor_router, prefix=settings.api_prefix)

    # SaaS modules
    from backend.auth.routes import auth_router
    app.include_router(auth_router, prefix=settings.api_prefix)

    from backend.billing.routes import billing_router
    app.include_router(billing_router, prefix=settings.api_prefix)

    from backend.onboarding.routes import onboarding_router
    app.include_router(onboarding_router, prefix=settings.api_prefix)

    # ── Root endpoint ────────────────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "product": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "api": settings.api_prefix,
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )
