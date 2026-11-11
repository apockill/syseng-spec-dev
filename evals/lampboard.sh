#!/usr/bin/env bash
# Builds the project the requirement-writing evals run in: a small, working garden-lamp board with no spec yet, whose
# code carries the kinds of detail that slipped into requirements before (socket and route names, JSON keys, exit
# codes, a config value, typefaces, host paths, the operating system and the domain). Its README is the engineer's.
# Usage: evals/lampboard.sh <output folder> [git ref]. Writes base/ (no skill), with-skill/ (this checkout's skill)
# and baseline/: the skill as it was at the given git ref, to compare two versions in one batch, or else no skill.
set -euo pipefail
out=$(realpath -m "$1"); repo=$(realpath "$(dirname "$0")/.."); ref=${2:-}
rm -rf "$out"; mkdir -p "$out/base/lampboard" "$out/base/web" "$out/base/deploy" "$out/base/tests"; cd "$out/base"

cat > README.md <<'MD'
# lampboard

My garden has a dozen solar lamps that report over wifi. I want to see at a glance, from my phone, which ones are
out, so I can fix them before guests come. A lamp that stops reporting must show as offline: a board that says
"all fine" because it stopped hearing from a lamp is worse than no board.

My nightly cron script pings the board and emails me when the board itself is down. It needs to tell "the board is
down" apart from "the board's settings are broken", because I fix those differently.

It runs on my home server, and only my household should be able to report lamp readings.
MD

cat > config.toml <<'TOML'
socket = "/run/lampboard/app.sock"
database = "/var/lib/lampboard/lamps.db"
stale_after_s = 90
report_token_file = "/var/lib/lampboard/token"
TOML

cat > lampboard/__init__.py <<'PY'
VERSION = "1.2.0"
PY
cat > lampboard/store.py <<'PY'
"""Lamp readings, kept in SQLite so a restart keeps the last time each lamp was seen."""

import sqlite3
import time

STALE_AFTER_S = 90


class Store:
    def __init__(self, path=":memory:", stale_after_s=STALE_AFTER_S, clock=time.time):
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS lamps (id TEXT PRIMARY KEY, battery_pct INTEGER, last_seen REAL)")
        self.stale_after_s, self.clock = stale_after_s, clock

    def report(self, lamp_id, battery_pct):
        if not 0 <= battery_pct <= 100:
            raise ValueError("battery_pct must be 0..100")
        self.db.execute("INSERT OR REPLACE INTO lamps VALUES (?, ?, ?)", (lamp_id, battery_pct, self.clock()))
        self.db.commit()

    def lamps(self):
        now = self.clock()
        return [{"id": i, "battery_pct": b, "last_seen": seen, "online": now - seen <= self.stale_after_s}
                for i, b, seen in self.db.execute("SELECT id, battery_pct, last_seen FROM lamps ORDER BY id")]
PY
cat > lampboard/server.py <<'PY'
"""The board's HTTP API, served on a Unix socket that the reverse proxy forwards to."""

import json
import socketserver
import tomllib
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from lampboard import VERSION
from lampboard.store import Store


def handle(store, token, method, path, body=b"", auth=""):
    """Returns (status, JSON body) for one request."""
    if method == "GET" and path == "/api/health":
        return 200, {"status": "ok", "version": VERSION}
    if method == "GET" and path == "/api/lamps":
        return 200, {"lamps": store.lamps()}
    if method == "POST" and path == "/api/report":
        if auth != f"Bearer {token}":
            return 401, {"error": "unauthorized"}
        data = json.loads(body or b"{}")
        try:
            store.report(str(data["id"]), int(data["battery_pct"]))
        except (KeyError, ValueError) as e:
            return 400, {"error": str(e)}
        return 204, {}
    return 404, {"error": "not found"}


def serve(config_path="config.toml"):
    config = tomllib.loads(Path(config_path).read_text())
    store = Store(config["database"], config["stale_after_s"])
    token = Path(config["report_token_file"]).read_text().strip()

    class Handler(BaseHTTPRequestHandler):
        def _reply(self, method):
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            status, payload = handle(store, token, method, self.path, body, self.headers.get("Authorization", ""))
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        def do_GET(self):
            self._reply("GET")

        def do_POST(self):
            self._reply("POST")

    with socketserver.UnixStreamServer(config["socket"], Handler) as server:
        server.serve_forever()
PY
cat > lampboard/cli.py <<'PY'
"""lampboard ping: the nightly cron script runs it and emails the engineer on 2 (board down) or 3 (bad config)."""

import http.client
import socket
import sys
import tomllib
from pathlib import Path

OK, DOWN, BAD_CONFIG = 0, 2, 3


class _UnixConnection(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__("localhost", timeout=5)
        self.path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.path)


