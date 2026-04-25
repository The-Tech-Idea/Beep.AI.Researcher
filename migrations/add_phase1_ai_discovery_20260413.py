"""Add Phase 1 AI discovery models.

Revision ID: add_phase1_ai_discovery_20260413
Revises: add_phase05_collab_export_20260412
Create Date: 2026-04-13

Adds additive tables for:
- research_interest_profiles
- feed_recommendations
- reading_list_items
- paper_alerts
"""

from alembic import op
import sqlalchemy as sa


revision = "add_phase1_ai_discovery_20260413"
down_revision = "add_phase05_collab_export_20260412"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()

    if "research_interest_profiles" not in existing_tables:
        op.create_table(
            "research_interest_profiles",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("declared_topics", sa.JSON(), nullable=False),
            sa.Column("inferred_topics", sa.JSON(), nullable=False),
            sa.Column("preferred_sources", sa.JSON(), nullable=False),
            sa.Column("inference_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", name="uq_research_interest_profiles_user_id"),
        )
        op.create_index(
            "ix_research_interest_profiles_user_id",
            "research_interest_profiles",
            ["user_id"],
        )

    if "feed_recommendations" not in existing_tables:
        op.create_table(
            "feed_recommendations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("external_id", sa.String(length=255), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("authors", sa.JSON(), nullable=False),
            sa.Column("abstract", sa.Text(), nullable=True),
            sa.Column("source", sa.String(length=50), nullable=False),
            sa.Column("relevance_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("dismissed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("saved", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("feed_date", sa.Date(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sqlite_autoincrement=True,
        )
        op.create_index("ix_feed_recommendations_user_id", "feed_recommendations", ["user_id"])
        op.create_index("ix_feed_recommendations_feed_date", "feed_recommendations", ["feed_date"])
        op.create_index(
            "ix_feed_recommendations_user_date_dismissed",
            "feed_recommendations",
            ["user_id", "feed_date", "dismissed"],
        )

    if "reading_list_items" not in existing_tables:
        op.create_table(
            "reading_list_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "reference_id",
                sa.Integer(),
                sa.ForeignKey("references.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("external_id", sa.String(length=255), nullable=True),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="unread"),
            sa.Column("topic_tags", sa.JSON(), nullable=False),
            sa.Column("saved_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_reading_list_items_user_id", "reading_list_items", ["user_id"])
        op.create_index(
            "ix_reading_list_items_user_status",
            "reading_list_items",
            ["user_id", "status"],
        )

    if "paper_alerts" not in existing_tables:
        op.create_table(
            "paper_alerts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("external_id", sa.String(length=255), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("source", sa.String(length=50), nullable=False),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("alert_date", sa.Date(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_paper_alerts_user_id", "paper_alerts", ["user_id"])
        op.create_index("ix_paper_alerts_alert_date", "paper_alerts", ["alert_date"])
        op.create_index(
            "ix_paper_alerts_user_read_date",
            "paper_alerts",
            ["user_id", "is_read", "alert_date"],
        )


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()

    if "paper_alerts" in existing_tables:
        op.drop_index("ix_paper_alerts_user_read_date", table_name="paper_alerts")
        op.drop_index("ix_paper_alerts_alert_date", table_name="paper_alerts")
        op.drop_index("ix_paper_alerts_user_id", table_name="paper_alerts")
        op.drop_table("paper_alerts")

    if "reading_list_items" in existing_tables:
        op.drop_index("ix_reading_list_items_user_status", table_name="reading_list_items")
        op.drop_index("ix_reading_list_items_user_id", table_name="reading_list_items")
        op.drop_table("reading_list_items")

    if "feed_recommendations" in existing_tables:
        op.drop_index("ix_feed_recommendations_user_date_dismissed", table_name="feed_recommendations")
        op.drop_index("ix_feed_recommendations_feed_date", table_name="feed_recommendations")
        op.drop_index("ix_feed_recommendations_user_id", table_name="feed_recommendations")
        op.drop_table("feed_recommendations")

    if "research_interest_profiles" in existing_tables:
        op.drop_index("ix_research_interest_profiles_user_id", table_name="research_interest_profiles")
        op.drop_table("research_interest_profiles")