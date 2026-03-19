"""
GridIQ — Migration 0002: Vegetation, Asset Intelligence, Sensor Management
============================================================================
Adds tables for:
  - vegetation_span_risks      (LiDAR-derived risk scores per transmission span)
  - detected_faults            (universal asset fault detection results)
  - deployed_sensors           (sensor fleet tracking)
  - sensor_calibration_log     (calibration history)
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0002_vegetation_assets_sensors'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:

    # ── vegetation_span_risks ─────────────────────────────────────────────────
    op.create_table(
        'vegetation_span_risks',
        sa.Column('id',                       sa.String(36), primary_key=True),
        sa.Column('span_id',                  sa.String(100), nullable=False, unique=True),
        sa.Column('line_id',                  sa.String(100)),
        sa.Column('line_name',                sa.String(200)),
        sa.Column('voltage_kv',               sa.Float),
        sa.Column('zone',                     sa.String(100)),
        sa.Column('lat',                      sa.Float),
        sa.Column('lon',                      sa.Float),
        sa.Column('span_length_m',            sa.Float),
        sa.Column('survey_date',              sa.DateTime(timezone=True)),
        sa.Column('survey_source',            sa.String(100)),
        sa.Column('overall_risk_score',       sa.Float),
        sa.Column('risk_level',               sa.String(20)),
        sa.Column('nerc_min_clearance_m',     sa.Float),
        sa.Column('min_clearance_observed_m', sa.Float),
        sa.Column('clearance_violations',     sa.Integer, default=0),
        sa.Column('encroaching_trees',        sa.Integer, default=0),
        sa.Column('total_trees_in_corridor',  sa.Integer, default=0),
        sa.Column('canopy_cover_pct',         sa.Float),
        sa.Column('growth_rate_m_yr',         sa.Float),
        sa.Column('years_to_next_violation',  sa.Float),
        sa.Column('dominant_species',         sa.String(100)),
        sa.Column('fire_risk_score',          sa.Float),
        sa.Column('terrain_risk_multiplier',  sa.Float),
        sa.Column('last_trim_date',           sa.DateTime(timezone=True)),
        sa.Column('recommended_action',       sa.Text),
        sa.Column('work_order_priority',      sa.String(50)),
        sa.Column('trend',                    sa.String(20)),
        sa.Column('growth_trend_m_yr',        sa.Float),
        sa.Column('top_threats_json',         postgresql.JSON),
        sa.Column('created_at',               sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at',               sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_veg_risk_level',    'vegetation_span_risks', ['risk_level'])
    op.create_index('ix_veg_line_id',       'vegetation_span_risks', ['line_id'])
    op.create_index('ix_veg_updated_at',    'vegetation_span_risks', ['updated_at'])

    # ── detected_faults ───────────────────────────────────────────────────────
    op.create_table(
        'detected_faults',
        sa.Column('id',                      sa.String(36), primary_key=True),
        sa.Column('fault_code',              sa.String(50), nullable=False),
        sa.Column('asset_id',               sa.String(36), sa.ForeignKey('assets.id')),
        sa.Column('asset_name',             sa.String(200)),
        sa.Column('asset_type',             sa.String(50)),
        sa.Column('severity',               sa.String(20)),
        sa.Column('category',               sa.String(50)),
        sa.Column('title',                  sa.String(300)),
        sa.Column('description',            sa.Text),
        sa.Column('trigger_param',          sa.String(100)),
        sa.Column('trigger_value',          sa.Float),
        sa.Column('trigger_threshold',      sa.Float),
        sa.Column('estimated_loss_mw',      sa.Float),
        sa.Column('estimated_revenue_loss_hr', sa.Float),
        sa.Column('recommended_action',     sa.Text),
        sa.Column('work_order_priority',    sa.String(50)),
        sa.Column('maintenance_type',       sa.String(50)),
        sa.Column('confidence',             sa.Float),
        sa.Column('status',                 sa.String(20), default='open'),
        sa.Column('detected_at',            sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('resolved_at',            sa.DateTime(timezone=True)),
        sa.Column('resolved_by',            sa.String(100)),
    )
    op.create_index('ix_faults_asset_id',   'detected_faults', ['asset_id'])
    op.create_index('ix_faults_status',     'detected_faults', ['status'])
    op.create_index('ix_faults_severity',   'detected_faults', ['severity'])
    op.create_index('ix_faults_detected_at','detected_faults', ['detected_at'])

    # ── deployed_sensors ──────────────────────────────────────────────────────
    op.create_table(
        'deployed_sensors',
        sa.Column('sensor_id',              sa.String(36), primary_key=True),
        sa.Column('sensor_type_id',         sa.String(20), nullable=False),
        sa.Column('asset_id',               sa.String(36), sa.ForeignKey('assets.id')),
        sa.Column('asset_name',             sa.String(200)),
        sa.Column('asset_type',             sa.String(50)),
        sa.Column('manufacturer',           sa.String(100)),
        sa.Column('model',                  sa.String(100)),
        sa.Column('serial_number',          sa.String(100)),
        sa.Column('firmware_version',       sa.String(50)),
        sa.Column('installation_point',     sa.String(300)),
        sa.Column('lat',                    sa.Float),
        sa.Column('lon',                    sa.Float),
        sa.Column('status',                 sa.String(30), default='online'),
        sa.Column('install_date',           sa.DateTime(timezone=True)),
        sa.Column('last_calibration_date',  sa.DateTime(timezone=True)),
        sa.Column('next_calibration_date',  sa.DateTime(timezone=True)),
        sa.Column('last_seen',              sa.DateTime(timezone=True)),
        sa.Column('data_quality_score',     sa.Float, default=100.0),
        sa.Column('availability_pct_30d',   sa.Float, default=99.5),
        sa.Column('outlier_rate_pct',       sa.Float, default=0.2),
        sa.Column('drift_detected',         sa.Boolean, default=False),
        sa.Column('protocol',               sa.String(50)),
        sa.Column('ip_address',             sa.String(45)),
        sa.Column('purchase_cost_usd',      sa.Integer),
        sa.Column('warranty_expiry',        sa.DateTime(timezone=True)),
        sa.Column('notes',                  sa.Text),
        sa.Column('created_at',             sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at',             sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_sensors_asset_id',   'deployed_sensors', ['asset_id'])
    op.create_index('ix_sensors_status',     'deployed_sensors', ['status'])
    op.create_index('ix_sensors_cal_due',    'deployed_sensors', ['next_calibration_date'])

    # ── sensor_calibration_log ────────────────────────────────────────────────
    op.create_table(
        'sensor_calibration_log',
        sa.Column('id',                  sa.String(36), primary_key=True),
        sa.Column('sensor_id',           sa.String(36), sa.ForeignKey('deployed_sensors.sensor_id')),
        sa.Column('calibrated_at',       sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('calibrated_by',       sa.String(100)),
        sa.Column('method',              sa.String(200)),
        sa.Column('result',              sa.String(20), default='pass'),
        sa.Column('pre_cal_reading',     sa.Float),
        sa.Column('post_cal_reading',    sa.Float),
        sa.Column('reference_standard',  sa.String(200)),
        sa.Column('certificate_number',  sa.String(100)),
        sa.Column('next_cal_due',        sa.DateTime(timezone=True)),
        sa.Column('notes',               sa.Text),
    )
    op.create_index('ix_cal_log_sensor_id', 'sensor_calibration_log', ['sensor_id'])
    op.create_index('ix_cal_log_cal_at',    'sensor_calibration_log', ['calibrated_at'])


def downgrade() -> None:
    op.drop_table('sensor_calibration_log')
    op.drop_table('deployed_sensors')
    op.drop_table('detected_faults')
    op.drop_table('vegetation_span_risks')
