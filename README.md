# GridIQ Platform — Quick Start

## Run in 3 commands

```bash
# 1. Backend
cd gridiq
pip install -r requirements.txt
python scripts/seed_data.py
uvicorn backend.main:app --reload --port 8000

# 2. Frontend (new terminal)
cd gridiq/frontend
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000 — the dashboard connects live to the backend.

---

## What's running

| Service       | URL                              | Purpose                          |
|---------------|----------------------------------|----------------------------------|
| Dashboard     | http://localhost:3000            | React frontend                   |
| API           | http://localhost:8000            | FastAPI backend                  |
| API Docs      | http://localhost:8000/docs       | Swagger UI (all 25+ endpoints)   |
| WS Telemetry  | ws://localhost:8000/api/v1/ws/telemetry | Live readings every 5s  |
| WS Alerts     | ws://localhost:8000/api/v1/ws/alerts    | Real-time alert push    |

---

## Full stack (Docker)

```bash
docker compose up -d
# All services start: PostgreSQL, Redis, Kafka, MQTT, API
```

---

## Architecture summary

```
React Dashboard
  ├── TanStack Query (HTTP polling: KPIs 10s, assets 30s, forecasts 5m)
  ├── Zustand store  (live state: telemetry, alerts, threats)
  └── WebSocket      (push: telemetry every 5s, alerts on event)
        │
        ▼
FastAPI Backend (port 8000)
  ├── /api/v1/grid/*          Grid KPIs, topology, energy mix
  ├── /api/v1/assets/*        Asset health, telemetry history
  ├── /api/v1/forecast/*      Demand 48h, renewable 12h, AI recommendations
  ├── /api/v1/alerts/*        Alert CRUD with acknowledge/resolve
  ├── /api/v1/maintenance/*   Predictive maintenance schedule
  ├── /api/v1/security/*      Threats, zones, NERC CIP, zero-trust
  └── /ws/*                   WebSocket telemetry + alert streams
        │
  ┌─────┴──────────────────────┐
  │  Internal Event Bus         │  (Redis pub/sub in production)
  └─────┬──────────────────────┘
        │
  ┌─────┴──────────────────┐  ┌──────────────┐  ┌─────────────────┐
  │  Telemetry Simulator   │  │  AI/ML Engine │  │  Security Engine│
  │  20 assets, 5s interval│  │  TFT forecast │  │  Zero-trust     │
  │  Modbus/DNP3/MQTT      │  │  Anomaly det. │  │  ICS threat det.│
  └────────────────────────┘  └──────────────┘  └─────────────────┘
        │
  ┌─────┴──────────────────────────────────────────────────────┐
  │  PostgreSQL + TimescaleDB   Redis   Kafka   MQTT broker    │
  └────────────────────────────────────────────────────────────┘
```

## File inventory (7,322 lines)

### Backend (4,567 lines — Python)
| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app factory, lifespan hooks |
| `backend/core/config.py` | Pydantic settings from env |
| `backend/core/event_bus.py` | In-memory + Redis event bus |
| `backend/models/db_models.py` | SQLAlchemy models (TimescaleDB-ready) |
| `backend/models/schemas.py` | Pydantic API schemas |
| `backend/api/routes.py` | All 25+ REST + WebSocket endpoints |
| `backend/ml/engine.py` | Demand/renewable forecast, anomaly detection, health scoring |
| `backend/security/cyber.py` | Zero-trust, ICS threat detection, NERC CIP |
| `backend/protocols/adapters.py` | Modbus TCP, DNP3, IEC 61850, MQTT |
| `backend/services/asset_service.py` | Asset + telemetry ingestion pipeline |
| `backend/services/alert_service.py` | Alert lifecycle + notifications |
| `backend/services/polling_service.py` | Multi-asset polling orchestrator |
| `backend/db/database.py` | Async SQLAlchemy + TimescaleDB setup |
| `scripts/simulate_telemetry.py` | Realistic SCADA data generator |
| `scripts/seed_data.py` | Grid topology seed data |
| `tests/test_gridiq.py` | Full test suite (22 tests) |

### Frontend (2,755 lines — TypeScript/React)
| File | Purpose |
|------|---------|
| `src/types/index.ts` | All TypeScript interfaces |
| `src/services/api.ts` | API client + WebSocket manager |
| `src/stores/gridStore.ts` | Zustand global state |
| `src/hooks/useGridData.ts` | TanStack Query hooks (auto-refresh) |
| `src/components/KPICard.tsx` | Metric card widget |
| `src/components/AlertFeed.tsx` | Live alert list with actions |
| `src/components/AssetHealthTable.tsx` | Sortable health table |
| `src/components/ForecastCharts.tsx` | Recharts demand/renewable charts |
| `src/components/TopBar.tsx` | Header with live frequency + WS status |
| `src/components/Sidebar.tsx` | Navigation with live badge counts |
| `src/pages/GridOverview.tsx` | Main dashboard (fully wired) |
| `src/pages/AIAnalytics.tsx` | Forecast + AI recommendations |
| `src/pages/Cybersecurity.tsx` | Threats + zones + NERC CIP |
| `src/pages/stubs.tsx` | Renewables, Alerts, Maintenance, Compliance |
| `src/App.tsx` | Root with QueryClient + routing |
