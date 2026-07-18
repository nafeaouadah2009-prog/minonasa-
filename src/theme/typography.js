// نظام الخطوط: خط عرض مميز للعناوين + خط نصي مريح للقراءة الطويلة
// نستخدم Tajawal (حديث وواضح) للواجهة، وAmiri (كلاسيكي) لنصوص القرآن حصراً

export const fonts = {
  display: 'Tajawal-Bold',
  body: 'Tajawal-Regular',
  medium: 'Tajawal-Medium',
  quran: 'Amiri-Regular', // يُستخدم فقط داخل شاشة القرآن
};

export const typeScale = {
  greeting: 22,
  title: 18,
  body: 15,
  caption: 12,
  quranText: 24,
};

export default { fonts, typeScale };
