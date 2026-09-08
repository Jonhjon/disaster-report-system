import { useCallback, useEffect, useMemo, useState } from "react";
import { Download, FileSpreadsheet } from "lucide-react";
import CategoryBars from "../components/statistics/CategoryBars";
import CrossTabTable from "../components/statistics/CrossTabTable";
import EfficiencyPanel from "../components/statistics/EfficiencyPanel";
import StatFilters, {
  type StatFilterState,
} from "../components/statistics/StatFilters";
import SummaryCards from "../components/statistics/SummaryCards";
import TrendLineChart from "../components/statistics/TrendLineChart";
import { downloadEventsCsv, getEventStatistics } from "../services/api";
import {
  DISASTER_TYPE_COLORS,
  DISASTER_TYPE_LABELS,
  SEVERITY_LABELS,
  STATUS_LABELS,
  TREND_BUCKET_LABELS,
  type DisasterType,
  type EventStatistics,
  type EventStatus,
  type StatisticsQuery,
} from "../types";
import {
  dateInTimeZone,
  dateInputToIsoEnd,
  dateInputToIsoStart,
} from "../utils/format";
import { buildSummaryCsv, downloadCsv, withBom } from "../utils/statsCsv";
import { createStatisticsRequestCoordinator } from "../utils/statisticsRequest";

const SEVERITY_COLORS: Record<number, string> = {
  1: "#fde68a",
  2: "#fcd34d",
  3: "#fb923c",
  4: "#ef4444",
  5: "#991b1b",
};

const INITIAL_FILTERS: StatFilterState = {
  search: "",
  disaster_type: "",
  severity_min: "",
  status: "",
  date_from: "",
  date_to: "",
  bucket: "day",
};

/** 把畫面上的篩選轉成 API 參數。日期需轉成當地整日邊界，否則會漏掉結束當天。 */
function toQueryParams(filters: StatFilterState) {
  return {
    search: filters.search || undefined,
    disaster_type: filters.disaster_type || undefined,
    severity_min: filters.severity_min ? Number(filters.severity_min) : undefined,
    status: filters.status || undefined,
    date_from: filters.date_from ? dateInputToIsoStart(filters.date_from) : undefined,
    date_to: filters.date_to ? dateInputToIsoEnd(filters.date_to) : undefined,
  };
}

/** 給匯出 CSV 用的人類可讀篩選描述。 */
function describeFilters(filters: StatFilterState): string {
  const parts: string[] = [];
  if (filters.search) parts.push(`關鍵字=${filters.search}`);
  if (filters.disaster_type) {
    parts.push(
      `災害類型=${DISASTER_TYPE_LABELS[filters.disaster_type as DisasterType] ?? filters.disaster_type}`
    );
  }
  if (filters.status) {
    parts.push(`狀態=${STATUS_LABELS[filters.status as EventStatus] ?? filters.status}`);
  }
  if (filters.severity_min) parts.push(`嚴重度≥${filters.severity_min}`);
  if (filters.date_from || filters.date_to) {
    parts.push(`期間=${filters.date_from || "不限"} ~ ${filters.date_to || "不限"}`);
  }
  return parts.length > 0 ? parts.join("；") : "無（全部事件）";
}

