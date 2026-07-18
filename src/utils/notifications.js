import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import { quickPopupPhrases } from '../data/adhkar';

// إعداد سلوك الإشعارات: تظهر حتى والتطبيق مفتوح (نحتاج هذا خصيصاً للإشعار الخاطف)
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

export async function requestNotificationPermissions() {
  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;

  if (existingStatus !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'التذكيرات',
      importance: Notifications.AndroidImportance.DEFAULT,
    });
  }

  return finalStatus === 'granted';
}

// جدولة تذكير يومي متكرر بوقت ثابت (أذكار الصباح/المساء)
export async function scheduleDailyReminder({ id, title, body, hour, minute }) {
  await Notifications.cancelScheduledNotificationAsync(id).catch(() => {});
  await Notifications.scheduleNotificationAsync({
    identifier: id,
    content: { title, body, sound: false },
    trigger: { hour, minute, repeats: true },
  });
}

export async function cancelReminder(id) {
  await Notifications.cancelScheduledNotificationAsync(id).catch(() => {});
}

// "الإشعار الخاطف": يظهر ثم يختفي تلقائياً — منفذ كإشعار عادي بدل Overlay حقيقي
// (Overlay فوق تطبيقات أخرى غير مسموح به على iOS، وهذا البديل يعطي نفس الأثر تقريباً)
export async function scheduleRandomPopups(timesPerDay = 8) {
  // نلغي أي جدولة سابقة لتفادي التكرار
  const scheduled = await Notifications.getAllScheduledNotificationsAsync();
  await Promise.all(
    scheduled
      .filter((n) => n.identifier.startsWith('popup-'))
      .map((n) => Notifications.cancelScheduledNotificationAsync(n.identifier))
  );

  const wakeHour = 6;
  const sleepHour = 23;
  const windowMinutes = (sleepHour - wakeHour) * 60;
  const gap = Math.floor(windowMinutes / timesPerDay);

  for (let i = 0; i < timesPerDay; i += 1) {
    const minutesFromWake = gap * i + Math.floor(Math.random() * (gap / 2));
    const hour = wakeHour + Math.floor(minutesFromWake / 60);
    const minute = minutesFromWake % 60;
    const phrase = quickPopupPhrases[i % quickPopupPhrases.length];

    await Notifications.scheduleNotificationAsync({
      identifier: `popup-${i}`,
      content: { title: phrase, sound: false },
      trigger: { hour, minute, repeats: true },
    });
  }
}

export default {
  requestNotificationPermissions,
  scheduleDailyReminder,
  cancelReminder,
  scheduleRandomPopups,
};
