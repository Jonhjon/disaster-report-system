import { DISASTER_TYPE_LABELS, type TrendBucket } from "../../types";

// 按鈕上用短標籤；完整的「週（週一起算）」說明留給圖表標題
const BUCKET_BUTTON_LABELS: Record<TrendBucket, string> = {
  day: "日",
  week: "週",
  month: "月",
};

export interface StatFilterState {
  search: string;
  disaster_type: string;
  severity_min: string;
  status: string;
  date_from: string;
  date_to: string;
  bucket: TrendBucket;
}

interface StatFiltersProps {
  filters: StatFilterState;
  onChange: (filters: StatFilterState) => void;
}

function StatFilters({ filters, onChange }: StatFiltersProps) {
  const update = <K extends keyof StatFilterState>(
    key: K,
    value: StatFilterState[K]
  ) => {
    onChange({ ...filters, [key]: value });
  };

  return (
    <div className="mb-4 space-y-3 rounded-lg border bg-white p-4">
      <input
        type="text"
        aria-label="搜尋災情"
        placeholder="搜尋災情（標題、描述、地點）..."
        className="w-full rounded-lg border px-3 py-2 text-sm focus:border-red-500 focus:outline-none"
        value={filters.search}
        onChange={(e) => update("search", e.target.value)}
      />

      <div className="flex flex-wrap items-center gap-3">
        <select
          aria-label="災害類型"
          className="rounded border px-2 py-1 text-sm"
          value={filters.disaster_type}
          onChange={(e) => update("disaster_type", e.target.value)}
        >
          <option value="">全部種類</option>
          {Object.entries(DISASTER_TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>

        <select
          aria-label="事件狀態"
          className="rounded border px-2 py-1 text-sm"
          value={filters.status}
          onChange={(e) => update("status", e.target.value)}
        >
          <option value="">全部狀態</option>
          <option value="reported">通報中</option>
          <option value="in_progress">處理中</option>
          <option value="resolved">已結案</option>
        </select>

        <select
          aria-label="最低嚴重程度"
          className="rounded border px-2 py-1 text-sm"
          value={filters.severity_min}
          onChange={(e) => update("severity_min", e.target.value)}
        >
          <option value="">最低嚴重程度</option>
          {[1, 2, 3, 4, 5].map((v) => (
            <option key={v} value={v}>
              {v} 以上
            </option>
          ))}
        </select>

        <label className="flex items-center gap-1.5 text-sm text-gray-600">
          起
          <input
            type="date"
            aria-label="開始日期"
            className="rounded border px-2 py-1 text-sm"
            value={filters.date_from}
            onChange={(e) => update("date_from", e.target.value)}
          />
        </label>
        <label className="flex items-center gap-1.5 text-sm text-gray-600">
          迄
          <input
            type="date"
            aria-label="結束日期"
            className="rounded border px-2 py-1 text-sm"
            value={filters.date_to}
            onChange={(e) => update("date_to", e.target.value)}
          />
        </label>

        <fieldset
          className="flex items-center gap-1.5 text-sm text-gray-600"
          aria-label="趨勢分桶"
        >
          <legend className="sr-only">趨勢分桶</legend>
          <span aria-hidden="true">趨勢分桶</span>
          <div className="flex overflow-hidden rounded border">
            {(Object.keys(BUCKET_BUTTON_LABELS) as TrendBucket[]).map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={filters.bucket === value}
                onClick={() => update("bucket", value)}
                className={`px-3 py-1 text-sm ${
                  filters.bucket === value
                    ? "bg-blue-600 text-white"
                    : "bg-white text-gray-700 hover:bg-gray-100"
                }`}
              >
                {BUCKET_BUTTON_LABELS[value]}
              </button>
            ))}
          </div>
        </fieldset>
      </div>
    </div>
  );
}

export default StatFilters;
