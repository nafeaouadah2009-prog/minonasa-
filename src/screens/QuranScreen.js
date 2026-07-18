import React, { useState, useMemo } from 'react';
import { View, Text, FlatList, TouchableOpacity, TextInput, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import colors from '../theme/colors';
import { fonts, typeScale } from '../theme/typography';
import surahs from '../data/surahs';

export default function QuranScreen({ navigation }) {
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    if (!query.trim()) return surahs;
    const q = query.trim();
    return surahs.filter(
      (s) => s.name.includes(q) || s.english.toLowerCase().includes(q.toLowerCase())
    );
  }, [query]);

  return (
    <View style={styles.container}>
      <Text style={styles.header}>القرآن الكريم</Text>

      <View style={styles.searchBox}>
        <Ionicons name="search-outline" size={18} color={colors.textMuted} />
        <TextInput
          style={styles.searchInput}
          placeholder="ابحث عن سورة..."
          placeholderTextColor={colors.textMuted}
          value={query}
          onChangeText={setQuery}
          textAlign="right"
        />
      </View>

      <FlatList
        data={filtered}
        keyExtractor={(item) => String(item.number)}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.row}
            activeOpacity={0.7}
            onPress={() =>
              navigation.navigate('SurahReader', {
                surahNumber: item.number,
                surahName: item.name,
                totalAyahs: item.ayahs,
              })
            }
          >
            <View style={styles.numberBadge}>
              <Text style={styles.numberText}>{item.number}</Text>
            </View>
            <View style={styles.rowText}>
              <Text style={styles.surahName}>{item.name}</Text>
              <Text style={styles.surahMeta}>
                {item.type} · {item.ayahs} آية
              </Text>
            </View>
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, paddingHorizontal: 20 },
  header: {
    color: colors.textPrimary,
    fontFamily: fonts.display,
    fontSize: 24,
    textAlign: 'right',
    marginTop: 16,
    marginBottom: 12,
  },
  searchBox: {
    flexDirection: 'row-reverse',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 4,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  searchInput: {
    flex: 1,
    color: colors.textPrimary,
    fontFamily: fonts.body,
    fontSize: typeScale.body,
    paddingVertical: 10,
    marginRight: 8,
  },
  list: { paddingBottom: 40 },
  row: {
    flexDirection: 'row-reverse',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 14,
    paddingVertical: 14,
    paddingHorizontal: 16,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
  numberBadge: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: colors.accentSoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 12,
  },
  numberText: {
    color: colors.accent,
    fontFamily: fonts.medium,
    fontSize: typeScale.caption,
  },
  rowText: { flex: 1 },
  surahName: {
    color: colors.textPrimary,
    fontFamily: fonts.medium,
    fontSize: typeScale.title,
    textAlign: 'right',
  },
  surahMeta: {
    color: colors.textSecondary,
    fontFamily: fonts.body,
    fontSize: typeScale.caption,
    textAlign: 'right',
    marginTop: 2,
  },
});
