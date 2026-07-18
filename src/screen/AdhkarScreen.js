import React from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import colors from '../theme/colors';
import { fonts, typeScale } from '../theme/typography';
import { adhkarCategories, adhkarData } from '../data/adhkar';

export default function AdhkarScreen({ navigation }) {
  return (
    <View style={styles.container}>
      <Text style={styles.header}>الأذكار</Text>
      <FlatList
        data={adhkarCategories}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.row}
            activeOpacity={0.7}
            onPress={() =>
              navigation.navigate('AdhkarCategory', {
                categoryId: item.id,
                title: item.title,
              })
            }
          >
            <Ionicons name="chevron-back" size={18} color={colors.textMuted} />
            <View style={styles.rowText}>
              <Text style={styles.rowTitle}>{item.title}</Text>
              <Text style={styles.rowCount}>
                {adhkarData[item.id]?.length || 0} أذكار
              </Text>
            </View>
            <View style={styles.iconWrap}>
              <Ionicons name={item.icon} size={22} color={colors.accent} />
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
  list: { paddingBottom: 40 },
  row: {
    flexDirection: 'row-reverse',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 16,
    paddingVertical: 16,
    paddingHorizontal: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  iconWrap: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: colors.accentSoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 12,
  },
  rowText: { flex: 1, marginRight: 8 },
  rowTitle: {
    color: colors.textPrimary,
    fontFamily: fonts.medium,
    fontSize: typeScale.title,
    textAlign: 'right',
  },
  rowCount: {
    color: colors.textSecondary,
    fontFamily: fonts.body,
    fontSize: typeScale.caption,
    textAlign: 'right',
    marginTop: 2,
  },
});
