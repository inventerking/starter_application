"""initial client schema

Revision ID: 0001
Revises: 

Use the SCHEMA constant, never a literal schema name, so migrations stay testable.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.core.database import SCHEMA

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('audit_logs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('actor_type', sa.String(length=32), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=True),
    sa.Column('target_type', sa.String(length=32), nullable=True),
    sa.Column('target_id', sa.Uuid(), nullable=True),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('user_agent', sa.String(length=512), nullable=True),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_logs')),
    schema=SCHEMA
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False, schema=SCHEMA)
    op.create_index('ix_audit_logs_actor', 'audit_logs', ['actor_id'], unique=False, schema=SCHEMA)
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'], unique=False, schema=SCHEMA)
    op.create_index('ix_audit_logs_target', 'audit_logs', ['target_type', 'target_id'], unique=False, schema=SCHEMA)
    op.create_table('permissions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('resource', sa.String(length=64), nullable=False),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('code', sa.String(length=128), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('deprecated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_permissions')),
    sa.UniqueConstraint('code', name=op.f('uq_permissions_code')),
    sa.UniqueConstraint('resource', 'action', name=op.f('uq_permissions_resource_action')),
    schema=SCHEMA
    )
    op.create_table('rate_limit_counters',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('window_started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.PrimaryKeyConstraint('key', name=op.f('pk_rate_limit_counters')),
    schema=SCHEMA
    )
    op.create_index('ix_rate_limit_counters_window', 'rate_limit_counters', ['window_started_at'], unique=False, schema=SCHEMA)
    op.create_table('roles',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('is_system', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('is_default', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_roles')),
    schema=SCHEMA
    )
    op.create_index('uq_roles_name', 'roles', [sa.literal_column('lower(name)')], unique=True, schema=SCHEMA)
    op.create_table('users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('full_name', sa.String(length=128), nullable=True),
    sa.Column('password_hash', sa.Text(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('must_change_password', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('mfa_enabled', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('mfa_secret_encrypted', sa.Text(), nullable=True),
    sa.Column('mfa_key_id', sa.String(length=32), nullable=True),
    sa.Column('mfa_confirmed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('mfa_last_used_step', sa.BigInteger(), nullable=True),
    sa.Column('failed_login_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    schema=SCHEMA
    )
    op.create_index('uq_users_email_active', 'users', [sa.literal_column('lower(email)')], unique=True, schema=SCHEMA, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_index('uq_users_username_active', 'users', [sa.literal_column('lower(username)')], unique=True, schema=SCHEMA, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_table('mfa_challenges',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], [f'{SCHEMA}.users.id'], name=op.f('fk_mfa_challenges_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_mfa_challenges')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_mfa_challenges_token_hash')),
    schema=SCHEMA
    )
    op.create_index(op.f('ix_mfa_challenges_user_id'), 'mfa_challenges', ['user_id'], unique=False, schema=SCHEMA)
    op.create_table('mfa_recovery_codes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('code_hash', sa.Text(), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], [f'{SCHEMA}.users.id'], name=op.f('fk_mfa_recovery_codes_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_mfa_recovery_codes')),
    schema=SCHEMA
    )
    op.create_index(op.f('ix_mfa_recovery_codes_user_id'), 'mfa_recovery_codes', ['user_id'], unique=False, schema=SCHEMA)
    op.create_table('password_reset_tokens',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], [f'{SCHEMA}.users.id'], name=op.f('fk_password_reset_tokens_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_password_reset_tokens')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_password_reset_tokens_token_hash')),
    schema=SCHEMA
    )
    op.create_index(op.f('ix_password_reset_tokens_user_id'), 'password_reset_tokens', ['user_id'], unique=False, schema=SCHEMA)
    op.create_table('role_permissions',
    sa.Column('role_id', sa.Uuid(), nullable=False),
    sa.Column('permission_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['permission_id'], [f'{SCHEMA}.permissions.id'], name=op.f('fk_role_permissions_permission_id_permissions'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['role_id'], [f'{SCHEMA}.roles.id'], name=op.f('fk_role_permissions_role_id_roles'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('role_id', 'permission_id', name=op.f('pk_role_permissions')),
    schema=SCHEMA
    )
    op.create_table('sessions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('scope', sa.String(length=32), nullable=False),
    sa.Column('access_token_hash', sa.String(length=64), nullable=False),
    sa.Column('access_expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('previous_access_token_hash', sa.String(length=64), nullable=True),
    sa.Column('previous_access_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoke_reason', sa.String(length=64), nullable=True),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('user_agent', sa.String(length=512), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("scope IN ('full', 'mfa_enrollment')", name=op.f('ck_sessions_scope')),
    sa.ForeignKeyConstraint(['user_id'], [f'{SCHEMA}.users.id'], name=op.f('fk_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sessions')),
    sa.UniqueConstraint('access_token_hash', name=op.f('uq_sessions_access_token_hash')),
    schema=SCHEMA
    )
    op.create_index(op.f('ix_sessions_previous_access_token_hash'), 'sessions', ['previous_access_token_hash'], unique=False, schema=SCHEMA)
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'], unique=False, schema=SCHEMA)
    op.create_table('user_permissions',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('permission_id', sa.Uuid(), nullable=False),
    sa.Column('effect', sa.String(length=8), nullable=False),
    sa.Column('reason', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("effect IN ('ALLOW', 'DENY')", name=op.f('ck_user_permissions_effect')),
    sa.ForeignKeyConstraint(['permission_id'], [f'{SCHEMA}.permissions.id'], name=op.f('fk_user_permissions_permission_id_permissions'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], [f'{SCHEMA}.users.id'], name=op.f('fk_user_permissions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'permission_id', name=op.f('pk_user_permissions')),
    schema=SCHEMA
    )
    op.create_table('user_roles',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('role_id', sa.Uuid(), nullable=False),
    sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['role_id'], [f'{SCHEMA}.roles.id'], name=op.f('fk_user_roles_role_id_roles'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], [f'{SCHEMA}.users.id'], name=op.f('fk_user_roles_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'role_id', name=op.f('pk_user_roles')),
    schema=SCHEMA
    )
    op.create_table('refresh_tokens',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('session_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], [f'{SCHEMA}.sessions.id'], name=op.f('fk_refresh_tokens_session_id_sessions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_refresh_tokens')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_refresh_tokens_token_hash')),
    schema=SCHEMA
    )
    op.create_index(op.f('ix_refresh_tokens_session_id'), 'refresh_tokens', ['session_id'], unique=False, schema=SCHEMA)

    op.execute(f"""
        CREATE FUNCTION "{SCHEMA}".audit_logs_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute(f"""
        CREATE TRIGGER audit_logs_append_only
        BEFORE UPDATE OR DELETE ON "{SCHEMA}".audit_logs
        FOR EACH ROW EXECUTE FUNCTION "{SCHEMA}".audit_logs_append_only()
    """)


