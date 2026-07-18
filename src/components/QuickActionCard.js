import React from 'react';
import { TouchableOpacity, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import colors from '../theme/colors';
import { fonts, typeScale } from '../theme/typography';

export default function QuickActionCard({ icon, label, onPress }) {
  return (
    <TouchableOpacity
      style={styles.card}
      activeOpacity={0.7}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      <Ionicons name={icon} size={26} color={colors.accent} />
      <Text style={styles.label}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    width: '47%',
    backgroundColor: colors.surface,
    borderRadius: 16,
    paddingVertical: 22,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 14,
    borderWidth: 1,
    borderColor: colors.border,
  },
  label: {
    color: colors.textPrimary,
    fontFamily: fonts.medium,
    fontSize: typeScale.body,
    marginTop: 10,
  },
});
