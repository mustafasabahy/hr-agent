"""Customer-owned orders, returns and complaint escalation."""

from database import db, one, rows, policy, today
from services.common import operation, require, actor, role, day, text, pending


def order(order_id):
    user = role("customer")
    r = one("SELECT * FROM orders WHERE id=?", (order_id,))
    require(r is not None, "Order not found.", "not_found")
    require(
        r["customer_id"] == user["customer_id"],
        "Access denied to this order.",
        "forbidden",
    )
    return r


def return_eligibility(r):
    window = policy("return_exceptions").get(r["id"], policy("return_window_days"))
    elapsed = (today() - day(r["delivered_on"])).days if r["delivered_on"] else None
    reason = "Within return window."
    eligible = (
        r["status"] == "delivered" and elapsed is not None and 0 <= elapsed <= window
    )
    if not eligible:
        reason = "Order must be delivered and within its configured return window."
    return {
        "eligible": eligible,
        "days_since_delivery": elapsed,
        "window_days": window,
        "reason": reason,
    }


@operation("customers")
def get_order_status(order_id: str) -> dict:
    """Read an order owned by the selected local customer identity."""
    return order(order_id)


@operation("customers", write=True)
def request_product_return(order_id: str) -> dict:
    """Request return of own delivered order within its return window; no automatic refund."""
    r = order(order_id)
    check = return_eligibility(r)
    require(check["eligible"], check["reason"])
    return pending(
        "product_return",
        None,
        {"order_id": order_id, "customer_id": actor()["customer_id"]},
    )


@operation("customers")
def check_return_eligibility(order_id: str) -> dict:
    """Check own order against the standard 14-day return policy and configured exceptions."""
    return return_eligibility(order(order_id))


@operation("customers", write=True)
def update_shipping_address(order_id: str, new_address: str) -> dict:
    """Change own order address before shipment only; shipped or delivered orders are rejected."""
    r = order(order_id)
    require(
        r["status"] in ["pending", "processing"],
        "Address cannot change after shipment.",
    )
    address = text(new_address, "Shipping address", 500)
    require(address != r["address"], "Address is unchanged.", "conflict")
    db().execute("UPDATE orders SET address=? WHERE id=?", (address, order_id))
    return {"order_id": order_id, "shipping_address": address, "status": r["status"]}


@operation("customers", write=True)
def escalate_customer_ticket(ticket_id: int, reason: str) -> dict:
    """Escalate own open customer complaint for human review."""
    user = role("customer")
    require(ticket_id > 0, "Ticket ID must be positive.")
    r = one("SELECT * FROM tickets WHERE id=? AND kind='customer'", (ticket_id,))
    require(r is not None, "Customer ticket not found.", "not_found")
    require(
        r["customer_id"] == user["customer_id"],
        "Access denied to this ticket.",
        "forbidden",
    )
    require(
        r["status"] == "open",
        "Only open, un-escalated tickets can be escalated.",
        "conflict",
    )
    reason = text(reason, "Escalation reason")
    db().execute(
        "UPDATE tickets SET status='escalated',escalation_reason=? WHERE id=?",
        (reason, ticket_id),
    )
    return {
        "ticket_id": ticket_id,
        "status": "escalated",
        "human_review_required": True,
    }
