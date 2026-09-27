# amneziageo-geo

Geo lists of AmneziaGeo that close gaps in the public ones.

## Use

Add a geo source of kind `geoip` with the address

```
https://raw.githubusercontent.com/bor-project/amneziageo-geo/release/geoip.dat
```

Mirror: `https://cdn.jsdelivr.net/gh/bor-project/amneziageo-geo@release/geoip.dat`

## Keys

| Key | Holds |
|---|---|
| `geoip:ag-youtube` | YouTube for clients that route by address: Google front ends and the video caches of our servers |

Every key starts with `ag-`, so it never replaces a key of another source.

## Lists

One file per key in `src/ip`, named after the key: `src/ip/ag-youtube.txt` is `geoip:ag-youtube`.
A line holds one network, `#` starts a comment.

A push to `master` builds `geoip.dat` and publishes it with its `geoip.dat.sha256sum` to the `release` branch.
Build by hand: `python3 tools/build.py src out`.
