import json

from scripts.build import cell_of, to_record, write_tiles


def row(**kw):
    base = {"관리번호": "1", "화장실명": "a", "구분명": "공중화장실",
            "소재지도로명주소": "서울특별시 종로구 인사동길 44", "소재지지번주소": "",
            "개방시간": "상시", "개방시간상세": "",
            "남성용-장애인용대변기수": "0", "여성용-장애인용대변기수": "0",
            "기저귀교환대유무": "N", "비상벨설치여부": "N", "전화번호": ""}
    base.update(kw)
    return base


def test_cell_of_city_hall():
    assert cell_of(37.5663, 126.9779) == (2539, 751)


def test_to_record_fields():
    r = to_record(row(**{"여성용-장애인용대변기수": "1", "기저귀교환대유무": "Y",
                         "비상벨설치여부": "Y", "전화번호": "021234"}), (37.5742511, 126.9848358))
    assert r == {"id": "1", "n": "a", "lat": 37.574251, "lng": 126.984836, "k": "공중화장실",
                 "h": {"t": "always"}, "dis": True, "dia": True, "bell": True,
                 "a": "서울특별시 종로구 인사동길 44", "tel": "021234"}


def test_to_record_no_disabled_and_jibun_address():
    r = to_record(row(**{"소재지도로명주소": "", "소재지지번주소": "경기도 성남시 정자동 1",
                         "남성용-장애인용대변기수": ""}), (37.0, 127.0))
    assert r["dis"] is False
    assert r["a"] == "경기도 성남시 정자동 1"


def test_write_tiles_splits_by_cell(tmp_path):
    a = {"id": "a", "lat": 37.5499, "lng": 126.97}
    b = {"id": "b", "lat": 37.5501, "lng": 126.97}
    write_tiles([a, b], tmp_path)
    files = sorted(p.name for p in tmp_path.iterdir())
    assert files == ["2539_750.json", "2539_751.json"]
    assert json.loads((tmp_path / "2539_751.json").read_text())[0]["id"] == "b"
