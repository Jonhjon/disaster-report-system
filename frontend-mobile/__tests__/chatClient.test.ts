// chatClient 行為驗證：mock react-native-sse 監聽 'message' / 'error'
jest.mock('react-native', () => ({
  Platform: {
    OS: 'android',
    select: (obj: Record<string, unknown>) => obj.android,
  },
}));

// 在 factory 內定義 MockEventSource，並把控制權暴露到 mock 物件本身，
// 避免 class/const 在 jest.mock factory 執行時尚未初始化（TDZ）問題。
jest.mock('react-native-sse', () => {
  const state: {
    listeners: Record<string, (e: { data?: string }) => void>;
    close: jest.Mock;
    ctorArgs: unknown[][];
  } = {
    listeners: {},
    close: jest.fn(),
    ctorArgs: [],
  };
  function MockEventSource(this: unknown, url: string, opts: unknown) {
    state.ctorArgs.push([url, opts]);
    (this as { addEventListener: unknown }).addEventListener = (
      event: string,
      fn: (e: { data?: string }) => void,
    ) => {
      state.listeners[event] = fn;
    };
    (this as { close: unknown }).close = () => state.close();
  }
  // 把 state 掛在 constructor 自身上，方便測試從 default import 取得。
  (MockEventSource as unknown as { __state: typeof state }).__state = state;
  return {
    __esModule: true,
    default: MockEventSource,
  };
});

import sseDefault from 'react-native-sse';
import { streamChat } from '../src/api/chatClient';
import { useSessionStore } from '../src/stores/sessionStore';

const sseState = (
  sseDefault as unknown as {
    __state: {
      listeners: Record<string, (e: { data?: string }) => void>;
      close: jest.Mock;
      ctorArgs: unknown[][];
    };
  }
).__state;

describe('streamChat', () => {
  beforeEach(() => {
    sseState.listeners = {};
    sseState.close.mockReset();
    sseState.ctorArgs.length = 0;
    useSessionStore.getState().reset();
  });

  it('文字 chunk 透過 onText 回傳', () => {
    const onText = jest.fn();
    streamChat('火警', [], [], {
      onText,
      onReportSubmitted: jest.fn(),
      onError: jest.fn(),
      onDone: jest.fn(),
    });
    sseState.listeners.message({
      data: JSON.stringify({ type: 'text', content: '處理中' }),
    });
    expect(onText).toHaveBeenCalledWith('處理中');
  });

  it('done 事件呼叫 onDone 並關閉連線', () => {
    const onDone = jest.fn();
    streamChat('火警', [], [], {
      onText: jest.fn(),
      onReportSubmitted: jest.fn(),
      onError: jest.fn(),
      onDone,
    });
    sseState.listeners.message({ data: JSON.stringify({ type: 'done' }) });
    expect(onDone).toHaveBeenCalled();
    expect(sseState.close).toHaveBeenCalled();
  });

  it('error 訊息透過 onError 傳出', () => {
    const onError = jest.fn();
    streamChat('火警', [], [], {
      onText: jest.fn(),
      onReportSubmitted: jest.fn(),
      onError,
      onDone: jest.fn(),
    });
    sseState.listeners.message({
      data: JSON.stringify({ type: 'error', message: '伺服器錯誤' }),
    });
    expect(onError).toHaveBeenCalledWith('伺服器錯誤');
  });

  it('帶入 sessionStore.verifiedPhone 與 deviceLocation 至 request body', () => {
    useSessionStore.getState().setVerifiedPhone('+886912345678');
    useSessionStore.getState().setDeviceLocation({ lat: 25.0, lng: 121.5 });
    streamChat('火警', [], [], {
      onText: jest.fn(),
      onReportSubmitted: jest.fn(),
      onError: jest.fn(),
      onDone: jest.fn(),
    });
    const [, options] = sseState.ctorArgs[0] as [unknown, { body: string }];
    const body = JSON.parse(options.body);
    expect(body.verified_phone).toBe('+886912345678');
    expect(body.device_location).toEqual({ lat: 25.0, lng: 121.5 });
  });

  it('handle.close 可被呼叫', () => {
    const handle = streamChat('火警', [], [], {
      onText: jest.fn(),
      onReportSubmitted: jest.fn(),
      onError: jest.fn(),
      onDone: jest.fn(),
    });
    handle.close();
    expect(sseState.close).toHaveBeenCalled();
  });
});
