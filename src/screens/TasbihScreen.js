import React, { useState, useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import * as Haptics from 'expo-haptics';
import { Ionicons } from '@expo/vector-icons';
import colors from '../theme/colors';
import { fonts, typeScale } from '../theme/typography';

const PRESETS = [
  { label: 'سبحان الله', target: 33 },
  { label: 'الحمد لله', target: 33 },
  { label: 'الله أكبر', target: 34 },
  { label: 'حر (بدون هدف)', target: null },
];

export default function TasbihScreen() {
  const [presetIndex, setPresetIndex] = useState(0);
  const [count, setCount] = useState(0);
  const preset = PRESETS[presetIndex];

  const increment = useCallback(() => {
    setCount((c) => {
      // لو وصلنا للهدف بالضغطة السابقة، هذه الضغطة تبدأ عدّاً جديداً من 1
      if (preset.target && c >= preset.target) {
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
        return 1;
      }
      const next = c + 1;
      if (preset.target && next === preset.target) {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
      } else {
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
      }
      return next;
    });
  }, [preset]);

  const reset = () => setCount(0);

  const switchPreset = (index) => {
    setPresetIndex(index);
    setCount(0);
  };

  return (
    <View style={styles.container}>
      <Text style={styles.header}>السبحة</Text>

      <View style={styles.presetRow}>
        {PRESETS.map((p, i) => (
          <TouchableOpacity
            key={p.label}
            style={[styles.presetChip, presetIndex === i && styles.presetChipActive]}
            onPress={() => switchPreset(i)}
          >
            <Text
              style={[
                styles.presetLabel,
                presetIndex === i && styles.presetLabelActive,
              ]}
            >
              {p.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <TouchableOpacity
        style={styles.counterCircle}
        activeOpacity={0.85}
        onPress={increment}
      >
        <Text style={styles.countText}>{count}</Text>
        {preset.target && (
          <Text style={styles.targetText}>من {preset.target}</Text>
        )}
      </TouchableOpacity>

      <TouchableOpacity style={styles.resetButton} onPress={reset}>
        <Ionicons name="refresh-outline" size={18} color={colors.textSecondary} />
        <Text style={styles.resetText}>إعادة الضبط</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    paddingHorizontal: 20,
    alignItems: 'center',
  },
  header: {
    color: colors.textPrimary,
    fontFamily: fonts.display,
    fontSize: 22,
    alignSelf: 'flex-end',
    marginTop: 16,
    marginBottom: 20,
  },
  presetRow: {
    flexDirection: 'row-reverse',
    flexWrap: 'wrap',
    justifyContent: 'center',
    marginBottom: 40,
  },
  presetChip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    margin: 4,
  },
  presetChipActive: {
    backgroundColor: colors.accentSoft,
    borderColor: colors.accent,
  },
  presetLabel: {
    color: colors.textSecondary,
    fontFamily: fonts.body,
    fontSize: typeScale.caption,
  },
  presetLabelActive: {
    color: colors.accent,
    fontFamily: fonts.medium,
  },
  counterCircle: {
    width: 220,
    height: 220,
    borderRadius: 110,
    backgroundColor: colors.surface,
    borderWidth: 2,
    borderColor: colors.accent,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 30,
  },
  countText: {
    color: colors.textPrimary,
    fontFamily: fonts.display,
    fontSize: 56,
  },
  targetText: {
    color: colors.textSecondary,
    fontFamily: fonts.body,
    fontSize: typeScale.body,
    marginTop: 4,
  },
  resetButton: {
    flexDirection: 'row-reverse',
    alignItems: 'center',
    padding: 10,
  },
  resetText: {
    color: colors.textSecondary,
    fontFamily: fonts.body,
    fontSize: typeScale.body,
    marginRight: 6,
  },
});
