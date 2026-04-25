"""Admin enhancement: quota system, user management, integration registry.

Revision ID: add_quota_user_management_integrations
Revises: phase_a_enhancement_models
Create Date: 2026-02-25

Adds the following new tables (all additions, no existing tables altered):
  plan_tiers                      — PlanTier definitions (Phase 1.2)
  tenant_quotas                   — Per-tenant quota pool (Phase 1.2)
  user_storage_stats              — Per-user live usage tracker (Phase 1.2)
  user_invites                    — Invite tokens for registration (Phase 8.1)
  password_history                — Hashed previous passwords (Phase 8.1)
  user_sessions                   — Server-side session tracking (Phase 8.1)
  global_integration_services     — Admin-registered integration registry (Phase 9.2)
  user_integration_credentials    — Per-user OAuth2 / API key storage (Phase 9.2)

Modifies existing tables (additive only — column additions):
  users     — quota columns, MFA columns, profile columns, lockout columns
  tenants   — plan_tier_id FK
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_quota_user_management_integrations'
down_revision = 'phase_a_enhancement_models'
branch_labels = None
depends_on = None


def upgrade():
    # ──────────────────────────────────────────────────────────────────────────
    # plan_tiers
    # ──────────────────────────────────────────────────────────────────────────
    op.create_table(
        'plan_tiers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(80), nullable=False),
        sa.Column('storage_quota_bytes', sa.BigInteger(), nullable=True, default=1_073_741_824),
        sa.Column('document_quota', sa.Integer(), nullable=True, default=500),
        sa.Column('project_quota', sa.Integer(), nullable=True, default=10),
        sa.Column('api_calls_per_day', sa.Integer(), nullable=True, default=1000),
        sa.Column('max_upload_size_bytes', sa.BigInteger(), nullable=True, default=52_428_800),
        sa.Column('price_display', sa.String(40), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    # ──────────────────────────────────────────────────────────────────────────
    # tenant_quotas
    # ──────────────────────────────────────────────────────────────────────────
    op.create_table(
        'tenant_quotas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('plan_tier_id', sa.Integer(), nullable=True),
        sa.Column('storage_quota_bytes', sa.BigInteger(), nullable=True),
        sa.Column('document_quota', sa.Integer(), nullable=True),
        sa.Column('max_upload_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('used_storage_bytes', sa.BigInteger(), default=0),
        sa.Column('document_count', sa.Integer(), default=0),
        sa.Column('last_recalculated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['plan_tier_id'], ['plan_tiers.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id'),
    )

    # ──────────────────────────────────────────────────────────────────────────
    # user_storage_stats
    # ──────────────────────────────────────────────────────────────────────────
    op.create_table(
        'user_storage_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('used_storage_bytes', sa.BigInteger(), default=0),
        sa.Column('document_count', sa.Integer(), default=0),
        sa.Column('last_upload_at', sa.DateTime(), nullable=True),
        sa.Column('last_recalculated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )

    # ──────────────────────────────────────────────────────────────────────────
    # user_invites  (must exist before users.invite_id FK)
    # ──────────────────────────────────────────────────────────────────────────
    op.create_table(
        'user_invites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(64), nullable=False),
        sa.Column('email', sa.String(120), nullable=True),
        sa.Column('role_name', sa.String(80), nullable=True),
        sa.Column('plan_tier_id', sa.Integer(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('max_uses', sa.Integer(), default=1),
        sa.Column('use_count', sa.Integer(), default=0),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('used_by_id', sa.Integer(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['plan_tier_id'], ['plan_tiers.id']),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.ForeignKeyConstraint(['used_by_id'], ['users.id']),
        sa.ForeignKeyConstraint(['revoked_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index('ix_user_invites_token', 'user_invites', ['token'])

    # ──────────────────────────────────────────────────────────────────────────
    # password_history
    # ──────────────────────────────────────────────────────────────────────────
    op.create_table(
        'password_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_password_history_user_id', 'password_history', ['user_id'])

    # ──────────────────────────────────────────────────────────────────────────
    # user_sessions
    # ──────────────────────────────────────────────────────────────────────────
    op.create_table(
        'user_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_token_hash', sa.String(255), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(255), nullable=True),
        sa.Column('device_label', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['revoked_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_token_hash'),
    )
    op.create_index('ix_user_sessions_user_id', 'user_sessions', ['user_id'])
    op.create_index('ix_user_sessions_token_hash', 'user_sessions', ['session_token_hash'])

    # ──────────────────────────────────────────────────────────────────────────
    # global_integration_services
    # ──────────────────────────────────────────────────────────────────────────
    op.create_table(
        'global_integration_services',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('service_type', sa.String(50), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('scope', sa.String(20), default='user_personal'),
        sa.Column('is_enabled', sa.Boolean(), default=False),
        sa.Column('allow_user_override', sa.Boolean(), default=True),
        sa.Column('oauth2_client_id', sa.String(255), nullable=True),
        sa.Column('oauth2_client_secret_encrypted', sa.Text(), nullable=True),
        sa.Column('oauth2_scopes', sa.String(500), nullable=True),
        sa.Column('oauth2_auth_url', sa.String(500), nullable=True),
        sa.Column('oauth2_token_url', sa.String(500), nullable=True),
        sa.Column('oauth2_redirect_uri', sa.String(500), nullable=True),
        sa.Column('global_api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('global_extra_config', sa.Text(), nullable=True),
        sa.Column('last_tested_at', sa.DateTime(), nullable=True),
        sa.Column('last_test_ok', sa.Boolean(), nullable=True),
        sa.Column('last_test_error', sa.String(500), nullable=True),
        sa.Column('last_test_latency_ms', sa.Integer(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('connected_user_count', sa.Integer(), default=0),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_global_integration_services_type', 'global_integration_services',
                    ['service_type'])

    # ──────────────────────────────────────────────────────────────────────────
    # user_integration_credentials
    # ──────────────────────────────────────────────────────────────────────────
    op.create_table(
        'user_integration_credentials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('service_id', sa.Integer(), nullable=False),
        sa.Column('access_token_encrypted', sa.Text(), nullable=True),
        sa.Column('refresh_token_encrypted', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(), nullable=True),
        sa.Column('token_scopes', sa.String(500), nullable=True),
        sa.Column('api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('display_name', sa.String(200), nullable=True),
        sa.Column('connected_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('disconnected_at', sa.DateTime(), nullable=True),
        sa.Column('extra_data', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['service_id'], ['global_integration_services.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'service_id', name='uq_user_service_credential'),
    )
    op.create_index('ix_user_integration_credentials_user_id',
                    'user_integration_credentials', ['user_id'])

    # ──────────────────────────────────────────────────────────────────────────
    # ALTER users — add new columns (additive only)
    # ──────────────────────────────────────────────────────────────────────────
    with op.batch_alter_table('users') as batch_op:
        # Quota / plan tier
        batch_op.add_column(sa.Column('storage_quota_bytes', sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column('document_quota', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('plan_tier_id', sa.Integer(),
                                      sa.ForeignKey('plan_tiers.id'), nullable=True))
        # Invite
        batch_op.add_column(sa.Column('invite_id', sa.Integer(),
                                      sa.ForeignKey('user_invites.id'), nullable=True))
        # Lockout
        batch_op.add_column(sa.Column('failed_login_attempts', sa.Integer(), default=0))
        batch_op.add_column(sa.Column('locked_until', sa.DateTime(), nullable=True))
        # Password policy
        batch_op.add_column(sa.Column('password_changed_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('must_change_password', sa.Boolean(), default=False))
        # Profile
        batch_op.add_column(sa.Column('avatar_url', sa.String(255), nullable=True))
        batch_op.add_column(sa.Column('bio', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('phone_number', sa.String(30), nullable=True))
        batch_op.add_column(sa.Column('locale', sa.String(10), default='en'))
        batch_op.add_column(sa.Column('timezone', sa.String(50), default='UTC'))
        # MFA
        batch_op.add_column(sa.Column('mfa_enabled', sa.Boolean(), default=False))
        batch_op.add_column(sa.Column('mfa_methods', sa.String(100), default=''))
        batch_op.add_column(sa.Column('mfa_totp_secret', sa.String(64), nullable=True))
        batch_op.add_column(sa.Column('mfa_backup_codes_hash', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('mfa_backup_codes_remaining', sa.Integer(), default=0))
        batch_op.add_column(sa.Column('mfa_last_used_at', sa.DateTime(), nullable=True))

    # ──────────────────────────────────────────────────────────────────────────
    # ALTER tenants — add plan_tier_id
    # ──────────────────────────────────────────────────────────────────────────
    with op.batch_alter_table('tenants') as batch_op:
        batch_op.add_column(sa.Column('plan_tier_id', sa.Integer(),
                                      sa.ForeignKey('plan_tiers.id'), nullable=True))


def downgrade():
    # Remove new user columns
    with op.batch_alter_table('users') as batch_op:
        for col in [
            'storage_quota_bytes', 'document_quota', 'plan_tier_id', 'invite_id',
            'failed_login_attempts', 'locked_until', 'password_changed_at', 'must_change_password',
            'avatar_url', 'bio', 'phone_number', 'locale', 'timezone',
            'mfa_enabled', 'mfa_methods', 'mfa_totp_secret', 'mfa_backup_codes_hash',
            'mfa_backup_codes_remaining', 'mfa_last_used_at',
        ]:
            batch_op.drop_column(col)

    with op.batch_alter_table('tenants') as batch_op:
        batch_op.drop_column('plan_tier_id')

    op.drop_index('ix_user_integration_credentials_user_id', 'user_integration_credentials')
    op.drop_table('user_integration_credentials')

    op.drop_index('ix_global_integration_services_type', 'global_integration_services')
    op.drop_table('global_integration_services')

    op.drop_index('ix_user_sessions_token_hash', 'user_sessions')
    op.drop_index('ix_user_sessions_user_id', 'user_sessions')
    op.drop_table('user_sessions')

    op.drop_index('ix_password_history_user_id', 'password_history')
    op.drop_table('password_history')

    op.drop_index('ix_user_invites_token', 'user_invites')
    op.drop_table('user_invites')

    op.drop_table('user_storage_stats')
    op.drop_table('tenant_quotas')
    op.drop_table('plan_tiers')
