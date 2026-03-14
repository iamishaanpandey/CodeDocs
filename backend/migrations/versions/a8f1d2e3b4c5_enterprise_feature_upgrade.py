"""Enterprise Feature Upgrade — pgvector, RBAC, webhook, audit log, PR analysis

Revision ID: a8f1d2e3b4c5
Revises: a75bc3fa0c4a
Create Date: 2026-03-14

This migration adds all columns and tables required for the 7 enterprise
work streams: RAG embeddings, RBAC roles, zombie detection metrics,
webhook tracking, audit logging, and PR analysis persistence.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'a8f1d2e3b4c5'
down_revision = 'a75bc3fa0c4a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enable pgvector extension ────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # ── documentations table: embedding + context columns ───────────────────
    op.add_column('documentations', sa.Column('source_code_snippet', sa.Text(), nullable=True))
    op.add_column('documentations', sa.Column('git_blame_summary', sa.Text(), nullable=True))
    op.add_column('documentations', sa.Column('embedding_model', sa.String(), nullable=True))
    # Add the embedding vector column (768 dimensions for Gemini text-embedding-004)
    op.execute("ALTER TABLE documentations ADD COLUMN IF NOT EXISTS embedding vector(768);")
    # Create IVFFlat index for fast cosine similarity search
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_doc_embedding "
        "ON documentations USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
    )

    # ── repositories table: enterprise tracking columns ──────────────────────
    op.add_column('repositories', sa.Column('zombie_code_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('repositories', sa.Column('embedding_status', sa.String(), nullable=False, server_default='not_embedded'))
    op.add_column('repositories', sa.Column('webhook_id', sa.String(), nullable=True))
    op.add_column('repositories', sa.Column('auto_scan_on_push', sa.Boolean(), nullable=False, server_default='true'))

    # ── users table: RBAC role ────────────────────────────────────────────────
    op.add_column('users', sa.Column('role', sa.String(), nullable=False, server_default='member'))

    # ── audit_logs table ─────────────────────────────────────────────────────
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=True),
        sa.Column('resource_id', sa.String(), nullable=True),
        sa.Column('details', postgresql.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'))
    )
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])

    # ── pr_analyses table ────────────────────────────────────────────────────
    op.create_table(
        'pr_analyses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('pr_number', sa.Integer(), nullable=True),
        sa.Column('pr_url', sa.String(), nullable=True),
        sa.Column('diff_text', sa.Text(), nullable=True),
        sa.Column('risk_level', sa.String(), nullable=False, server_default='LOW'),
        sa.Column('affected_function_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('untested_function_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('affected_functions', postgresql.JSON(), nullable=True),
        sa.Column('mermaid_markup', sa.Text(), nullable=True),
        sa.Column('summary_markdown', sa.Text(), nullable=True),
        sa.Column('github_comment_id', sa.String(), nullable=True),
        sa.Column('comment_posted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'))
    )
    op.create_index('ix_pr_analyses_repository_id', 'pr_analyses', ['repository_id'])
    op.create_index('ix_pr_analyses_pr_number', 'pr_analyses', ['pr_number'])


def downgrade() -> None:
    # Drop new tables
    op.drop_table('pr_analyses')
    op.drop_table('audit_logs')

    # Drop new columns
    op.drop_column('users', 'role')
    op.drop_column('repositories', 'auto_scan_on_push')
    op.drop_column('repositories', 'webhook_id')
    op.drop_column('repositories', 'embedding_status')
    op.drop_column('repositories', 'zombie_code_count')
    op.drop_column('documentations', 'embedding_model')
    op.drop_column('documentations', 'git_blame_summary')
    op.drop_column('documentations', 'source_code_snippet')
    op.execute("ALTER TABLE documentations DROP COLUMN IF EXISTS embedding;")
    op.execute("DROP INDEX IF EXISTS ix_doc_embedding;")
