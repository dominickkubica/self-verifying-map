"""HTTP API for orders."""

from shop.storage import db

router = APIRouter(prefix="/orders")  # noqa: F821 - a fixture, never imported


def _load(conn, order_id):
    return db.fetch_order(conn, order_id)


@router.get("/{order_id}")
def get_order(order_id: int):
    return _load(None, order_id)


@router.post("/")
async def create_order(order: dict):
    db.save_order(None, order)
