// Pure logic shared by the UI: no DOM, no Kakao SDK.
export const CELL = 0.05;

export function cellOf(lat, lng) {
  return [Math.floor(lng / CELL), Math.floor(lat / CELL)];
}

export function cellsAround(lat, lng) {
  const [cx, cy] = cellOf(lat, lng);
  const out = [];
  for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) out.push(`${cx + dx}_${cy + dy}`);
  return out;
}

const R_EARTH = 6371008.8;
const rad = (d) => (d * Math.PI) / 180;

export function distanceM(lat1, lng1, lat2, lng2) {
  const a = Math.sin(rad(lat2 - lat1) / 2) ** 2 +
    Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lng2 - lng1) / 2) ** 2;
  return 2 * R_EARTH * Math.asin(Math.sqrt(a));
}

const fmt = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", hourCycle: "h23", weekday: "short",
});
const DOW = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };

export function seoulNow(date) {
  const p = Object.fromEntries(fmt.formatToParts(date).map((x) => [x.type, x.value]));
  return { ymd: `${p.year}-${p.month}-${p.day}`, dow: DOW[p.weekday], min: Number(p.hour) * 60 + Number(p.minute) };
}

const toMin = (hhmm) => {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
};

export function openStatus(h, now, holidays) {
  if (!h || h.t === "unknown") return "unknown";
  if (h.t === "always") return "open";
  if (h.weekdayOnly) {
    const year = Number(now.ymd.slice(0, 4));
    const known = holidays && holidays.years && holidays.years.includes(year);
    if (!known || now.dow === 0 || now.dow === 6 || holidays.dates.includes(now.ymd)) return "unknown";
  }
  const o = toMin(h.open), c = toMin(h.close), t = now.min;
  const open = o < c ? t >= o && t < c : t >= o || t < c; // o > c: past midnight
  return open ? "open" : "closed";
}

export function nearest(records, lat, lng, n) {
  return records
    .map((rec) => ({ rec, d: distanceM(lat, lng, rec.lat, rec.lng) }))
    .sort((a, b) => a.d - b.d)
    .slice(0, n);
}

export function directionsUrl(rec) {
  return `https://map.kakao.com/link/to/${encodeURIComponent(rec.n)},${rec.lat},${rec.lng}`;
}
