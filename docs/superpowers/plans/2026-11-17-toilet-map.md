# 화장실 지도 (toilet-map) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 서울·경기 공중화장실을 현재 위치 기준 가까운 순으로 보여 주는 정적 웹(GitHub Pages)과, 그 데이터를 만드는 로컬 파이프라인.

**Architecture:** Python 파이프라인(`scripts/`)이 localdata CSV를 받아 서울·경기만 거르고, 브이월드 지오코더로 좌표를 붙이고(캐시 커밋), 개방시간을 정규화해 격자 타일 JSON(`site/data/`)으로 출력한다. 프런트(`site/`)는 바닐라 JS + Kakao Maps SDK로 주변 타일만 받아 거리순 목록·핀·열림 상태·길찾기 링크를 그린다.

**Tech Stack:** Python 3.12 (표준 라이브러리만, 테스트 pytest), Node 22 (`node --test`로 프런트 순수 로직 테스트), Kakao Maps JS SDK, GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-11-17-toilet-map-design.md`

## Global Constraints

- 대상: 주소 첫 토큰 `서울특별시` 또는 `경기도`; `개방시간 == "미개방"` 제외.
- 원천 CSV: `https://file.localdata.go.kr/file/download/public_restroom_info/info`, 인코딩 cp949, 브라우저 UA + Referer `https://file.localdata.go.kr/file/public_restroom_info/info` 필요.
- 지오코더: 브이월드 `https://api.vworld.kr/req/address` (`service=address&request=getcoord&version=2.0&crs=epsg:4326&format=json&type=road|parcel`). 카카오 로컬 API 사용 금지(결과 저장 불가 정책).
- 키: `~/.config/toilet-map/keys.env` (`VWORLD_KEY`, `KAKAO_JS_KEY`). `VWORLD_KEY`는 저장소 어디에도 들어가면 안 됨. `KAKAO_JS_KEY`는 `site/`에 포함 가능(도메인 제한).
- 목표 지오코딩 매칭률 ≥ 95%.
- 열림 판정이 불확실하면 `unknown`("시간 확인 필요") — 절대 `open`으로 추정하지 않음. `weekdayOnly`는 주말·공휴일에 `unknown`. 공휴일 목록에 해당 연도가 없으면 `weekdayOnly`는 항상 `unknown`.
- 시간대: 열림 판정은 Asia/Seoul 기준.
- 길찾기: `https://map.kakao.com/link/to/<이름>,<lat>,<lng>` (이름은 encodeURIComponent).
- 출처 표기: "행정안전부 공중화장실정보 (데이터 기준일 YYYY-MM-DD) · 좌표: 국토교통부 브이월드".
- 위치 권한 거부 시 서울시청(37.5663, 126.9779) 중심으로 시작.
- GitHub 저장소 생성·푸시는 사용자 승인 후.

## Review Focus

1. 자정을 넘기는 개방시간(`22:00~06:00`)을 새벽 3시에 조회 → `open`이어야 함. (Task 1, Task 4 테스트)
2. 도로명 칸에 지번이 들어 있는 행(예: `서울특별시 종로구 사직동 1-28`) → road 실패 후 parcel 재시도로 매칭돼야 함. (Task 2 테스트)
3. 같은 주소의 화장실 여러 개(건물 내 층별 개방화장실) → 지오코딩 1회 호출, 레코드는 모두 유지. (Task 2 테스트)
4. 위치가 격자 경계 근처일 때 → 인접 칸 화장실이 더 가까우면 목록에 나와야 함(3x3 칸 로드). (Task 4 테스트)
5. 기기 시간대가 한국이 아닌 사용자(해외 로밍 등) → 한국 시각으로 판정. (Task 4 테스트)

---

### Task 1: 개방시간 정규화 (Python)

**Files:**
- Create: `scripts/__init__.py`, `scripts/hours.py`
- Test: `tests/test_hours.py`

