import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, Switch, TouchableOpacity } from 'react-native';
import colors from '../theme/colors';
import { fonts, typeScale } from '../theme/typography';
import { getSettings, saveSettings, defaultSettings } from '../utils/storage';
import {
  requestNotificationPermissions,
  scheduleDailyReminder,
  scheduleRandomPopups,
} from '../utils/notifications';

function SectionTitle({ children }) {
  return <Text style={styles.sectionTitle}>{children}</Text>;
}

function OptionRow({ label, value, options, onChange }) {
  return (
    <View style={styles.optionRow}>
      <Text style={styles.optionLabel}>{label}</Text>
      <View style={styles.chipsWrap}>
        {options.map((opt) => (
          <TouchableOpacity
            key={opt.value}
            style={[styles.chip, value === opt.value && styles.chipActive]}
            onPress={() => onChange(opt.value)}
          >
            <Text style={[styles.chipText, value === opt.value && styles.chipTextActive]}>
              {opt.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

function ToggleRow({ label, value, onChange }) {
  return (
    <View style={styles.toggleRow}>
      <Switch
        value={value}
        onValueChange={onChange}
        trackColor={{ false: colors.border, true: colors.accentSecondary }}
        thumbColor={colors.textPrimary}
      />
      <Text style={styles.optionLabel}>{label}</Text>
    </View>
  );
}

export default function SettingsScreen() {
  const [settings, setSettings] = useState(defaultSettings);

  useEffect(() => {
    getSettings().then(setSettings);
  }, []);

  const update = useCallback(async (patch) => {
    const next = { ...settings, ...patch };
    setSettings(next);
    await saveSettings(next);
  }, [settings]);

  const handleToggleNotifications = useCallback(
    async (enabled) => {
      if (enabled) {
        const granted = await requestNotificationPermissions();
        if (!granted) return;
        await scheduleDailyReminder({
          id: 'morning-reminder',
          title: 'أذكار الصباح',
          body: 'حان وقت أذكار الصباح',
          hour: settings.morningReminderTime.hour,
          minute: settings.morningReminderTime.minute,
        });
        await scheduleDailyReminder({
          id: 'evening-reminder',
          title: 'أذكار المساء',
          body: 'حان وقت أذكار المساء',
          hour: settings.eveningReminderTime.hour,
          minute: settings.eveningReminderTime.minute,
        });
      }
      update({ notificationsEnabled: enabled });
    },
    [settings, update]
  );

  const handleTogglePopups = useCallback(
    async (enabled) => {
      if (enabled) {
        await scheduleRandomPopups(settings.popupFrequencyPerDay);
      }
      update({ popupNotifications: enabled });
    },
    [settings, update]
  );

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.header}>الإعدادات</Text>

      <SectionTitle>القراءة</SectionTitle>
      <OptionRow
        label="حجم خط القرآن"
        value={settings.fontSize}
        onChange={(v) => update({ fontSize: v })}
        options={[
          { label: 'صغير', value: 'small' },
          { label: 'متوسط', value: 'medium' },
          { label: 'كبير', value: 'large' },
        ]}
      />

      <SectionTitle>الإشعارات والتذكيرات</SectionTitle>
      <ToggleRow
        label="تذكير أذكار الصباح والمساء"
        value={settings.notificationsEnabled}
        onChange={handleToggleNotifications}
      />
      <ToggleRow
        label="الإشعار الخاطف (ذكر عشوائي خلال اليوم)"
        value={settings.popupNotifications}
        onChange={handleTogglePopups}
      />
      {settings.popupNotifications && (
        <OptionRow
          label="عدد مرات الإشعار الخاطف يومياً"
          value={settings.popupFrequencyPerDay}
          onChange={(v) => {
            update({ popupFrequencyPerDay: v });
            scheduleRandomPopups(v);
          }}
          options={[
            { label: '5', value: 5 },
            { label: '8', value: 8 },
            { label: '12', value: 12 },
            { label: '20', value: 20 },
          ]}
        />
      )}

      <SectionTitle>مواقيت الصلاة</SectionTitle>
      <OptionRow
        label="المذهب (لحساب وقت العصر)"
        value={settings.madhhab}
        onChange={(v) => update({ madhhab: v })}
        options={[
          { label: 'الشافعي وغيره', value: 'shafi' },
          { label: 'الحنفي', value: 'hanafi' },
        ]}
      />

      <SectionTitle>عام</SectionTitle>
      <ToggleRow
        label="اهتزاز عند التسبيح"
        value={settings.hapticsEnabled}
        onChange={(v) => update({ hapticsEnabled: v })}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { paddingHorizontal: 20, paddingBottom: 60 },
  header: {
    color: colors.textPrimary,
    fontFamily: fonts.display,
    fontSize: 24,
    textAlign: 'right',
    marginTop: 16,
    marginBottom: 8,
  },
  sectionTitle: {
    color: colors.accent,
    fontFamily: fonts.medium,
    fontSize: typeScale.caption,
    textAlign: 'right',
    marginTop: 22,
    marginBottom: 10,
  },
  optionRow: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
  optionLabel: {
    color: colors.textPrimary,
    fontFamily: fonts.body,
    fontSize: typeScale.body,
    textAlign: 'right',
    marginBottom: 10,
  },
  chipsWrap: {
    flexDirection: 'row-reverse',
    flexWrap: 'wrap',
  },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 18,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    marginLeft: 8,
    marginBottom: 6,
  },
  chipActive: {
    backgroundColor: colors.accentSoft,
    borderColor: colors.accent,
  },
  chipText: {
    color: colors.textSecondary,
    fontFamily: fonts.body,
    fontSize: typeScale.caption,
  },
  chipTextActive: {
    color: colors.accent,
    fontFamily: fonts.medium,
  },
  toggleRow: {
    flexDirection: 'row-reverse',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
});
