"""Builds geoip.dat from the lists in src/ip and geosite.dat from the lists in src/site."""
import hashlib
import ipaddress
import pathlib
import re
import sys

KEY = re.compile(r"^ag-[a-z0-9][a-z0-9-]{0,60}$")
NAME = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
KINDS = {"full": 3, "domain": 2}


def varint(value):
    out = bytearray()
    while value > 0x7F:
        out.append(value & 0x7F | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def field(number, payload):
    return varint(number << 3 | 2) + varint(len(payload)) + payload


def read_varint(buf, at):
    value = shift = 0
    while True:
        byte = buf[at]
        at += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if byte < 0x80:
            return value, at


def parts(buf):
    at = 0
    while at < len(buf):
        key, at = read_varint(buf, at)
        if key & 7 == 0:
            value, at = read_varint(buf, at)
        elif key & 7 == 2:
            size, at = read_varint(buf, at)
            value, at = buf[at:at + size], at + size
        else:
            raise ValueError(f"wire type {key & 7}")
        yield key >> 3, value


def encode(lists):
    def cidr(net):
        return field(1, net.network_address.packed) + varint(2 << 3) + varint(net.prefixlen)

    def entry(code, nets):
        return field(1, code.encode("ascii")) + b"".join(field(2, cidr(net)) for net in nets)

    return b"".join(field(1, entry(code, nets)) for code, nets in lists.items())


def decode(data):
    lists = {}
    for _, body in parts(data):
        code, nets = "", []
        for number, value in parts(body):
            if number == 1:
                code = value.decode("ascii")
            elif number == 2:
                got = dict(parts(value))
                nets.append(ipaddress.ip_network((ipaddress.ip_address(got[1]), got.get(2, 0))))
        lists[code] = nets
    return lists


def encode_site(lists):
    def domain(kind, name):
        return varint(1 << 3) + varint(kind) + field(2, name.encode("ascii"))

    def entry(code, names):
        return field(1, code.encode("ascii")) + b"".join(field(2, domain(kind, name)) for kind, name in names)

    return b"".join(field(1, entry(code, names)) for code, names in lists.items())


def decode_site(data):
    lists = {}
    for _, body in parts(data):
        code, names = "", []
        for number, value in parts(body):
            if number == 1:
                code = value.decode("ascii")
            elif number == 2:
                got = dict(parts(value))
                names.append((got.get(1, 0), got[2].decode("ascii")))
        lists[code] = names
    return lists


def read(path):
    nets = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        text = line.split("#", 1)[0].strip()
        if not text:
            continue
        try:
            net = ipaddress.ip_network(text)
        except ValueError as ex:
            sys.exit(f"{path}:{number}: {ex}")
        if not net.is_global:
            sys.exit(f"{path}:{number}: {net} is not a global network")
        nets.append(net)
    if not nets:
        sys.exit(f"{path}: no networks")
    return [net for version in (4, 6) for net in ipaddress.collapse_addresses(n for n in nets if n.version == version)]


def read_site(path):
    names, seen = [], set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        text = line.split("#", 1)[0].strip()
        if not text:
            continue
        kind, _, name = text.rpartition(":")
        if (kind or "full") not in KINDS:
            sys.exit(f"{path}:{number}: a name is bare, full: or domain:")
        if not NAME.match(name):
            sys.exit(f"{path}:{number}: {name} is not a host name in lower case")
        if name in seen:
            sys.exit(f"{path}:{number}: {name} is listed twice")
        seen.add(name)
        names.append((KINDS[kind or "full"], name))
    if not names:
        sys.exit(f"{path}: no names")
    return names


def lists_of(folder, reader):
    lists = {}
    for path in sorted(folder.glob("*.txt")):
        if not KEY.match(path.stem):
            sys.exit(f"{path}: a key is ag- and then lower case letters, digits and hyphens, at most 64 in all")
        lists[path.stem.upper()] = reader(path)
    return lists


def write(out, name, data):
    (out / name).write_bytes(data)
    (out / f"{name}.sha256sum").write_text(f"{hashlib.sha256(data).hexdigest()}  {name}\n", encoding="ascii", newline="\n")


def main():
    src = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "src")
    out = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "out")
    lists = lists_of(src / "ip", read)
    sites = lists_of(src / "site", read_site)
    if not lists:
        sys.exit(f"{src / 'ip'}: no lists")
    data = encode(lists)
    if decode(data) != lists:
        sys.exit("geoip.dat does not read back as built")
    site_data = encode_site(sites)
    if decode_site(site_data) != sites:
        sys.exit("geosite.dat does not read back as built")
    out.mkdir(parents=True, exist_ok=True)
    write(out, "geoip.dat", data)
    for code, nets in lists.items():
        print(f"geoip:{code.lower()}: {sum(n.version == 4 for n in nets)} v4, {sum(n.version == 6 for n in nets)} v6")
    print(f"geoip.dat: {len(data)} bytes")
    if sites:
        write(out, "geosite.dat", site_data)
        for code, names in sites.items():
            print(f"geosite:{code.lower()}: {sum(k == 3 for k, _ in names)} full, {sum(k == 2 for k, _ in names)} domain")
        print(f"geosite.dat: {len(site_data)} bytes")


if __name__ == "__main__":
    main()
