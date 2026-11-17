"""Address -> (lat, lng) via the VWorld geocoder, with a persistent cache.

Only VWorld (MOLIT public API) is used: Kakao Local API results may not be stored.
"""
import http.client
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = "https://api.vworld.kr/req/address"

_PARENS = re.compile(r"\([^)]*\)|\[[^\]]*\]")
# trailing floor / unit notes: ", 2층", "지하1층", "B1", "1층 101호" ...
_TAIL = re.compile(r"(,|\s)\s*(지하\s*\d+\s*층|지상\s*\d+\s*층|\d+\s*층|B\d+|\d+\s*호|지하$).*$")
# a lot / building number must be present, else the geocoder returns a road or town centroid
_NUMBER = re.compile(r"(?:^|[\s,동리가로길])(?:산\s?)?\d+(?:-\d+)?(?=[\s,]|$)")


def has_number(addr):
    return bool(_NUMBER.search(addr or ""))


_UNDERGROUND = re.compile(r"지하\s+(\d+(?:-\d+)?)(?=[\s,]|$)")
_GLUED = re.compile(r"(?<=[로길동리가])(\d+(?:-\d+)?)(?=[\s,]|$)")
# "<road|dong> [산] <number>" core used to check VWorld's refined address
_CORE = re.compile(r"(\S+?(?:로|길|동|리|가))\s(?:산\s?)?(\d+(?:-\d+)?)(?=[\s,]|$)")


def normalize(addr):
    s = _PARENS.sub(" ", addr or "")
    s = re.sub(r"\s+", " ", s).strip()
    # VWorld cannot parse "지하 N" and silently fuzzy-matches another road; the surface number is close
    s = _UNDERGROUND.sub(r"\1", s)
    s = _GLUED.sub(r" \1", s)
    s = _TAIL.sub("", s).strip(" ,")
    return s


def matches(query, refined, kind):
    """True when VWorld's refined address keeps the queried road/lot number."""
    m = _CORE.search(query)
    if not m or not refined:
        return False
    name, num = m.group(1), re.escape(m.group(2))
    refined = re.sub(r"\s+", " ", refined)
    if kind == "road":
        return re.search(rf"(?:^|\s){re.escape(name)} {num}(?=[\s,(]|$)", refined) is not None
    # parcel: legal/admin dong names may differ, the lot number must not
    return re.search(rf"[동리가] (?:산 ?)?{num}(?=[\s,(]|$)", refined) is not None


class Geocoder:
    def __init__(self, fetch, cache):
        self.fetch = fetch
        self.cache = cache  # "<type>|<normalized address>" -> [lat, lng, refined] | None
        self.used = set()

    def _query(self, addr, kind):
        addr = normalize(addr)
        if not addr or not has_number(addr):
            return None
        key = f"{kind}|{addr}"
        self.used.add(key)
        hit = self.cache.get(key, "missing")
        if hit == "missing" or (hit is not None and len(hit) != 3):  # legacy entries lack refined text
            res = self.fetch({"address": addr, "type": kind})
            resp = res.get("response", {})
            if resp.get("status") == "OK":
                pt = resp["result"]["point"]
                refined = (resp.get("refined") or {}).get("text", "")
                hit = [round(float(pt["y"]), 6), round(float(pt["x"]), 6), refined]
            else:
                hit = None
            self.cache[key] = hit
        if hit and matches(addr, hit[2], kind):
            return (hit[0], hit[1])
        return None

    def lookup(self, road, parcel):
        for addr, kind in ((road, "road"), (parcel, "parcel"), (road, "parcel")):
            if not (addr or "").strip():
                continue
            hit = self._query(addr, kind)
            if hit:
                return hit
        return None

    def used_cache(self):
        return {k: self.cache[k] for k in self.used if k in self.cache}


_last_call = [0.0]


def vworld_fetch(params):
    key = os.environ["VWORLD_KEY"]
    q = {"service": "address", "request": "getcoord", "version": "2.0",
         "crs": "epsg:4326", "format": "json", "refine": "true", "simple": "false",
         "key": key, **params}
    url = ENDPOINT + "?" + urllib.parse.urlencode(q)
    attempts = 6
    for attempt in range(attempts):
        wait = 0.1 - (time.monotonic() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                data = json.load(r)
            status = data.get("response", {}).get("status")
            if status == "ERROR":
                err = data["response"].get("error", {})
                # quota / key errors must stop the run, not be cached as "not found"
                raise RuntimeError(f"vworld error: {err.get('code')} {err.get('text')}")
            return data
        # RemoteDisconnected / ConnectionReset are OSError or HTTPException, not URLError
        except (OSError, http.client.HTTPException, json.JSONDecodeError):
            if attempt == attempts - 1:
                raise
            time.sleep(min(30, 2 ** attempt))
    raise AssertionError("unreachable")


def load_cache(path):
    p = pathlib.Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_cache(path, cache):
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, sort_keys=True, indent=0), encoding="utf-8")
    tmp.replace(p)
