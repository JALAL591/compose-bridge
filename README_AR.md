# ComposeBridge 🌉

**محرر بصري حي على الجهاز الحقيقي لتطبيقات Jetpack Compose.**
تعديل الواجهة لحظياً + مُولّد شاشات من JSON + تعديل جراحي في الكود المصدري.

[![Kotlin](https://img.shields.io/badge/Kotlin-2.1.20+-purple.svg)](https://kotlinlang.org)
[![Jetpack Compose](https://img.shields.io/badge/Jetpack%20Compose-1.7.3+-4285F4.svg)](https://developer.android.com/jetpack/compose)
[![Zero Rebuild](https://img.shields.io/badge/DevEx-Zero--Rebuild%20Preview-brightgreen.svg)]()
[![Latency](https://img.shields.io/badge/Latency-%3C50ms-success.svg)]()
[![Engine](https://img.shields.io/badge/Engine-AST--Guided%20Byte--Splice-orange.svg)]()
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

[English](README.md) | [العربية](README_AR.md)

---

**ComposeBridge** هي حزمة أدوات للمطورين تربط تطبيق Android يعمل على جهاز حقيقي بمحرر الأكواد عبر WebSocket محلي. تتيح لك:

- 🎯 **لمس أي عنصر Composable** على الهاتف لفحصه فوراً
- 🎨 **تعديل الألوان والأبعاد والحواشي لحظياً** بمعدل 60 إطاراً في الثانية — بدون إعادة بناء Gradle
- 💾 **حفظ التعديلات في كود Kotlin** (`AppDimens.kt`، `AppColors.kt`) عبر استبدال بايتات جراحي يحافظ على تنسيق الملف
- 🧩 **توليد شاشات Compose كاملة** من توصيف JSON
- 🔍 **التنقل في شجرة وقت التشغيل** — المس العنصر الأب، ثم انزل لأبنائه

> **المعاينة الحيّة فعلاً بدون إعادة بناء.** أما تثبيت التعديل في حزمة APK النهائية فيحتاج إعادة بناء واحدة، ليصبح بعدها المصدر هو الحقيقة.

### 🎬 شاهد الأداة أثناء العمل

اضغط على الصورة لمشاهدة الفيديو التجريبي على YouTube:

[![شاهد العرض الحي — ComposeBridge يعدل جهازاً حقيقياً](https://img.youtube.com/vi/Hywyq7cBdDM/maxresdefault.jpg)](https://youtu.be/Hywyq7cBdDM)

---

## 🚀 المميزات الرئيسية

| الميزة | الوصف |
|--------|-------|
| **⚡ معاينة بدون إعادة بناء** | عدّل الألوان والحواشي وزوايا الاستدارة وأحجام الخطوط بـ **زمن استجابة أقل من 50 مللي ثانية** أثناء عمل التطبيق. |
| **🎯 فحص بصري على الجهاز** | المس أي عنصر Composable لترى ملف المصدر ورقم السطر والـ tokens المستخدمة. |
| **💾 تعديل جراحي مدعوم بـ AST** | يحدد النطاق الحرفي بدقة عبر Tree-sitter، ثم يستبدل البايتات مباشرة مع الحفاظ على **سطر واحد فقط في `git diff`**. |
| **🧩 مُولّد واجهات ديناميكي** | أعطه توصيف JSON (`dashboard.json`) — ستحصل على شاشة Compose كاملة مع الثيم والمكونات والـ tokens. |
| **🌳 التنقل في شجرة وقت التشغيل** | تنقّل من الأب إلى الأبناء داخل شجرة الـ composition — بدون XML أو reflection. |
| **🔌 خادم WebSocket محلي** | جسر Python خفيف بين Agent الهاتف ونظام الملفات. |

---

## 📦 هيكل المستودع

```text
composebridge/
├── cli/         # مُولّد شاشات Compose من JSON
├── agent/       # مكتبة Android للـ runtime (:composebridge-agent)
├── server/      # خادم WebSocket + مُعدّل الكود المصدري الجراحي
├── examples/    # تطبيق مرجعي كامل (StudentApp)
└── docs/        # التوثيق المعماري وأدلة الإعداد
```

**ثلاثة مكونات، سير عمل واحد:**
1. **CLI** — يولّد مشروعاً كاملاً من JSON
2. **Agent** — يلتقط اللمسات ويبث التحديثات الحيّة على الجهاز
3. **Server** — ينسّق الرسائل ويكتب التغييرات في ملفات `.kt`

---

## ✅ التوافق

| المكوّن | الإصدار |
|---------|---------|
| Kotlin | 2.1.20+ |
| Jetpack Compose | 1.7.3+ |
| Compose Multiplatform | 1.7.3+ |
| Gradle | 8.5+ |
| Android Gradle Plugin | 8.5+ |
| Min SDK | 24 |
| Python | 3.10+ |
| الجهاز | Android (حقيقي أو محاكي) |

---

## 🛠️ التشغيل السريع

### 1. شغّل السيرفر المحلي

```bash
cd server
pip install -r requirements.txt
python server.py
```

### 2. ولّد مشروع Compose

```bash
cd cli
python generate.py screens/dashboard.json
```

سيُنتج الـ CLI مشروعاً كاملاً داخل `output/` يحتوي على:

- ✅ ملفات الثيم (`AppColors.kt`, `AppDimens.kt`, `AppTypography.kt`, `AppStrings.kt`)
- ✅ مكونات الواجهة (`HeroCard`, `StatCard`, `DashboardHeader`, ...)
- ✅ `DashboardPage.kt` كاملة
- ✅ وحدة `composebridge-agent`
- ✅ خادم `bridge/` Python مربوطاً بمسار المشروع الجديد
- ✅ `MainActivity.kt` مع wire-up جاهز
- ✅ `AndroidManifest.xml` مع صلاحية `INTERNET`

### 3. افتح المشروع في Android Studio

افتح المشروع المُولَّد، ثبّته على جهاز حقيقي، ثم:

```bash
adb reverse tcp:8711 tcp:8711
```

اضغط على **الزر العائم 🔧** → يفتح وضع التصميم.
المس أي عنصر → تفتح اللوحة → اسحب/اضغط للتعديل الحي.

---

## 🤔 لماذا لا ننتظر Compose Hot Reload الرسمي؟

| | Compose Hot Reload (JetBrains) | **ComposeBridge** |
|---|---|---|
| التوفّر | معاينة / تجريبي | ✅ يعمل اليوم |
| الجهاز | المحاكي أساساً | ✅ جهاز حقيقي |
| الحفظ | معاينة فقط | ✅ كتابة في المصدر |
| التفاعل | نصي | ✅ بصري — لمس العناصر |
| أمان الكود | إعادة تحميل كاملة | ✅ سطر واحد في `git diff` |

---

## ⚡ الأداء

| المقياس | القيمة |
|---------|--------|
| زمن الاستجابة للمعاينة الحيّة | **أقل من 50 مللي ثانية** (WebSocket محلي) |
| نطاق إعادة التركيب | **موضعي** — فقط الـ Composable المستهدف يُعاد |
| تعديل AST | **غير متزامن** — لا يحجب UI thread |
| الفرق في الكود | **سطر واحد** — تعديل بايت-إزاحة عبر Tree-sitter |

تعديل وقت التشغيل والحفظ على القرص منفصلان تماماً.

---

## 🧠 تحت الغطاء

- **ربط ثنائي الاتجاه بين وقت التشغيل والمصدر** — كل تغيير بصري يمكن تتبعه إلى النطاق الحرفي الدقيق في Kotlin.
- **فحص مدعوم بـ AST، وتعديل بـ byte-splice** — Tree-sitter يحدد الموقع، ثم Regex + استبدال البايتات. لا يضيع أي تنسيق في الملف.
- **تجميع حتمي للتخطيطات** — الـ CLI يُنتج كود Compose منظّم وموحّد — بدون هلوسة الذكاء الاصطناعي.
- **خادم WebSocket منخفض التأخير** — رحلة ذهاب وإياب أقل من 50 مللي ثانية بين الجهاز ونظام الملفات.

---

## 🔒 الأمان

- **نسخ Debug فقط**: وحدة ComposeBridge Agent تُضمَّن عبر `debugImplementation`، مما يضمن صفر عبء وإزالة كاملة من نسخ الإنتاج.
- **مصادقة التوكن**: اتصالات WebSocket تتطلب تحققاً آمناً من توكن عند الاتصال لمنع الاتصالات المحلية غير المصرح بها.
- **التراجع التلقائي عبر Journal**: يحدث تراجع تلقائي في حال فشل التحقق من سلامة الـ AST بعد التعديل.

---

## ⚠️ القيود

- **التحقق من AST**: التعديلات الجراحية محصورة بقيم بسيطة (`integer_literal`, `float_literal`, `string_literal`, `simple_identifier`, `long_literal`) لمنع كسر صحة الملف.
- **المراسلات (Correspondence)**: ~70% على تطبيقات الإنتاج (inline composables قد تنحرف). Compose Compiler plugin على Roadmap.
- **UTF-16/UTF-8**: حالات حافة مع ملفات مكتظة بالـ emoji قيد المعالجة. الدقة الكاملة على Roadmap.
- **الكود المُولَّد**: ملفات KSP/Kapt قد تحتاج استثناءً يدوياً اليوم. الاكتشاف التلقائي على Roadmap.

---

## 🤖 قادم قريباً

- **اقتراحات مدعومة بالذكاء الاصطناعي** (تكامل Qwen) — اكتب التغيير بلغة طبيعية؛ الأداة تجد الـ token الصحيح وتطبّقه.
- **تعديل باللغة الطبيعية** — "اجعل هذه البطاقة أطول." "استخدم الذهبي هنا."
- **MCP Server** — تقديم ComposeBridge كأداة لـ Claude Desktop و Cursor وغيرهم من وكلاء AI.
- **قوالب مكونات إضافية** — تجارة إلكترونية، نماذج، شاشات ملف شخصي.
- **تعديل كامل للـ Typography tokens**.

---

## 🔎 عبارات البحث التي يحلها هذا المشروع

إذا بحثت يوماً عن أي من هذه، فهذا المشروع لك:

- تعديل Jetpack Compose بدون إعادة تجميع
- بديل Hot Reload لـ Compose
- فاحص تخطيط تفاعلي لـ Android
- تعديل واجهة حي على جهاز Android حقيقي
- مزامنة design tokens إلى كود Kotlin
- توليد واجهة Compose من JSON

---

## 📜 الترخيص

موزّع تحت رخصة [Apache License 2.0](LICENSE).
