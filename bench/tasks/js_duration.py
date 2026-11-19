import shutil
from _lib import write, run

PROMPT = "node test.js fails. Fix duration.js so the tests pass, without changing test.js."
KIND, SIZE, WEB = "dev", "short", False

CODE = r"""// Durations as text: formatDuration(3725) === "1h 2m 5s", parseDuration("1h 30m") === 5400
const UNITS = [["d", 86400], ["h", 3600], ["m", 60], ["s", 1]];

function formatDuration(seconds) {
  if (seconds === 0) return "0s";
  const parts = [];
  for (const [name, size] of UNITS) {
    const n = Math.floor(seconds / size);
    if (n > 0) parts.push(n + name);
    seconds = seconds - n;
  }
  return parts.join(" ");
}

function parseDuration(text) {
  let total = 0;
  for (const [, n, unit] of text.matchAll(/(\d+)\s*([hms])/g)) {
    total += Number(n) * UNITS.find(([name]) => name === unit)[1];
  }
  return total;
}

module.exports = { formatDuration, parseDuration };
"""
TESTS = r"""const assert = require("node:assert");
const { formatDuration, parseDuration } = require("./duration");

assert.strictEqual(formatDuration(0), "0s");
assert.strictEqual(formatDuration(59), "59s");
assert.strictEqual(formatDuration(3725), "1h 2m 5s");
assert.strictEqual(formatDuration(90061), "1d 1h 1m 1s");
assert.strictEqual(parseDuration("1h 30m"), 5400);
assert.strictEqual(parseDuration("2d 1s"), 172801);
console.log("all tests passed");
"""
HIDDEN = r"""const assert = require("node:assert");
const { formatDuration, parseDuration } = require("./duration");
assert.strictEqual(formatDuration(86400), "1d");
assert.strictEqual(formatDuration(3600 + 1), "1h 1s");
assert.strictEqual(parseDuration("3d"), 259200);
assert.strictEqual(parseDuration(formatDuration(200000)), 200000);
console.log("ok");
"""

def setup(d):
    write(d, "duration.js", CODE)
    write(d, "test.js", TESTS)

def check(d, answer):
    if not shutil.which("node"):
        return False, "node isn't installed"
    if (d / "test.js").read_text() != TESTS:
        return False, "test.js was changed"
    write(d, "hidden_check.js", HIDDEN)
    for script in ("test.js", "hidden_check.js"):
        code, out = run(["node", script], d)
        if code != 0:
            return False, f"{script}: {out[-300:]}"
    return True, "tests pass"
