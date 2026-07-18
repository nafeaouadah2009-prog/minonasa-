import React, { useEffect, useState } from 'react';
import { View, Text, ActivityIndicator, StyleSheet, TouchableOpacity } from 'react-native';
import * as Location from 'expo-location';
import { Ionicons } from '@expo/vector-icons';
import colors from '../theme/colors';
import { fonts, typeScale } from '../theme/typography';
import { getSettings } from '../utils/storage';

const PRAYER_LABELS = {
  Fajr: 'الفجر',
  Sunrise: 'الشروق',
  Dhuhr: 'الظهر',
  Asr: 'العصر',
  Maghrib: 'المغرب',
  Isha: 'العشاء',
};

// طريقة الحساب: 4 = أم القرى (تُلائم غالبية المستخدمين)، يمكن تخصيصها لاحقاً بالإعدادات
async function fetchPrayerTimes(lat, lng, madhhab) {
  const school = madhhab === 'hanafi' ? 1 : 0; // Aladhan: 0=Shafi/default, 1=Hanafi
  const url = `https://api.aladhan.com/v1/timings?latitude=${lat}&longitude=${lng}&method=4&school=${school}`;
  const res = await fetch(url);
  const json = await res.json();
  return json?.data?.timings;
}

export default function PrayerTimesScreen() {
  const [status, setStatus] = useState('loading'); // loading | denied | error | ready
  const [timings, setTimings] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const { status: permStatus } = await Location.requestForegroundPermissionsAsync();
        if (permStatus !== 'granted') {
          setStatus('denied');
          return;
        }
        const location = await Location.getCurrentPositionAsync({});
        const settings = await getSettings();
        const data = await fetchPrayerTimes(
          location.coords.latitude,
          location.coords.longitude,
          settings.madhhab
        );
        setTimings(data);
        setStatus('ready');
      } catch (e) {
        setStatus('error');
      }
    })();
  }, []);

  if (status === 'loading') {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} size="large" />
        <Text style={styles.hint}>جارٍ تحديد موقعك...</Text>
      </View>
    );
  }

  if (status === 'denied') {
    return (
      <View style={styles.center}>
        <Ionicons name="location-outline" size={40} color={colors.textMuted} />
        <Text style={styles.hint}>
          نحتاج إذن الموقع لعرض مواقيت الصلاة الدقيقة لمنطقتك
        </Text>
      </View>
    );
  }

  if (status === 'error') {
    return (
      <View style={styles.center}>
        <Ionicons name="cloud-offline-outline" size={40} color={colors.textMuted} />
        <Text style={styles.hint}>تعذّر جلب المواقيت، تأكد من الاتصال بالإنترنت</Text>
      </View>
    );
  }

  const rows = Object.keys(PRAYER_LABELS).map((key) => ({
    key,
    label: PRAYER_LABELS[key],
    time: timings[key],
  }));

  return (
    <View style={styles.container}>
      <Text style={styles.header}>مواقيت الصلاة</Text>
      {rows.map((row) => (
        <View key={row.key} style={styles.row}>
          <Text style={styles.time}>{row.time}</Text>
          <Text style={styles.label}>{row.label}</Text>
        </View>
      ))}
      <TouchableOpacity style={styles.qiblaButton}>
        <Ionicons name="compass-outline" size={20} color={colors.accent} />
        <Text style={styles.qiblaText}>اتجاه القبلة</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, paddingHorizontal: 20 },
  center: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 40,
  },
  hint: {
    color: colors.textSecondary,
    fontFamily: fonts.body,
    fontSize: typeScale.body,
    textAlign: 'center',
    marginTop: 14,
  },
  header: {
    color: colors.textPrimary,
    fontFamily: fonts.display,
    fontSize: 22,
    textAlign: 'right',
    marginTop: 16,
    marginBottom: 16,
  },
  row: {
    flexDirection: 'row-reverse',
    justifyContent: 'space-between',
    backgroundColor: colors.surface,
    borderRadius: 14,
    paddingVertical: 16,
    paddingHorizontal: 18,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
  label: {
    color: colors.textPrimary,
    fontFamily: fonts.medium,
    fontSize: typeScale.title,
  },
  time: {
    color: colors.accent,
    fontFamily: fonts.display,
    fontSize: typeScale.title,
  },
  qiblaButton: {
    flexDirection: 'row-reverse',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 20,
    padding: 14,
    borderRadius: 14,
    backgroundColor: colors.accentSoft,
  },
  qiblaText: {
    color: colors.accent,
    fontFamily: fonts.medium,
    fontSize: typeScale.body,
    marginRight: 8,
  },
});
