# amneziageo-geo

Geo lists of AmneziaGeo that close gaps in the public ones.

## Use

Add a geo source of kind `geoip` with the address

```
https://raw.githubusercontent.com/bor-project/amneziageo-geo/release/geoip.dat
```

and a geo source of kind `geosite` with the address

```
https://raw.githubusercontent.com/bor-project/amneziageo-geo/release/geosite.dat
```

Mirrors: `https://cdn.jsdelivr.net/gh/bor-project/amneziageo-geo@release/geoip.dat` and
`https://cdn.jsdelivr.net/gh/bor-project/amneziageo-geo@release/geosite.dat`

## Keys

| Key | Holds |
|---|---|
| `geoip:ag-youtube` | YouTube for clients that route by address: Google front ends and the video caches of our servers |
| `geoip:ag-tiktok` | TikTok for clients that route by address: the networks its names answer with from our servers and from Russia |
| `geosite:ag-tiktok` | Names of TikTok hosts (API, images, video, live) for a template to resolve |

Every key starts with `ag-`, so it never replaces a key of another source.

## Lists

One file per key, named after the key: `src/ip/ag-youtube.txt` is `geoip:ag-youtube`, `src/site/ag-tiktok.txt` is
`geosite:ag-tiktok`. `#` starts a comment.

- `src/ip`: a line holds one global network.
- `src/site`: a line holds one name, asked as it is; `domain:` before a name takes its subdomains too.

A push to `master` builds `geoip.dat` and `geosite.dat` and publishes them with their `.sha256sum` files to the
`release` branch. Build by hand: `python3 tools/build.py src out`.

The names of `geosite:ag-tiktok` come in part from [rekryt/iplist](https://github.com/rekryt/iplist) under the MIT
License, see `NOTICE.md`.
