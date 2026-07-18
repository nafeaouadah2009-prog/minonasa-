import React from 'react';
import { View, Text, ScrollView, StyleSheet, I18nManager } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import colors from '../theme/colors';
import { fonts, typeScale } from '../theme/typography';
import Header from '../components/Header';
import QuickActionCard from '../components/QuickActionCard';
import BreathingDivider from '../components/BreathingDivider';

// فرض اتجاه RTL لكامل الواجهة (يُستدعى مرة واحدة في نقطة دخول التطبيق أيضاً)
I18nManager.allowRTL(true);

const QUICK_ACTIONS = [
  { icon: 'book-outline', label: 'القرآن الكريم', route: 'Quran' },
  { icon: 'moon-outline', label: 'الأذكار', route: 'Adhkar' },
  { icon: 'ellipse-outline', label: 'السبحة', route: 'Tasbih' },
  { icon: 'time-outline', label: 'مواقيت الصلاة', route: 'PrayerTimes' },
];

export default function HomeScreen({ navigation }) {
  return (
    <View style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <Header />

        {/* بطاقة "متابعة القراءة" - العنصر الأكثر أهمية في الشاشة */}
        <LinearGradient
          colors={[colors.surfaceRaised, colors.surface]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.continueCard}
        >
          <Text style={styles.continueLabel}>تابع من حيث توقفت</Text>
          <Text style={styles.continueSurah}>سورة الكهف - آية 12</Text>
          <View style={styles.progressTrack}>
            <View style={[styles.progressFill, { width: '34%' }]} />
          </View>
        </LinearGradient>

        <BreathingDivider />

        {/* الاختصارات الرئيسية */}
        <View style={styles.grid}>
          {QUICK_ACTIONS.map((item) => (
            <QuickActionCard
              key={item.route}
              icon={item.icon}
              label={item.label}
              onPress={() => navigation?.navigate?.(item.route)}
            />
          ))}
        </View>

        <BreathingDivider />

        {/* ذكر اليوم */}
        <View style={styles.dhikrCard}>
          <Text style={styles.dhikrEyebrow}>ذكر اليوم</Text>
          <Text style={styles.dhikrText}>
            سُبْحَانَ اللَّهِ وَبِحَمْدِهِ، سُبْحَانَ اللَّهِ الْعَظِيمِ
          </Text>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingBottom: 40,
  },
  continueCard: {
    borderRadius: 20,
    padding: 20,
    marginTop: 18,
    borderWidth: 1,
    borderColor: colors.border,
  },
  continueLabel: {
    color: colors.textSecondary,
    fontFamily: fonts.body,
    fontSize: typeScale.caption,
    textAlign: 'right',
  },
  continueSurah: {
    color: colors.textPrimary,
    fontFamily: fonts.display,
    fontSize: typeScale.title,
    marginTop: 6,
    textAlign: 'right',
  },
  progressTrack: {
    height: 4,
    backgroundColor: colors.border,
    borderRadius: 4,
    marginTop: 14,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: colors.accent,
    borderRadius: 4,
  },
  grid: {
    flexDirection: 'row-reverse', // RTL
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  dhikrCard: {
    backgroundColor: colors.accentSoft,
    borderRadius: 20,
    padding: 22,
    borderWidth: 1,
    borderColor: colors.divider,
  },
  dhikrEyebrow: {
    color: colors.accent,
    fontFamily: fonts.medium,
    fontSize: typeScale.caption,
    textAlign: 'right',
    marginBottom: 10,
  },
  dhikrText: {
    color: colors.textPrimary,
    fontFamily: fonts.body,
    fontSize: typeScale.title,
    lineHeight: 30,
    textAlign: 'right',
  },
});
