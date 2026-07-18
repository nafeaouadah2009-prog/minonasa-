import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import colors from '../theme/colors';
import { fonts, typeScale } from '../theme/typography';

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 5) return 'طاب ليلك';
  if (hour < 12) return 'صباح الخير';
  if (hour < 17) return 'طاب نهارك';
  if (hour < 20) return 'طاب مساؤك';
  return 'طاب ليلك';
}

export default function Header() {
  return (
    <View style={styles.wrapper}>
      <Text style={styles.greeting}>{getGreeting()}</Text>
      <Text style={styles.subtitle}>نسأل الله أن يبارك في وقتك</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    paddingTop: 12,
    paddingBottom: 4,
    alignItems: 'flex-end', // RTL: المحاذاة لليمين
  },
  greeting: {
    color: colors.textPrimary,
    fontFamily: fonts.display,
    fontSize: typeScale.greeting,
    textAlign: 'right',
  },
  subtitle: {
    color: colors.textSecondary,
    fontFamily: fonts.body,
    fontSize: typeScale.body,
    marginTop: 4,
    textAlign: 'right',
  },
});
