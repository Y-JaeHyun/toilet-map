from scripts.hours import parse_hours as p

A = {"t": "always"}
U = {"t": "unknown"}


def R(o, c, w=False):
    return {"t": "range", "open": o, "close": c, "weekdayOnly": w}


def test_always():
    assert p("상시", "") == A
    assert p("정시", "24시간") == A
    assert p("정시", "00:00~24:00") == A
    assert p("", "00:00-24:00") == A


def test_range():
    assert p("정시", "09:00~18:00") == R("09:00", "18:00")
    assert p("정시", "10:30-20:30") == R("10:30", "20:30")
    assert p("정시", "9:00~18:00") == R("09:00", "18:00")


def test_overnight():
    assert p("정시", "22:00~06:00") == R("22:00", "06:00")


def test_weekday():
    assert p("정시", "(평일)09:00~18:00") == R("09:00", "18:00", True)


def test_unknown():
    for k, d in [("정시", ""), ("정시", "9시간"), ("불규칙", ""), ("", ""),
                 ("정시", "하절기 06:00~21:00, 동절기 07:00~20:00"),
                 ("정시", "(주말)09:00~18:00")]:
        assert p(k, d) == U, (k, d)


def test_hour_only_ranges():
    assert p("", "00~24") == A
    assert p("정시", "09~18시") == R("09:00", "18:00")
    assert p("정시", "09시~18시") == R("09:00", "18:00")
    assert p("", "9시~18시") == R("09:00", "18:00")
    assert p("", "05~24") == R("05:00", "24:00")


def test_always_kind_with_garbage_detail():
    assert p("상시", ":~:") == A


def test_weekday_and_weekend_same():
    assert p("정시", "(평일)09:00-18:00+(주말)09:00-18:00") == R("09:00", "18:00")


def test_weekday_and_weekend_differ_is_unknown():
    assert p("정시", "(평일)09:00-18:00+(주말)10:00-17:00") == U


def test_weekday_with_holiday_closed_note():
    assert p("정시", "(평일)09:00-18:00+공휴일, 국경일 미개방") == R("09:00", "18:00", True)
