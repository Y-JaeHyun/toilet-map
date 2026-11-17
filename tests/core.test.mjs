import { test } from "node:test";
import assert from "node:assert/strict";
import { cellOf, cellsAround, distanceM, seoulNow, openStatus, nearest, directionsUrl } from "../site/js/core.js";

const H = { years: [2026, 2027], dates: ["2026-11-19"] };
const R = (open, close, weekdayOnly = false) => ({ t: "range", open, close, weekdayOnly });

test("cellOf matches python", () => {
  assert.deepEqual(cellOf(37.5663, 126.9779), [2539, 751]);
});

test("cellsAround is 3x3 including center", () => {
  const c = cellsAround(37.5663, 126.9779);
  assert.equal(c.length, 9);
  assert.ok(c.includes("2539_751"));
  assert.ok(c.includes("2538_750") && c.includes("2540_752"));
});

test("distanceM", () => {
  const d = distanceM(37.5663, 126.9779, 37.5665, 126.9780);
  assert.ok(d > 23 && d < 25, String(d));
});

test("overnight range open at 3am, closed at noon", () => {
  assert.equal(openStatus(R("22:00", "06:00"), { ymd: "2026-11-18", dow: 3, min: 180 }, H), "open");
  assert.equal(openStatus(R("22:00", "06:00"), { ymd: "2026-11-18", dow: 3, min: 720 }, H), "closed");
});

test("plain range and 24:00 close", () => {
  assert.equal(openStatus(R("09:00", "18:00"), { ymd: "2026-11-18", dow: 3, min: 600 }, H), "open");
  assert.equal(openStatus(R("09:00", "18:00"), { ymd: "2026-11-18", dow: 3, min: 1080 }, H), "closed");
  assert.equal(openStatus(R("05:00", "24:00"), { ymd: "2026-11-18", dow: 3, min: 1439 }, H), "open");
  assert.equal(openStatus(R("05:00", "24:00"), { ymd: "2026-11-18", dow: 3, min: 200 }, H), "closed");
});

test("weekdayOnly: weekend, holiday, unknown year -> unknown", () => {
  const w = R("09:00", "18:00", true);
  assert.equal(openStatus(w, { ymd: "2026-11-18", dow: 3, min: 600 }, H), "open");
  assert.equal(openStatus(w, { ymd: "2026-11-21", dow: 6, min: 600 }, H), "unknown");
  assert.equal(openStatus(w, { ymd: "2026-11-19", dow: 4, min: 600 }, H), "unknown");
  assert.equal(openStatus(w, { ymd: "2028-03-08", dow: 3, min: 600 }, H), "unknown");
});

test("always / unknown", () => {
  assert.equal(openStatus({ t: "always" }, { ymd: "2026-11-18", dow: 3, min: 0 }, H), "open");
  assert.equal(openStatus({ t: "unknown" }, { ymd: "2026-11-18", dow: 3, min: 0 }, H), "unknown");
});

test("seoulNow ignores device timezone", () => {
  assert.deepEqual(seoulNow(new Date("2026-11-17T20:00:00Z")), { ymd: "2026-11-18", dow: 3, min: 300 });
  assert.deepEqual(seoulNow(new Date("2026-11-17T15:00:00Z")), { ymd: "2026-11-18", dow: 3, min: 0 });
});

test("nearest picks closer record across cell boundary", () => {
  const recs = [
    { id: "far", lat: 37.5600, lng: 126.9750 },
    { id: "near", lat: 37.5501, lng: 126.9750 },
  ];
  const r = nearest(recs, 37.5499, 126.9750, 1);
  assert.equal(r.length, 1);
  assert.equal(r[0].rec.id, "near");
  assert.ok(r[0].d < 30);
});

test("directionsUrl", () => {
  assert.equal(directionsUrl({ n: "쌈지길(지하1층)", lat: 37.5742, lng: 126.9848 }),
    "https://map.kakao.com/link/to/" + encodeURIComponent("쌈지길(지하1층)") + ",37.5742,126.9848");
});
