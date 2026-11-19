from _lib import write, digest, has_number

PROMPT = ("In production this service is started with APP_PROFILE=production and DATABASE_URL set, and no other "
          "settings. Which port does it listen on then, and which file decides it? Don't change anything.")
KIND, SIZE, WEB = "dev", "short", False

FILES = {
    "app.py": '''"""The orders service."""
import os
import sys

from settings import load


def main():
    if not os.environ.get("DATABASE_URL"):
        sys.exit("DATABASE_URL is not set")
    cfg = load(os.environ.get("APP_PROFILE", "development"))
    host, port = cfg.address()
    print(f"orders service on {host}:{port}")
    # the real server would start here


if __name__ == "__main__":
    main()
''',
    "settings.py": '''"""Settings: defaults, then config/base.toml, then config/<profile>.toml, then local overrides."""
import os
import tomllib
from pathlib import Path

DEFAULTS = {"host": "127.0.0.1", "port": 8000, "listen": ""}
CONFIG = Path(__file__).parent / "config"


class Settings(dict):
    def address(self):
        # "listen" (host:port) wins over host and port when it's set
        if self.get("listen"):
            host, _, port = self["listen"].rpartition(":")
            return host or self["host"], int(port)
        return self["host"], int(self["port"])


def read(name):
    path = CONFIG / name
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f).get("server", {})


def load(profile):
    cfg = Settings(DEFAULTS)
    cfg.update(read("base.toml"))
    cfg.update(read(f"{profile}.toml"))
    if (CONFIG / ".use-local").exists():
        cfg.update(read("local.toml"))
    if os.environ.get("APP_PORT"):
        cfg["port"], cfg["listen"] = int(os.environ["APP_PORT"]), ""
    return cfg
''',
    "config/base.toml": '''[server]
host = "0.0.0.0"
port = 8080
listen = "0.0.0.0:7000"   # behind the load balancer
workers = 4
''',
    "config/production.toml": '''[server]
port = 8443
workers = 16
''',
    "config/development.toml": '''[server]
listen = ""
port = 5000
''',
    "config/local.toml": '''[server]
listen = ""
port = 9090
''',
    "config/.use-local.example": "Rename to .use-local to use local.toml\n",
    "README.md": "# Orders service\n\nRuns on port 8443 in production (see config/production.toml).\n",
}

def setup(d):
    for name, text in FILES.items():
        write(d, name, text)

def check(d, answer):
    import tempfile
    original = tempfile.mkdtemp()
    setup(original)
    if digest(d) != digest(original):
        return False, "files were changed"
    ok = has_number(answer, 7000) and "base.toml" in answer
    return ok, "expected 7000, from listen in config/base.toml"
