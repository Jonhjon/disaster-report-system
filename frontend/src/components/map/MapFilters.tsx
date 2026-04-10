import { DISASTER_TYPE_LABELS } from "../../types";
import type { DisasterType } from "../../types";

interface MapFiltersProps {
  filters: {
    disaster_type?: DisasterType;
    severity_min?: number;
    status: string;
  };
  onChange: (filters: MapFiltersProps["filters"]) => void;
}

function MapFilters({ filters, onChange }: MapFiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 border-b bg-white p-3">
      <label className="flex items-center gap-1 text-sm">
        <span className="text-gray-600">災情種類：</span>
        <select
          className="rounded border px-2 py-1 text-sm"
          value={filters.disaster_type || ""}
          onChange={(e) =>
            onChange({
              ...filters,
              disaster_type: (e.target.value as DisasterType) || undefined,
            })
          }
        >
          <option value="">全部</option>
          {Object.entries(DISASTER_TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-1 text-sm">
        <span className="text-gray-600">最低嚴重程度：</span>
        <select
          className="rounded border px-2 py-1 text-sm"
          value={filters.severity_min || ""}
          onChange={(e) =>
            onChange({
              ...filters,
              severity_min: e.target.value ? Number(e.target.value) : undefined,
            })
          }
        >
          <option value="">不限</option>
          {[1, 2, 3, 4, 5].map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-1 text-sm">
        <span className="text-gray-600">狀態：</span>
        <select
          className="rounded border px-2 py-1 text-sm"
          value={filters.status}
          onChange={(e) => onChange({ ...filters, status: e.target.value })}
        >
          <option value="">全部</option>
          <option value="reported">通報中</option>
          <option value="in_progress">處理中</option>
          <option value="resolved">已結案</option>
        </select>
      </label>
    </div>
  );
}

export default MapFilters;
