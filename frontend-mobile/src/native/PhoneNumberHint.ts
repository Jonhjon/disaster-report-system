// 與 Android 原生模組 PhoneNumberHintModule 對應的 TS 橋接
import { NativeModules, Platform } from 'react-native';

interface NativePhoneNumberHint {
  requestPhoneNumber(): Promise<{
    phoneNumber?: string;
    canceled: boolean;
    reason?: string;
  }>;
}

const native: NativePhoneNumberHint | undefined = (
  NativeModules as { PhoneNumberHint?: NativePhoneNumberHint }
).PhoneNumberHint;

export type PhoneHintResult =
  | { canceled: false; phoneNumber: string }
  | { canceled: true; reason?: string };

export async function requestPhoneNumber(): Promise<PhoneHintResult> {
  if (Platform.OS !== 'android') {
    return { canceled: true, reason: 'unsupported_platform' };
  }
  if (!native) {
    return { canceled: true, reason: 'native_module_missing' };
  }
  const raw = await native.requestPhoneNumber();
  if (raw.canceled || !raw.phoneNumber || raw.phoneNumber.length === 0) {
    return { canceled: true, reason: raw.reason };
  }
  return { canceled: false, phoneNumber: raw.phoneNumber };
}
