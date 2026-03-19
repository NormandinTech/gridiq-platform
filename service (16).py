"""
GridIQ — Initial Database Migration
=====================================
Creates all tables for the GridIQ platform:
  - grid_zones
  - assets
  - telemetry_readings  (converted to TimescaleDB hypertable)
  - grid_snapshots      (converted to TimescaleDB hypertable)
  - alerts
  - forecast_records
  - maintenance_records
  - security_threats
  - access_logs
  - compliance_controls

TimescaleDB hypertables enable:
  - Automatic time-based partitioning (1-day chunks for telemetry)
  - Native compression (compress chunks older than 7 days)
  - Fast time-range queries (10–100× faster than plain PostgreSQL)
  - Continuous aggregates for dashboard KPIs
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:

    # ── Enum types ────────────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE assettype AS ENUM (
                'transformer','circuit_breaker','switch','capacitor_bank',
                'rtu','scada_server','solar_farm','wind_farm','hydro_plant',
                'gas_peaker','bess','substation','transmission_line',
                'smart_meter','ev_charger'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE assetstatus AS ENUM (
                'online','offline','degraded','maintenance','unknown'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE alertseverity AS ENUM (
                'critical','high','medium','low','info'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE alertstatus AS ENUM (
                'open','acknowledged','resolved','suppressed'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE threatlevel AS ENUM (
                'critical','high','medium','low'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE networkzone AS ENUM (
                'internet','dmz','it','ot','ami'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)

    # ── grid_zones ────────────────────────────────────────────────────────────
    op.create_table(
        'grid_zones',
        sa.Column('id',           sa.String(36),  primary_key=True),
        sa.Column('name',         sa.String(100), nullable=False),
        sa.Column('code',         sa.String(20),  nullable=False, unique=True),
        sa.Column('description',  sa.Text),
        sa.Column('latitude',     sa.Float),
        sa.Column('longitude',    sa.Float),
        sa.Column('voltage_kv',   sa.Float),
        sa.Column('capacity_mw',  sa.Float),
        sa.Column('is_active',    sa.Boolean, default=True),
        sa.Column('created_at',   sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at',   sa.DateTime(timezone=True), server_default=sa.func.now(),
                  onupdate=sa.func.now()),
    )

    # ── assets ────────────────────────────────────────────────────────────────
    op.create_table(
        'assets',
        sa.Column('id',                  sa.String(36),  primary_key=True),
        sa.Column('zone_id',             sa.String(36),  sa.ForeignKey('grid_zones.id')),
        sa.Column('name',                sa.String(200), nullable=False),
        sa.Column('asset_tag',           sa.String(50),  nullable=False, unique=True),
        sa.Column('asset_type',          sa.Enum('transformer','circuit_breaker','switch',
                                                  'capacitor_bank','rtu','scada_server',
                                                  'solar_farm','wind_farm','hydro_plant',
                                                  'gas_peaker','bess','substation',
                                                  'transmission_line','smart_meter',
                                                  'ev_charger', name='assettype'),
                  nullable=False),
        sa.Column('status',              sa.Enum('online','offline','degraded',
                                                  'maintenance','unknown', name='assetstatus'),
                  default='online'),
        sa.Column('manufacturer',        sa.String(100)),
        sa.Column('model',               sa.String(100)),
        sa.Column('serial_number',       sa.String(100)),
        sa.Column('install_date',        sa.DateTime(timezone=True)),
        sa.Column('rated_capacity_mw',   sa.Float),
        sa.Column('rated_voltage_kv',    sa.Float),
        sa.Column('latitude',            sa.Float),
        sa.Column('longitude',           sa.Float),
        sa.Column('protocol',            sa.String(50)),
        sa.Column('ip_address',          sa.String(45)),
        sa.Column('port',                sa.Integer),
        sa.Column('polling_interval_sec',sa.Integer, default=30),
        sa.Column('health_score',        sa.Float,   default=100.0),
        sa.Column('last_seen',           sa.DateTime(timezone=True)),
        sa.Column('metadata_json',       postgresql.JSON),
        sa.Column('is_critical',         sa.Boolean, default=False),
        sa.Column('nerc_cip_asset',      sa.Boolean, default=False),
        sa.Column('created_at',          sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at',          sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_assets_zone_id',    'assets', ['zone_id'])
    op.create_index('ix_assets_asset_type', 'assets', ['asset_type'])
    op.create_index('ix_assets_status',     'assets', ['status'])

    # ── telemetry_readings (→ TimescaleDB hypertable) ─────────────────────────
    op.create_table(
        'telemetry_readings',
        sa.Column('id',                 sa.String(36), primary_key=True),
        sa.Column('asset_id',           sa.String(36), sa.ForeignKey('assets.id'), nullable=False),
        sa.Column('timestamp',          sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('active_power_mw',    sa.Float),
        sa.Column('reactive_power_mvar',sa.Float),
        sa.Column('apparent_power_mva', sa.Float),
        sa.Column('power_factor',       sa.Float),
        sa.Column('voltage_kv',         sa.Float),
        sa.Column('current_amps',       sa.Float),
        sa.Column('frequency_hz',       sa.Float),
        sa.Column('temperature_c',      sa.Float),
        sa.Column('oil_temperature_c',  sa.Float),
        sa.Column('status_raw',         sa.String(50)),
        sa.Column('extra',              postgresql.JSON),
    )
    op.create_index('ix_telemetry_asset_ts',  'telemetry_readings', ['asset_id', 'timestamp'])
    op.create_index('ix_telemetry_timestamp', 'telemetry_readings', ['timestamp'])

    # Convert to TimescaleDB hypertable (1-day chunks, partitioned by timestamp)
    op.execute("""
        SELECT create_hypertable(
            'telemetry_readings', 'timestamp',
            if_not_exists => TRUE,
            chunk_time_interval => INTERVAL '1 day'
        );
    """)
    # Enable compression — older chunks are compressed automatically
    op.execute("""
        ALTER TABLE telemetry_readings
        SET (
            timescaledb.compress,
            timescaledb.compress_orderby = 'timestamp DESC',
            timescaledb.compress_segmentby = 'asset_id'
        );
    """)
    op.execute("""
        SELECT add_compression_policy(
            'telemetry_readings',
            INTERVAL '7 days',
            if_not_exists => TRUE
        );
    """)

    # ── grid_snapshots (→ TimescaleDB hypertable) ─────────────────────────────
    op.create_table(
        'grid_snapshots',
        sa.Column('id',                              sa.String(36), primary_key=True),
        sa.Column('timestamp',                       sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('total_load_mw',                   sa.Float),
        sa.Column('total_generation_mw',             sa.Float),
        sa.Column('renewable_mw',                    sa.Float),
        sa.Column('renewable_pct',                   sa.Float),
        sa.Column('frequency_hz',                    sa.Float),
        sa.Column('transmission_capacity_used_pct',  sa.Float),
        sa.Column('voltage_stability_index',         sa.Float),
        sa.Column('co2_intensity_g_kwh',             sa.Float),
        sa.Column('co2_avoided_tonnes',              sa.Float),
    )
    op.create_index('ix_grid_snapshots_timestamp', 'grid_snapshots', ['timestamp'])
    op.execute("""
        SELECT create_hypertable(
            'grid_snapshots', 'timestamp',
            if_not_exists => TRUE,
            chunk_time_interval => INTERVAL '1 hour'
        );
    """)

    # ── alerts ────────────────────────────────────────────────────────────────
    op.create_table(
        'alerts',
        sa.Column('id',                 sa.String(36), primary_key=True),
        sa.Column('asset_id',           sa.String(36), sa.ForeignKey('assets.id')),
        sa.Column('zone_id',            sa.String(36), sa.ForeignKey('grid_zones.id')),
        sa.Column('severity',           sa.Enum('critical','high','medium','low','info',
                                                  name='alertseverity'), nullable=False),
        sa.Column('status',             sa.Enum('open','acknowledged','resolved','suppressed',
                                                  name='alertstatus'), default='open'),
        sa.Column('title',              sa.String(300), nullable=False),
        sa.Column('description',        sa.Text),
        sa.Column('source',             sa.String(50),  default='system'),
        sa.Column('category',           sa.String(50),  default='operational'),
        sa.Column('confidence',         sa.Float),
        sa.Column('anomaly_score',      sa.Float),
        sa.Column('recommended_action', sa.Text),
        sa.Column('fault_code',         sa.String(50)),
        sa.Column('estimated_loss_mw',  sa.Float),
        sa.Column('revenue_loss_hr',    sa.Float),
        sa.Column('created_at',         sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('acknowledged_at',    sa.DateTime(timezone=True)),
        sa.Column('acknowledged_by',    sa.String(100)),
        sa.Column('resolved_at',        sa.DateTime(timezone=True)),
        sa.Column('resolved_by',        sa.String(100)),
        sa.Column('metadata_json',      postgresql.JSON),
    )
    op.create_index('ix_alerts_status',     'alerts', ['status'])
    op.create_index('ix_alerts_severity',   'alerts', ['severity'])
    op.create_index('ix_alerts_created_at', 'alerts', ['created_at'])

    # ── forecast_records ──────────────────────────────────────────────────────
    op.create_table(
        'forecast_records',
        sa.Column('id',              sa.String(36), primary_key=True),
        sa.Column('forecast_type',   sa.String(50)),
        sa.Column('zone_id',         sa.String(36), sa.ForeignKey('grid_zones.id')),
        sa.Column('generated_at',    sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('model_version',   sa.String(50), default='v1'),
        sa.Column('horizon_hours',   sa.Integer,    default=48),
        sa.Column('forecast_data',   postgresql.JSON, nullable=False),
        sa.Column('rmse_mw',         sa.Float),
        sa.Column('mape_pct',        sa.Float),
        sa.Column('metadata_json',   postgresql.JSON),
    )

    # ── maintenance_records ───────────────────────────────────────────────────
    op.create_table(
        'maintenance_records',
        sa.Column('id',                      sa.String(36), primary_key=True),
        sa.Column('asset_id',                sa.String(36), sa.ForeignKey('assets.id'), nullable=False),
        sa.Column('maintenance_type',        sa.String(100)),
        sa.Column('priority',                sa.String(20), default='normal'),
        sa.Column('title',                   sa.String(300), nullable=False),
        sa.Column('description',             sa.Text),
        sa.Column('predicted_failure_date',  sa.DateTime(timezone=True)),
        sa.Column('failure_probability',     sa.Float),
        sa.Column('scheduled_date',          sa.DateTime(timezone=True)),
        sa.Column('completed_date',          sa.DateTime(timezone=True)),
        sa.Column('assigned_to',             sa.String(100)),
        sa.Column('work_order_id',           sa.String(100)),
        sa.Column('status',                  sa.String(50), default='open'),
        sa.Column('fault_code',              sa.String(50)),
        sa.Column('estimated_loss_mw',       sa.Float),
        sa.Column('revenue_loss_hr',         sa.Float),
        sa.Column('created_at',              sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at',              sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_maintenance_asset_id', 'maintenance_records', ['asset_id'])
    op.create_index('ix_maintenance_status',   'maintenance_records', ['status'])

    # ── security_threats ──────────────────────────────────────────────────────
    op.create_table(
        'security_threats',
        sa.Column('id',              sa.String(36), primary_key=True),
        sa.Column('asset_id',        sa.String(36), sa.ForeignKey('assets.id')),
        sa.Column('threat_level',    sa.Enum('critical','high','medium','low',
                                              name='threatlevel'), nullable=False),
        sa.Column('network_zone',    sa.Enum('internet','dmz','it','ot','ami',
                                              name='networkzone')),
        sa.Column('title',           sa.String(300), nullable=False),
        sa.Column('description',     sa.Text),
        sa.Column('source_ip',       sa.String(45)),
        sa.Column('destination_ip',  sa.String(45)),
        sa.Column('protocol',        sa.String(50)),
        sa.Column('cve_id',          sa.String(50)),
        sa.Column('attack_type',     sa.String(100)),
        sa.Column('threat_score',    sa.Float),
        sa.Column('is_blocked',      sa.Boolean, default=False),
        sa.Column('is_active',       sa.Boolean, default=True),
        sa.Column('incident_ticket', sa.String(100)),
        sa.Column('detected_at',     sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('resolved_at',     sa.DateTime(timezone=True)),
        sa.Column('metadata_json',   postgresql.JSON),
    )
    op.create_index('ix_threats_detected_at', 'security_threats', ['detected_at'])
    op.create_index('ix_threats_is_active',   'security_threats', ['is_active'])

    # ── access_logs ───────────────────────────────────────────────────────────
    op.create_table(
        'access_logs',
        sa.Column('id',               sa.String(36), primary_key=True),
        sa.Column('timestamp',        sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('user_id',          sa.String(100)),
        sa.Column('username',         sa.String(100)),
        sa.Column('source_ip',        sa.String(45)),
        sa.Column('target_asset_id',  sa.String(36), sa.ForeignKey('assets.id')),
        sa.Column('target_resource',  sa.String(200)),
        sa.Column('action',           sa.String(100)),
        sa.Column('outcome',          sa.String(20)),
        sa.Column('mfa_used',         sa.Boolean, default=False),
        sa.Column('session_id',       sa.String(100)),
        sa.Column('details',          postgresql.JSON),
    )
    op.create_index('ix_access_logs_timestamp', 'access_logs', ['timestamp'])

    # ── compliance_controls ───────────────────────────────────────────────────
    op.create_table(
        'compliance_controls',
        sa.Column('id',                sa.String(36), primary_key=True),
        sa.Column('standard',          sa.String(50)),
        sa.Column('control_id',        sa.String(50), nullable=False),
        sa.Column('title',             sa.String(300), nullable=False),
        sa.Column('description',       sa.Text),
        sa.Column('category',          sa.String(100)),
        sa.Column('compliance_pct',    sa.Float, default=0.0),
        sa.Column('status',            sa.String(50), default='unknown'),
        sa.Column('last_assessed',     sa.DateTime(timezone=True)),
        sa.Column('due_date',          sa.DateTime(timezone=True)),
        sa.Column('findings',          sa.Text),
        sa.Column('remediation_plan',  sa.Text),
        sa.Column('updated_at',        sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('standard', 'control_id', name='uq_compliance_standard_control'),
    )

    # ── TimescaleDB continuous aggregates for dashboard KPIs ─────────────────
    # Hourly rollup of telemetry for fast dashboard queries
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_hourly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', timestamp) AS bucket,
            asset_id,
            AVG(active_power_mw)    AS avg_power_mw,
            MAX(active_power_mw)    AS max_power_mw,
            MIN(active_power_mw)    AS min_power_mw,
            AVG(frequency_hz)       AS avg_frequency_hz,
            AVG(temperature_c)      AS avg_temp_c,
            MAX(temperature_c)      AS max_temp_c,
            COUNT(*)                AS reading_count
        FROM telemetry_readings
        GROUP BY bucket, asset_id
        WITH NO DATA;
    """)
    op.execute("""
        SELECT add_continuous_aggregate_policy('telemetry_hourly',
            start_offset => INTERVAL '3 hours',
            end_offset   => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour',
            if_not_exists => TRUE
        );
    """)


def downgrade() -> None:
    """Drop all tables in reverse order."""
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_hourly CASCADE;")
    op.drop_table('compliance_controls')
    op.drop_table('access_logs')
    op.drop_table('security_threats')
    op.drop_table('maintenance_records')
    op.drop_table('forecast_records')
    op.drop_table('alerts')
    op.drop_table('grid_snapshots')
    op.drop_table('telemetry_readings')
    op.drop_table('assets')
    op.drop_table('grid_zones')
    # Drop enum types
    for enum in ['assettype','assetstatus','alertseverity','alertstatus','threatlevel','networkzone']:
        op.execute(f"DROP TYPE IF EXISTS {enum} CASCADE;")
