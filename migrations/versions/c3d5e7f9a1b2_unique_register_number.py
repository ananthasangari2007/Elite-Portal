"""Enforce unique register numbers (safe, non-destructive).

The unique index is only created when the existing data has no duplicate register
numbers. If duplicates exist the migration leaves the schema unchanged and prints the
number of conflicting values, so an administrator can resolve them and re-run
``python -m app.cli db-upgrade`` after ``db-downgrade 5b8f1d2a4e90``. The API also
rejects duplicates at registration/profile update regardless of this index.

Revision ID: c3d5e7f9a1b2
Revises: 5b8f1d2a4e90
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d5e7f9a1b2"
down_revision = "5b8f1d2a4e90"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_user_register_number"


def _index_exists(bind) -> bool:
    return any(ix["name"] == INDEX_NAME for ix in sa.inspect(bind).get_indexes("user"))


def upgrade():
    bind = op.get_bind()
    if _index_exists(bind):
        return
    duplicates = bind.execute(
        sa.text(
            'SELECT COUNT(*) FROM (SELECT register_number FROM "user" '
            "WHERE register_number IS NOT NULL AND register_number <> '' "
            "GROUP BY register_number HAVING COUNT(*) > 1) d"
        )
    ).scalar()
    if duplicates:
        print(
            f"[elite-portal] Skipping {INDEX_NAME}: {duplicates} register number(s) are used by more than "
            "one account. Resolve them, then re-run this migration."
        )
        return
    op.create_index(INDEX_NAME, "user", ["register_number"], unique=True)


def downgrade():
    bind = op.get_bind()
    if _index_exists(bind):
        op.drop_index(INDEX_NAME, table_name="user")
