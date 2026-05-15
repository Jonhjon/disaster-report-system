import { useState, useEffect, useRef } from "react";
import type { AttachmentOut } from "../../types";

interface ImageLightboxProps {
  image: AttachmentOut;
  images: AttachmentOut[];
  onClose: () => void;
}

export default function ImageLightbox({ image, images, onClose }: ImageLightboxProps) {
  const [currentIndex, setCurrentIndex] = useState(
    () => Math.max(0, images.findIndex((i) => i.id === image.id))
  );

  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  const total = images.length;
  const current = images[currentIndex] ?? image;

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCloseRef.current();
      } else if (e.key === "ArrowLeft") {
        setCurrentIndex((i) => Math.max(0, i - 1));
      } else if (e.key === "ArrowRight") {
        setCurrentIndex((i) => (i < total - 1 ? i + 1 : i));
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [total]);

  const stopPropagation = (e: React.MouseEvent) => e.stopPropagation();

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
      onClick={onClose}
    >
      <button
        className="absolute right-4 top-4 z-10 rounded-full bg-white/20 px-3 py-1 text-lg text-white hover:bg-white/40"
        onClick={onClose}
      >
        ✕
      </button>

      {total > 1 && currentIndex > 0 && (
        <button
          className="absolute left-4 top-1/2 -translate-y-1/2 rounded-full bg-white/20 px-3 py-2 text-2xl text-white hover:bg-white/40"
          onClick={(e) => { stopPropagation(e); setCurrentIndex((i) => i - 1); }}
        >
          ‹
        </button>
      )}

      {total > 1 && currentIndex < total - 1 && (
        <button
          className="absolute right-4 top-1/2 -translate-y-1/2 rounded-full bg-white/20 px-3 py-2 text-2xl text-white hover:bg-white/40"
          onClick={(e) => { stopPropagation(e); setCurrentIndex((i) => i + 1); }}
        >
          ›
        </button>
      )}

      <div className="flex flex-col items-center gap-3" onClick={stopPropagation}>
        <img
          src={current.url}
          alt={current.original_filename}
          className="max-h-[85vh] max-w-[90vw] rounded object-contain shadow-2xl"
        />
        <div className="text-center text-sm text-white/80">
          <span>{current.original_filename}</span>
          {total > 1 && (
            <span className="ml-3 text-white/50">
              {currentIndex + 1} / {total}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
