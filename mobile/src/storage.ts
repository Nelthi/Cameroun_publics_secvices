import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';
import type { Settings } from './types';

const KEY = 'cps.settings.v1';

// Émulateur Android : 10.0.2.2 = ordinateur hôte. Sur un vrai téléphone : saisir l'IP de la machine dans Paramètres.
export const DEFAULT_URL = Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000';

function newUserId(): string {
  return 'u-' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
}

export async function loadSettings(): Promise<Settings> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<Settings>;
      return {
        baseUrl: parsed.baseUrl || DEFAULT_URL,
        adminToken: parsed.adminToken || '',
        userId: parsed.userId || newUserId(),
      };
    }
  } catch {
    // paramètres illisibles : on repart de zéro
  }
  const fresh: Settings = { baseUrl: DEFAULT_URL, adminToken: '', userId: newUserId() };
  await saveSettings(fresh);
  return fresh;
}

export async function saveSettings(settings: Settings): Promise<void> {
  await AsyncStorage.setItem(KEY, JSON.stringify(settings));
}