**Interfaces:**
- Produces: `parse_hours(kind: str, detail: str) -> dict` — 반환 형태는 셋 중 하나:
  - `{"t": "always"}`
  - `{"t": "range", "open": "HH:MM", "close": "HH:MM", "weekdayOnly": bool}` (`close`가 `open`보다 작거나 같으면 자정 넘김; `24:00` 허용)
  - `{"t": "unknown"}`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_hours.py`

```python
from scripts.hours import parse_hours as p
A={"t":"always"}; U={"t":"unknown"}
def R(o,c,w=False): return {"t":"range","open":o,"close":c,"weekdayOnly":w}

def test_always():
    assert p("상시","")==A
    assert p("정시","24시간")==A
    assert p("정시","00:00~24:00")==A
    assert p("","00:00-24:00")==A
def test_range():
    assert p("정시","09:00~18:00")==R("09:00","18:00")
    assert p("정시","10:30-20:30")==R("10:30","20:30")
    assert p("정시","9:00~18:00")==R("09:00","18:00")
def test_overnight():
    assert p("정시","22:00~06:00")==R("22:00","06:00")
def test_weekday():
    assert p("정시","(평일)09:00~18:00")==R("09:00","18:00",True)
def test_unknown():
    for k,d in [("정시",""),("정시","9시간"),("불규칙",""),("",""),("정시","하절기 06:00~21:00, 동절기 07:00~20:00")]:
        assert p(k,d)==U
```

- [ ] **Step 2: 실패 확인** — Run: `python3 -m pytest tests/test_hours.py -q` → FAIL (ImportError)
- [ ] **Step 3: `parse_hours` 구현** — 공백 제거 후 정규식. `~`, `-`, `∼`, `〜` 모두 구분자로 허용. 시간 범위가 2개 이상이거나(계절별 등) 해석 불가한 텍스트가 섞이면 `unknown`. `(평일)`/`평일` 접두는 `weekdayOnly=True`; `(주말)`, `(토)` 등 다른 요일 조건은 `unknown`.
- [ ] **Step 4: 통과 확인** — 같은 명령 → PASS
- [ ] **Step 5: 실데이터 커버리지 확인** — 원천 CSV(스크래치 `dl/all.bin` 또는 Task 2 다운로드 결과)에서 서울·경기 행의 `parse_hours` 결과 분포 출력. `unknown` 중 상위 20개 `개방시간상세` 패턴을 보고, 명백히 해석 가능한 패턴이 있으면 테스트 추가 후 파서 보강. 결과 분포를 커밋 메시지에 기록.
- [ ] **Step 6: Commit** — `git commit -m "feat(scripts): opening-hours normalizer"`

---

### Task 2: 다운로드·필터·지오코딩 (Python)

**Files:**
- Create: `scripts/source.py`, `scripts/geocode.py`
- Test: `tests/test_source.py`, `tests/test_geocode.py`

**Interfaces:**
- Produces:
  - `source.download(dest: pathlib.Path) -> pathlib.Path` — CSV 저장(덮어쓰기).
  - `source.load_rows(path) -> list[dict]` — cp949 디코딩, `csv.DictReader`.
  - `source.filter_region(rows) -> list[dict]` — Global Constraints의 대상 조건 적용. 시도 판정은 `소재지도로명주소` 우선, 비어 있으면 `소재지지번주소`의 첫 토큰.
  - `geocode.normalize(addr: str) -> str` — 앞뒤 공백·연속 공백 정리, 괄호 내용 제거, 끝의 층/호 표기(`지하1층`, `2층`, `B1` 등) 제거.
  - `geocode.Geocoder(fetch: Callable[[dict], dict], cache: dict)` 와 `Geocoder.lookup(road: str, parcel: str) -> tuple[float, float] | None` — `(lat, lng)`. 순서: road(정규화) `type=road` → parcel(정규화) `type=parcel` → road 문자열을 `type=parcel`로. 캐시 키는 `"<type>|<정규화주소>"`, 실패도 `None`으로 캐시. `fetch`는 쿼리 파라미터 dict를 받아 브이월드 JSON을 돌려주는 함수(테스트에서 가짜 주입).
  - `geocode.vworld_fetch(params: dict) -> dict` — 실제 HTTP 호출(`urllib`), key는 환경변수 `VWORLD_KEY`, 호출 간 최소 0.05초, 5xx/타임아웃 3회 재시도.
  - `geocode.load_cache(path) -> dict`, `geocode.save_cache(path, cache)` — JSON, 키 정렬(diff 안정).

- [ ] **Step 1: 실패하는 테스트 작성**
  - `test_source.py`: 작은 cp949 CSV 픽스처(헤더는 실제 컬럼명 사용)로 `filter_region`이 서울·경기만 남기고 `미개방`을 빼고, 도로명 비고 지번만 있는 경기 행을 포함하는지.
  - `test_geocode.py`:
    - `normalize("서울특별시 종로구 인사동길 44 (쌈지길) 지하1층") == "서울특별시 종로구 인사동길 44"`
    - 가짜 fetch가 `type=road`엔 NOT_FOUND, `type=parcel`엔 OK를 주면 `lookup("서울특별시 종로구 사직동 1-28", "")`이 좌표 반환 (Review Focus 2).
    - 같은 주소 두 번 `lookup` → fetch 호출 1회 (Review Focus 3).
    - 모두 실패 → `None`, 두 번째 호출 시 fetch 추가 호출 없음.
    - 브이월드 응답 `{"response":{"status":"OK","result":{"point":{"x":"126.98","y":"37.57"}}}}` → `(37.57, 126.98)` (x=lng, y=lat 순서 주의).
- [ ] **Step 2: 실패 확인** — `python3 -m pytest tests/test_source.py tests/test_geocode.py -q` → FAIL
- [ ] **Step 3: 구현** (위 Interfaces 그대로)
- [ ] **Step 4: 통과 확인** — 같은 명령 → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(scripts): source download/filter and vworld geocoder with cache"`

