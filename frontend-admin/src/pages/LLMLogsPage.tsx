import { useEffect, useState } from "react";
import { getLLMLogs } from "../services/api";

interface LLMLog {
  id: string;
  timestamp: string;
  model: string;
  latency_ms: number;
  token_usage: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  };
  status: string;
  prompt: string;
  output: string;
}

function LLMLogsPage() {
  const [logs, setLogs] = useState<LLMLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    getLLMLogs()
      .then((data) => setLogs(data as unknown as LLMLog[]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="py-12 text-center text-gray-400">載入中...</div>;
  }

  return (
    <div>
      <h1 className="mb-4 text-xl font-bold">LLM 呼叫日誌</h1>
      <div className="overflow-hidden rounded-lg border bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
            <tr>
              <th className="px-4 py-3">時間</th>
              <th className="px-4 py-3">模型</th>
              <th className="px-4 py-3">延遲</th>
              <th className="px-4 py-3">輸入 tokens</th>
              <th className="px-4 py-3">輸出 tokens</th>
              <th className="px-4 py-3">狀態</th>
              <th className="px-4 py-3">詳情</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <>
                <tr key={log.id} className="border-b hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-600">
                    {new Date(log.timestamp).toLocaleString("zh-TW")}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">{log.model}</td>
                  <td className="px-4 py-3">{log.latency_ms} ms</td>
                  <td className="px-4 py-3">{log.token_usage.input_tokens}</td>
                  <td className="px-4 py-3">{log.token_usage.output_tokens}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-1 text-xs ${
                        log.status === "success"
                          ? "bg-green-100 text-green-700"
                          : "bg-red-100 text-red-700"
                      }`}
                    >
                      {log.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() =>
                        setExpandedId(expandedId === log.id ? null : log.id)
                      }
                      className="text-blue-600 hover:underline"
                    >
                      {expandedId === log.id ? "收合" : "展開"}
                    </button>
                  </td>
                </tr>
                {expandedId === log.id && (
                  <tr key={`${log.id}-detail`} className="border-b bg-gray-50">
                    <td colSpan={7} className="px-4 py-3">
                      <div className="space-y-2">
                        <div>
                          <span className="text-xs font-semibold text-gray-500">Prompt：</span>
                          <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-white p-2 text-xs">
                            {log.prompt}
                          </pre>
                        </div>
                        <div>
                          <span className="text-xs font-semibold text-gray-500">Output：</span>
                          <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-white p-2 text-xs">
                            {log.output}
                          </pre>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
            {logs.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  尚無 LLM 呼叫日誌
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default LLMLogsPage;