def downgrade() -> None:
    op.execute(f'DROP TRIGGER audit_logs_append_only ON "{SCHEMA}".audit_logs')
    op.execute(f'DROP FUNCTION "{SCHEMA}".audit_logs_append_only()')
    op.drop_index(op.f('ix_refresh_tokens_session_id'), table_name='refresh_tokens', schema=SCHEMA)
    op.drop_table('refresh_tokens', schema=SCHEMA)
    op.drop_table('user_roles', schema=SCHEMA)
    op.drop_table('user_permissions', schema=SCHEMA)
    op.drop_index(op.f('ix_sessions_user_id'), table_name='sessions', schema=SCHEMA)
    op.drop_index(op.f('ix_sessions_previous_access_token_hash'), table_name='sessions', schema=SCHEMA)
    op.drop_table('sessions', schema=SCHEMA)
    op.drop_table('role_permissions', schema=SCHEMA)
    op.drop_index(op.f('ix_password_reset_tokens_user_id'), table_name='password_reset_tokens', schema=SCHEMA)
    op.drop_table('password_reset_tokens', schema=SCHEMA)
    op.drop_index(op.f('ix_mfa_recovery_codes_user_id'), table_name='mfa_recovery_codes', schema=SCHEMA)
    op.drop_table('mfa_recovery_codes', schema=SCHEMA)
    op.drop_index(op.f('ix_mfa_challenges_user_id'), table_name='mfa_challenges', schema=SCHEMA)
    op.drop_table('mfa_challenges', schema=SCHEMA)
    op.drop_index('uq_users_username_active', table_name='users', schema=SCHEMA, postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index('uq_users_email_active', table_name='users', schema=SCHEMA, postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_table('users', schema=SCHEMA)
    op.drop_index('uq_roles_name', table_name='roles', schema=SCHEMA)
    op.drop_table('roles', schema=SCHEMA)
    op.drop_index('ix_rate_limit_counters_window', table_name='rate_limit_counters', schema=SCHEMA)
    op.drop_table('rate_limit_counters', schema=SCHEMA)
    op.drop_table('permissions', schema=SCHEMA)
    op.drop_index('ix_audit_logs_target', table_name='audit_logs', schema=SCHEMA)
    op.drop_index('ix_audit_logs_created_at', table_name='audit_logs', schema=SCHEMA)
    op.drop_index('ix_audit_logs_actor', table_name='audit_logs', schema=SCHEMA)
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs', schema=SCHEMA)
    op.drop_table('audit_logs', schema=SCHEMA)
