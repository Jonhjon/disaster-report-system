/**
 * 智慧災害通報 App - 民眾端 Android
 *
 * 啟動流程：Splash → Phone Hint + GPS → BottomTabs（對話通報 + 災情地圖）
 */
import { useCallback, useState } from 'react';
import { StatusBar } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { ChatScreen } from './src/screens/ChatScreen';
import { MapScreen } from './src/screens/MapScreen';
import { SplashScreen } from './src/screens/SplashScreen';

const Tab = createBottomTabNavigator();

function MainTabs() {
  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={{
          tabBarActiveTintColor: '#dc2626',
          tabBarInactiveTintColor: '#6b7280',
          headerStyle: { backgroundColor: '#dc2626' },
          headerTintColor: '#fff',
          headerTitleStyle: { fontWeight: '700' },
        }}
      >
        <Tab.Screen
          name="Chat"
          component={ChatScreen}
          options={{ title: '災情通報', tabBarLabel: '通報' }}
        />
        <Tab.Screen
          name="Map"
          component={MapScreen}
          options={{ title: '災情地圖', tabBarLabel: '地圖' }}
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
}

function App() {
  const [ready, setReady] = useState(false);
  const handleReady = useCallback(() => setReady(true), []);

  return (
    <SafeAreaProvider>
      <StatusBar barStyle="light-content" backgroundColor="#dc2626" />
      {ready ? <MainTabs /> : <SplashScreen onReady={handleReady} />}
    </SafeAreaProvider>
  );
}

export default App;
