import { useState } from "react";
import type { DisasterEvent, EventStatus } from "../../types";
import { fromDatetimeLocal, toDatetimeLocal } from "../../utils/format";
import { clampSevereInjured } from "../../utils/injury";

interface EventEditFormProps {
  event: DisasterEvent;
  onSave: (data: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
}

function EventEditForm({ event, onSave, onCancel }: EventEditFormProps) {
  const [form, setForm] = useState({
    title: event.title,
    severity: event.severity,
    status: event.status,
    description: event.description || "",
    casualties: event.casualties,
    injured: event.injured,
    severe_injured: event.severe_injured,
    trapped: event.trapped,
    occurred_at: toDatetimeLocal(event.occurred_at),
  });
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await onSave({
        ...form,
        occurred_at: fromDatetimeLocal(form.occurred_at),
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="mb-1 block text-sm text-gray-600">標題</label>
        <input
          type="text"
          className="w-full rounded border px-3 py-2 text-sm"
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
        />
      </div>

      <div>
        <label className="mb-1 block text-sm text-gray-600">發生時間</label>
        <input
          type="datetime-local"
          className="w-full rounded border px-3 py-2 text-sm"
          value={form.occurred_at}
          onChange={(e) => setForm({ ...form, occurred_at: e.target.value })}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="mb-1 block text-sm text-gray-600">嚴重程度</label>
          <select
            className="w-full rounded border px-3 py-2 text-sm"
            value={form.severity}
            onChange={(e) =>
              setForm({ ...form, severity: Number(e.target.value) })
            }
          >
            {[1, 2, 3, 4, 5].map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm text-gray-600">狀態</label>
          <select
            className="w-full rounded border px-3 py-2 text-sm"
            value={form.status}
            onChange={(e) => setForm({ ...form, status: e.target.value as EventStatus })}
          >
            <option value="reported">通報中</option>
            <option value="in_progress">處理中</option>
            <option value="resolved">已結案</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="mb-1 block text-sm text-gray-600">死亡人數</label>
          <input
            type="number"
            min="0"
            className="w-full rounded border px-3 py-2 text-sm"
            value={form.casualties}
            onChange={(e) =>
              setForm({ ...form, casualties: Number(e.target.value) })
            }
          />
        </div>
        <div>
          <label className="mb-1 block text-sm text-gray-600">受傷人數</label>
          <input
            type="number"
            min="0"
            className="w-full rounded border px-3 py-2 text-sm"
            value={form.injured}
            onChange={(e) => {
              const injured = Number(e.target.value);
              setForm({
                ...form,
                injured,
                // 重傷是受傷子集，受傷數下修時同步夾擠重傷數
                severe_injured: clampSevereInjured(form.severe_injured, injured),
              });
            }}
          />
        </div>
        <div>
          <label className="mb-1 block text-sm text-gray-600">
            其中重傷人數
          </label>
          <input
            type="number"
            min="0"
            max={form.injured}
            className="w-full rounded border px-3 py-2 text-sm"
            value={form.severe_injured}
            onChange={(e) =>
              setForm({
                ...form,
                severe_injured: clampSevereInjured(
                  Number(e.target.value),
                  form.injured,
                ),
              })
            }
          />
        </div>
        <div>
          <label className="mb-1 block text-sm text-gray-600">受困人數</label>
          <input
            type="number"
            min="0"
            className="w-full rounded border px-3 py-2 text-sm"
            value={form.trapped}
            onChange={(e) =>
              setForm({ ...form, trapped: Number(e.target.value) })
            }
          />
        </div>
      </div>

      <div>
        <label className="mb-1 block text-sm text-gray-600">描述</label>
        <textarea
          className="w-full rounded border px-3 py-2 text-sm"
          rows={3}
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
        />
      </div>

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
        >
          {saving ? "儲存中..." : "儲存"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border px-4 py-2 text-sm hover:bg-gray-50"
        >
          取消
        </button>
      </div>
    </form>
  );
}

export default EventEditForm;
