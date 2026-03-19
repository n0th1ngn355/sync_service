"""Initial schema for sync service tables.

Revision ID: 20260319_01
Revises:
Create Date: 2026-03-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260319_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "paper",
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("authors", sa.Text(), nullable=True),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("categories", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="NEW", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "external_id", name="uq_paper_source_external_id"),
    )
    op.create_index("ix_paper_source", "paper", ["source"], unique=False)
    op.create_index("ix_paper_status", "paper", ["status"], unique=False)
    op.create_index("ix_paper_published_at", "paper", ["published_at"], unique=False)

    op.create_table(
        "scheduler_config",
        sa.Column("job_name", sa.String(length=128), nullable=False),
        sa.Column("cron_expression", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_status", sa.String(length=32), server_default="IDLE", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_name", name="uq_scheduler_config_job_name"),
    )

    op.create_table(
        "sync_state",
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("last_status", sa.String(length=32), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_run_started_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_finished_at", sa.DateTime(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_success_datestamp", sa.Date(), nullable=True),
        sa.Column("last_rows", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("total_rows", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", name="uq_sync_state_source"),
    )

    op.create_table(
        "paper_content",
        sa.Column("paper_id", sa.Integer(), nullable=False),
        sa.Column("full_text", sa.Text(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["paper_id"], ["paper.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("paper_id"),
    )
    op.create_index("ix_paper_content_paper_id", "paper_content", ["paper_id"], unique=True)

    op.create_table(
        "paper_file",
        sa.Column("paper_id", sa.Integer(), nullable=False),
        sa.Column("file_type", sa.String(length=16), server_default="PDF", nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["paper_id"], ["paper.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("paper_id", "file_type", name="uq_paper_file_type"),
    )
    op.create_index("ix_paper_file_paper_id", "paper_file", ["paper_id"], unique=False)

    op.create_table(
        "paper_source_meta",
        sa.Column("paper_id", sa.Integer(), nullable=False),
        sa.Column("source_meta", sa.JSON(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["paper_id"], ["paper.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("paper_id"),
    )
    op.create_index("ix_paper_source_meta_paper_id", "paper_source_meta", ["paper_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_paper_source_meta_paper_id", table_name="paper_source_meta")
    op.drop_table("paper_source_meta")

    op.drop_index("ix_paper_file_paper_id", table_name="paper_file")
    op.drop_table("paper_file")

    op.drop_index("ix_paper_content_paper_id", table_name="paper_content")
    op.drop_table("paper_content")

    op.drop_table("sync_state")
    op.drop_table("scheduler_config")

    op.drop_index("ix_paper_published_at", table_name="paper")
    op.drop_index("ix_paper_status", table_name="paper")
    op.drop_index("ix_paper_source", table_name="paper")
    op.drop_table("paper")
