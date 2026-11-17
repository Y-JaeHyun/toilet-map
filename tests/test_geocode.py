from scripts.geocode import Geocoder, normalize


def ok(x, y, refined=None):
    def resp(params):
        text = refined if refined is not None else params["address"]
        return {"response": {"status": "OK", "refined": {"text": text},
                             "result": {"point": {"x": str(x), "y": str(y)}}}}
    return resp


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
    g = Geocoder(FakeFetch(lambda p: ok(126.98, 37.57)(p)), {})
    assert g.lookup("서울특별시 종로구 인사동길 44", "") == (37.57, 126.98)


def test_road_column_with_jibun_falls_back_to_parcel():
    f = FakeFetch(lambda p: NF if p["type"] == "road" else ok(126.97, 37.58)(p))
    g = Geocoder(f, {})
    assert g.lookup("서울특별시 종로구 사직동 1-28", "") == (37.58, 126.97)
    assert [c["type"] for c in f.calls] == ["road", "parcel"]


def test_parcel_column_used_when_road_fails():
    f = FakeFetch(lambda p: ok(127.0, 37.0)(p) if p["address"] == "경기도 성남시 분당구 정자동 1" else NF)
    g = Geocoder(f, {})
    assert g.lookup("경기도 성남시 분당구 없는로 9", "경기도 성남시 분당구 정자동 1") == (37.0, 127.0)


def test_same_address_fetched_once():
    f = FakeFetch(lambda p: ok(126.98, 37.57)(p))
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


