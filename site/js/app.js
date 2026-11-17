import { KAKAO_JS_KEY } from "./config.js";
import { cellsAround, nearest, openStatus, seoulNow, directionsUrl } from "./core.js";

const CITY_HALL = { lat: 37.5663, lng: 126.9779 };
const LIST_N = 30;
const PIN_N = 60;
const STATUS_TEXT = { open: "열림", closed: "닫힘", unknown: "시간 확인 필요" };

const $ = (id) => document.getElementById(id);
const tiles = new Map(); // "cx_cy" -> Promise<record[]>
let holidays = { years: [], dates: [] };
let map, me = null, meDot = null, pins = [], info = null;

function loadSdk() {
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${KAKAO_JS_KEY}&autoload=false`;
    s.onload = () => window.kakao.maps.load(resolve);
    s.onerror = () => reject(new Error("지도를 불러오지 못했어요."));
    document.head.appendChild(s);
  });
}

async function getJson(url, fallback) {
  try {
    const r = await fetch(url);
    return r.ok ? await r.json() : fallback;
  } catch {
    return fallback;
  }
}

function tile(key) {
  if (!tiles.has(key)) tiles.set(key, getJson(`data/tiles/${key}.json`, []));
  return tiles.get(key);
}

async function recordsAround(lat, lng) {
  const parts = await Promise.all(cellsAround(lat, lng).map(tile));
  return parts.flat();
}

function notice(text) {
  const el = $("notice");
  el.textContent = text || "";
  el.hidden = !text;
}

function fmtDist(d) {
  return d < 1000 ? `${Math.round(d / 10) * 10}m` : `${(d / 1000).toFixed(1)}km`;
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

function pinNode(status) {
  const colors = { open: "#15803d", closed: "#9ca3af", unknown: "#c2410c" };
  const d = el("div");
  d.style.cssText = `width:14px;height:14px;border-radius:50%;border:2px solid #fff;` +
    `box-shadow:0 0 2px rgba(0,0,0,.6);background:${colors[status]}`;
  return d;
}

function showInfo(rec, status) {
  if (info) info.setMap(null);
  const box = el("div", "iw");
  box.appendChild(el("strong", null, rec.n));
  box.appendChild(el("div", null, `${STATUS_TEXT[status]} · ${rec.k}`));
  box.appendChild(el("div", null, rec.a));
  const k = window.kakao.maps;
  info = new k.InfoWindow({ position: new k.LatLng(rec.lat, rec.lng), content: box, removable: true });
  info.open(map);
}

function drawPins(items, now) {
  pins.forEach((p) => p.setMap(null));
  const k = window.kakao.maps;
  pins = items.map(({ rec }) => {
    const status = openStatus(rec.h, now, holidays);
    const node = pinNode(status);
    node.addEventListener("click", () => showInfo(rec, status));
    return new k.CustomOverlay({ position: new k.LatLng(rec.lat, rec.lng), content: node, yAnchor: 0.5, map });
  });
}

function renderList(items, now, basisText) {
  $("basis").textContent = basisText;
  const list = $("list");
  list.replaceChildren();
  if (!items.length) {
    list.appendChild(el("li", "empty", "이 주변엔 등록된 화장실이 없어요. 지도를 옮겨 보세요."));
    return;
  }
  for (const { rec, d } of items) {
    const status = openStatus(rec.h, now, holidays);
    const li = el("li", `item ${status}`);
    li.appendChild(el("div", "name", rec.n));
    li.appendChild(el("div", "dist", fmtDist(d)));
    const meta = el("div", "meta");
    meta.appendChild(el("span", `badge ${status}`, STATUS_TEXT[status]));
    meta.appendChild(el("span", null, rec.k));
    if (rec.dis) meta.appendChild(el("span", null, "♿ 장애인용"));
    if (rec.dia) meta.appendChild(el("span", null, "🍼 기저귀"));
    if (rec.bell) meta.appendChild(el("span", null, "🔔 비상벨"));
    li.appendChild(meta);
    const go = el("a", "go", "길찾기");
    go.href = directionsUrl(rec);
    go.target = "_blank";
    go.rel = "noopener";
    go.addEventListener("click", (e) => e.stopPropagation());
    li.appendChild(go);
    li.addEventListener("click", () => {
      map.panTo(new window.kakao.maps.LatLng(rec.lat, rec.lng));
      showInfo(rec, status);
    });
    list.appendChild(li);
  }
}

async function refresh() {
  const now = seoulNow(new Date());
  const c = map.getCenter();
  const center = { lat: c.getLat(), lng: c.getLng() };
  const origin = me || center;
  const [listRecs, pinRecs] = await Promise.all([
    recordsAround(origin.lat, origin.lng),
    recordsAround(center.lat, center.lng),
  ]);
  renderList(nearest(listRecs, origin.lat, origin.lng, LIST_N), now,
    me ? "내 위치에서 가까운 순" : "지도 중심에서 가까운 순");
  drawPins(nearest(pinRecs, center.lat, center.lng, PIN_N), now);
}

function setMe(pos) {
  const k = window.kakao.maps;
  me = { lat: pos.coords.latitude, lng: pos.coords.longitude };
  const ll = new k.LatLng(me.lat, me.lng);
  if (!meDot) {
    const node = el("div");
    node.style.cssText = "width:16px;height:16px;border-radius:50%;background:#2563eb;" +
      "border:3px solid #fff;box-shadow:0 0 0 6px rgba(37,99,235,.25)";
    meDot = new k.CustomOverlay({ position: ll, content: node, yAnchor: 0.5, zIndex: 3, map });
  } else {
    meDot.setPosition(ll);
  }
  map.setCenter(ll);
  notice("");
}

function locate() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      notice("이 브라우저는 위치 기능을 지원하지 않아요. 지도를 옮겨 찾아 주세요.");
      return resolve(false);
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => { setMe(pos); resolve(true); },
      () => {
        notice("위치 권한이 없어 지도 중심 기준으로 보여 드려요. 지도를 옮겨 찾아 주세요.");
        resolve(false);
      },
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 },
    );
  });
}

async function main() {
  const metaP = getJson("data/meta.json", null);
  const holP = getJson("data/holidays.json", holidays);
  try {
    await loadSdk();
  } catch (e) {
    $("basis").textContent = e.message;
    return;
  }
  const k = window.kakao.maps;
  map = new k.Map($("map"), { center: new k.LatLng(CITY_HALL.lat, CITY_HALL.lng), level: 4 });
  holidays = await holP;
  const meta = await metaP;
  if (meta && meta.baseDate) {
    $("credit").textContent = `행정안전부 공중화장실정보 (데이터 기준일 ${meta.baseDate}) · 좌표: 국토교통부 브이월드`;
  }
  await locate();
  await refresh();
  k.event.addListener(map, "idle", refresh);
  $("locate").addEventListener("click", async () => {
    if (await locate()) refresh();
  });
}

main();
