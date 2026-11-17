from fastapi import APIRouter, Depends

from opname360.api.deps import OwnerDep, SessionDep, get_current_user
from opname360.models import ShopSettings, ShopSettingsPublic, ShopSettingsSave
from opname360.services import shop_settings


router = APIRouter(
    prefix='/shop-settings',
    tags=['shop_settings'],
    dependencies=[Depends(get_current_user)],
)


@router.get('/', response_model=ShopSettingsPublic)
def read_settings(session: SessionDep) -> ShopSettings:
    """Everyone reads them: the till prints them on Receipts."""
    return shop_settings.get_settings(session)


@router.put('/', response_model=ShopSettingsPublic)
def save_settings(
    session: SessionDep, owner: OwnerDep, settings_in: ShopSettingsSave
) -> ShopSettings:
    return shop_settings.save_settings(session, settings_in, actor=owner)
