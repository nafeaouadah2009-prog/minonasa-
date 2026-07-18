import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet } from 'react-native';
import * as Haptics from 'expo-haptics';
import colors from '../theme/colors';
import { fonts, typeScale } from '../theme/typography';
import { adhkarData } from '../data/adhkar';
import { getAdhkarProgress, saveAdhkarProgress, markTodayActive } from '../utils/storage';

function DhikrCard({ item, doneCount, onPress }) {
  const remaining = Math.max(item.count - doneCount, 0);
  const isComplete = remaining === 0;

  return (
    <TouchableOpacity
      style={[styles.card, isComplete && styles.cardComplete]}
      activeOpacity={0.8}
      onPress={onPress}
      disabled={isComplete}
    >
      <Text style={styles.text}>{item.text}</Text>
      <View style={styles.footer}>
        <Text style={[styles.counter, isComplete && styles.counterComplete]}>
          {isComplete ? 'تم ✓' : `${remaining} متبقية`}
        </Text>
      </View>
    </TouchableOpacity>
  );
}

export default function AdhkarCategoryScreen({ route, navigation }) {
  const { categoryId, title } = route.params;
  const items = adhkarData[categoryId] || [];
  const [progress, setProgress] = useState({});

  useEffect(() => {
    navigation.setOptions?.({ title });
    getAdhkarProgress(categoryId).then(setProgress);
  }, [categoryId]);

  const handlePress = useCallback(
    async (itemId, maxCount) => {
      const current = progress[itemId] || 0;
      const next = Math.min(current + 1, maxCount);
      const updated = { ...progress, [itemId]: next };
      setProgress(updated);
      await saveAdhkarProgress(categoryId, updated);
      Haptics.selectionAsync().catch(() => {});

      const allDone = items.every(
        (i) => (updated[i.id] || 0) >= i.count
      );
      if (allDone) {
        await markTodayActive();
      }
    },
    [progress, categoryId, items]
  );

  return (
    <View style={styles.container}>
      <Text style={styles.header}>{title}</Text>
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => (
          <DhikrCard
            item={item}
            doneCount={progress[item.id] || 0}
            onPress={() => handlePress(item.id, item.count)}
          />
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
    fontSize: 22,
    textAlign: 'right',
    marginTop: 16,
    marginBottom: 12,
  },
  list: { paddingBottom: 40 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 18,
    padding: 20,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardComplete: {
    borderColor: colors.accentSecondary,
    opacity: 0.55,
  },
  text: {
    color: colors.textPrimary,
    fontFamily: fonts.quran,
    fontSize: 19,
    lineHeight: 32,
    textAlign: 'right',
  },
  footer: {
    marginTop: 14,
    alignItems: 'flex-end',
  },
  counter: {
    color: colors.accent,
    fontFamily: fonts.medium,
    fontSize: typeScale.caption,
  },
  counterComplete: {
    color: colors.accentSecondary,
  },
});
