"""Add new columns in user table for first time

Revision ID: 3eec99c48447
Revises: 
Create Date: 2025-09-14 20:04:31.298168

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import uuid


# revision identifiers, used by Alembic.
revision: str = '3eec99c48447'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
op.create_table(
        'phoneusers',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('phoneNumber', sa.String(length=32), nullable=False),

        sa.Column('country_iso2', sa.String(length=2), nullable=False, server_default='--'),
        sa.Column('country_name', sa.String(length=100), nullable=False, server_default='Unknown'),
        sa.Column('country_dial_code', sa.String(length=6), nullable=False, server_default='+++'),
        sa.Column('operator_name', sa.String(length=100), nullable=False, server_default='Unknown'),

        sa.Column('createdOn', sa.DateTime(timezone=True), server_default=sa.func.now()),

        sa.Column('registration_status', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('last_registration_status_change', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),

        sa.Column('call_direction', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('last_call_direction_change', sa.DateTime(timezone=True), nullable=True),

        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('user_role', sa.String(length=50), server_default=sa.text("'basic'"), nullable=False),

        sa.Column('last_login_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_logout_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_type', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('automatic_mode', sa.Boolean(), server_default=sa.text('false'), nullable=False),

        sa.Column('device_uuid', sa.dialects.postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), unique=True, nullable=False),
        sa.Column('last_login_ip', sa.String(length=45), nullable=True)
    )



def downgrade() -> None:
    """Downgrade schema."""
    # op.drop_column('phoneusers', 'id')
    # op.drop_column('phoneusers', 'phoneNumber')
    # op.drop_column('phoneusers', 'createdOn')
    # op.drop_column('phoneusers', 'automatic_mode')
    # op.drop_column('phoneusers', 'last_login_ip')
    # op.drop_column('phoneusers', 'device_uuid')
    # op.drop_column('phoneusers', 'user_type')
    # op.drop_column('phoneusers', 'last_logout_date')
    # op.drop_column('phoneusers', 'last_login_date')
    # op.drop_column('phoneusers', 'user_role')
    # op.drop_column('phoneusers', 'hashed_password')
    # op.drop_column('phoneusers', 'last_call_direction_change')
    # op.drop_column('phoneusers', 'call_direction')
    # op.drop_column('phoneusers', 'last_registration_status_change')
    # op.drop_column('phoneusers', 'registration_status')
    # op.drop_column('phoneusers', 'operator_name')
    # op.drop_column('phoneusers', 'country_dial_code')
    # op.drop_column('phoneusers', 'country_name')
    # op.drop_column('phoneusers', 'country_iso2')
