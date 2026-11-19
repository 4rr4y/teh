import re, sys, tempfile
from pathlib import Path
from _lib import write, digest, run, python

PROMPT = ("We upgraded our notify library to version 2 (see notify/CHANGELOG.md) and the app no longer works. Update "
          "the app's code to the new API so the tests pass (python3 -m unittest). Don't change notify/ or the tests.")
KIND, SIZE, WEB = "dev", "long", False

FILES = {
    "notify/__init__.py": '''"""notify 2.0: sends messages to users."""
from .client import Client, Priority

__version__ = "2.0.0"
''',
    "notify/client.py": '''import enum

from . import testing


class Priority(enum.Enum):
    NORMAL = "normal"
    HIGH = "high"


class Client:
    def __init__(self, channel="default"):
        self.channel = channel

    def send(self, user_id, text, *, priority=Priority.NORMAL):
        if not isinstance(priority, Priority):
            raise TypeError("priority must be a notify.Priority")
        if not isinstance(user_id, int):
            raise TypeError("user_id must be an int")
        testing.sent.append((user_id, text, priority, self.channel))
''',
    "notify/testing.py": '"""Messages sent, for tests: (user_id, text, priority, channel)."""\nsent = []\n',
    "notify/CHANGELOG.md": '''# Changelog

## 2.0.0

Breaking: the module-level `notify.send(text, user_id, urgent=False, channel="default")` is gone. Create a client
for the channel and call its `send`, which takes the user first:

    notify.send(text, user_id, urgent=True, channel="billing")
    # becomes
    notify.Client("billing").send(user_id, text, priority=notify.Priority.HIGH)

`urgent=False` (the default) becomes `priority=notify.Priority.NORMAL` (also the default). A `Client` can be reused.

## 1.4.0

Added the `channel` argument.
''',
    "app/__init__.py": "",
    "app/orders.py": '''import notify


def order_shipped(order_id, user_id):
    notify.send(f"Order {order_id} has shipped", user_id)
''',
    "app/billing.py": '''import notify


def payment_failed(user):
    notify.send("Your payment failed. Please update your card.", user["id"], urgent=True, channel="billing")


def invoice_ready(uid, invoice_no):
    notify.send(text=f"Invoice {invoice_no} is ready", user_id=uid, channel="billing")
''',
    "app/alerts.py": '''import notify


def alert(uid, message, is_urgent):
    notify.send(message, uid, is_urgent)
''',
    "app/signup.py": '''from notify import send


def welcome(user_id, name):
    send(f"Welcome, {name}!", user_id)
''',
    "app/reminders.py": '''import notify


def renewal_reminders(subscriptions):
    for sub in subscriptions:
        days = sub["days_left"]
        notify.send(f"Your plan renews in {days} days", sub["user_id"], urgent=days < 2, channel="renewals")
''',
    "app/support.py": '''import notify as n


def ticket_answered(user_id, ticket):
    n.send(f"Ticket #{ticket} has a reply", user_id, False, "support")
''',
    "app/security.py": '''import notify

SECURITY = "security"


def new_login(user_id, device):
    notify.send(f"New sign-in from {device}", user_id, urgent=True, channel=SECURITY)


def password_changed(user_id):
    notify.send("Your password was changed", user_id, channel=SECURITY, urgent=True)
''',
    "app/digest.py": '''import notify


def weekly_digest(user_ids, items):
    text = "This week: " + ", ".join(items)
    for uid in user_ids:
        notify.send(text, uid)
''',
    "tests/__init__.py": "",
    "tests/test_app.py": '''import unittest

from notify import Priority, testing
from app import alerts, billing, digest, orders, reminders, security, signup, support

N, H = Priority.NORMAL, Priority.HIGH


class TestApp(unittest.TestCase):
    def setUp(self):
        testing.sent.clear()

    def test_orders(self):
        orders.order_shipped(7, 1)
        self.assertEqual(testing.sent, [(1, "Order 7 has shipped", N, "default")])

    def test_billing(self):
        billing.payment_failed({"id": 2})
        billing.invoice_ready(3, "A-9")
        self.assertEqual(testing.sent, [(2, "Your payment failed. Please update your card.", H, "billing"),
                                        (3, "Invoice A-9 is ready", N, "billing")])

    def test_alerts(self):
        alerts.alert(4, "Disk full", True)
        alerts.alert(4, "Disk ok", False)
        self.assertEqual(testing.sent, [(4, "Disk full", H, "default"), (4, "Disk ok", N, "default")])

    def test_signup(self):
        signup.welcome(5, "Ana")
        self.assertEqual(testing.sent, [(5, "Welcome, Ana!", N, "default")])

    def test_reminders(self):
        reminders.renewal_reminders([{"user_id": 6, "days_left": 1}, {"user_id": 7, "days_left": 9}])
        self.assertEqual(testing.sent, [(6, "Your plan renews in 1 days", H, "renewals"),
                                        (7, "Your plan renews in 9 days", N, "renewals")])

    def test_support(self):
        support.ticket_answered(8, 31)
        self.assertEqual(testing.sent, [(8, "Ticket #31 has a reply", N, "support")])

    def test_security(self):
        security.new_login(9, "Firefox on Linux")
        security.password_changed(9)
        self.assertEqual(testing.sent, [(9, "New sign-in from Firefox on Linux", H, "security"),
                                        (9, "Your password was changed", H, "security")])

    def test_digest(self):
        digest.weekly_digest([1, 2], ["a", "b"])
        self.assertEqual(testing.sent, [(1, "This week: a, b", N, "default"), (2, "This week: a, b", N, "default")])


if __name__ == "__main__":
    unittest.main()
''',
}

def setup(d):
    for name, text in FILES.items():
        write(d, name, text)

def check(d, answer):
    original = Path(tempfile.mkdtemp())
    setup(original)
    for folder in ("notify", "tests"):
        if digest(Path(d, folder)) != digest(original / folder):
            return False, f"{folder}/ was changed"
    code, out = run([sys.executable, "-B", "-m", "unittest", "-q"], d)
    if code != 0:
        return False, "tests fail: " + out[-400:]
    for path in Path(d, "app").glob("*.py"):
        if re.search(r"(\bnotify|\bn)\.send\(|from notify import send\b", path.read_text()):
            return False, f"old API still used in {path.name}"
    code, out = python("from notify import testing, Priority\nfrom app import alerts\n"
                       "alerts.alert(1, 'x', 1)\nassert testing.sent[-1][2] is Priority.HIGH, testing.sent", d)
    return code == 0, out[-300:] or "ok"
