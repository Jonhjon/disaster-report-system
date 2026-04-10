import { DISASTER_TYPE_LABELS } from "../../types";

interface EventFiltersProps {
  filters: {
    search: string;
    disaster_type: string;
    severity_min: string;
    severity_max: string;
    status: string;
    sort_by: string;
    sort_order: string;
  };
  onChange: (filters: EventFiltersProps["filters"]) => void;
}

function EventFilters({ filters, onChange }: EventFiltersProps) {
  const update = (key: string, value: string) => {
    onChange({ ...filters, [key]: value });
  };

  return (
    <div className="mb-4 space-y-3 rounded-lg border bg-white p-4">
      {/* Search */}
      <div>
        <input
          type="text"
          placeholder="搜尋災情（標題、描述、地點）..."
          className="w-full rounded-lg border px-3 py-2 text-sm focus:border-red-500 focus:outline-none"
          value={filters.search}
          onChange={(e) => update("search", e.target.value)}
        />
      </div>

      {/* Filter row */}
      <div className="flex flex-wrap gap-3">
        <select
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

        <select
          className="rounded border px-2 py-1 text-sm"
          value={`${filters.sort_by}-${filters.sort_order}`}
          onChange={(e) => {
            const [sortBy, sortOrder] = e.target.value.split("-");
            onChange({ ...filters, sort_by: sortBy, sort_order: sortOrder });
          }}
        >
          <option value="occurred_at-desc">時間（新→舊）</option>
          <option value="occurred_at-asc">時間（舊→新）</option>
          <option value="severity-desc">嚴重程度（高→低）</option>
          <option value="severity-asc">嚴重程度（低→高）</option>
          <option value="report_count-desc">通報數（多→少）</option>
        </select>
      </div>
    </div>
  );
}

export default EventFilters;
