import React, { useState } from 'react';
import { KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { api, configure } from '../api';
import { Button, Card, Field } from '../components/ui';
import { saveSettings } from '../storage';
import { colors } from '../theme';
import type { Settings } from '../types';

export function SettingsModal(props: { visible: boolean; settings: Settings; onClose: () => void; onSaved: (s: Settings) => void }) {
  const [baseUrl, setBaseUrl] = useState(props.settings.baseUrl);
  const [adminToken, setAdminToken] = useState(props.settings.adminToken);
  const [status, setStatus] = useState<{ ok: boolean; text: string } | null>(null);
  const [testing, setTesting] = useState(false);

  const next = (): Settings => ({ ...props.settings, baseUrl: baseUrl.trim().replace(/\/+$/, ''), adminToken: adminToken.trim() });

  const test = async () => {
    setTesting(true);
    setStatus(null);
    configure(next());
    try {
      const h = await api.health();
      setStatus({ ok: true, text: `Connecté. LLM : ${h.llm}. Groq : ${h.groq_configured ? 'configuré' : 'non configuré'}.` });
    } catch (e) {
      setStatus({ ok: false, text: (e as Error).message });
    } finally {
      setTesting(false);
    }
  };

  const save = async () => {
    const value = next();
    configure(value);
    await saveSettings(value);
    props.onSaved(value);
  };

  return (
    <Modal visible={props.visible} animationType="slide" onRequestClose={props.onClose}>
      <SafeAreaView style={styles.root}>
        <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <View style={styles.header}>
            <Text style={styles.title}>Paramètres</Text>
            <Pressable onPress={props.onClose} hitSlop={10}><Text style={styles.close}>Fermer</Text></Pressable>
          </View>
          <ScrollView contentContainerStyle={{ padding: 16, gap: 14 }} keyboardShouldPersistTaps="handled">
            <Card>
              <Field label="Adresse de l'API" value={baseUrl} onChangeText={setBaseUrl} autoCapitalize="none" autoCorrect={false}
                placeholder="http://192.168.1.20:8000" keyboardType="url" />
              <Text style={styles.help}>
                Émulateur Android : http://10.0.2.2:8000. Téléphone réel : l'adresse IP de la machine qui lance le serveur
                (même Wi-Fi ; avec VirtualBox, carte réseau en « accès par pont »).
              </Text>
              <Field label="Jeton administrateur (facultatif)" value={adminToken} onChangeText={setAdminToken}
                autoCapitalize="none" autoCorrect={false} secureTextEntry placeholder="Seulement si ADMIN_TOKEN est défini" />
              {status ? <Text style={[styles.status, { color: status.ok ? colors.success : colors.danger }]}>{status.text}</Text> : null}
              <View style={{ flexDirection: 'row', gap: 10, marginTop: 6 }}>
                <Button label="Tester" variant="secondary" icon="pulse" loading={testing} onPress={test} style={{ flex: 1 }} />
                <Button label="Enregistrer" icon="checkmark" onPress={save} style={{ flex: 1 }} />
              </View>
            </Card>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16, backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.border },
  title: { fontSize: 18, fontWeight: '700', color: colors.text },
  close: { color: colors.primary, fontWeight: '700', fontSize: 15 },
  help: { fontSize: 12.5, color: colors.muted, lineHeight: 18, marginBottom: 12, marginTop: -2 },
  status: { fontSize: 13.5, fontWeight: '600', marginVertical: 6 },
});