def test_vworld_fetch_retries_on_remote_disconnect(monkeypatch):
    import http.client
    import io
    import json as _json

    from scripts import geocode as gmod

    calls = []

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(url, timeout=None):
        calls.append(url)
        if len(calls) < 3:
            raise http.client.RemoteDisconnected("Remote end closed connection without response")
        return Resp(_json.dumps({"response": {"status": "NOT_FOUND"}}).encode())

    monkeypatch.setenv("VWORLD_KEY", "test")
    monkeypatch.setattr(gmod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(gmod.time, "sleep", lambda s: None)
    assert gmod.vworld_fetch({"address": "x", "type": "road"})["response"]["status"] == "NOT_FOUND"
    assert len(calls) == 3


def test_normalize_keeps_underground_building_number():
    # VWorld cannot parse "지하 N" and fuzzy-matches another address; the surface number is close
    assert normalize("서울특별시 중구 세종대로 지하 2") == "서울특별시 중구 세종대로 2"
    assert normalize("서울특별시 중구 세종대로 지하 101 (시청역)") == "서울특별시 중구 세종대로 101"


def test_has_number():
    from scripts.geocode import has_number
    assert has_number("서울특별시 중구 세종대로 지하 2")
    assert has_number("경기도 고양시 덕양구 화정동994, 화정2동 행정복지센터")
    assert has_number("경기도 김포시 풍무동 산 141-3 금정산 산책로")
    assert not has_number("서울특별시 중구 세종대로")
    assert not has_number("서울특별시 중구 세종대로12길")
    assert not has_number("경기도 가평군 청평면")


def test_numberless_address_is_not_queried():
    f = FakeFetch(lambda p: ok(126.97, 37.56)(p))
    g = Geocoder(f, {})
    assert g.lookup("서울특별시 중구 세종대로", "") is None
    assert f.calls == []


def test_used_cache_only_keeps_queried_keys():
    cache = {"road|서울특별시 옛주소 1": [37.0, 127.0]}
    g = Geocoder(FakeFetch(lambda p: ok(126.98, 37.57)(p)), cache)
    g.lookup("서울특별시 종로구 인사동길 44", "")
    assert g.used_cache() == {"road|서울특별시 종로구 인사동길 44": [37.57, 126.98, "서울특별시 종로구 인사동길 44"]}


def test_normalize_splits_glued_numbers():
    assert normalize("서울특별시 도봉구 노해로379") == "서울특별시 도봉구 노해로 379"
    assert normalize("경기도 수원시 팔달구 일월로22번길23") == "경기도 수원시 팔달구 일월로22번길 23"
    assert normalize("경기도 고양시 덕양구 화정동994, 화정2동 행정복지센터") == "경기도 고양시 덕양구 화정동 994, 화정2동 행정복지센터"
    assert normalize("서울특별시 중구 세종대로12길") == "서울특별시 중구 세종대로12길"


def test_refined_mismatch_road_is_rejected():
    f = FakeFetch(lambda p: ok(127.1, 37.5, "서울특별시 송파구 오금로21길 1 (방이동)")(p))
    g = Geocoder(f, {})
    assert g.lookup("서울특별시 송파구 오금로 1", "") is None


def test_refined_match_road_with_dong_suffix_is_accepted():
    f = FakeFetch(lambda p: ok(127.0, 37.6, "서울특별시 도봉구 노해로 379 (창동)")(p))
    assert Geocoder(f, {}).lookup("서울특별시 도봉구 노해로379", "") == (37.6, 127.0)


def test_refined_parcel_must_keep_lot_number():
    bad = FakeFetch(lambda p: ok(127.1, 37.3, "경기도 성남시 분당구 미금로 218 (금곡동)")(p))
    assert Geocoder(bad, {}).lookup("", "경기도 성남시 분당구 금곡동 218") is None
    renamed = FakeFetch(lambda p: ok(126.7, 37.3, "경기도 시흥시 거모동 1352")(p))
    assert Geocoder(renamed, {}).lookup("", "경기도 시흥시 군자동 1352") == (37.3, 126.7)
    mountain = FakeFetch(lambda p: ok(127.0, 37.6, "서울특별시 노원구 중계동 산 104-12")(p))
    assert Geocoder(mountain, {}).lookup("", "서울특별시 노원구 중계본동 산 104-12") == (37.6, 127.0)


def test_legacy_cache_entries_without_refined_are_requeried():
    f = FakeFetch(lambda p: ok(126.98, 37.57)(p))
    g = Geocoder(f, {"road|서울특별시 종로구 인사동길 44": [1.0, 2.0]})
    assert g.lookup("서울특별시 종로구 인사동길 44", "") == (37.57, 126.98)
    assert len(f.calls) == 1


def test_review_road_core_never_accepted_as_parcel():
    from scripts.geocode import matches
    assert not matches("서울특별시 송파구 오금로 1", "서울특별시 송파구 방이동 1", "parcel")


def test_review_mountain_lot_must_match_exactly():
    from scripts.geocode import matches
    assert not matches("서울특별시 성동구 행당동 산17", "서울특별시 성동구 행당동 17", "parcel")
    assert not matches("서울특별시 성동구 행당동 17", "서울특별시 성동구 행당동 산 17", "parcel")
    assert matches("서울특별시 노원구 중계본동 산 104-12", "서울특별시 노원구 중계동 산 104-12", "parcel")


def test_review_sigungu_must_match():
    from scripts.geocode import matches
    assert not matches("경기도 수원시 팔달구 중앙로 10", "경기도 안양시 만안구 중앙로 10", "road")
    assert matches("경기도 수원시 팔달구 중앙로 10", "경기도 수원시 팔달구 중앙로 10 (매산로1가)", "road")


def test_review_glued_district_and_road_split():
    assert normalize("서울특별시 용산구원효로 147") == "서울특별시 용산구 원효로 147"


def test_review_road_string_with_road_core_not_retried_as_parcel():
    f = FakeFetch(lambda p: NF if p["type"] == "road" else ok(126.96, 37.53, "서울특별시 용산구 원효로3가 147")(p))
    assert Geocoder(f, {}).lookup("서울특별시 용산구 원효로 147", "") is None
    assert [c["type"] for c in f.calls] == ["road"]
