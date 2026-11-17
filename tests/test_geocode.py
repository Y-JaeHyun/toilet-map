from scripts.geocode import Geocoder, normalize


def ok(x, y):
    return {"response": {"status": "OK", "result": {"point": {"x": str(x), "y": str(y)}}}}


NF = {"response": {"status": "NOT_FOUND"}}


class FakeFetch:
    def __init__(self, fn):
        self.fn, self.calls = fn, []

    def __call__(self, params):
        self.calls.append(dict(params))
        return self.fn(params)


def test_normalize_strips_parens_and_floor():
    assert normalize("서울특별시 종로구 인사동길 44 (쌈지길) 지하1층") == "서울특별시 종로구 인사동길 44"
    assert normalize("  경기도  수원시 팔달구 정조로 1, 2층 ") == "경기도 수원시 팔달구 정조로 1"


def test_point_order_is_lat_lng():
    g = Geocoder(FakeFetch(lambda p: ok(126.98, 37.57)), {})
    assert g.lookup("서울특별시 종로구 인사동길 44", "") == (37.57, 126.98)


def test_road_column_with_jibun_falls_back_to_parcel():
    f = FakeFetch(lambda p: NF if p["type"] == "road" else ok(126.97, 37.58))
    g = Geocoder(f, {})
    assert g.lookup("서울특별시 종로구 사직동 1-28", "") == (37.58, 126.97)
    assert [c["type"] for c in f.calls] == ["road", "parcel"]


def test_parcel_column_used_when_road_fails():
    f = FakeFetch(lambda p: ok(127.0, 37.0) if p["address"] == "경기도 성남시 분당구 정자동 1" else NF)
    g = Geocoder(f, {})
    assert g.lookup("경기도 성남시 분당구 없는로 9", "경기도 성남시 분당구 정자동 1") == (37.0, 127.0)


def test_same_address_fetched_once():
    f = FakeFetch(lambda p: ok(126.98, 37.57))
    g = Geocoder(f, {})
    g.lookup("서울특별시 종로구 인사동길 44", "")
    g.lookup("서울특별시 종로구 인사동길 44 (지하1층)", "")
    assert len(f.calls) == 1


def test_failure_is_cached():
    f = FakeFetch(lambda p: NF)
    g = Geocoder(f, {})
    assert g.lookup("서울특별시 없는구 없는로 1", "") is None
    n = len(f.calls)
    assert g.lookup("서울특별시 없는구 없는로 1", "") is None
    assert len(f.calls) == n


def test_normalize_keeps_road_names_starting_with_jiha():
    assert normalize("서울특별시 중구 지하상가로 5") == "서울특별시 중구 지하상가로 5"
    assert normalize("서울특별시 중구 을지로 1 지하") == "서울특별시 중구 을지로 1"
