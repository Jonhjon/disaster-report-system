// 測試 TS 橋接層：mock NativeModules.PhoneNumberHint
jest.mock('react-native', () => ({
  NativeModules: {
    PhoneNumberHint: {
      requestPhoneNumber: jest.fn(),
    },
  },
  Platform: { OS: 'android' },
}));

import { NativeModules, Platform } from 'react-native';
import type { PhoneHintResult } from '../src/native/PhoneNumberHint';

const mockNative = NativeModules.PhoneNumberHint as {
  requestPhoneNumber: jest.Mock;
};

function loadBridge(): { requestPhoneNumber: () => Promise<PhoneHintResult> } {
  let mod!: { requestPhoneNumber: () => Promise<PhoneHintResult> };
  jest.isolateModules(() => {
    mod = require('../src/native/PhoneNumberHint');
  });
  return mod;
}

describe('requestPhoneNumber bridge', () => {
  beforeEach(() => {
    mockNative.requestPhoneNumber.mockReset();
    (Platform as { OS: string }).OS = 'android';
  });

  it('回傳 phoneNumber 當原生模組成功', async () => {
    mockNative.requestPhoneNumber.mockResolvedValue({
      canceled: false,
      phoneNumber: '+886912345678',
    });
    const { requestPhoneNumber } = loadBridge();
    const result = await requestPhoneNumber();
    expect(result).toEqual({ canceled: false, phoneNumber: '+886912345678' });
  });

  it('canceled 為 true 時回傳取消結果', async () => {
    mockNative.requestPhoneNumber.mockResolvedValue({
      canceled: true,
      reason: 'user_canceled',
    });
    const { requestPhoneNumber } = loadBridge();
    const result = await requestPhoneNumber();
    expect(result).toEqual({ canceled: true, reason: 'user_canceled' });
  });

  it('phoneNumber 為空字串視為取消', async () => {
    mockNative.requestPhoneNumber.mockResolvedValue({
      canceled: false,
      phoneNumber: '',
    });
    const { requestPhoneNumber } = loadBridge();
    const result = await requestPhoneNumber();
    expect(result.canceled).toBe(true);
  });

  it('iOS 平台直接回傳不支援', async () => {
    (Platform as { OS: string }).OS = 'ios';
    const { requestPhoneNumber } = loadBridge();
    const result = await requestPhoneNumber();
    expect(result).toEqual({ canceled: true, reason: 'unsupported_platform' });
  });
});
