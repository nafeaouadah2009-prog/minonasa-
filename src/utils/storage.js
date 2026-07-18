import AsyncStorage from '@react-native-async-storage/async-storage';

// مفاتيح التخزين المحلي
const KEYS = {
  SETTINGS: '@adhkar_quran/settings',
  BOOKMARK: '@adhkar_quran/bookmark',
  STREAK: '@adhkar_quran/streak',
  ADHKAR_PROGRESS: '@adhkar_quran/adhkar_progress',
};

export const defaultSettings = {
  fontSize: 'medium', // small | medium | large
  reciter: 'ar.alafasy',
  language: 'ar',
  notificationsEnabled: true,
  popupNotifications: true,
  popupFrequencyPerDay: 8,
  morningReminderTime: { hour: 6, minute: 0 },
  eveningReminderTime: { hour: 17, minute: 30 },
  madhhab: 'shafi', // shafi | hanafi (يؤثر على حساب وقت العصر)
  hapticsEnabled: true,
};

export async function getSettings() {
  try {
    const raw = await AsyncStorage.getItem(KEYS.SETTINGS);
    return raw ? { ...defaultSettings, ...JSON.parse(raw) } : defaultSettings;
  } catch (e) {
    return defaultSettings;
  }
}

export async function saveSettings(settings) {
  await AsyncStorage.setItem(KEYS.SETTINGS, JSON.stringify(settings));
}

export async function getBookmark() {
  try {
    const raw = await AsyncStorage.getItem(KEYS.BOOKMARK);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

export async function saveBookmark(bookmark) {
  // bookmark: { surahNumber, surahName, ayahNumber, totalAyahs }
  await AsyncStorage.setItem(KEYS.BOOKMARK, JSON.stringify(bookmark));
}

export async function getStreak() {
  try {
    const raw = await AsyncStorage.getItem(KEYS.STREAK);
    return raw ? JSON.parse(raw) : { count: 0, lastDate: null };
  } catch (e) {
    return { count: 0, lastDate: null };
  }
}

// يستدعى عند إكمال أي نشاط (أذكار/قراءة) لتحديث سلسلة الأيام المتتالية
export async function markTodayActive() {
  const today = new Date().toISOString().slice(0, 10);
  const streak = await getStreak();

  if (streak.lastDate === today) return streak; // اليوم محسوب فعلاً

  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
  const newCount = streak.lastDate === yesterday ? streak.count + 1 : 1;
  const updated = { count: newCount, lastDate: today };

  await AsyncStorage.setItem(KEYS.STREAK, JSON.stringify(updated));
  return updated;
}

export async function getAdhkarProgress(categoryId) {
  try {
    const raw = await AsyncStorage.getItem(`${KEYS.ADHKAR_PROGRESS}/${categoryId}`);
    return raw ? JSON.parse(raw) : {};
  } catch (e) {
    return {};
  }
}

export async function saveAdhkarProgress(categoryId, progress) {
  await AsyncStorage.setItem(
    `${KEYS.ADHKAR_PROGRESS}/${categoryId}`,
    JSON.stringify(progress)
  );
}

export default {
  getSettings,
  saveSettings,
  getBookmark,
  saveBookmark,
  getStreak,
  markTodayActive,
  getAdhkarProgress,
  saveAdhkarProgress,
};
