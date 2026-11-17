import csv

from scripts.source import filter_region, load_rows

HEADER = ["관리번호", "구분명", "화장실명", "소재지도로명주소", "소재지지번주소", "개방시간", "개방시간상세"]


def _write(path, rows):
    with open(path, "w", encoding="cp949", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)


def test_filter_region_keeps_seoul_gyeonggi_and_drops_closed(tmp_path):
    p = tmp_path / "t.csv"
    _write(p, [
        ["1", "공중화장실", "a", "서울특별시 종로구 인사동길 44", "", "상시", ""],
        ["2", "공중화장실", "b", "경기도 수원시 팔달구 정조로 1", "", "정시", ""],
        ["3", "공중화장실", "c", "부산광역시 중구 중앙대로 1", "", "상시", ""],
        ["4", "공중화장실", "d", "서울특별시 중구 세종대로 110", "", "미개방", ""],
        ["5", "개방화장실", "e", "", "경기도 성남시 분당구 정자동 1", "상시", ""],
    ])
    rows = load_rows(p)
    assert len(rows) == 5
    assert [r["관리번호"] for r in filter_region(rows)] == ["1", "2", "5"]
