from fastapi import APIRouter, Depends, HTTPException, status

from opname360.api.deps import verify_same_origin
from opname360.api.routes import (
    activity_log,
    auth,
    categories,
    counting,
    employee_charges,
    goods_receipts,
    health,
    opnames,
    payment_methods,
    production_receipts,
    products,
    promotions,
    receipts,
    shifts,
    shop_settings,
    stock,
    supplier_returns,
    suppliers,
    users,
)


api_router = APIRouter(
    prefix='/api/v1', dependencies=[Depends(verify_same_origin)]
)
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(categories.router)
api_router.include_router(products.router)
api_router.include_router(suppliers.router)
api_router.include_router(goods_receipts.router)
api_router.include_router(production_receipts.router)
api_router.include_router(supplier_returns.router)
api_router.include_router(stock.router)
api_router.include_router(opnames.router)
api_router.include_router(counting.router)
api_router.include_router(employee_charges.router)
api_router.include_router(shop_settings.router)
api_router.include_router(payment_methods.router)
api_router.include_router(shifts.router)
api_router.include_router(receipts.router)
api_router.include_router(promotions.router)
api_router.include_router(activity_log.router)


# Last on purpose: without it an unknown API path would fall through to the
# frontend and answer with index.html.
@api_router.get('/{path:path}', include_in_schema=False)
def api_not_found(path: str) -> None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
