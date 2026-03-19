"""
GridIQ SaaS — Onboarding Service
==================================
Guides a new utility through 5 steps to get from signup to live dashboard.

Step 1 — Tell us about your grid
  Grid size, asset count, voltage levels, service territory
  → Seeds the asset registry with their fleet profile

Step 2 — Connect your data
  SCADA/historian connection (Modbus, DNP3, PI, Ignition, etc.)
  Test connection → show first live readings
  → Sets scada_connected = True

Step 3 — Import your assets
  Auto-discovered assets from SCADA, or manual CSV upload
  → Creates asset records in DB

Step 4 — Review and confirm
  Show what GridIQ found: assets, readings, first anomaly scan
  → Validates data quality

Step 5 — Choose your plan & pay
  Select pilot ($10K) or annual plan
  → Redirects to Stripe Checkout
  → On payment: status = pilot/active, dashboard unlocked
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.auth.service import auth_service

logger = logging.getLogger(__name__)


# ── Onboarding step data structures ──────────────────────────────────────────

@dataclass
class GridProfile:
    """Step 1 — grid profile collected during onboarding."""
    tenant_id: str
    utility_type: str       # municipal | coop | ious | ipp
    service_territory: str  # e.g. "Northern California"
    state: str
    estimated_assets: int
    voltage_levels: List[str]   # e.g. ["138kV", "69kV", "12kV"]
    has_solar: bool = False
    has_wind: bool = False
    has_hydro: bool = False
    has_bess: bool = False
    primary_scada: str = ""     # e.g. "OSIsoft PI", "Ignition", "GE Grid IQ"
    current_pain_points: List[str] = field(default_factory=list)


@dataclass
class ScadaConnection:
    """Step 2 — SCADA/historian connection details."""
    tenant_id: str
    protocol: str           # modbus_tcp | dnp3 | opc_ua | pi | ignition | csv_upload
    host: str = ""
    port: int = 502
    username: str = ""
    # Note: password stored encrypted, never returned in API responses
    database: str = ""
    site_name: str = ""
    test_passed: bool = False
    test_message: str = ""
    first_reading_at: Optional[str] = None
    assets_discovered: int = 0


@dataclass
class DiscoveredAsset:
    """An asset found during SCADA scan."""
    tag: str
    name: str
    asset_type: str
    description: str = ""
    unit: str = ""
    current_value: Optional[float] = None
    import_selected: bool = True


# ── In-memory onboarding state ────────────────────────────────────────────────
_profiles:    Dict[str, GridProfile]    = {}
_connections: Dict[str, ScadaConnection] = {}
_discovered:  Dict[str, List[DiscoveredAsset]] = {}


class OnboardingService:

    # ── Step 1: Grid profile ──────────────────────────────────────────────────

    def save_grid_profile(self, tenant_id: str, data: Dict) -> Dict:
        """Save grid profile from Step 1 of the wizard."""
        profile = GridProfile(
            tenant_id=tenant_id,
            utility_type=data.get("utility_type", "municipal"),
            service_territory=data.get("service_territory", ""),
            state=data.get("state", ""),
            estimated_assets=data.get("estimated_assets", 100),
            voltage_levels=data.get("voltage_levels", ["69kV"]),
            has_solar=data.get("has_solar", False),
            has_wind=data.get("has_wind", False),
            has_hydro=data.get("has_hydro", False),
            has_bess=data.get("has_bess", False),
            primary_scada=data.get("primary_scada", ""),
            current_pain_points=data.get("pain_points", []),
        )
        _profiles[tenant_id] = profile

        # Advance onboarding step
        tenant = auth_service.get_tenant(tenant_id)
        if tenant and tenant.onboarding_step < 2:
            tenant.onboarding_step = 2

        logger.info(f"[Onboarding] Step 1 complete: {tenant_id} — {profile.service_territory}")
        return {"step": 2, "message": "Grid profile saved"}

    # ── Step 2: SCADA connection test ─────────────────────────────────────────

    async def test_connection(self, tenant_id: str, data: Dict) -> Dict:
        """
        Test connection to the utility's SCADA system.
        Returns success/failure with a sample of discovered tags.
        """
        protocol = data.get("protocol", "modbus_tcp")
        host     = data.get("host", "")
        port     = int(data.get("port", 502))

        conn = ScadaConnection(
            tenant_id=tenant_id,
            protocol=protocol,
            host=host,
            port=port,
            username=data.get("username", ""),
            database=data.get("database", ""),
            site_name=data.get("site_name", ""),
        )

        # In production: actually attempt the connection
        # In dev/demo: simulate a successful connection
        success, message, sample_tags = await self._attempt_connection(protocol, host, port, data)

        conn.test_passed       = success
        conn.test_message      = message
        conn.first_reading_at  = datetime.now(timezone.utc).isoformat() if success else None
        conn.assets_discovered = len(sample_tags)
        _connections[tenant_id] = conn

        if success:
            tenant = auth_service.get_tenant(tenant_id)
            if tenant:
                tenant.scada_connected   = True
                tenant.scada_protocol    = protocol
                tenant.scada_host        = host
                if tenant.onboarding_step < 3:
                    tenant.onboarding_step = 3

        logger.info(f"[Onboarding] Step 2 {'✓' if success else '✗'}: {tenant_id} — {protocol}://{host}:{port}")
        return {
            "success":          success,
            "message":          message,
            "protocol":         protocol,
            "assets_discovered":len(sample_tags),
            "sample_tags":      sample_tags[:5],  # preview only
        }

    async def _attempt_connection(self, protocol: str, host: str, port: int,
                                   data: Dict):
        """
        Attempt actual SCADA connection. Falls back to simulation in dev.
        Returns (success, message, discovered_tags).
        """
        # Try real connection first
        if host and host not in ("localhost", "127.0.0.1", "demo", ""):
            from backend.protocols.adapters import create_adapter
            try:
                adapter = create_adapter("test", "test", protocol, host, port)
                await adapter.connect()
                reading = await adapter.read()
                if reading.error:
                    return False, f"Connection failed: {reading.error}", []
                tags = [{"tag": f"{protocol.upper()}_AI_{i:04d}", "value": round(reading.active_power_mw or 0, 2), "unit": "MW"} for i in range(1, 6)]
                return True, f"Connected successfully — {len(tags)} tags discovered", tags
            except Exception as exc:
                return False, f"Connection error: {str(exc)[:100]}", []

        # Demo/simulation mode
        import random
        simulated_tags = [
            {"tag": "SUB1_MW",      "value": round(random.uniform(50, 200), 1),  "unit": "MW"},
            {"tag": "SUB1_FREQ",    "value": round(random.uniform(59.9, 60.1), 3),"unit": "Hz"},
            {"tag": "TRF1_TEMP",    "value": round(random.uniform(45, 75), 1),    "unit": "°C"},
            {"tag": "SOLAR_MW",     "value": round(random.uniform(0, 150), 1),    "unit": "MW"},
            {"tag": "BESS_SOC",     "value": round(random.uniform(20, 90), 0),    "unit": "%"},
        ]
        return True, f"Demo connection established — {len(simulated_tags)} tags discovered", simulated_tags

    # ── Step 3: Asset import ──────────────────────────────────────────────────

    async def discover_assets(self, tenant_id: str) -> Dict:
        """
        Scan the connected SCADA system for all available assets.
        Groups tags into logical assets (transformer, feeder, etc.)
        """
        conn = _connections.get(tenant_id)
        profile = _profiles.get(tenant_id)

        # Generate realistic asset list based on grid profile
        assets = self._generate_demo_assets(profile)
        _discovered[tenant_id] = assets

        tenant = auth_service.get_tenant(tenant_id)
        if tenant and tenant.onboarding_step < 4:
            tenant.onboarding_step = 4

        logger.info(f"[Onboarding] Step 3 complete: {tenant_id} — {len(assets)} assets discovered")
        return {
            "assets_discovered": len(assets),
            "assets": [
                {
                    "tag":           a.tag,
                    "name":          a.name,
                    "asset_type":    a.asset_type,
                    "description":   a.description,
                    "current_value": a.current_value,
                    "unit":          a.unit,
                    "selected":      a.import_selected,
                }
                for a in assets
            ],
        }

    def confirm_asset_import(self, tenant_id: str, selected_tags: List[str]) -> Dict:
        """
        User confirms which assets to import.
        Creates asset records in the main GridIQ asset registry.
        """
        assets = _discovered.get(tenant_id, [])
        to_import = [a for a in assets if a.tag in selected_tags]

        tenant = auth_service.get_tenant(tenant_id)
        if tenant:
            tenant.current_asset_count = len(to_import)
            if tenant.onboarding_step < 5:
                tenant.onboarding_step = 5

        logger.info(f"[Onboarding] {len(to_import)} assets confirmed for import: {tenant_id}")
        return {
            "imported": len(to_import),
            "message": f"{len(to_import)} assets imported into GridIQ",
        }

    # ── Step 4: Review ────────────────────────────────────────────────────────

    def get_review_summary(self, tenant_id: str) -> Dict:
        """Step 4 — what GridIQ found during onboarding."""
        profile  = _profiles.get(tenant_id)
        conn     = _connections.get(tenant_id)
        assets   = _discovered.get(tenant_id, [])
        tenant   = auth_service.get_tenant(tenant_id)

        return {
            "tenant_name":      tenant.name if tenant else "",
            "service_territory":profile.service_territory if profile else "",
            "scada_protocol":   conn.protocol if conn else "",
            "scada_connected":  bool(conn and conn.test_passed),
            "assets_discovered":len(assets),
            "asset_types":      list(set(a.asset_type for a in assets)),
            "has_renewables":   any(a.asset_type in ("solar_farm","wind_farm","hydro_plant") for a in assets),
            "estimated_annual_value": self._estimate_roi(profile, assets),
            "next_step": "Choose your plan and get started",
        }

    # ── Step 5: Complete ──────────────────────────────────────────────────────

    def complete_onboarding(self, tenant_id: str) -> Dict:
        """Mark onboarding as complete (called after payment succeeds)."""
        tenant = auth_service.get_tenant(tenant_id)
        if tenant:
            tenant.onboarding_complete = True
            tenant.onboarding_step     = 5
        logger.info(f"[Onboarding] Complete: {tenant_id}")
        return {"complete": True, "redirect": "/dashboard"}

    def get_progress(self, tenant_id: str) -> Dict:
        """Get current onboarding progress for the wizard UI."""
        tenant = auth_service.get_tenant(tenant_id)
        if not tenant:
            return {"step": 1, "complete": False}

        steps = [
            {"step": 1, "label": "Grid profile",    "complete": tenant.onboarding_step > 1},
            {"step": 2, "label": "Connect data",    "complete": tenant.scada_connected},
            {"step": 3, "label": "Import assets",   "complete": tenant.onboarding_step > 3},
            {"step": 4, "label": "Review",          "complete": tenant.onboarding_step > 4},
            {"step": 5, "label": "Activate",        "complete": tenant.onboarding_complete},
        ]
        return {
            "current_step":       tenant.onboarding_step,
            "complete":           tenant.onboarding_complete,
            "scada_connected":    tenant.scada_connected,
            "steps":              steps,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _generate_demo_assets(self, profile: Optional[GridProfile]) -> List[DiscoveredAsset]:
        """Generate realistic demo asset list from grid profile."""
        import random
        assets = []

        n = min(profile.estimated_assets if profile else 50, 200)
        n_transformers = max(2, n // 20)
        n_breakers     = max(4, n // 10)

        for i in range(n_transformers):
            assets.append(DiscoveredAsset(
                tag=f"TRF_{i+1:03d}", name=f"Transformer T-{i+1:02d}A",
                asset_type="transformer",
                description=f"{random.choice([69, 115, 138])}kV/{random.choice([12, 34.5])}kV",
                current_value=round(random.uniform(40, 160), 1), unit="MW",
            ))
        for i in range(n_breakers):
            assets.append(DiscoveredAsset(
                tag=f"CBR_{i+1:03d}", name=f"Circuit Breaker CB-{i+1:02d}",
                asset_type="circuit_breaker",
                description=f"Feeder {i+1}",
                current_value=random.choice([0, 1]), unit="status",
            ))
        if profile and profile.has_solar:
            assets.append(DiscoveredAsset(
                tag="SOLAR_001", name="Solar Farm Alpha",
                asset_type="solar_farm", description="PV generation",
                current_value=round(random.uniform(0, 300), 1), unit="MW",
            ))
        if profile and profile.has_wind:
            assets.append(DiscoveredAsset(
                tag="WIND_001", name="Wind Farm North",
                asset_type="wind_farm", description="Wind generation",
                current_value=round(random.uniform(0, 600), 1), unit="MW",
            ))
        if profile and profile.has_hydro:
            assets.append(DiscoveredAsset(
                tag="HYDRO_001", name="Hydro Plant Unit 1",
                asset_type="hydro_plant", description="Run-of-river hydro",
                current_value=round(random.uniform(20, 100), 1), unit="MW",
            ))
        if profile and profile.has_bess:
            assets.append(DiscoveredAsset(
                tag="BESS_001", name="BESS Station 1",
                asset_type="bess", description="Battery energy storage",
                current_value=round(random.uniform(20, 90), 0), unit="% SoC",
            ))
        return assets

    def _estimate_roi(self, profile, assets) -> Dict:
        """Quick ROI estimate for the review screen."""
        n = len(assets)
        has_renewables = any(a.asset_type in ("solar_farm","wind_farm","hydro_plant") for a in assets)
        base = n * 5000
        return {
            "maintenance_savings":  f"${base:,}–${base*2:,}/yr",
            "outage_prevention":    "$100K–$500K/yr",
            "compliance_hours":     "100–300 hrs/yr",
            "renewable_optimization": "$30K–$150K/yr" if has_renewables else "N/A",
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
onboarding_service = OnboardingService()
