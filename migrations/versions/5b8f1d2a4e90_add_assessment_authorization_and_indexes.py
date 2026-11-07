"""add assessment authorization and composite indexes

Revision ID: 5b8f1d2a4e90
Revises: 10f07532ee3a
Create Date: 2026-10-22 11:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5b8f1d2a4e90'
down_revision = '10f07532ee3a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'assessment_authorization',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=True),
        sa.Column('authorized_by', sa.Integer(), nullable=False),
        sa.Column('authorization_type', sa.String(length=50), nullable=False, server_default='student_unlock'),
        sa.Column('extra_attempts', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('valid_until', sa.DateTime(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessment.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['authorized_by'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('assessment_authorization', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_assessment_authorization_assessment_id'), ['assessment_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_assessment_authorization_student_id'), ['student_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_assessment_authorization_authorized_by'), ['authorized_by'], unique=False)

    # High frequency composite indexes
    with op.batch_alter_table('point_ledger', schema=None) as batch_op:
        batch_op.create_index('ix_point_ledger_student_domain', ['student_id', 'domain_id'], unique=False)

    with op.batch_alter_table('student_domain_enrollment', schema=None) as batch_op:
        batch_op.create_index('ix_student_domain_enrollment_student_active', ['student_id', 'is_active'], unique=False)


def downgrade():
    with op.batch_alter_table('student_domain_enrollment', schema=None) as batch_op:
        batch_op.drop_index('ix_student_domain_enrollment_student_active')

    with op.batch_alter_table('point_ledger', schema=None) as batch_op:
        batch_op.drop_index('ix_point_ledger_student_domain')

    with op.batch_alter_table('assessment_authorization', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_assessment_authorization_authorized_by'))
        batch_op.drop_index(batch_op.f('ix_assessment_authorization_student_id'))
        batch_op.drop_index(batch_op.f('ix_assessment_authorization_assessment_id'))

    op.drop_table('assessment_authorization')
