"""Inventory reads and requests; stock stays unchanged until separate human fulfillment."""

from database import one, rows
from services.common import operation, require, self_access, role, pending


def check_item(item_id, quantity):
    require(
        isinstance(quantity, int) and not isinstance(quantity, bool) and quantity > 0,
        "Quantity must be a positive integer.",
    )
    item = one("SELECT * FROM inventory_items WHERE id=?", (item_id,))
    require(item is not None, "Inventory item not found.", "not_found")
    require(
        quantity <= item["request_limit"], "Quantity exceeds the per-request limit."
    )
    require(quantity <= item["quantity"], "Insufficient stock.")
    return item


@operation("inventory")
def check_inventory(item_name: str) -> dict:
    """Read available stock by exact item name, e.g. laptops or mice."""
    role("employee", "manager", "hr", "finance")
    r = one(
        "SELECT id item_id,name,quantity quantity_available FROM inventory_items WHERE lower(name)=lower(?)",
        (item_name.strip(),),
    )
    require(r is not None, "Item not found.", "not_found")
    return r


@operation("inventory", write=True)
def request_inventory_item(employee_id: str, item_id: str, quantity: int) -> dict:
    """Submit own inventory request after checking positive quantity, limits and stock. Does not reserve stock."""
    p = self_access(employee_id)
    require(p["status"] == "active", "Employee must be active.")
    check_item(item_id, quantity)
    return pending(
        "inventory",
        employee_id,
        {
            "item_id": item_id,
            "quantity": quantity,
            "stock_policy": "No reservation or deduction until separate human fulfillment.",
        },
    )


@operation("inventory")
def get_low_stock_items() -> dict:
    """List items whose available stock is at or below their configured reorder threshold."""
    role("employee", "manager", "finance")
    return {
        "items": rows("SELECT * FROM inventory_items WHERE quantity<=reorder_threshold")
    }


@operation("inventory")
def check_inventory_request(item_id: str, quantity: int) -> dict:
    """Check quantity, request limit and available stock without creating a request."""
    role("employee", "manager", "finance")
    item = check_item(item_id, quantity)
    return {
        "eligible": True,
        "item_id": item_id,
        "requested_quantity": quantity,
        "available_quantity": item["quantity"],
        "request_limit": item["request_limit"],
    }


@operation("inventory")
def get_restock_status(item_id: str) -> dict:
    """Retrieve known pending purchase-order dates; never estimate an unknown arrival."""
    role("employee", "manager", "finance")
    require(
        one("SELECT id FROM inventory_items WHERE id=?", (item_id,)) is not None,
        "Item not found.",
        "not_found",
    )
    return {
        "purchase_orders": rows(
            "SELECT id,quantity restock_quantity,expected_date,status FROM purchase_orders WHERE item_id=? AND status='pending'",
            (item_id,),
        )
    }
