import type { CategoryCount, EventStatus, ResolutionStats } from "../../types";
import { STATUS_LABELS } from "../../types";

interface EfficiencyPanelProps {
  byStatus: CategoryCount[];
  resolution: ResolutionStats;
}

const STATUS_COLORS: Record<EventStatus, string> = {
  reported: "#ef4444",
  in_progress: "#f59e0b",
  resolved: "#10b981",
};

function statusColor(key: string): string {
  return STATUS_COLORS[key as EventStatus] ?? "#9ca3af";
}

function statusLabel(key: string): string {
  return STATUS_LABELS[key as EventStatus] ?? key;
}

/** null 顯示破折號。顯示「0 小時」會是明確的錯誤陳述。 */
function hours(value: number | null): string {
  return value === null ? "—" : `${value} 小時`;
}

function EfficiencyPanel({ byStatus, resolution }: EfficiencyPanelProps) {
  const total = byStatus.reduce((sum, item) => sum + item.count, 0);

  return (
    <section className="rounded-lg border bg-white p-4">
      <h2 className="mb-3 text-sm font-semibold text-gray-700">處理效率</h2>

      {total === 0 ? (
        <p className="py-6 text-center text-sm text-gray-400">此區間沒有資料</p>
      ) : (
        <>
          <div className="flex h-6 overflow-hidden rounded bg-gray-100">
            {byStatus.map((item) => (
              <div
                key={item.key}
                style={{
                  width: `${(item.count / Math.max(total, 1)) * 100}%`,
                  backgroundColor: statusColor(item.key),
                }}
                title={`${statusLabel(item.key)} ${item.count} 件（${item.percentage}%）`}
              />
            ))}
          </div>
          <div className="mt-2 flex flex-wrap gap-4">
            {byStatus.map((item) => (
              <span key={item.key} className="flex items-center gap-1.5 text-xs text-gray-600">
                <span
                  className="inline-block h-2.5 w-2.5 rounded-sm"
                  style={{ backgroundColor: statusColor(item.key) }}
                  aria-hidden="true"
                />
                {statusLabel(item.key)} {item.count}（{item.percentage}%）
              </span>
            ))}
          </div>
        </>
      )}

      <div className="mt-5 grid grid-cols-3 gap-3 border-t pt-4">
        {/* 中位數放在最顯眼的位置：少數「結案後又被編輯」的離群值會把平均拉爆 */}
        <div>
          <div className="text-xs text-gray-500">結案耗時中位數</div>
          <div className="mt-0.5 text-2xl font-bold tabular-nums text-gray-800">
            {hours(resolution.median_hours)}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500">平均</div>
          <div className="mt-0.5 text-lg tabular-nums text-gray-700">
            {hours(resolution.avg_hours)}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500">P90</div>
          <div className="mt-0.5 text-lg tabular-nums text-gray-700">
            {hours(resolution.p90_hours)}
          </div>
        </div>
      </div>

      <p className="mt-3 text-xs text-gray-500">
        樣本數 n = {resolution.resolved_count}
        {resolution.legacy_excluded_count > 0 && (
          <>
            ；另有 {resolution.legacy_excluded_count} 筆已結案事件無結案時戳，未納入計算
          </>
        )}
      </p>
      {/* 口徑說明由後端提供並原樣顯示，確保畫面與匯出的 CSV 講的是同一件事 */}
      <p className="mt-1 text-xs leading-relaxed text-gray-400">
        {resolution.method_note}
      </p>
    </section>
  );
}

export default EfficiencyPanel;
