"""initial schema

Revision ID: 20260507_0001
Revises:
Create Date: 2026-05-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

revision: str = "20260507_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Idempotent enum creation (survives partial runs / orphaned types without alembic_version).
    op.execute(
        text(
            """
            DO $$ BEGIN
                CREATE TYPE userrole AS ENUM ('user', 'admin');
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )
    op.execute(
        text(
            """
            DO $$ BEGIN
                CREATE TYPE jobstatus AS ENUM ('pending', 'processing', 'succeeded', 'failed');
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )
    op.execute(
        text(
            """
            DO $$ BEGIN
                CREATE TYPE transactiontype AS ENUM (
                    'prediction_charge', 'payment_credit', 'adjustment'
                );
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )

    userrole = postgresql.ENUM("user", "admin", name="userrole", create_type=False)
    jobstatus = postgresql.ENUM(
        "pending", "processing", "succeeded", "failed", name="jobstatus", create_type=False
    )
    txtype = postgresql.ENUM(
        "prediction_charge",
        "payment_credit",
        "adjustment",
        name="transactiontype",
        create_type=False,
    )

    op.create_table(
        "loyalty_tiers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("min_predictions_monthly", sa.Integer(), nullable=False),
        sa.Column("discount_percent", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", userrole, nullable=False),
        sa.Column("balance_credits", sa.Integer(), nullable=False),
        sa.Column("loyalty_tier_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["loyalty_tier_id"], ["loyalty_tiers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "ml_models",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("storage_filename", sa.String(length=512), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "prediction_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("status", jobstatus, nullable=False),
        sa.Column("input_features", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("base_cost", sa.Integer(), nullable=False),
        sa.Column("discount_percent_applied", sa.Integer(), nullable=False),
        sa.Column("credits_charged", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["model_id"], ["ml_models.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "credit_transactions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("tx_type", txtype, nullable=False),
        sa.Column("reference_type", sa.String(length=64), nullable=True),
        sa.Column("reference_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference_type", "reference_id", name="uq_credit_tx_reference"),
    )

    op.create_table(
        "billing_config",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )

    op.execute(
        text(
            """
            INSERT INTO loyalty_tiers (id, name, min_predictions_monthly, discount_percent, sort_order)
            VALUES
            (1, 'Bronze', 0, 0, 0),
            (2, 'Silver', 10, 5, 1),
            (3, 'Gold', 50, 10, 2)
            """
        )
    )
    op.execute(
        text(
            "INSERT INTO billing_config (key, value) VALUES ('prediction_base_cost_credits', '10')"
        )
    )
    op.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('loyalty_tiers', 'id'), "
            "(SELECT COALESCE(MAX(id), 1) FROM loyalty_tiers))"
        )
    )


def downgrade() -> None:
    op.drop_table("billing_config")
    op.drop_table("credit_transactions")
    op.drop_table("prediction_jobs")
    op.drop_table("ml_models")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_table("loyalty_tiers")
    bind = op.get_bind()
    postgresql.ENUM(name="transactiontype").drop(bind, checkfirst=True)
    postgresql.ENUM(name="jobstatus").drop(bind, checkfirst=True)
    postgresql.ENUM(name="userrole").drop(bind, checkfirst=True)
