"""Download and filter the MOIS public toilet dataset (localdata)."""
import csv
import io
import pathlib
import urllib.request

URL = "https://file.localdata.go.kr/file/download/public_restroom_info/info"
REFERER = "https://file.localdata.go.kr/file/public_restroom_info/info"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
REGIONS = ("서울특별시", "경기도")


def download(dest):
    dest = pathlib.Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(URL, headers={"User-Agent": UA, "Referer": REFERER})
    with urllib.request.urlopen(req, timeout=180) as r:
        ctype = r.headers.get("Content-Type", "")
        body = r.read()
    if "csv" not in ctype:
        raise RuntimeError(f"unexpected content-type {ctype!r} ({len(body)} bytes)")
    dest.write_bytes(body)
    return dest


def load_rows(path):
    text = pathlib.Path(path).read_bytes().decode("cp949")
    return list(csv.DictReader(io.StringIO(text)))


def _sido(row):
    addr = (row.get("소재지도로명주소") or "").strip() or (row.get("소재지지번주소") or "").strip()
    return addr.split()[0] if addr else ""


def filter_region(rows):
    return [r for r in rows
            if _sido(r) in REGIONS and (r.get("개방시간") or "").strip() != "미개방"]
