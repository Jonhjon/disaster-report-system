// 全域會話狀態：經 Phone Number Hint 取得的電話、GPS 位置
import { create } from 'zustand';
import type { DeviceLocation } from '../types';

interface SessionState {
  verifiedPhone: string | null;
  deviceLocation: DeviceLocation | null;
  setVerifiedPhone: (phone: string | null) => void;
  setDeviceLocation: (loc: DeviceLocation | null) => void;
  reset: () => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  verifiedPhone: null,
  deviceLocation: null,
  setVerifiedPhone: (phone) => set({ verifiedPhone: phone }),
  setDeviceLocation: (loc) => set({ deviceLocation: loc }),
  reset: () => set({ verifiedPhone: null, deviceLocation: null }),
}));

// 純函式：用於非 React 環境（例如 API 呼叫器）取值
export function getSessionSnapshot(): {
  verifiedPhone: string | null;
  deviceLocation: DeviceLocation | null;
} {
  const { verifiedPhone, deviceLocation } = useSessionStore.getState();
  return { verifiedPhone, deviceLocation };
}
