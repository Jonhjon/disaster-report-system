// 驗證 sessionStore（zustand 全域狀態）行為
import { getSessionSnapshot, useSessionStore } from '../src/stores/sessionStore';

describe('sessionStore', () => {
  beforeEach(() => {
    useSessionStore.getState().reset();
  });

  it('預設為 null', () => {
    const { verifiedPhone, deviceLocation } = useSessionStore.getState();
    expect(verifiedPhone).toBeNull();
    expect(deviceLocation).toBeNull();
  });

  it('setVerifiedPhone 寫入後 getSessionSnapshot 可讀取', () => {
    useSessionStore.getState().setVerifiedPhone('+886912345678');
    expect(getSessionSnapshot().verifiedPhone).toBe('+886912345678');
  });

  it('setDeviceLocation 寫入後可讀取', () => {
    useSessionStore.getState().setDeviceLocation({ lat: 25.0, lng: 121.5 });
    expect(getSessionSnapshot().deviceLocation).toEqual({ lat: 25.0, lng: 121.5 });
  });

  it('reset 清除所有狀態', () => {
    const store = useSessionStore.getState();
    store.setVerifiedPhone('0912345678');
    store.setDeviceLocation({ lat: 1, lng: 1 });
    store.reset();
    const snap = getSessionSnapshot();
    expect(snap.verifiedPhone).toBeNull();
    expect(snap.deviceLocation).toBeNull();
  });
});
