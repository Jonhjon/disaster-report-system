jest.mock('react-native', () => ({
  Platform: { OS: 'android', select: (obj: Record<string, unknown>) => obj.android },
}));

import { apiUrl, API_BASE_URL } from '../src/config/env';

describe('env / apiUrl', () => {
  it('Android 預設 base URL 指向 10.0.2.2:8000', () => {
    expect(API_BASE_URL).toBe('http://10.0.2.2:8000');
  });

  it('apiUrl 加上 /api 前綴', () => {
    expect(apiUrl('/chat')).toBe('http://10.0.2.2:8000/api/chat');
    expect(apiUrl('events/map')).toBe('http://10.0.2.2:8000/api/events/map');
  });
});
