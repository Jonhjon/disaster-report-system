export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// UTC ISO 字串 → <input type="datetime-local"> 需要的本地時區值（YYYY-MM-DDTHH:mm，去秒）
export function toDatetimeLocal(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// datetime-local 的本地時間值 → UTC ISO 字串
export function fromDatetimeLocal(local: string): string {
  return new Date(local).toISOString();
}

const REPORT_TIMEZONE_OFFSET = "+08:00";

function nextCalendarDate(value: string): string {
  const date = new Date(`${value}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + 1);
  return date.toISOString().slice(0, 10);
}

// 報表固定使用 Asia/Taipei；不可依賴管理員電腦的瀏覽器時區。
export function dateInputToIsoStart(value: string): string {
  return new Date(`${value}T00:00:00.000${REPORT_TIMEZONE_OFFSET}`).toISOString();
}

// 結束值是隔日台北午夜，後端以 `< date_to` 套用半開區間。
export function dateInputToIsoEnd(value: string): string {
  return new Date(
    `${nextCalendarDate(value)}T00:00:00.000${REPORT_TIMEZONE_OFFSET}`
  ).toISOString();
}

export function dateInTimeZone(
  value: Date | string,
  timeZone = "Asia/Taipei"
): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
}
