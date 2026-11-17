"""Normalize the free-text opening hours of the public toilet dataset."""
import re

ALWAYS = {"t": "always"}
UNKNOWN = {"t": "unknown"}

_ALWAYS_WORDS = {"상시", "24시간", "연중무휴", "24시간개방", "상시개방"}
_SEP = r"[~\-∼〜～]"
# "09:00", "0900", "9", "09시", "9시30분"
_TIME = r"(\d{1,2})(?::?(\d{2})|시(?:(\d{1,2})분)?)?"
_RANGE = re.compile(rf"^{_TIME}{_SEP}{_TIME}시?$")
_WEEKDAY = re.compile(r"^\(?평일\)?:?")
_WEEKEND = re.compile(r"^\(?(주말|주말및공휴일|토일|토·일)\)?:?")


def _hhmm(h, m):
    h, m = int(h), int(m or 0)
    if h > 24 or m > 59 or (h == 24 and m != 0):
        return None
    return f"{h:02d}:{m:02d}"


def _parse_range(s):
    """Return (open, close) or None."""
    m = _RANGE.match(s)
    if not m:
        return None
    g = m.groups()
    o = _hhmm(g[0], g[1] or g[2])
    c = _hhmm(g[3], g[4] or g[5])
    if not o or not c or o == c:
        if o == "00:00" and c == "00:00":
            return ("00:00", "24:00")
        return None
    return (o, c)


def _range(oc, weekday):
    o, c = oc
    if o == "00:00" and c == "24:00" and not weekday:
        return ALWAYS
    return {"t": "range", "open": o, "close": c, "weekdayOnly": weekday}


def _parse_detail(detail):
    s = re.sub(r"\s+", "", detail or "")
    if not s:
        return None
    if s in _ALWAYS_WORDS:
        return ALWAYS
    m = _WEEKDAY.match(s)
    if m and m.group(0):
        parts = s[m.end():].split("+", 1)
        wk = _parse_range(parts[0])
        if not wk:
            return UNKNOWN
        if len(parts) == 2:
            we = _WEEKEND.match(parts[1])
            if we:
                # weekend hours listed: only usable when identical to weekday
                return _range(wk, False) if _parse_range(parts[1][we.end():]) == wk else UNKNOWN
        return _range(wk, True)
    oc = _parse_range(s)
    return _range(oc, False) if oc else UNKNOWN


def parse_hours(kind, detail):
    """Return {"t":"always"} | {"t":"range",...} | {"t":"unknown"}."""
    kind = (kind or "").strip()
    parsed = _parse_detail(detail)
    if parsed is not None and parsed is not UNKNOWN:
        return parsed
    # "상시" with an unreadable detail: trust it only when the detail has no times at all (e.g. ":~:")
    if kind == "상시" and not re.search(r"\d", detail or ""):
        return ALWAYS
    return UNKNOWN
