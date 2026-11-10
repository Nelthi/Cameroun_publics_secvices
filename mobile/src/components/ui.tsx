import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator, Animated, Pressable, StyleSheet, Text, TextInput, TextInputProps, View, ViewStyle,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, radius, shadow } from '../theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

export function Button(props: {
  label: string;
  onPress: () => void;
  icon?: IconName;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  loading?: boolean;
  disabled?: boolean;
  small?: boolean;
  style?: ViewStyle;
}) {
  const variant = props.variant ?? 'primary';
  const palette = {
    primary: { bg: colors.primary, fg: '#fff', border: colors.primary },
    secondary: { bg: colors.primarySoft, fg: colors.primaryDark, border: colors.primarySoft },
    ghost: { bg: 'transparent', fg: colors.primaryDark, border: colors.border },
    danger: { bg: colors.dangerSoft, fg: colors.danger, border: colors.dangerSoft },
  }[variant];
  const inactive = props.disabled || props.loading;
  return (
    <Pressable
      onPress={props.onPress}
      disabled={inactive}
      style={({ pressed }) => [
        styles.button,
        props.small && styles.buttonSmall,
        { backgroundColor: palette.bg, borderColor: palette.border, opacity: inactive ? 0.55 : pressed ? 0.85 : 1 },
        props.style,
      ]}
    >
      {props.loading ? (
        <ActivityIndicator size="small" color={palette.fg} />
      ) : props.icon ? (
        <Ionicons name={props.icon} size={props.small ? 15 : 18} color={palette.fg} />
      ) : null}
      <Text style={[styles.buttonText, props.small && { fontSize: 13 }, { color: palette.fg }]}>{props.label}</Text>
    </Pressable>
  );
}

export function IconButton(props: { icon: IconName; onPress: () => void; color?: string; size?: number; bg?: string; disabled?: boolean }) {
  return (
    <Pressable
      onPress={props.onPress}
      disabled={props.disabled}
      hitSlop={8}
      style={({ pressed }) => [styles.iconButton, { backgroundColor: props.bg ?? 'transparent', opacity: props.disabled ? 0.4 : pressed ? 0.7 : 1 }]}
    >
      <Ionicons name={props.icon} size={props.size ?? 22} color={props.color ?? colors.primaryDark} />
    </Pressable>
  );
}

export function Card(props: { children: React.ReactNode; style?: ViewStyle }) {
  return <View style={[styles.card, props.style]}>{props.children}</View>;
}

export function Badge(props: { label: string; tone?: 'success' | 'warn' | 'danger' | 'info' | 'neutral' }) {
  const tone = props.tone ?? 'neutral';
  const map = {
    success: [colors.successSoft, colors.success],
    warn: [colors.warnSoft, colors.warn],
    danger: [colors.dangerSoft, colors.danger],
    info: [colors.infoSoft, colors.info],
    neutral: ['#ECEFED', colors.muted],
  }[tone];
  return (
    <View style={[styles.badge, { backgroundColor: map[0] }]}>
      <Text style={[styles.badgeText, { color: map[1] }]}>{props.label}</Text>
    </View>
  );
}

export function SectionTitle(props: { title: string; right?: React.ReactNode }) {
  return (
    <View style={styles.sectionRow}>
      <Text style={styles.sectionTitle}>{props.title}</Text>
      {props.right}
    </View>
  );
}

export function Field(props: TextInputProps & { label: string }) {
  const { label, style, ...rest } = props;
  return (
    <View style={{ marginBottom: 10 }}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <TextInput placeholderTextColor="#9AA7A1" style={[styles.input, style]} {...rest} />
    </View>
  );
}

export function Segmented<T extends string>(props: { options: { value: T; label: string }[]; value: T; onChange: (v: T) => void }) {
  return (
    <View style={styles.segmented}>
      {props.options.map((o) => {
        const active = o.value === props.value;
        return (
          <Pressable key={o.value} onPress={() => props.onChange(o.value)} style={[styles.segment, active && styles.segmentActive]}>
            <Text style={[styles.segmentText, active && { color: '#fff' }]}>{o.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function ProgressBar(props: { value: number }) {
  return (
    <View style={styles.track}>
      <View style={[styles.fill, { width: `${Math.round(Math.min(Math.max(props.value, 0), 1) * 100)}%` }]} />
    </View>
  );
}

export function Empty(props: { icon: IconName; text: string }) {
  return (
    <View style={styles.empty}>
      <Ionicons name={props.icon} size={34} color="#9AA7A1" />
      <Text style={styles.emptyText}>{props.text}</Text>
    </View>
  );
}

export function useToast() {
  const [message, setMessage] = useState<string | null>(null);
  const opacity = useRef(new Animated.Value(0)).current;
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const show = useCallback((text: string) => {
    setMessage(text);
    opacity.setValue(0);
    Animated.timing(opacity, { toValue: 1, duration: 160, useNativeDriver: true }).start();
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      Animated.timing(opacity, { toValue: 0, duration: 220, useNativeDriver: true }).start(() => setMessage(null));
    }, 2200);
  }, [opacity]);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  const node = message ? (
    <Animated.View pointerEvents="none" style={[styles.toast, { opacity }]}>
      <Text style={styles.toastText}>{message}</Text>
    </Animated.View>
  ) : null;
  return { show, node };
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

export function formatSize(bytes: number | null | undefined): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(0)} Ko`;
  return `${(bytes / 1048576).toFixed(1)} Mo`;
}

const styles = StyleSheet.create({
  button: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 12, paddingHorizontal: 16, borderRadius: radius.md, borderWidth: 1 },
  buttonSmall: { paddingVertical: 8, paddingHorizontal: 12, borderRadius: radius.sm },
  buttonText: { fontSize: 15, fontWeight: '600' },
  iconButton: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  card: { backgroundColor: colors.surface, borderRadius: radius.lg, padding: 16, borderWidth: 1, borderColor: colors.border, ...shadow },
  badge: { paddingHorizontal: 9, paddingVertical: 3, borderRadius: radius.pill, alignSelf: 'flex-start' },
  badgeText: { fontSize: 11.5, fontWeight: '700' },
  sectionRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10, marginTop: 6 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: colors.text },
  fieldLabel: { fontSize: 12, fontWeight: '600', color: colors.muted, marginBottom: 4 },
  input: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm, backgroundColor: '#FBFCFB', paddingHorizontal: 12, paddingVertical: 9, fontSize: 14.5, color: colors.text },
  segmented: { flexDirection: 'row', backgroundColor: '#E7ECE9', borderRadius: radius.md, padding: 3 },
  segment: { flex: 1, paddingVertical: 9, alignItems: 'center', borderRadius: radius.sm + 1 },
  segmentActive: { backgroundColor: colors.primary },
  segmentText: { fontSize: 13, fontWeight: '600', color: colors.primaryDark },
  track: { height: 8, borderRadius: 4, backgroundColor: '#E3E9E6', overflow: 'hidden' },
  fill: { height: 8, backgroundColor: colors.primary, borderRadius: 4 },
  empty: { alignItems: 'center', paddingVertical: 30, gap: 8 },
  emptyText: { color: colors.muted, fontSize: 14, textAlign: 'center' },
  toast: { position: 'absolute', bottom: 96, alignSelf: 'center', backgroundColor: colors.primaryDark, paddingHorizontal: 16, paddingVertical: 10, borderRadius: radius.pill, maxWidth: '88%' },
  toastText: { color: '#fff', fontSize: 13.5, fontWeight: '600', textAlign: 'center' },
});
