# 가까운 화장실 (toilet-map)

급할 때 **내 위치에서 가장 가까운, 지금 쓸 수 있는 화장실**을 찾아 주는 모바일 웹입니다. 서울·경기 공중화장실(공중/개방/간이/이동)을 다룹니다.

- 서비스: https://y-jaehyun.github.io/toilet-map/
- 서버 없음: 데이터는 빌드 시 정적 JSON(`site/data/`)으로 생성해 GitHub Pages로 배포
- 배포: `site/`를 `gh-pages` 브랜치로 올림 → `git subtree push --prefix site origin gh-pages`

## 데이터

- 원천: 행정안전부 공중화장실정보 (localdata, 이용허락범위 제한 없음)
- 좌표: 원천 데이터에 2025-02부터 위경도가 빠져 있어, 주소를 국토교통부 브이월드 지오코더로 변환합니다.
  결과는 `data/geocode-cache.json`에 캐시되어 재실행 시 새 주소만 조회합니다. 변환 실패 목록은 `data/geocode-failed.csv`.
- 개방시간: 자유 텍스트를 `always / range / unknown`으로 정규화. 판단 불가하면 "시간 확인 필요"로 표시합니다.
- 공휴일: `site/data/holidays.json` (매년 갱신 필요 — 없는 연도는 평일 전용 화장실을 "시간 확인 필요"로 표시)

## 데이터 갱신

```bash
# ~/.config/toilet-map/keys.env 에 VWORLD_KEY=... (저장소에 커밋 금지)
set -a; . ~/.config/toilet-map/keys.env; set +a
python3 -m scripts.build          # 다운로드 → 필터 → 지오코딩 → site/data 생성
```

## 개발

```bash
python3 -m pytest -q
node --test tests/*.test.mjs
cd site && python3 -m http.server 8000   # 카카오 앱에 http://localhost:8000 등록 필요
```

`site/js/config.js`의 카카오 JavaScript 키는 브라우저 노출용이며 등록된 도메인에서만 동작합니다.