---

### Task 3: 타일 빌드 + 파이프라인 실행 + 데이터 커밋

**Files:**
- Create: `scripts/build.py` (CLI 진입점 `python3 -m scripts.build`), `site/data/holidays.json`
- Generated (커밋): `data/geocode-cache.json`, `data/geocode-failed.csv`, `site/data/meta.json`, `site/data/tiles/*.json`
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: Task 1 `parse_hours`, Task 2 전부.
- Produces (프런트가 의존하는 데이터 계약):
  - `CELL = 0.05` (도). `cell_of(lat, lng) -> (cx, cy)` = `(floor(lng/CELL), floor(lat/CELL))`. 파일명 `site/data/tiles/{cx}_{cy}.json`.
  - 타일 JSON: 레코드 배열. 레코드 = `{"id": 관리번호, "n": 화장실명, "lat": float(6자리 반올림), "lng": float, "k": 구분명, "h": parse_hours 결과, "dis": bool(장애인용 대변기 남+여 > 0), "dia": bool(기저귀교환대유무=="Y"), "bell": bool(비상벨설치여부=="Y"), "a": 도로명 우선 주소, "tel": 전화번호|""}`
  - `site/data/meta.json`: `{"cell": 0.05, "baseDate": 데이터기준일자 최댓값 "YYYY-MM-DD", "count": int, "generatedAt": ISO8601}`
  - `site/data/holidays.json`: `{"years":[2026,2027], "dates":["YYYY-MM-DD", ...]}` — 2026·2027 한국 법정공휴일·대체공휴일(빌더가 공식 자료로 작성).
- CLI 동작: `python3 -m scripts.build [--csv PATH] [--skip-download]` — 다운로드 → 필터 → 지오코딩(진행률 출력, 캐시 주기적 저장) → 실패 CSV → 타일·meta 작성(기존 tiles 디렉토리 비우고 재생성) → 매칭률 출력 `matched X / Y (Z%)`.

