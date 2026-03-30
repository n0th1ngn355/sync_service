"""Drop legacy users feature table.

Revision ID: 20260330_01
Revises: e7d8ad7af0b6
Create Date: 2026-03-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260330_01"
down_revision: Union[str, None] = "e7d8ad7af0b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove users table introduced by legacy feature."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_names = set(inspector.get_table_names())
    if "users" not in table_names:
        return

    index_names = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_telegram_id" in index_names:
        op.drop_index("ix_users_telegram_id", table_name="users")

    op.drop_table("users")


def downgrade() -> None:
    """Restore users table and unique index for rollback."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_names = set(inspector.get_table_names())
    if "users" not in table_names:
        op.create_table(
            "users",
            sa.Column("telegram_id", sa.BigInteger(), nullable=False),
            sa.Column("username", sa.String(length=255), nullable=True),
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        inspector = sa.inspect(bind)

    index_names = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_telegram_id" not in index_names:
        op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)
