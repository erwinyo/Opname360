from sqlmodel import Session

from opname360.models import ShopSettings, ShopSettingsSave, User
from opname360.services import activity_log


def get_settings(session: Session) -> ShopSettings:
    """The one settings row, seeded by the migration."""
    settings = session.get(ShopSettings, 1)
    assert settings is not None
    return settings


def save_settings(
    session: Session, settings_in: ShopSettingsSave, *, actor: User
) -> ShopSettings:
    settings = get_settings(session)
    settings.sqlmodel_update(
        {
            **settings_in.model_dump(),
            'name': settings_in.name.strip(),
            'address': (settings_in.address or '').strip() or None,
            'receipt_footer': (settings_in.receipt_footer or '').strip()
            or None,
        }
    )
    session.add(settings)
    activity_log.record(
        session,
        actor=actor,
        action='shop_settings.update',
        summary=(
            f'Mengubah pengaturan toko (batas retur '
            f'{settings.return_window_days} hari).'
        ),
        entity_type='shop_settings',
        entity_id=settings.id,
    )
    session.commit()
    return settings
