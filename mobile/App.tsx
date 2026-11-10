import React, { useEffect, useState } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { configure } from './src/api';
import { loadSettings } from './src/storage';
import { colors } from './src/theme';
import type { Role, Settings } from './src/types';
import { AdminApp } from './src/screens/AdminApp';
import { RoleScreen } from './src/screens/RoleScreen';
import { SettingsModal } from './src/screens/SettingsModal';
import { UserChat } from './src/screens/UserChat';

export default function App() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [role, setRole] = useState<Role | null>(null);
  const [showSettings, setShowSettings] = useState(false);

  useEffect(() => {
    void loadSettings().then((s) => {
      configure(s);
      setSettings(s);
    });
  }, []);

  if (!settings) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg }}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  return (
    <SafeAreaProvider>
      <StatusBar style={role === null ? 'light' : 'light'} />
      {role === null ? <RoleScreen onPick={setRole} onSettings={() => setShowSettings(true)} /> : null}
      {role === 'user' ? <UserChat onExit={() => setRole(null)} /> : null}
      {role === 'admin' ? <AdminApp onExit={() => setRole(null)} /> : null}
      <SettingsModal
        key={showSettings ? 'open' : 'closed'}
        visible={showSettings}
        settings={settings}
        onClose={() => setShowSettings(false)}
        onSaved={(s) => { setSettings(s); setShowSettings(false); }}
      />
    </SafeAreaProvider>
  );
}
