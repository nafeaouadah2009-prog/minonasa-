# أذكار وقرآن — تطبيق الجوال

تطبيق React Native (Expo) لعرض القرآن الكريم والأذكار، مبني بالكامل ليُطوَّر وينشر
بدون الحاجة لكمبيوتر، عبر GitHub + Expo/EAS.

## هوية التصميم: "ليل هادئ" (Calm Night)
- كحلي ليلي غامق + كريمي دافئ + نحاسي بدل الأخضر/الذهبي التقليدي
- العنصر المميز: فاصل "يتنفس" (Breathing Divider) بين الأقسام
- خطوط: Tajawal للواجهة، Amiri لنصوص القرآن

## الخطوات القادمة (من الهاتف فقط)

1. **رفع المشروع لجيت هاب**
   - أنشئ مستودع (repository) جديد فاضي على GitHub من تطبيق GitHub أو المتصفح
   - استخدم تطبيق مثل **Working Copy** (iOS) أو **Termux + git** (Android) لرفع هذا المجلد،
     أو ببساطة ارفع الملفات عبر واجهة GitHub "Add file > Upload files"

2. **تحميل الخطوط**
   - نزّل ملفات Tajawal وAmiri من Google Fonts وضعها في `assets/fonts/`
     (بدون هذه الملفات، خطوة تحميل الخطوط في App.js ستفشل)

3. **تجربة التطبيق مباشرة (بدون بناء نهائي)**
   - نزّل تطبيق **Expo Go** من App Store/Google Play
   - اربط المستودع بحساب Expo عبر **EAS** (سنجهز هذا سوياً بالخطوة القادمة)
   - أو استخدم **Expo Snack** (snack.expo.dev) كبديل مؤقت للمعاينة من المتصفح

4. **البناء والنشر (لاحقاً)**
   - EAS Build يبني ملفات APK/AAB (أندرويد) وIPA (iOS) بشكل سحابي كامل
   - النشر عبر Google Play Console وApp Store Connect (كلاهما يعملان من متصفح الهاتف)

## هيكل المشروع (كامل)
```
adhkar-quran-app/
├── App.js                        # نقطة الدخول (تحميل الخطوط + المُنقّل)
├── app.json                      # إعدادات Expo + صلاحيات الموقع
├── package.json
└── src/
    ├── theme/
    │   ├── colors.js              # ألوان "ليل هادئ"
    │   └── typography.js          # الخطوط ومقاييسها
    ├── components/
    │   ├── Header.js               # ترحيب حسب وقت اليوم
    │   ├── QuickActionCard.js      # بطاقات الاختصارات
    │   └── BreathingDivider.js     # العنصر المميز (التنفس)
    ├── data/
    │   ├── surahs.js                # فهرس السور الـ114
    │   └── adhkar.js                # نصوص الأذكار + عبارات الإشعار الخاطف
    ├── utils/
    │   ├── storage.js               # الإعدادات، الإشارة المرجعية، الستريك
    │   └── notifications.js         # التذكيرات المجدولة + الإشعار الخاطف
    ├── navigation/
    │   └── AppNavigator.js          # تبويبات سفلية + مسارات فرعية
    └── screens/
        ├── HomeScreen.js
        ├── QuranScreen.js            # فهرس السور + بحث
        ├── SurahReaderScreen.js      # عرض الآيات (API + تخزين offline)
        ├── AdhkarScreen.js           # فئات الأذكار
        ├── AdhkarCategoryScreen.js   # عداد تفاعلي لكل ذكر
        ├── TasbihScreen.js           # سبحة رقمية باهتزاز
        ├── PrayerTimesScreen.js      # مواقيت الصلاة حسب الموقع
        └── SettingsScreen.js         # كل الإعدادات
```

## مصادر البيانات المستخدمة
- **نص القرآن:** Al-Quran Cloud API (alquran.cloud) — رواية حفص، رسم عثماني مبسط، يُخزَّن محلياً بعد أول تحميل لكل سورة (عمل offline)
- **مواقيت الصلاة:** Aladhan API (aladhan.com) — طريقة أم القرى مع خيار المذهب
- **الأذكار:** نصوص من حصن المسلم مُضمَّنة مباشرة بالتطبيق (لا تحتاج إنترنت)

## قبل الانتقال لخطوة البيلدر
1. ارفع كل الملفات لمستودع GitHub
2. حمّل خطوط Tajawal وAmiri وضعها في `assets/fonts/`
3. غيّر `com.yourname.adhkarquran` في `app.json` لاسم حزمة فريد باسمك

## الخطوة القادمة
بعد رفع كل شيء على GitHub، جاهزين نربط المشروع بـ EAS Build (أو Codemagic) لعمل أول نسخة تجريبية،
ثم بناء ملفات APK/IPA ونشرها على المتجرين.
