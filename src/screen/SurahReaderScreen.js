import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  ActivityIndicator,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Ionicons } from '@expo/vector-icons';
import colors from '../theme/colors';
import { fonts, typeScale } from '../theme/typography';
import { saveBookmark, getSettings } from '../utils/storage';

const FONT_SIZES = { small: 20, medium: 24, large: 29 };
const CACHE_PREFIX = '@adhkar_quran/surah_cache/';

// نص السورة بالرسم العثماني المبسط + الترجمة المعتمدة (edition: quran-uthmani)
async function fetchSurah(surahNumber) {
  const cacheKey = `${CACHE_PREFIX}${surahNumber}`;
  try {
    const cached = await AsyncStorage.getItem(cacheKey);
    if (cached) return JSON.parse(cached);
  } catch (e) {
    // نتجاهل خطأ التخزين المؤقت ونكمل بالجلب عبر الشبكة
  }

  const res = await fetch(
    `https://api.alquran.cloud/v1/surah/${surahNumber}/quran-uthmani`
  );
  const json = await res.json();
  const ayahs = json?.data?.ayahs || [];

  AsyncStorage.setItem(cacheKey, JSON.stringify(ayahs)).catch(() => {});
  return ayahs;
}

export default function SurahReaderScreen({ route }) {
  const { surahNumber, surahName, totalAyahs } = route.params;
  const [ayahs, setAyahs] = useState([]);
  const [status, setStatus] = useState('loading');
  const [fontSize, setFontSize] = useState(FONT_SIZES.medium);

  useEffect(() => {
    (async () => {
      const settings = await getSettings();
      setFontSize(FONT_SIZES[settings.fontSize] || FONT_SIZES.medium);
      try {
        const data = await fetchSurah(surahNumber);
        setAyahs(data);
        setStatus('ready');
      } catch (e) {
        setStatus('error');
      }
    })();
  }, [surahNumber]);

  const handleBookmark = useCallback(
    (ayahNumber) => {
      saveBookmark({ surahNumber, surahName, ayahNumber, totalAyahs });
    },
    [surahNumber, surahName, totalAyahs]
  );

  if (status === 'loading') {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} size="large" />
      </View>
    );
  }

  if (status === 'error') {
    return (
      <View style={styles.center}>
        <Ionicons name="cloud-offline-outline" size={40} color={colors.textMuted} />
        <Text style={styles.errorText}>
          تعذّر تحميل السورة. تحقق من الاتصال بالإنترنت وحاول مجدداً
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.surahTitle}>سورة {surahName}</Text>
      <FlatList
        data={ayahs}
        keyExtractor={(item) => String(item.numberInSurah)}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.ayahRow}
            activeOpacity={0.6}
            onLongPress={() => handleBookmark(item.numberInSurah)}
          >
            <Text style={[styles.ayahText, { fontSize }]}>
              {item.text}
              <Text style={styles.ayahNumber}> ﴿{item.numberInSurah}﴾</Text>
            </Text>
          </TouchableOpacity>
        )}
      />
      <Text style={styles.bookmarkHint}>اضغط مطولاً على أي آية لحفظها كإشارة مرجعية</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 40,
  },
  errorText: {
    color: colors.textSecondary,
    fontFamily: fonts.body,
    fontSize: typeScale.body,
    textAlign: 'center',
    marginTop: 14,
  },
  surahTitle: {
    color: colors.textPrimary,
    fontFamily: fonts.display,
    fontSize: 22,
    textAlign: 'center',
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  list: { padding: 20 },
  ayahRow: {
    marginBottom: 18,
  },
  ayahText: {
    color: colors.textPrimary,
    fontFamily: fonts.quran,
    lineHeight: 46,
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  ayahNumber: {
    color: colors.accent,
    fontSize: 16,
  },
  bookmarkHint: {
    color: colors.textMuted,
    fontFamily: fonts.body,
    fontSize: 11,
    textAlign: 'center',
    paddingBottom: 14,
  },
});
