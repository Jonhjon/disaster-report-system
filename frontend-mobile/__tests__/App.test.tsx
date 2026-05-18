/**
 * @format
 */
import React from 'react';
import ReactTestRenderer from 'react-test-renderer';

jest.mock('react-native-sse', () => jest.fn().mockImplementation(() => ({
  addEventListener: jest.fn(),
  close: jest.fn(),
})));
jest.mock('react-native-maps', () => {
  const { View } = require('react-native');
  return {
    __esModule: true,
    default: View,
    Marker: View,
    PROVIDER_GOOGLE: 'google',
  };
});
jest.mock('react-native-geolocation-service', () => ({
  getCurrentPosition: jest.fn(),
}));
jest.mock('react-native-image-picker', () => ({
  launchCamera: jest.fn(),
  launchImageLibrary: jest.fn(),
}));
jest.mock('@react-navigation/native', () => ({
  NavigationContainer: ({ children }: { children: React.ReactNode }) => children,
}));
jest.mock('@react-navigation/bottom-tabs', () => ({
  createBottomTabNavigator: () => ({
    Navigator: ({ children }: { children: React.ReactNode }) => children,
    Screen: () => null,
  }),
}));

import App from '../App';

test('App 在 Splash 階段可以渲染', async () => {
  await ReactTestRenderer.act(() => {
    ReactTestRenderer.create(<App />);
  });
});
