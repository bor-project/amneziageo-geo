"""Builds geoip.dat from the lists in src/ip."""
import hashlib
import ipaddress
import pathlib
import re
import sys

KEY = re.compile(r"^ag-[a-z0-9][a-z0-9-]{0,60}$")


def varint(value):
    out = bytearray()
    while value > 0x7F:
        out.append(value & 0x7F | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def field(number, payload):
    return varint(number << 3 | 2) + varint(len(payload)) + payload


def encode(lists):
    def cidr(net):
        return field(1, net.network_address.packed) + varint(2 << 3) + varint(net.prefixlen)

    def entry(code, nets):
        return field(1, code.encode("ascii")) + b"".join(field(2, cidr(net)) for net in nets)

    return b"".join(field(1, entry(code, nets)) for code, nets in lists.items())


def decode(data):
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


def read(path):
    nets = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        text = line.split("#", 1)[0].strip()
        if not text:
            continue
        try:
            nets.append(ipaddress.ip_network(text))
        except ValueError as ex:
            sys.exit(f"{path}:{number}: {ex}")
    if not nets:
        sys.exit(f"{path}: no networks")
    return [net for version in (4, 6) for net in ipaddress.collapse_addresses(n for n in nets if n.version == version)]


def main():
    src = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "src")
    out = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "out")
    lists = {}
    for path in sorted((src / "ip").glob("*.txt")):
        if not KEY.match(path.stem):
            sys.exit(f"{path}: a key is ag- and then lower case letters, digits and hyphens, at most 64 in all")
        lists[path.stem.upper()] = read(path)
    if not lists:
        sys.exit(f"{src / 'ip'}: no lists")
    data = encode(lists)
    if decode(data) != lists:
        sys.exit("geoip.dat does not read back as built")
    out.mkdir(parents=True, exist_ok=True)
    (out / "geoip.dat").write_bytes(data)
    (out / "geoip.dat.sha256sum").write_text(f"{hashlib.sha256(data).hexdigest()}  geoip.dat\n", encoding="ascii", newline="\n")
    for code, nets in lists.items():
        print(f"geoip:{code.lower()}: {sum(n.version == 4 for n in nets)} v4, {sum(n.version == 6 for n in nets)} v6")
    print(f"geoip.dat: {len(data)} bytes")


if __name__ == "__main__":
    main()
