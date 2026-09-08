import type { CrossTabCell, DisasterType } from "../../types";
import { DISASTER_TYPE_LABELS, SEVERITY_LABELS } from "../../types";
import { pivotCrossTab } from "../../utils/statsChart";

interface CrossTabTableProps {
  cells: CrossTabCell[];
}

const SEVERITIES = [1, 2, 3, 4, 5];

function CrossTabTable({ cells }: CrossTabTableProps) {
  // 以既定清單為主軸，再把後端回傳但不在清單內的類型接在後面，避免資料被吃掉
  const knownTypes = Object.keys(DISASTER_TYPE_LABELS);
  const extraTypes = [...new Set(cells.map((c) => c.disaster_type))].filter(
    (t) => !knownTypes.includes(t)
  );
  const types = [...knownTypes, ...extraTypes];

  const { matrix, rowTotals, colTotals, grandTotal, max } = pivotCrossTab(
    cells,
    types,
    SEVERITIES
  );

  // 只顯示有資料的列，否則 9 種類型會有一大半是空的
  const visibleRows = types
    .map((type, i) => ({ type, index: i }))
    .filter(({ index }) => rowTotals[index] > 0);

  return (
    <section className="rounded-lg border bg-white p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold text-gray-700">
          交叉統計（災害類型 × 嚴重度）
        </h2>
        <span className="text-xs text-gray-400">共 {grandTotal} 件</span>
      </div>

      {visibleRows.length === 0 ? (
        <p className="py-6 text-center text-sm text-gray-400">此區間沒有資料</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
              <tr>
                <th scope="col" className="px-3 py-2">災害類型</th>
                {SEVERITIES.map((sev) => (
                  <th scope="col" key={sev} className="px-3 py-2 text-right">
                    {sev} {SEVERITY_LABELS[sev] ?? String(sev)}
                  </th>
                ))}
                <th scope="col" className="px-3 py-2 text-right">小計</th>
              </tr>
            </thead>
            <tbody>
              {visibleRows.map(({ type, index }) => (
                <tr key={type} className="border-b last:border-0">
                  <th scope="row" className="px-3 py-2 text-left font-normal text-gray-700">
                    {DISASTER_TYPE_LABELS[type as DisasterType] ?? type}
                  </th>
                  {SEVERITIES.map((sev, col) => {
                    const value = matrix[index][col];
                    return (
                      <td
                        key={sev}
                        className="px-3 py-2 text-right tabular-nums"
                        // 熱度底色：分母用 Math.max(max, 1) 護欄，全 0 時不會變 NaN
                        style={{
                          backgroundColor:
                            value > 0
                              ? `rgba(220, 38, 38, ${
                                  0.08 + (value / Math.max(max, 1)) * 0.35
                                })`
                              : undefined,
                        }}
                      >
                        {value === 0 ? (
                          <span className="text-gray-300">0</span>
                        ) : (
                          value
                        )}
                      </td>
                    );
                  })}
                  <td className="px-3 py-2 text-right font-semibold tabular-nums">
                    {rowTotals[index]}
                  </td>
                </tr>
              ))}
              <tr className="bg-gray-50 font-semibold">
                <th scope="row" className="px-3 py-2 text-left">小計</th>
                {colTotals.map((total, i) => (
                  <td key={SEVERITIES[i]} className="px-3 py-2 text-right tabular-nums">
                    {total}
                  </td>
                ))}
                <td className="px-3 py-2 text-right tabular-nums">{grandTotal}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default CrossTabTable;
