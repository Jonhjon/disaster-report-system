function ReportSummary({ result }: { result: Record<string, unknown> }) {
  const isNew = result.status === "created";
  const geocoded = result.geocoded_address
    ? String(result.geocoded_address)
    : null;
  const possibleDup = result.possible_duplicate_event_id
    ? String(result.possible_duplicate_event_id)
    : null;

  return (
    <div
      className={`mx-4 my-3 rounded-lg border-2 p-4 ${
        isNew
          ? "border-green-300 bg-green-50"
          : "border-blue-300 bg-blue-50"
      }`}
    >
      <div className="mb-2 flex items-center gap-2">
        <span className="text-lg">{isNew ? "✅" : "🔄"}</span>
        <span className="font-semibold">
          {isNew ? "通報成功 - 已建立新事件" : "通報成功 - 已合併至現有事件"}
        </span>
      </div>
      <p className="text-sm text-gray-700">{result.message as string}</p>
      {geocoded && (
        <p className="mt-2 text-xs text-gray-600">地點：{geocoded}</p>
      )}
      {possibleDup && (
        <p className="mt-1 text-xs text-amber-700">
          ⚠ 系統偵測到可能與另一筆通報重複
        </p>
      )}
    </div>
  );
}

export default ReportSummary;
