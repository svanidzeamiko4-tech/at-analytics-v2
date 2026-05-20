"""Parse RS.ge waybill XML (mock SOAP envelope or simplified waybills XML)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pandas as pd

_COLUMNS = [
    "invoice_id",
    "date",
    "seller_name",
    "seller_address",
    "buyer_name",
    "buyer_address",
    "buyer_barcode",
    "product_name",
    "quantity",
    "price",
    "line_total",
]

_INVOICE_TAGS = frozenset({"Waybill", "invoice", "Invoice"})
_PRODUCT_CONTAINER_TAGS = frozenset({"Products", "products"})
_PRODUCT_TAGS = frozenset({"Product", "product"})


def _tag(el: ET.Element) -> str:
    return el.tag.split("}")[-1] if "}" in el.tag else el.tag


def _text(el: ET.Element | None) -> str:
    if el is None or el.text is None:
        return ""
    return el.text.strip()


def _find_child(parent: ET.Element, name: str) -> ET.Element | None:
    for child in parent:
        if _tag(child) == name:
            return child
    return None


def _find_children(parent: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in parent if _tag(c) == name]


def _field(inv: ET.Element, *names: str) -> str:
    for name in names:
        el = _find_child(inv, name)
        if el is not None:
            return _text(el)
    return ""


def _iter_invoices(root: ET.Element) -> list[ET.Element]:
    found: list[ET.Element] = []
    for el in root.iter():
        if _tag(el) in _INVOICE_TAGS:
            found.append(el)
    if found:
        return found
    # Fallback: direct children named invoice
    return [c for c in root if _tag(c) == "invoice"]


def _iter_products(inv: ET.Element) -> list[ET.Element]:
    products: list[ET.Element] = []
    for el in inv.iter():
        if _tag(el) in _PRODUCT_CONTAINER_TAGS:
            products.extend(_find_children(el, "Product") or _find_children(el, "product"))
    if products:
        return products
    return [c for c in inv if _tag(c) in _PRODUCT_TAGS]


def parse_invoices(xml_string: str) -> pd.DataFrame:
    """
    Parse waybill XML into a flat DataFrame (one row per product line).

    Supports:
    - SOAP ``GetWaybillsResponse`` / ``Waybill`` nodes (mock + live)
    - Simple ``<waybills><invoice>…`` mock layout
    """
    root = ET.fromstring(xml_string.encode("utf-8") if isinstance(xml_string, str) else xml_string)
    rows: list[dict[str, object]] = []

    for inv in _iter_invoices(root):
        header = {
            "invoice_id": _field(inv, "invoice_id", "InvoiceId", "WaybillNumber"),
            "date": _field(inv, "date", "Date", "invoice_date"),
            "seller_name": _field(inv, "seller_name", "SellerName"),
            "seller_address": _field(inv, "seller_address", "SellerAddress"),
            "buyer_name": _field(inv, "buyer_name", "BuyerName"),
            "buyer_address": _field(inv, "buyer_address", "BuyerAddress"),
            "buyer_barcode": _field(inv, "buyer_barcode", "BuyerBarcode", "barcode"),
        }
        products = _iter_products(inv)
        if not products:
            rows.append(
                {
                    **header,
                    "product_name": "",
                    "quantity": 0.0,
                    "price": 0.0,
                    "line_total": 0.0,
                }
            )
            continue

        for prod in products:
            qty = float(_field(prod, "quantity", "Quantity") or 0)
            price = float(_field(prod, "price", "Price", "UnitPrice") or 0)
            pname = _field(prod, "product_name", "ProductName", "name")
            rows.append(
                {
                    **header,
                    "product_name": pname,
                    "quantity": qty,
                    "price": price,
                    "line_total": round(qty * price, 2),
                }
            )

    if not rows:
        return pd.DataFrame(columns=_COLUMNS)
    return pd.DataFrame(rows)[_COLUMNS]
