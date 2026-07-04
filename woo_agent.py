"""
WooCommerce Dashboard Agent - powered by Agno
================================================
Ye agent aapke WooCommerce store ka data (orders, customers, sales,
products) fetch karta hai aur natural language (Urdu/English) mein
jawab deta hai.

SETUP:
1. pip install agno groq requests python-dotenv
2. .env file banayein (isi folder mein) is content ke sath:

    GROQ_API_KEY=gsk_xxxxxxxx
    WOO_STORE_URL=https://yourstore.com
    WOO_CONSUMER_KEY=ck_xxxxxxxx
    WOO_CONSUMER_SECRET=cs_xxxxxxxx

   (WooCommerce keys yahan se banayein:
    WP Admin -> WooCommerce -> Settings -> Advanced -> REST API -> Add key
    Permissions: Read/Write)

3. Run: python woo_agent.py
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

from agno.agent import Agent
from agno.models.groq import Groq
from agno.tools import tool

load_dotenv()

STORE_URL = os.getenv("WOO_STORE_URL", "").rstrip("/")
CONSUMER_KEY = os.getenv("WOO_CONSUMER_KEY", "")
CONSUMER_SECRET = os.getenv("WOO_CONSUMER_SECRET", "")

API_BASE = f"{STORE_URL}/wp-json/wc/v3"


def _woo_get(endpoint: str, params: dict | None = None):
    """Internal helper - WooCommerce REST API se GET request bhejta hai."""
    params = params or {}
    params["consumer_key"] = CONSUMER_KEY
    params["consumer_secret"] = CONSUMER_SECRET
    resp = requests.get(f"{API_BASE}/{endpoint}", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json(), resp.headers


# ---------------------------------------------------------------------------
# TOOLS - Agent inhi functions ko call karega
# ---------------------------------------------------------------------------

@tool(show_result=True)
def get_recent_orders(count: int = 10, status: str = "any") -> str:
    """
    Store ke recent orders fetch karta hai.

    Args:
        count: Kitne recent orders chahiye (default 10)
        status: Order status filter - any, processing, completed,
                pending, on-hold, cancelled, refunded
    """
    data, _ = _woo_get("orders", {"per_page": count, "status": status, "orderby": "date", "order": "desc"})
    if not data:
        return "Koi order nahi mila."

    lines = []
    for o in data:
        lines.append(
            f"Order #{o['id']} | {o['status']} | "
            f"{o['billing']['first_name']} {o['billing']['last_name']} | "
            f"Total: {o['total']} {o['currency']} | Date: {o['date_created']}"
        )
    return "\n".join(lines)


@tool(show_result=True)
def get_orders_count_today() -> str:
    """Aaj kitne orders aye hain, ye count karta hai (status: any)."""
    today_start = datetime.utcnow().strftime("%Y-%m-%dT00:00:00")
    data, headers = _woo_get(
        "orders",
        {"after": today_start, "per_page": 100, "status": "any"},
    )
    total = headers.get("X-WP-Total", len(data))
    return f"Aaj total {total} orders aye hain."


@tool(show_result=True)
def get_orders_count_range(days: int = 7) -> str:
    """
    Pichle N dinon mein kitne orders aye, unka count aur total sales deta hai.

    Args:
        days: Kitne pichle dinon ka data chahiye (default 7)
    """
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00")
    data, headers = _woo_get(
        "orders",
        {"after": since, "per_page": 100, "status": "any"},
    )
    total_orders = headers.get("X-WP-Total", len(data))
    total_sales = sum(float(o["total"]) for o in data)
    return (
        f"Pichle {days} din mein {total_orders} orders aye. "
        f"Total sales: {total_sales:.2f}"
    )


@tool(show_result=True)
def get_order_details(order_id: int) -> str:
    """
    Ek specific order ki poori detail deta hai (line items, customer, payment).

    Args:
        order_id: WooCommerce order ID
    """
    data, _ = _woo_get(f"orders/{order_id}")
    items = ", ".join(f"{it['name']} x{it['quantity']}" for it in data.get("line_items", []))
    return (
        f"Order #{data['id']}\n"
        f"Status: {data['status']}\n"
        f"Customer: {data['billing']['first_name']} {data['billing']['last_name']} "
        f"({data['billing'].get('email', 'N/A')})\n"
        f"Items: {items}\n"
        f"Total: {data['total']} {data['currency']}\n"
        f"Payment method: {data.get('payment_method_title', 'N/A')}\n"
        f"Date: {data['date_created']}"
    )


@tool(show_result=True)
def get_total_customers() -> str:
    """Store ke total registered customers/users ki count deta hai."""
    _, headers = _woo_get("customers", {"per_page": 1})
    total = headers.get("X-WP-Total", "unknown")
    return f"Total registered customers: {total}"


@tool(show_result=True)
def get_recent_customers(count: int = 10) -> str:
    """
    Recent register hone wale customers ki list deta hai.

    Args:
        count: Kitne recent customers chahiye (default 10)
    """
    data, _ = _woo_get("customers", {"per_page": count, "orderby": "registered_date", "order": "desc"})
    if not data:
        return "Koi customer nahi mila."
    lines = [
        f"{c['first_name']} {c['last_name']} | {c['email']} | Orders: {c.get('orders_count', 0)}"
        for c in data
    ]
    return "\n".join(lines)


@tool(show_result=True)
def get_low_stock_products(threshold: int = 5) -> str:
    """
    Wo products jinka stock threshold se kam hai, unki list deta hai.

    Args:
        threshold: Stock quantity threshold (default 5)
    """
    data, _ = _woo_get("products", {"per_page": 100, "stock_status": "instock"})
    low = [p for p in data if p.get("manage_stock") and p.get("stock_quantity") is not None and p["stock_quantity"] <= threshold]
    if not low:
        return f"Koi product {threshold} se kam stock mein nahi hai."
    lines = [f"{p['name']} - Stock: {p['stock_quantity']}" for p in low]
    return "\n".join(lines)


@tool(show_result=True)
def get_top_selling_products(count: int = 5) -> str:
    """
    Best-selling products ki list deta hai (WooCommerce reports API se).

    Args:
        count: Kitne top products chahiye (default 5)
    """
    data, _ = _woo_get("reports/top_sellers", {"period": "month"})
    if not data:
        return "Data available nahi hai."
    lines = [f"{p['name']} - Sold: {p['quantity']}" for p in data[:count]]
    return "\n".join(lines)


@tool(show_result=True)
def get_sales_report(period: str = "week") -> str:
    """
    Sales summary report deta hai.

    Args:
        period: week, month, last_month, ya year
    """
    data, _ = _woo_get("reports/sales", {"period": period})
    if not data:
        return "Sales data nahi mila."
    totals = data[0] if isinstance(data, list) else data
    return (
        f"Period: {period}\n"
        f"Total Sales: {totals.get('total_sales')}\n"
        f"Total Orders: {totals.get('total_orders')}\n"
        f"Total Items Sold: {totals.get('total_items')}\n"
        f"Average Sales: {totals.get('average_sales')}"
    )


# ---------------------------------------------------------------------------
# AGENT
# ---------------------------------------------------------------------------

woo_agent = Agent(
    name="WooCommerce Dashboard Agent",
    # model=Groq(id="llama-3.3-70b-versatile"),
    model=Groq(id="openai/gpt-oss-120b"),
    tools=[
        get_recent_orders,
        get_orders_count_today,
        get_orders_count_range,
        get_order_details,
        get_total_customers,
        get_recent_customers,
        get_low_stock_products,
        get_top_selling_products,
        get_sales_report,
    ],
    instructions=[
        "Aap ek WooCommerce store dashboard assistant hain.",
        "Har jawab clear aur seedha dein - agar user Urdu mein pooche to Urdu/Roman Urdu mein jawab dein.",
        "Numbers aur totals ko table ya bullet points mein dikhayein jab multiple items hon.",
        "Agar tool se error aye, user ko batayein ke API keys ya store URL check karein.",
        "Kabhi bhi order ya customer data invent na karein - hamesha tools se hi fetch karein.",
    ],
    markdown=True,
    add_datetime_to_context=True,
)


if __name__ == "__main__":
    print("WooCommerce Dashboard Agent ready! Type 'exit' to quit.\n")
    while True:
        user_input = input("Aap: ")
        if user_input.strip().lower() in ("exit", "quit"):
            break
        woo_agent.print_response(user_input, stream=True)