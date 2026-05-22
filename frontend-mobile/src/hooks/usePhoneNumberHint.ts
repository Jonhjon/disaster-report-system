// React hook：呼叫 Phone Number Hint API，並把取得的電話寫入 sessionStore
import { useCallback, useState } from 'react';
import { requestPhoneNumber, type PhoneHintResult } from '../native/PhoneNumberHint';
import { useSessionStore } from '../stores/sessionStore';

interface UsePhoneNumberHint {
  loading: boolean;
  error: string | null;
  request: () => Promise<PhoneHintResult>;
}

export function usePhoneNumberHint(): UsePhoneNumberHint {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const setVerifiedPhone = useSessionStore((s) => s.setVerifiedPhone);

  const request = useCallback(async (): Promise<PhoneHintResult> => {
    setLoading(true);
    setError(null);
    try {
      const result = await requestPhoneNumber();
      if (!result.canceled) {
        setVerifiedPhone(result.phoneNumber);
      }
      return result;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '取得電話號碼失敗';
      setError(msg);
      return { canceled: true, reason: msg };
    } finally {
      setLoading(false);
    }
  }, [setVerifiedPhone]);

  return { loading, error, request };
}