function StatisticsPage() {
  const [stats, setStats] = useState<EventStatistics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [filters, setFilters] = useState<StatFilterState>(INITIAL_FILTERS);

  const requestCoordinator = useMemo(
    () =>
      createStatisticsRequestCoordinator<StatisticsQuery, EventStatistics>({
        debounceMs: 300,
        request: getEventStatistics,
        onLoading: setLoading,
        onSuccess: (data) => {
          setError(null);
          setStats(data);
        },
        onError: (requestError) => {
          setStats(null);
          setError(
            requestError instanceof Error
              ? requestError.message
              : "載入統計資料時發生未知錯誤"
          );
        },
      }),
    []
  );

  const loadStats = useCallback((immediate = false) => {
    setError(null);
    requestCoordinator.schedule(
      {
        ...toQueryParams(filters),
        bucket: filters.bucket,
      },
      { immediate }
    );
  }, [filters, requestCoordinator]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(
    () => () => {
      requestCoordinator.dispose();
    },
    [requestCoordinator]
  );

  const handleExportSummary = () => {
    if (!stats) return;
    setExportError(null);
    try {
      const csv = buildSummaryCsv(stats, {
        filterDescription: describeFilters(filters),
        generatedAtLabel: `${new Intl.DateTimeFormat("zh-TW", {
          timeZone: stats.timezone,
          dateStyle: "short",
          timeStyle: "medium",
        }).format(new Date(stats.generated_at))}（${stats.timezone}）`,
      });
      const stamp = dateInTimeZone(new Date(), stats.timezone);
      downloadCsv(`災情統計摘要_${stamp}.csv`, withBom(csv));
    } catch (e: unknown) {
      setExportError(e instanceof Error ? e.message : "匯出摘要時發生未知錯誤");
    }
  };

  const handleExportDetail = async () => {
    setExporting(true);
    setExportError(null);
    try {
      const { blob, filename, truncated } = await downloadEventsCsv(
        toQueryParams(filters)
      );
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);

      if (truncated) {
        setExportError(
          "匯出筆數已達單次上限，CSV 內容並非完整資料。請縮小篩選範圍後重新匯出。"
        );
      }
    } catch (e: unknown) {
      setExportError(e instanceof Error ? e.message : "匯出明細時發生未知錯誤");
    } finally {
      setExporting(false);
    }
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold">統計分析</h1>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleExportSummary}
            disabled={!stats || loading}
            className="flex items-center gap-1.5 rounded-lg border bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <FileSpreadsheet size={16} aria-hidden="true" />
            匯出統計摘要
          </button>
          <button
            type="button"
            onClick={handleExportDetail}
            disabled={exporting || loading}
            className="flex items-center gap-1.5 rounded-lg border bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download size={16} aria-hidden="true" />
            {exporting ? "匯出中..." : "匯出事件明細"}
          </button>
        </div>
      </div>

      <StatFilters filters={filters} onChange={setFilters} />

      {error && (
        <div className="mb-4 flex items-center justify-between rounded border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
          <span>無法載入統計資料：{error}</span>
          <button
            type="button"
            onClick={() => loadStats(true)}
            className="ml-4 rounded border border-red-400 bg-white px-3 py-1 text-red-700 hover:bg-red-100"
          >
            重試
          </button>
        </div>
      )}

      {exportError && (
        <div className="mb-4 rounded border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {exportError}
        </div>
      )}

      {loading ? (
        <div className="py-12 text-center text-gray-400">載入中...</div>
      ) : stats ? (
        <div className="space-y-4">
          <SummaryCards summary={stats.summary} />

          <div className="grid gap-4 lg:grid-cols-2">
            <CategoryBars
              title="依災害類型"
              items={stats.by_disaster_type}
              labelFor={(key) => DISASTER_TYPE_LABELS[key as DisasterType] ?? key}
              colorFor={(key) => DISASTER_TYPE_COLORS[key as DisasterType] ?? "#95a5a6"}
            />
            <CategoryBars
              title="依嚴重度"
              items={stats.by_severity}
              labelFor={(key) => `${key} ${SEVERITY_LABELS[Number(key)] ?? ""}`.trim()}
              colorFor={(key) => SEVERITY_COLORS[Number(key)] ?? "#95a5a6"}
            />
          </div>

          <TrendLineChart points={stats.trend} bucket={filters.bucket} />

          <div className="grid gap-4 lg:grid-cols-2">
            <CrossTabTable cells={stats.cross_tab} />
            <EfficiencyPanel
              byStatus={stats.by_status}
              resolution={stats.resolution}
            />
          </div>

          <p className="text-xs text-gray-400">
            統計依事件發生時間（{stats.time_field}）計算，時區 {stats.timezone}，
            趨勢以{TREND_BUCKET_LABELS[filters.bucket]}分桶。
            各分類佔比四捨五入至小數一位，加總未必剛好 100%。
          </p>
        </div>
      ) : null}
    </div>
  );
}

export default StatisticsPage;
