import sys, tempfile
from pathlib import Path
from _lib import write, digest, run, python

PROMPT = "Run the test suite (python3 -m unittest) and fix the code so that all the tests pass. Don't change the tests."
KIND, SIZE, WEB = "dev", "long", False

FILES = {
    "inventory/__init__.py": '"""A small stock-keeping library."""\n',
    "inventory/money.py": '''"""Amounts of money, in pounds, as Decimal."""
from decimal import Decimal, ROUND_HALF_UP

PENNY = Decimal("0.01")


def parse_money(text):
    """'£1,234.50' -> Decimal('1234.50'); '-£3' and '(3.00)' -> Decimal('-3.00')."""
    s = text.strip()
    negative = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    s = s.strip("-()").replace("£", "").replace(",", "").strip()
    value = Decimal(s).quantize(PENNY, ROUND_HALF_UP)
    return -value if negative else value


def format_money(amount):
    """Decimal('-1234.5') -> '-£1,234.50'."""
    amount = Decimal(amount).quantize(PENNY, ROUND_HALF_UP)
    return f"£{amount:,}"
''',
    "inventory/items.py": '''"""Stock items."""
import re
from dataclasses import dataclass
from decimal import Decimal

SKU = re.compile(r"^[A-Z]{3}-\\d{4}$")


@dataclass
class Item:
    sku: str
    name: str
    price: Decimal
    qty: int = 0

    def __post_init__(self):
        if not SKU.match(self.sku):
            raise ValueError(f"bad SKU {self.sku!r}: expected three capitals, a hyphen and four digits")
        if self.price < 0:
            raise ValueError(f"{self.sku}: negative price")
        if self.qty < 0:
            raise ValueError(f"{self.sku}: negative quantity")

    @property
    def value(self):
        return self.price * self.qty
''',
    "inventory/csvio.py": '''"""Reading and writing stock lists as CSV: sku, name, price, qty. Blank lines and # comments are skipped."""
import csv

from .items import Item
from .money import parse_money


def load_items(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = [line for line in f if line.strip() and not line.lstrip().startswith("#")]
    return [Item(row["sku"], row["name"], parse_money(row["price"]), int(row["qty"]))
            for row in csv.DictReader(rows)]


def save_items(path, items):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["sku", "name", "price", "qty"])
        for item in items:
            writer.writerow([item.sku, item.name, f"{item.price:.2f}", item.qty])
''',
    "inventory/pricing.py": '''"""Prices for an order: bulk discounts, then VAT."""
from decimal import Decimal, ROUND_HALF_UP

from .money import PENNY

# (minimum quantity, discount): 5% off from 10 units, 10% off from 50 units
TIERS = [(50, Decimal("0.10")), (10, Decimal("0.05"))]
VAT = Decimal("0.20")


def unit_price(item, qty):
    for minimum, discount in TIERS:
        if qty > minimum:
            return (item.price * (1 - discount)).quantize(PENNY, ROUND_HALF_UP)
    return item.price


def order_total(item, qty, vat=VAT):
    net = unit_price(item, qty) * qty
    return (net * (1 + vat)).quantize(PENNY, ROUND_HALF_UP)
''',
    "inventory/stock.py": '''"""An inventory: items by SKU."""
from decimal import Decimal


class OutOfStock(Exception):
    pass


class Inventory:
    def __init__(self, items=()):
        self._items = {}
        for item in items:
            self.add(item)

    def add(self, item):
        if item.sku in self._items:
            self._items[item.sku].qty += item.qty
        else:
            self._items[item.sku] = item

    def remove(self, sku, qty):
        item = self._items.get(sku)
        if item is None:
            raise KeyError(sku)
        if qty > item.qty:
            raise OutOfStock(f"{sku}: {item.qty} in stock, {qty} wanted")
        item.qty -= qty

    def low_stock(self, threshold=5):
        """Items with fewer than threshold in stock: fewest first, then by SKU."""
        return sorted((i for i in self._items.values() if i.qty < threshold), key=lambda i: i.qty)

    def total_value(self):
        return sum((i.value for i in self._items.values()), Decimal("0"))

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        return iter(sorted(self._items.values(), key=lambda i: i.sku))
''',
    "inventory/report.py": '''"""A text report of an inventory."""
from .money import format_money


def stock_report(inventory, threshold=5):
    lines = [f"{'SKU':<10}{'Name':<20}{'Qty':>5}{'Value':>12}"]
    for item in inventory:
        lines.append(f"{item.sku:<10}{item.name[:20]:<20}{item.qty:>5}{format_money(item.value):>12}")
    lines.append(f"Total value: {format_money(inventory.total_value())}")
    low = inventory.low_stock(threshold)
    if low:
        lines.append("Low stock: " + ", ".join(i.sku for i in low))
    return "\\n".join(lines)
''',
    "inventory/barcode.py": '''"""EAN-13 barcodes."""


def check_digit(first12):
    """The 13th digit of an EAN-13 barcode, from the first 12."""
    if len(first12) != 12 or not first12.isdigit():
        raise ValueError("expected 12 digits")
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(first12))
    return str((10 - total % 10) % 10)


def is_valid(code):
    return len(code) == 13 and code.isdigit() and check_digit(code[:12]) == code[12]
''',
    "inventory/units.py": '''"""Pack sizes: how many packs an order needs."""
import math

PACK_SIZES = {"tea": 25, "cups": 6, "tray": 1}


def packs_needed(product, units):
    size = PACK_SIZES.get(product, 1)
    return math.ceil(units / size)


def units_in(product, packs):
    return PACK_SIZES.get(product, 1) * packs
''',
    "tests/__init__.py": "",
    "tests/test_money.py": '''import unittest
from decimal import Decimal
from inventory.money import parse_money, format_money


class TestMoney(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_money("£1,234.50"), Decimal("1234.50"))
        self.assertEqual(parse_money(" 3 "), Decimal("3.00"))

    def test_parse_negative(self):
        self.assertEqual(parse_money("-£3"), Decimal("-3.00"))
        self.assertEqual(parse_money("(4.20)"), Decimal("-4.20"))

    def test_parse_rounds_half_up(self):
        self.assertEqual(parse_money("0.125"), Decimal("0.13"))

    def test_format(self):
        self.assertEqual(format_money(Decimal("1234.5")), "£1,234.50")
        self.assertEqual(format_money(0), "£0.00")

    def test_format_negative(self):
        self.assertEqual(format_money(Decimal("-5")), "-£5.00")

    def test_round_trip(self):
        for text in ("£0.01", "£999,999.99", "-£12.30"):
            self.assertEqual(format_money(parse_money(text)), text)
''',
    "tests/test_items.py": '''import unittest
from decimal import Decimal
from inventory.items import Item


class TestItems(unittest.TestCase):
    def test_value(self):
        self.assertEqual(Item("TEA-0001", "Green tea", Decimal("4.50"), 3).value, Decimal("13.50"))

    def test_bad_sku(self):
        for sku in ("tea-0001", "TEA0001", "TEA-001", "TEAS-0001"):
            with self.assertRaises(ValueError):
                Item(sku, "x", Decimal("1"))

    def test_negative(self):
        with self.assertRaises(ValueError):
            Item("TEA-0001", "x", Decimal("-1"))
        with self.assertRaises(ValueError):
            Item("TEA-0001", "x", Decimal("1"), -2)
''',
    "tests/test_csvio.py": '''import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from inventory.csvio import load_items, save_items
from inventory.items import Item

SAMPLE = """# stock list, exported by hand
sku, name, price, qty
TEA-0001, Green tea, £4.50, 12

CUP-0002, Mug, "£1,200.00", 1
"""


class TestCsv(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def test_load_with_spaces_and_comments(self):
        path = self.dir / "stock.csv"
        path.write_text(SAMPLE)
        items = load_items(path)
        self.assertEqual([(i.sku, i.name, i.price, i.qty) for i in items],
                         [("TEA-0001", "Green tea", Decimal("4.50"), 12), ("CUP-0002", "Mug", Decimal("1200.00"), 1)])

    def test_round_trip(self):
        items = [Item("TRY-0003", "Tray, wooden", Decimal("19.99"), 2)]
        path = self.dir / "out.csv"
        save_items(path, items)
        self.assertEqual(load_items(path), items)
''',
    "tests/test_pricing.py": '''import unittest
from decimal import Decimal
from inventory.items import Item
from inventory.pricing import unit_price, order_total

TEA = Item("TEA-0001", "Green tea", Decimal("10.00"), 100)


class TestPricing(unittest.TestCase):
    def test_no_discount(self):
        self.assertEqual(unit_price(TEA, 9), Decimal("10.00"))

    def test_discount_from_10(self):
        self.assertEqual(unit_price(TEA, 10), Decimal("9.50"))
        self.assertEqual(unit_price(TEA, 49), Decimal("9.50"))

    def test_discount_from_50(self):
        self.assertEqual(unit_price(TEA, 50), Decimal("9.00"))

    def test_total_with_vat(self):
        self.assertEqual(order_total(TEA, 2), Decimal("24.00"))
        self.assertEqual(order_total(TEA, 10, vat=Decimal("0")), Decimal("95.00"))
''',
    "tests/test_stock.py": '''import unittest
from decimal import Decimal
from inventory.items import Item
from inventory.stock import Inventory, OutOfStock


def item(sku, qty, price="1.00"):
    return Item(sku, sku.lower(), Decimal(price), qty)


class TestStock(unittest.TestCase):
    def test_add_merges(self):
        inv = Inventory([item("TEA-0001", 2), item("TEA-0001", 3)])
        self.assertEqual(len(inv), 1)
        self.assertEqual(next(iter(inv)).qty, 5)

    def test_remove(self):
        inv = Inventory([item("TEA-0001", 2)])
        inv.remove("TEA-0001", 2)
        self.assertEqual(next(iter(inv)).qty, 0)
        with self.assertRaises(OutOfStock):
            inv.remove("TEA-0001", 1)
        with self.assertRaises(KeyError):
            inv.remove("CUP-0001", 1)

    def test_low_stock_order(self):
        inv = Inventory([item("ZED-0001", 1), item("CUP-0002", 3), item("ABC-0003", 1), item("TEA-0004", 9)])
        self.assertEqual([i.sku for i in inv.low_stock(5)], ["ABC-0003", "ZED-0001", "CUP-0002"])

    def test_total_value(self):
        inv = Inventory([item("TEA-0001", 2, "2.50"), item("CUP-0002", 4, "1.25")])
        self.assertEqual(inv.total_value(), Decimal("10.00"))
''',
    "tests/test_report.py": '''import unittest
from decimal import Decimal
from inventory.items import Item
from inventory.report import stock_report
from inventory.stock import Inventory


class TestReport(unittest.TestCase):
    def test_report(self):
        inv = Inventory([Item("TEA-0001", "Green tea", Decimal("4.50"), 2),
                         Item("CUP-0002", "Mug", Decimal("1500.00"), 1),
                         Item("ABC-0003", "Spoon", Decimal("0.75"), 1)])
        lines = stock_report(inv).splitlines()
        self.assertEqual(lines[1], "ABC-0003  Spoon" + " " * 19 + "1       £0.75")
        self.assertEqual(lines[-2], "Total value: £1,509.75")
        self.assertEqual(lines[-1], "Low stock: ABC-0003, CUP-0002, TEA-0001")
''',
    "tests/test_barcode.py": '''import unittest
from inventory.barcode import check_digit, is_valid


class TestBarcode(unittest.TestCase):
    def test_check_digit(self):
        self.assertEqual(check_digit("400638133393"), "1")

    def test_valid(self):
        self.assertTrue(is_valid("4006381333931"))
        self.assertFalse(is_valid("4006381333932"))
''',
    "tests/test_units.py": '''import unittest
from inventory.units import packs_needed, units_in


class TestUnits(unittest.TestCase):
    def test_packs(self):
        self.assertEqual(packs_needed("tea", 26), 2)
        self.assertEqual(packs_needed("cups", 6), 1)
        self.assertEqual(units_in("cups", 3), 18)
''',
}
HIDDEN = '''
from decimal import Decimal
from inventory.money import format_money
from inventory.items import Item
from inventory.pricing import unit_price
from inventory.stock import Inventory
assert format_money(Decimal("-1234.5")) == "-£1,234.50", format_money(Decimal("-1234.5"))
assert format_money(Decimal("0.004")) == "£0.00"
t = Item("TEA-0001", "t", Decimal("20.00"), 1)
assert unit_price(t, 50) == Decimal("18.00") and unit_price(t, 51) == Decimal("18.00")
assert unit_price(t, 11) == Decimal("19.00") and unit_price(t, 10) == Decimal("19.00")
inv = Inventory([Item("BBB-0001", "b", Decimal(1), 0), Item("AAA-0001", "a", Decimal(1), 0)])
assert [i.sku for i in inv.low_stock(1)] == ["AAA-0001", "BBB-0001"]
print("ok")
'''

def setup(d):
    for name, text in FILES.items():
        write(d, name, text)

def check(d, answer):
    original = Path(tempfile.mkdtemp())
    setup(original)
    if digest(Path(d, "tests")) != digest(original / "tests"):
        return False, "the tests were changed"
    code, out = run([sys.executable, "-B", "-m", "unittest", "-q"], d)
    if code != 0:
        return False, "tests fail: " + out[-400:]
    code, out = python(HIDDEN, d)
    return code == 0, out[-300:]
