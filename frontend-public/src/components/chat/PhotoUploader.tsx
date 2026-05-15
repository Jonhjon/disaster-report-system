import { useRef, useState } from "react";
import { Camera } from "lucide-react";
import {
  ALLOWED_PHOTO_TYPES,
  MAX_PHOTOS_PER_REPORT,
  uploadPhoto,
} from "../../services/api";
import type { AttachmentOut } from "../../types";

interface PhotoUploaderProps {
  attachments: AttachmentOut[];
  onAdd: (a: AttachmentOut) => void;
  onRemove: (id: string) => void;
  disabled?: boolean;
}

const ACCEPT_ATTR = ALLOWED_PHOTO_TYPES.join(",");

function PhotoUploader({
  attachments,
  onAdd,
  onRemove,
  disabled,
}: PhotoUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const remaining = MAX_PHOTOS_PER_REPORT - attachments.length;
  const reachedLimit = remaining <= 0;

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setError(null);
    setUploading(true);

    const toUpload = Array.from(files).slice(0, remaining);
    for (const f of toUpload) {
      try {
        const a = await uploadPhoto(f);
        onAdd(a);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "上傳失敗";
        setError(msg);
      }
    }

    setUploading(false);
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  return (
    <div className="mb-2">
      <div className="flex flex-wrap items-center gap-2">
        {attachments.map((a) => (
          <div
            key={a.id}
            className="group relative h-16 w-16 overflow-hidden rounded border bg-gray-100"
          >
            <img
              src={a.url}
              alt={a.original_filename}
              className="h-full w-full object-cover"
            />
            <button
              type="button"
              onClick={() => onRemove(a.id)}
              disabled={disabled}
              aria-label="移除照片"
              className="absolute right-0 top-0 flex h-5 w-5 items-center justify-center bg-black/60 text-xs text-white hover:bg-black/80 disabled:opacity-50"
            >
              ✕
            </button>
          </div>
        ))}

        {!reachedLimit && (
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={disabled || uploading}
            className="flex h-16 w-16 flex-col items-center justify-center gap-1 rounded border-2 border-dashed border-gray-300 text-xs text-gray-500 hover:border-red-500 hover:text-red-500 disabled:opacity-50"
          >
            <Camera size={20} aria-hidden="true" />
            <span>{uploading ? "上傳中" : "加照片"}</span>
          </button>
        )}

        <span className="text-xs text-gray-500">
          {attachments.length} / {MAX_PHOTOS_PER_REPORT} 張
        </span>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT_ATTR}
        multiple
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />

      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
}

export default PhotoUploader;
