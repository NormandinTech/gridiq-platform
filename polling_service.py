"""
GridIQ SaaS — Onboarding API Routes
"""
from __future__ import annotations
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.auth.routes import get_current_user, TokenPayload
from backend.onboarding.service import onboarding_service

onboarding_router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


class GridProfileRequest(BaseModel):
    utility_type: str = "municipal"
    service_territory: str = ""
    state: str = ""
    estimated_assets: int = 100
    voltage_levels: List[str] = ["69kV"]
    has_solar: bool = False
    has_wind: bool = False
    has_hydro: bool = False
    has_bess: bool = False
    primary_scada: str = ""
    pain_points: List[str] = []


class ConnectionRequest(BaseModel):
    protocol: str = "modbus_tcp"
    host: str = ""
    port: int = 502
    username: str = ""
    password: str = ""
    database: str = ""
    site_name: str = ""


class AssetConfirmRequest(BaseModel):
    selected_tags: List[str]


@onboarding_router.get("/progress")
async def get_progress(current: TokenPayload = Depends(get_current_user)):
    return onboarding_service.get_progress(current.tenant_id)


@onboarding_router.post("/step1-profile")
async def save_grid_profile(
    req: GridProfileRequest,
    current: TokenPayload = Depends(get_current_user),
):
    return onboarding_service.save_grid_profile(current.tenant_id, req.dict())


@onboarding_router.post("/step2-connect")
async def test_connection(
    req: ConnectionRequest,
    current: TokenPayload = Depends(get_current_user),
):
    return await onboarding_service.test_connection(current.tenant_id, req.dict())


@onboarding_router.post("/step3-discover")
async def discover_assets(current: TokenPayload = Depends(get_current_user)):
    return await onboarding_service.discover_assets(current.tenant_id)


@onboarding_router.post("/step3-confirm")
async def confirm_assets(
    req: AssetConfirmRequest,
    current: TokenPayload = Depends(get_current_user),
):
    return onboarding_service.confirm_asset_import(current.tenant_id, req.selected_tags)


@onboarding_router.get("/step4-review")
async def get_review(current: TokenPayload = Depends(get_current_user)):
    return onboarding_service.get_review_summary(current.tenant_id)


@onboarding_router.post("/complete")
async def complete_onboarding(current: TokenPayload = Depends(get_current_user)):
    return onboarding_service.complete_onboarding(current.tenant_id)
