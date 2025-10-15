"""Add new columns in user table for first time

Revision ID: 3eec99c48447
Revises: 
Create Date: 2025-09-14 20:04:31.298168

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3eec99c48447'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        'phoneusers', sa.Column('country_iso2',
                                sa.String(length=2), nullable=False, )
    )

    op.add_column(
        'phoneusers', sa.Column('country_name',
                                sa.String(length=100), nullable=False, )
    )

    op.add_column(
        'phoneusers', sa.Column('country_dial_code',
                                sa.String(length=6), nullable=False, )
    )

    op.add_column('phoneusers', sa.Column('subscription_status',
                   sa.Boolean(), server_default=sa.text('true'), nullable=False))

    # UTC datetime with default now()
    op.add_column(
        'phoneusers', sa.Column('last_subs_status_change_date',
            sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False,)
    )

    # Boolean default false
    op.add_column(
        'phoneusers', sa.Column('ob_readiness',
            sa.Boolean(), server_default=sa.text('false'), nullable=False,)
    )

    # Datetime nullable, no default (NULL by default)
    op.add_column(
        'phoneusers', sa.Column('last_ob_readiness_date',
            sa.DateTime(timezone=True), nullable=True,)
    )

    # Boolean default false
    op.add_column(
        'phoneusers', sa.Column('ib_readiness',
            sa.Boolean(), server_default=sa.text('false'), nullable=False,)
    )

    # Datetime nullable, no default
    op.add_column(
        'phoneusers',
        sa.Column('last_ib_readiness_date', sa.DateTime(timezone=True), nullable=True,)
    )

    # String (VARCHAR) for hashed password
    op.add_column(
        'phoneusers', sa.Column('hashed_password',
            sa.String(length=255), nullable=False,)
    )

    # New column for user role
    op.add_column(
        'phoneusers', sa.Column('user_role',
            sa.String(length=50), server_default=sa.text("'basic'"), nullable=False,)
    )

    # Last login datetime
    op.add_column(
        'phoneusers', sa.Column('last_login_date',
                  sa.DateTime(timezone=True), nullable=True)
    )

    # Last logout datetime
    op.add_column(
        'phoneusers', sa.Column('last_logout_date',
                  sa.DateTime(timezone=True), nullable=True)
    )

    # User type (int)
    op.add_column(
        'phoneusers', sa.Column('user_type',
                  sa.Integer(), server_default=sa.text('0'), nullable=False)
    )

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('phoneusers', 'subscription_status')
    op.drop_column('phoneusers', 'hashed_password')
    op.drop_column('phoneusers', 'last_ib_readiness_date')
    op.drop_column('phoneusers', 'ib_readiness')
    op.drop_column('phoneusers', 'last_ob_readiness_date')
    op.drop_column('phoneusers', 'ob_readiness')
    op.drop_column('phoneusers', 'last_subs_status_change_date')
    op.drop_column('phoneusers', 'user_role')
    op.drop_column('phoneusers', 'country_iso2')
    op.drop_column('phoneusers', 'country_name')
    op.drop_column('phoneusers', 'country_dial_code')
    op.drop_column('phoneusers', 'last_login_date')
    op.drop_column('phoneusers', 'last_logout_date')
    op.drop_column('phoneusers', 'user_type')
