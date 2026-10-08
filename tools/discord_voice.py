"""Asks the RIPE database for the address space Discord holds, where its voice servers stand, and writes it as a list."""
import argparse
import datetime
import ipaddress
import json
import pathlib
import sys
import urllib.parse
import urllib.request

HOLDER = "lir-us-discord1-1-MNT"
REGISTRY = "https://rest.db.ripe.net/search.json"
MOST = 262144


def address(holder, registry):
    query = [
        ("query-string", holder), ("inverse-attribute", "mnt-by"), ("type-filter", "inetnum"),
        ("type-filter", "inet6num"), ("flags", "no-referenced"), ("flags", "no-irt"), ("flags", "no-filtering")]
    return f"{registry}?{urllib.parse.urlencode(query)}"


def fetch(url, wait):
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "amneziageo-geo"})
    with urllib.request.urlopen(request, timeout=wait) as answer:
        return json.load(answer)


def held(answer):
    """Returns the networks the objects of an answer name and the names of the sites they are assigned to."""
    nets, sites = [], set()
    for one in answer.get("objects", {}).get("object", []):
        fields = {}
        for field in one.get("attributes", {}).get("attribute", []):
            fields.setdefault(field.get("name"), field.get("value", ""))
        if one.get("type") == "inetnum" and " - " in fields.get("inetnum", ""):
            first, last = (ipaddress.ip_address(part.strip()) for part in fields["inetnum"].split(" - "))
            nets.extend(ipaddress.summarize_address_range(first, last))
        elif one.get("type") == "inet6num" and fields.get("inet6num"):
            nets.append(ipaddress.ip_network(fields["inet6num"].strip()))
        else:
            continue
        if fields.get("status", "").upper().startswith("ASSIGNED") and fields.get("netname"):
            sites.add(fields["netname"])
    return nets, sorted(sites)


def collapse(nets):
    return [net for version in (4, 6) for net in ipaddress.collapse_addresses(n for n in nets if n.version == version)]


def render(nets, sites, holder, day):
    head = [
        f"# Discord voice servers for clients that route by address. Checked {day}.",
        f"# The address space the RIPE database holds under the maintainer {holder} of Discord. Its sites:",
    ]
    line = "#"
    for site in sites:
        if len(line) + len(site) + 1 > 118:
            head.append(line)
            line = "#"
        line += f" {site}"
    if line != "#":
        head.append(line)
    return "\n".join(head + [""] + [str(net) for net in nets]) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holder", default=HOLDER, help="the maintainer the networks are registered under")
    parser.add_argument("--registry", default=REGISTRY, help="the search address of the registry")
    parser.add_argument("--wait", type=float, default=30.0, help="seconds the registry is waited for")
    parser.add_argument("--most", type=int, default=MOST, help="the most IPv4 addresses the list may hold")
    parser.add_argument("--out", default="src/ip/ag-discord-voice.txt", help="the list to write")
    args = parser.parse_args()

    try:
        found, sites = held(fetch(address(args.holder, args.registry), args.wait))
    except (OSError, ValueError) as ex:
        sys.exit(f"the registry gave no answer to read: {ex}")
    odd = [net for net in found if not net.is_global]
    if odd:
        sys.exit(f"the registry names a network that is not global: {odd[0]}")
    nets = collapse(found)
    if not nets:
        sys.exit("the registry names no network: the list is left as it was")
    count = sum(net.num_addresses for net in nets if net.version == 4)
    print(f"{len(found)} networks registered, {len(sites)} sites, {len(nets)} networks after joining, {count} IPv4 addresses")
    if count > args.most:
        sys.exit(f"the registry names more than {args.most} IPv4 addresses: look at it before the list is written")
    out = pathlib.Path(args.out)
    out.write_text(render(nets, sites, args.holder, datetime.date.today().isoformat()), encoding="utf-8", newline="\n")
    for net in nets:
        print(f"  {net}")
    print(f"{out}: {len(nets)} networks")


if __name__ == "__main__":
    main()
