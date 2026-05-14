/**
 * 管理中心通知音效。
 * 使用 Web Audio API 動態合成短促 beep（兩個音 800Hz → 1000Hz，~250ms），
 * 避免引入 mp3 二進位資產。
 *
 * 瀏覽器自動播放限制：使用者首次互動前無法播放 — 以 try/catch 沉默失敗。
 */

let cachedContext: AudioContext | null = null;

function getAudioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  if (cachedContext) return cachedContext;
  const Ctor =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext })
      .webkitAudioContext;
  if (!Ctor) return null;
  cachedContext = new Ctor();
  return cachedContext;
}

function playTone(
  ctx: AudioContext,
  frequency: number,
  startAt: number,
  duration: number,
): void {
  const oscillator = ctx.createOscillator();
  const gain = ctx.createGain();

  oscillator.type = "sine";
  oscillator.frequency.value = frequency;

  // 短促 envelope：避免 click 雜音
  gain.gain.setValueAtTime(0, startAt);
  gain.gain.linearRampToValueAtTime(0.18, startAt + 0.01);
  gain.gain.linearRampToValueAtTime(0, startAt + duration);

  oscillator.connect(gain).connect(ctx.destination);
  oscillator.start(startAt);
  oscillator.stop(startAt + duration);
}

export function playNotificationSound(): void {
  try {
    const ctx = getAudioContext();
    if (!ctx) return;
    if (ctx.state === "suspended") {
      void ctx.resume();
    }
    const now = ctx.currentTime;
    playTone(ctx, 800, now, 0.12);
    playTone(ctx, 1000, now + 0.13, 0.12);
  } catch {
    // 自動播放限制 / AudioContext 創建失敗 — 沉默失敗
  }
}
