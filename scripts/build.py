"""Pipeline: download -> filter -> geocode -> tiles.

Usage: set -a; . ~/.config/toilet-map/keys.env; set +a; python3 -m scripts.build
"""
import argparse
import csv
import datetime as dt
import json
import math
import pathlib
import shutil
import sys

from scripts import geocode, source
from scripts.hours import parse_hours

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "public_restroom.csv"
CACHE = ROOT / "data" / "geocode-cache.json"
FAILED = ROOT / "data" / "geocode-failed.csv"
SITE_DATA = ROOT / "site" / "data"
CELL = 0.05


def cell_of(lat, lng):
    return (math.floor(lng / CELL), math.floor(lat / CELL))


def _int(v):
    try:
        return int(str(v).strip() or 0)
    except ValueError:
        return 0


def to_record(row, latlng):
    lat, lng = latlng
    return {
        "id": row["관리번호"].strip(),
        "n": row["화장실명"].strip(),
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "k": row.get("구분명", "").strip(),
        "h": parse_hours(row.get("개방시간", ""), row.get("개방시간상세", "")),
        "dis": _int(row.get("남성용-장애인용대변기수")) + _int(row.get("여성용-장애인용대변기수")) > 0,
        "dia": row.get("기저귀교환대유무", "").strip().upper() == "Y",
        "bell": row.get("비상벨설치여부", "").strip().upper() == "Y",
        "a": row.get("소재지도로명주소", "").strip() or row.get("소재지지번주소", "").strip(),
        "tel": row.get("전화번호", "").strip(),
    }


def write_tiles(records, out_dir):
    out_dir = pathlib.Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    cells = {}
    for r in records:
        cells.setdefault(cell_of(r["lat"], r["lng"]), []).append(r)
    for (cx, cy), recs in cells.items():
        recs.sort(key=lambda r: r["id"])
        (out_dir / f"{cx}_{cy}.json").write_text(
            json.dumps(recs, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(cells)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=pathlib.Path, default=RAW)
    ap.add_argument("--skip-download", action="store_true")
    args = ap.parse_args(argv)

    if not args.skip_download:
        print("downloading ...", flush=True)
        source.download(args.csv)
    rows = source.filter_region(source.load_rows(args.csv))
    print(f"target rows: {len(rows)}", flush=True)

    cache = geocode.load_cache(CACHE)
    g = geocode.Geocoder(geocode.vworld_fetch, cache)
    records, failed = [], []
    try:
        for i, row in enumerate(rows, 1):
            hit = g.lookup(row.get("소재지도로명주소", ""), row.get("소재지지번주소", ""))
            if hit:
                records.append(to_record(row, hit))
            else:
                failed.append(row)
            if i % 500 == 0:
                geocode.save_cache(CACHE, cache)
                print(f"  {i}/{len(rows)} matched={len(records)}", flush=True)
    finally:
        geocode.save_cache(CACHE, cache)

    FAILED.parent.mkdir(parents=True, exist_ok=True)
    with open(FAILED, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["관리번호", "화장실명", "소재지도로명주소", "소재지지번주소"])
        for r in failed:
            w.writerow([r["관리번호"], r["화장실명"], r["소재지도로명주소"], r["소재지지번주소"]])

    n_cells = write_tiles(records, SITE_DATA / "tiles")
    base = max((r.get("데이터기준일자", "") for r in rows), default="")
    (SITE_DATA / "meta.json").write_text(json.dumps({
        "cell": CELL, "baseDate": base, "count": len(records),
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    pct = 100 * len(records) / len(rows) if rows else 0
    print(f"matched {len(records)} / {len(rows)} ({pct:.1f}%), tiles={n_cells}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