- [ ] **Step 1: 실패하는 테스트** — `test_build.py`: `cell_of(37.5663,126.9779)==(2539,751)`; 레코드 변환 함수 `to_record(row, latlng) -> dict`가 위 계약 필드를 만드는지(장애인 판정 포함); `write_tiles(records, out_dir)`가 셀별 파일로 나누는지(경계 양쪽 두 레코드 → 파일 2개).
- [ ] **Step 2: 실패 확인 → Step 3: 구현 → Step 4: 통과 확인** — `python3 -m pytest -q`
- [ ] **Step 5: 실제 실행** — `set -a; . ~/.config/toilet-map/keys.env; set +a; python3 -m scripts.build`. 기대: 약 14,950건 처리, 매칭률 출력.
- [ ] **Step 6: 매칭률 판정** — ≥95%면 다음. 미만이면 `data/geocode-failed.csv` 상위 패턴을 보고 `normalize` 규칙을 테스트와 함께 보강 → 재실행(캐시 덕에 실패분만 재호출. 실패 캐시 항목은 규칙 변경 후 다시 시도되도록, 정규화 결과가 바뀐 키만 새로 조회됨을 확인).
- [ ] **Step 7: 비밀값 검사** — `grep -rF "$VWORLD_KEY" . --exclude-dir=.git` 결과 없음.
- [ ] **Step 8: Commit** — 코드 + 생성 데이터. 메시지에 매칭률·건수 기록.

---

### Task 4: 프런트 순수 로직 (JS, node 테스트)

**Files:**
- Create: `site/js/core.js` (ES module, DOM·카카오 의존 없음)
- Test: `tests/core.test.mjs`

**Interfaces:**
- Consumes: Task 3 데이터 계약.
- Produces:
  - `export const CELL = 0.05`
  - `export function cellOf(lat, lng) -> [cx, cy]` (Python과 동일 규칙)
  - `export function cellsAround(lat, lng) -> string[]` — 3x3 `"cx_cy"`
  - `export function distanceM(lat1, lng1, lat2, lng2) -> number` (하버사인)
  - `export function seoulNow(date: Date) -> {ymd: "YYYY-MM-DD", dow: 0-6, min: 0-1439}` — `Intl.DateTimeFormat`에 `timeZone: "Asia/Seoul"`
  - `export function openStatus(h, now, holidays) -> "open"|"closed"|"unknown"` — `now`는 `seoulNow` 결과, `holidays`는 holidays.json 객체.
  - `export function nearest(records, lat, lng, n) -> Array<{rec, d}>` — 거리순, `closed`는 같은 거리권에서도 뒤로 가지 않고 정렬은 거리만; 표시 단계에서 흐리게 처리(UI 담당).
  - `export function directionsUrl(rec) -> string`

- [ ] **Step 1: 실패하는 테스트** — `tests/core.test.mjs` (`node:test`, `node:assert`):
  - `cellOf(37.5663,126.9779)` → `[2539,751]` (Python과 일치)
  - `cellsAround` 길이 9, 중심 포함
  - `distanceM(37.5663,126.9779,37.5665,126.9780)` ≈ 23~25m
  - `openStatus({t:"range",open:"22:00",close:"06:00",weekdayOnly:false}, {ymd:"2026-11-18",dow:3,min:180}, H)` → `"open"` (Review Focus 1); 같은 범위 `min: 720` → `"closed"`
  - `weekdayOnly` 범위: 토요일 → `"unknown"`; 공휴일 목록에 있는 평일 → `"unknown"`; `holidays.years`에 없는 연도 평일 → `"unknown"`
  - `close:"24:00"` 처리, `{t:"always"}` → `"open"`, `{t:"unknown"}` → `"unknown"`
  - `seoulNow(new Date("2026-11-17T20:00:00Z"))` → `{ymd:"2026-11-18", dow:3, min:300}` (기기 TZ 무관, Review Focus 5 — `TZ=America/New_York node --test`로도 실행)
  - `nearest`: 경계 너머 레코드가 더 가까우면 1위 (Review Focus 4)
  - `directionsUrl({n:"쌈지길(지하1층)",lat:37.5742,lng:126.9848})` === `"https://map.kakao.com/link/to/" + encodeURIComponent("쌈지길(지하1층)") + ",37.5742,126.9848"`
- [ ] **Step 2: 실패 확인** — `node --test tests/` → FAIL
- [ ] **Step 3: 구현**
- [ ] **Step 4: 통과 확인** — `node --test tests/ && TZ=America/New_York node --test tests/` → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(site): core geo/time logic"`

