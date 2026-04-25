"""Add persisted metadata columns to Phase 1 feed recommendations.

Revision ID: add_phase1_feed_recommendation_metadata_20260413
Revises: add_phase1_ai_discovery_20260413
Create Date: 2026-04-13
"""

from alembic import op
import sqlalchemy as sa


revision = "add_phase1_feed_recommendation_metadata_20260413"
down_revision = "add_phase1_ai_discovery_20260413"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "feed_recommendations" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("feed_recommendations")}
    if "source_id" not in existing_columns:
        op.add_column("feed_recommendations", sa.Column("source_id", sa.String(length=255), nullable=True))
    if "url" not in existing_columns:
        op.add_column("feed_recommendations", sa.Column("url", sa.Text(), nullable=True))
    if "publication_date" not in existing_columns:
        op.add_column("feed_recommendations", sa.Column("publication_date", sa.String(length=40), nullable=True))
    if "doi" not in existing_columns:
        op.add_column("feed_recommendations", sa.Column("doi", sa.String(length=255), nullable=True))


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "feed_recommendations" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("feed_recommendations")}
    if "doi" in existing_columns:
        op.drop_column("feed_recommendations", "doi")
    if "publication_date" in existing_columns:
        op.drop_column("feed_recommendations", "publication_date")
    if "url" in existing_columns:
        op.drop_column("feed_recommendations", "url")
    if "source_id" in existing_columns:
        op.drop_column("feed_recommendations", "source_id")