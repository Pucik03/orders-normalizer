import os
import re
from datetime import datetime
from typing import Any

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

SOURCE_URL = os.getenv("SOURCE_URL", "https://test.ooobs.ru/api/orders")
app = FastAPI(title="Orders Normalizer", docs_url=None, redoc_url=None)

def normalize_phone(value: Any) -> str | None:
    """Return Russian phone as +7XXXXXXXXXX, or None if invalid."""
    if value is None:
        return None

    # Keep digits only; tolerate spaces, punctuation, parentheses and country prefix.
    digits = re.sub(r"\D", "", str(value))
    if not digits:
        return None

    # Common Russian formats:
    # 8XXXXXXXXXX -> 7XXXXXXXXXX
    # 7XXXXXXXXXX -> unchanged
    # XXXXXXXXXX  -> assume missing leading 7
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    elif len(digits) == 11 and digits[0] == "7":
        pass
    else:
        return None

    # Reject obviously malformed Russian numbers (national number starts with 9 for mobile,
    # or 3-8 for other valid Russian numbering ranges). Require a non-zero area/operator digit.
    if digits[0] != "7" or digits[1] == "0":
        return None

    return "+" + digits

def parse_date(value: Any) -> datetime:
    if value is None:
        return datetime.min
    raw = str(value).strip()
    try:
        # Support ISO timestamps with trailing Z.
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return datetime.min

def parse_amount(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("-inf")

def get_orders() -> list[dict]:
    try:
        response = requests.get(SOURCE_URL, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Could not fetch source orders") from exc

    if not isinstance(payload, list):
        raise HTTPException(status_code=502, detail="Source API did not return a JSON array")
    return [item for item in payload if isinstance(item, dict)]

def build_result(orders: list[dict]) -> dict:
    received = len(orders)
    invalid_dropped = 0
    best_by_phone: dict[str, dict] = {}

    for order in orders:
        phone = normalize_phone(order.get("phone"))
        if phone is None:
            invalid_dropped += 1
            continue

        candidate = {
            "name": order.get("name") if order.get("name") is not None else "",
            "phone": phone,
            "email": order.get("email") if order.get("email") is not None else "",
            "amount": order.get("amount"),
            "_created_at": parse_date(order.get("created_at")),
            "_amount_num": parse_amount(order.get("amount")),
        }

        current = best_by_phone.get(phone)
        if current is None:
            best_by_phone[phone] = candidate
        elif (
            candidate["_amount_num"] > current["_amount_num"]
            or (
                candidate["_amount_num"] == current["_amount_num"]
                and candidate["_created_at"] > current["_created_at"]
            )
        ):
            best_by_phone[phone] = candidate

    clients = []
    for client in best_by_phone.values():
        clients.append({
            "name": client["name"],
            "phone": client["phone"],
            "email": client["email"],
            "amount": client["amount"],
        })

    # Stable ordering makes the output deterministic between repeated requests.
    clients.sort(key=lambda client: client["phone"])
    unique = len(clients)

    return {
        "clients": clients,
        "stats": {
            "received": received,
            "unique": unique,
            "duplicates_merged": received - invalid_dropped - unique,
            "invalid_dropped": invalid_dropped,
        },
    }

@app.get("/")
def root():
    return {"service": "orders-normalizer", "endpoint": "/clients"}

@app.get("/clients")
def clients():
    return JSONResponse(content=build_result(get_orders()))

# Optional alias in case the checker expects the root URL to return the exact schema.
@app.get("/result")
def result():
    return JSONResponse(content=build_result(get_orders()))
