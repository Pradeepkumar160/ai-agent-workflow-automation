"""WF005 Customer Order Status."""
import re

from app.config import mock
from app.core.errors import NeedsInput
from app.core.registry import InputSpec, workflow

ORDER_RE = re.compile(r"^[A-Z]{2,4}-\d{3,}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@workflow("WF005", inputs=[
    InputSpec("order_id", "Order ID", pattern=r"\b([A-Za-z]{2,4}-\d{3,})\b"),
    InputSpec("customer_email", "Customer email", pattern=r"([\w.+-]+@[\w-]+\.[\w.-]+)"),
    InputSpec("orders_path", "Orders data", default=mock("orders.csv"), kind="file"),
    InputSpec("shipments_path", "Shipments data", default=mock("shipments.csv"), kind="file"),
], any_of=[["order_id", "customer_email"]],
   any_of_question="Which order? Please provide an order ID (e.g. ORD-1001) or the customer's email address.")
def run(ctx):
    order_id, email = ctx.inputs.get("order_id"), ctx.inputs.get("customer_email")
    with ctx.step(0):  # Validate identifier
        if order_id and not ORDER_RE.match(order_id.strip().upper()):
            raise NeedsInput(f"'{order_id}' is not a valid order ID (expected like ORD-1001). Please provide another identifier.", ["order_id"])
        if email and not EMAIL_RE.match(email.strip()):
            raise NeedsInput(f"'{email}' is not a valid email address. Please provide another identifier.", ["customer_email"])

    with ctx.step(1):  # Search order data
        orders = ctx.call("order_api", path=ctx.inputs["orders_path"],
                          **({"order_id": order_id} if order_id else {"customer_email": email}))
        if not orders:
            ident = order_id or email
            raise NeedsInput(f"No order found for '{ident}'. Please check it or provide another identifier "
                             f"(order ID or customer email).", ["order_id"])

    results = []
    with ctx.step(2):  # Retrieve order status
        for o in orders:
            results.append({"order_id": o["order_id"], "items": [i.strip() for i in o["items"].split(";")],
                            "order_status": o["status"]})
    with ctx.step(3):  # Retrieve shipment information
        for r in results:
            ship = ctx.call("shipment_lookup", path=ctx.inputs["shipments_path"], order_id=r["order_id"])
            r["shipment"] = ship or None
    with ctx.step(4):  # Summarize current status
        lines = []
        for r in results:
            s = r["shipment"]
            ship_txt = (f"shipment {s['shipment_status']} via {s['carrier']}, tracking {s['tracking_number']}, "
                        f"ETA {s['estimated_delivery']}") if s else "no shipment/tracking information available yet"
            lines.append(f"{r['order_id']} ({', '.join(r['items'])}): order {r['order_status']}; {ship_txt}.")
    return {"summary": "\n".join(lines), "data": {"orders": results}}