---

### Task 5: 프런트 UI

**Files:**
- Create: `site/index.html`, `site/js/app.js`, `site/css/style.css`, `site/js/config.js` (`export const KAKAO_JS_KEY = "..."` — keys.env 값으로 생성)

**Interfaces:**
- Consumes: Task 4 전부, Task 3 데이터 계약.

**화면 (모바일 우선, 세로):**
```
┌───────────────────────────┐
│ 지도 (화면 높이 45%)        │  내 위치 점 + 핀(열림 초록/닫힘 회색/확인필요 주황)
│                 [⌖ 내 위치] │
├───────────────────────────┤
│ 가까운 화장실 · 기준: 내 위치 │
│ OO공원 화장실   120m  [길찾기]│  상태 배지 · ♿ · 🍼 · 🔔 아이콘
│ 열림 · 공중화장실             │
│ ...  (상위 30개)            │
├───────────────────────────┤
│ 출처 표기 (작게)             │
└───────────────────────────┘
```

- [ ] **Step 1: 구현**
  - Kakao SDK는 `//dapi.kakao.com/v2/maps/sdk.js?appkey=…&autoload=false` 동적 로드 후 `kakao.maps.load`.
  - 시작: `navigator.geolocation.getCurrentPosition`(timeout 8초). 실패·거부 → 서울시청 + 상단 안내 "위치 권한이 없어 지도 중심 기준으로 보여드려요".
  - 기준점(내 위치 또는 지도 중심)의 `cellsAround` 타일을 fetch(404는 빈 배열, 메모리 캐시) → `nearest(…, 30)` → 목록·핀 갱신. 지도 `idle` 이벤트에서 위치 권한 없으면 중심 기준으로 재계산, 있으면 화면 내 핀만 추가 로드.
  - 목록 항목 탭 → 지도 이동 + 정보 표시. [길찾기]는 `<a target="_blank">`.
  - `closed` 항목은 흐리게. 상태 문구: 열림 / 닫힘 / 시간 확인 필요.
  - 하단 출처: meta.json `baseDate` 사용.
- [ ] **Step 2: 로컬 실행 확인** — `cd site && python3 -m http.server 8000`; `curl -s localhost:8000/ | grep -c kakao`, `curl -s localhost:8000/data/meta.json` 정상.
- [ ] **Step 3: 브라우저 스모크** — 스크래치 디렉토리에서 `npx -y playwright@1.48.2 install chromium` 후 스크립트로 `http://localhost:8000/` 접속, geolocation 권한 + 좌표(37.5742,126.9848) 주입, 목록 첫 항목이 존재하고 거리 오름차순인지, 콘솔 에러 없는지 확인, 모바일 뷰포트(390x844) 스크린샷 저장 → 사용자에게 경로 전달. 권한 거부 시나리오도 1회.
- [ ] **Step 4: Commit** — `git commit -m "feat(site): map + nearest list UI"`

---

### Task 6: 배포 (사용자 승인 후)

**Files:**
- Create: `.github/workflows/pages.yml` (`site/`를 `actions/upload-pages-artifact` + `actions/deploy-pages`로 배포), `README.md`(목적, 데이터 갱신 방법 `python3 -m scripts.build`, 출처)

- [ ] **Step 1: 워크플로·README 작성 후 커밋**
- [ ] **Step 2: 비밀값 재검사** — Task 3 Step 7 명령 재실행, 결과 없음.
- [ ] **Step 3: 사용자 승인 요청** — 공개 저장소 `Y-JaeHyun/toilet-map` 생성·푸시·Pages 활성화. 승인 전 진행 금지.
- [ ] **Step 4: 승인 후** — `gh repo create Y-JaeHyun/toilet-map --public --source . --push`; Pages 소스를 GitHub Actions로 설정(`gh api -X POST repos/Y-JaeHyun/toilet-map/pages -f build_type=workflow`); 워크플로 성공 확인 후 `curl -sI https://y-jaehyun.github.io/toilet-map/` 200, `…/data/meta.json` 200.
