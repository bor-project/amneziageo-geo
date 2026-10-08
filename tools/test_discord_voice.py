"""Checks the collector of the Discord voice list against a registry on the loopback: python3 tools/test_discord_voice.py"""
import http.server
import ipaddress
import json
import pathlib
import subprocess
import sys
import tempfile
import threading
import urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build  # noqa: E402
import discord_voice as tool  # noqa: E402


def item(kind, value, name, status):
    fields = [{"name": kind, "value": value}, {"name": "netname", "value": name}, {"name": "status", "value": status}]
    return {"type": kind, "attributes": {"attribute": fields}}


HELD = [
    item("inetnum", "66.22.192.0 - 66.22.255.255", "US-DISCORD1-20000919", "ALLOCATED PA"),
    item("inetnum", "66.22.196.0 - 66.22.199.255", "discord-nlrtm1-1", "ASSIGNED PA"),
    item("inetnum", "66.22.216.0 - 66.22.217.255", "discord-rumow2-1", "ASSIGNED PA"),
    item("inetnum", "195.62.89.0 - 195.62.89.255", "US-DISCORD1-20221116", "ALLOCATED PA"),
    item("inet6num", "2a0f:5707:aa00::/40", "discord-v6", "ASSIGNED"),
    {"type": "route", "attributes": {"attribute": [{"name": "route", "value": "8.8.8.0/24"}]}},
]


class Registry(http.server.ThreadingHTTPServer):
    """A registry of the tests: it answers every search with the objects it was given and keeps what was asked."""

    def __init__(self, objects):
        super().__init__(("127.0.0.1", 0), Asked)
        self.objects = objects
        self.asked = []
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_address[1]}/search.json"


class Asked(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.asked.append(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
        body = json.dumps({"objects": {"object": self.server.objects}}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def run(registry, out, *words):
    return subprocess.run(
        [sys.executable, str(HERE / "discord_voice.py"), "--registry", registry, "--wait", "5", "--out", str(out), *words],
        capture_output=True, text=True, check=False)


def listed(path):
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]


def main():
    checks = 0

    asked = urllib.parse.parse_qsl(urllib.parse.urlsplit(tool.address("some-MNT", "https://registry.example/search.json")).query)
    assert ("query-string", "some-MNT") in asked and ("inverse-attribute", "mnt-by") in asked, asked
    assert [value for key, value in asked if key == "type-filter"] == ["inetnum", "inet6num"], asked
    checks += 2

    found, sites = tool.held({"objects": {"object": HELD}})
    assert sites == ["discord-nlrtm1-1", "discord-rumow2-1", "discord-v6"], sites
    assert ipaddress.ip_network("66.22.192.0/18") in found and ipaddress.ip_network("66.22.216.0/23") in found, found
    assert ipaddress.ip_network("8.8.8.0/24") not in found, "an object of another kind is passed by"
    nets = tool.collapse(found)
    assert [str(net) for net in nets] == ["66.22.192.0/18", "195.62.89.0/24", "2a0f:5707:aa00::/40"], nets
    assert tool.held({}) == ([], [])
    checks += 5

    text = tool.render(nets, [f"discord-site{number}-1" for number in range(30)], "some-MNT", "2026-10-08")
    assert text.startswith("# Discord voice servers for clients that route by address. Checked 2026-10-08.\n"), text
    assert "some-MNT" in text and "discord-site29-1" in text and max(len(line) for line in text.splitlines()) <= 120, text
    checks += 2

    with tempfile.TemporaryDirectory() as folder:
        path = pathlib.Path(folder) / "ag-discord-voice.txt"
        path.write_text(text, encoding="utf-8", newline="\n")
        assert build.KEY.match(path.stem)
        assert build.read(path) == nets, "the builder takes the list"
        checks += 2

        registry = Registry(HELD)
        out = pathlib.Path(folder) / "one.txt"
        said = run(registry.url, out)
        assert said.returncode == 0 and "5 networks registered, 3 sites, 3 networks after joining, 16640 IPv4 addresses" in said.stdout, said
        assert listed(out) == ["66.22.192.0/18", "195.62.89.0/24", "2a0f:5707:aa00::/40"], listed(out)
        assert ("query-string", tool.HOLDER) in registry.asked[0], registry.asked
        checks += 3

        kept = out.read_text(encoding="utf-8")
        said = run(registry.url, out, "--most", "1000")
        assert said.returncode != 0 and "more than 1000 IPv4 addresses" in said.stderr, said
        assert out.read_text(encoding="utf-8") == kept, "a list that would grow past the limit is left as it was"
        checks += 2
        registry.shutdown()

        registry = Registry([item("inetnum", "10.0.0.0 - 10.0.0.255", "discord-odd", "ASSIGNED PA")])
        said = run(registry.url, out)
        assert said.returncode != 0 and "not global" in said.stderr and out.read_text(encoding="utf-8") == kept, said
        registry.shutdown()

        registry = Registry([])
        said = run(registry.url, out)
        assert said.returncode != 0 and "names no network" in said.stderr and out.read_text(encoding="utf-8") == kept, said
        gone = registry.url
        registry.shutdown()
        registry.server_close()

        said = run(gone, out)
        assert said.returncode != 0 and "gave no answer to read" in said.stderr and out.read_text(encoding="utf-8") == kept, said
        checks += 3

    print(f"ok, {checks} checks")


if __name__ == "__main__":
    main()