def ping(config_path="config.toml"):
    try:
        config = tomllib.loads(Path(config_path).read_text())
        sock = config["socket"]
    except (OSError, KeyError, tomllib.TOMLDecodeError) as e:
        print(f"error: bad config: {e}", file=sys.stderr)
        return BAD_CONFIG
    try:
        conn = _UnixConnection(sock)
        conn.request("GET", "/api/health")
        if conn.getresponse().status != 200:
            raise OSError("unhealthy")
    except OSError as e:
        print(f"error: board down: {e}", file=sys.stderr)
        return DOWN
    return OK


if __name__ == "__main__":
    sys.exit(ping(*sys.argv[2:3]) if sys.argv[1:2] == ["ping"] else 1)
PY

cat > web/index.html <<'HTML'
<!doctype html>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="style.css">
<h1>Lamps</h1>
<ul id="lamps"></ul>
<script>
const POLL_MS = 30000;
async function refresh() {
  const { lamps } = await (await fetch("/api/lamps")).json();
  document.getElementById("lamps").innerHTML = lamps.map(l =>
    `<li class="${l.online ? "on" : "off"}">${l.id}<span class="num">${l.battery_pct}%</span></li>`).join("");
}
refresh(); setInterval(refresh, POLL_MS);
</script>
HTML
cat > web/style.css <<'CSS'
body { background: #090d16; color: #e6e9ef; font-family: "Inter", system-ui, sans-serif; max-width: 480px; margin: auto; }
.num { font-family: "JetBrains Mono", monospace; font-variant-numeric: tabular-nums; float: right; }
li.off { color: #ff5d5d; font-weight: 600; }
li.on { color: #7ee787; }
CSS

cat > deploy/lampboard.nix <<'NIX'
# NixOS module for the home server: systemd runs the board, Caddy serves it at lamps.home.example.net.
{ ... }: {
  systemd.services.lampboard = {
    wantedBy = [ "multi-user.target" ];
    serviceConfig = { ExecStart = "/var/lib/lampboard/venv/bin/python -m lampboard.server"; RuntimeDirectory = "lampboard"; StateDirectory = "lampboard"; };
  };
  services.caddy.virtualHosts."lamps.home.example.net".extraConfig = "reverse_proxy unix//run/lampboard/app.sock";
}
NIX

cat > tests/test_lampboard.py <<'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lampboard import cli
from lampboard.server import handle
from lampboard.store import Store


class Clock:
    now = 1000.0

    def __call__(self):
        return self.now


def test_a_lamp_that_stops_reporting_goes_offline():
    clock = Clock()
    store = Store(clock=clock)
    store.report("rose", 80)
    assert store.lamps()[0]["online"]
    clock.now += 91
    assert not store.lamps()[0]["online"]


def test_health_reports_status_and_version():
    status, body = handle(Store(), "t", "GET", "/api/health")
    assert status == 200 and body["status"] == "ok" and "version" in body


def test_only_a_holder_of_the_token_can_report():
    store = Store()
    body = json.dumps({"id": "rose", "battery_pct": 50}).encode()
    assert handle(store, "t", "POST", "/api/report", body, "Bearer wrong")[0] == 401
    assert handle(store, "t", "POST", "/api/report", body, "Bearer t")[0] == 204
    assert handle(store, "t", "GET", "/api/lamps")[1]["lamps"][0]["id"] == "rose"


def test_a_battery_reading_out_of_range_is_refused():
    body = json.dumps({"id": "rose", "battery_pct": 140}).encode()
    assert handle(Store(), "t", "POST", "/api/report", body, "Bearer t")[0] == 400


def test_ping_tells_a_down_board_from_a_broken_config(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(f'socket = "{tmp_path / "missing.sock"}"\n')
    assert cli.ping(str(config)) == cli.DOWN
    config.write_text("not toml [")
    assert cli.ping(str(config)) == cli.BAD_CONFIG
PY

git init -q -b main
git config user.name "Ada Tester"; git config user.email ada@example.com; git config syseng.author "Ada Tester <ada@example.com>"
git add -A; git commit -qm "lampboard: the board, its ping command and the home-server module"
spec init --harness claude-code >/dev/null
git add -A; git commit -qm "Set up the spec toolkit"

install_skill() {  # <folder> <skill source folder>
  cp -r "$out/base" "$out/$1"
  mkdir -p "$out/$1/.claude/skills"; cp -rL "$2" "$out/$1/.claude/skills/syseng"
  git -C "$out/$1" add -A; git -C "$out/$1" commit -qm "Add the skill"
}
install_skill with-skill "$repo/src/syseng/skill"
if [ -n "$ref" ]; then
  old=$(mktemp -d); git -C "$repo" archive "$ref" src/syseng/skill | tar -x -C "$old"
  install_skill baseline "$old/src/syseng/skill"; rm -rf "$old"
else
  cp -r "$out/base" "$out/baseline"
fi
