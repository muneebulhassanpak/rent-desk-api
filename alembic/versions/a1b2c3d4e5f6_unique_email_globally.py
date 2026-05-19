"""make user email globally unique

Revision ID: a1b2c3d4e5f6
Revises: 60838e30c196
Create Date: 2026-05-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "60838e30c196"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("users_org_id_email_key", "users", type_="unique")
    op.create_unique_constraint("uq_users_email", "users", ["email"])


def downgrade() -> None:
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.create_unique_constraint("users_org_id_email_key", "users", ["org_id", "email"])
