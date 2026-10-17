# ComposeBridge 🌉

**محرر بصري حي على الجهاز الحقيقي لتطبيقات Jetpack Compose + خادم MCP لوكلاء الذكاء الاصطناعي. تعديل الواجهة لحظياً + تعديل جراحي في الكود المصدري.**

[![Kotlin](https://img.shields.io/badge/Kotlin-2.1.20+-purple.svg)](https://kotlinlang.org)
[![Jetpack Compose](https://img.shields.io/badge/Jetpack%20Compose-1.7.3+-4285F4.svg)](https://developer.android.com/jetpack/compose)
[![Zero Rebuild](https://img.shields.io/badge/DevEx-Zero--Rebuild%20Preview-brightgreen.svg)]()
[![Latency](https://img.shields.io/badge/Latency-%3C50ms-success.svg)]()
[![Version](https://img.shields.io/badge/Version-1.0.0-blue.svg)]()
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![M8ven Score](https://m8ven.ai/badge/mcp/jalal591/compose-bridge)](https://m8ven.ai/mcp/jalal591/compose-bridge?s=readme)

## 📰 Featured In

<p align="left">
  <a href="https://androidweekly.net/issues/issue-746" title="Android Weekly Issue #746">
    <img alt="Android Weekly" src="https://androidweekly.net/issues/issue-746/badge" height="24">
  </a>
</p>

[English](README.md) | [العربية](README_AR.md)

---

**ComposeBridge** هي حزمة أدوات للمطورين تربط تطبيق Compose (KMP/Android) بمحرر الأكواد أو وكيل الذكاء الاصطناعي الخاص بك.

### 🎯 ما الجديد في الإصدار v1.0.0؟
- **وضع التركيز (Focus Mode):** الآن، تعرض النافذة السفلية **فقط** ألوان وأبعاد العنصر الذي تم لمسه. لا مزيد من البحث في القوائم الطويلة.
- **تعديل الكل أو الفصل (Global vs. Split):** قم بتغيير قيمة في المشروع بأكمله، أو أنشئ "توكن" معزول لهذا العنصر فقط.
- **طابور التعديلات المعلقة (Queue):** اجمع عدة تعديلات للواجهة محلياً ثم اضغط **Sync** مرة واحدة.
- **دعم الأبعاد (Dimensions):** عدّل الارتفاع، العرض، الحشوات، وأحجام الخطوط لحظياً — وليس الألوان فقط.
- **المراجعة والتراجع (Review & Reject):** مراجعة كاملة تشبه `git status` داخل بيئة التطوير. اعتمد التغييرات (Approve) أو تراجع عنها بالبايت (Reject All).
- **أكثر من 17 أداة MCP:** يمكن لوكلاء الذكاء الاصطناعي الآن تشغيل بناء Gradle، واكتشاف الأنماط، والتراجع عن التغييرات بشكل مستقل.

### 🎬 شاهد الأداة أثناء العمل

اضغط على الصورة لمشاهدة الفيديو التجريبي على YouTube:

[![شاهد العرض الحي — ComposeBridge يعدل جهازاً حقيقياً](https://img.youtube.com/vi/Hywyq7cBdDM/hqdefault.jpg)](https://youtu.be/Hywyq7cBdDM)

---

## 🚀 المميزات الرئيسية

| الميزة | الوصف |
|--------|-------|
| **⚡ معاينة حية** | عدّل الألوان والأبعاد بـ **زمن استجابة أقل من 50 مللي ثانية**. تنعكس التغييرات فوراً على الهاتف (بعد إعادة بناء أولية واحدة). |
| **🎯 وضع التركيز** | تعرض النافذة السفلية **فقط** خصائص العنصر المحدد (مثل `c1`، `c2`، `padding`). |
| **🧠 ذكاء دلالي** | يكتشف ما إذا كانت القيمة مشتركة. يوفر خيار **الفصل (Split)** (عزلها لهذه البطاقة) أو **الكل (Global)** (تغييرها في كل مكان). |
| **💾 إعادة هيكلة آمنة** | تعديل جراحي مدعوم بـ AST. يتم تتبع التغييرات في `PatternJournal`. **التراجع (Reject All)** يعيد الملفات بايت ببايت. |
| **🔌 إضافة بيئة التطوير** | 5 تبويبات: Scan، Impact، Split، Patterns، و **Changes** (واجهة اعتماد/رفض). |
| **🤖 خادم MCP مستقل** | يعمل بدون الحاجة إلى الهاتف. يمكن لوكلاء الذكاء الاصطناعي فحص المشروع، وإعادة هيكلته، وبنائه. |

---

## 📦 هيكل المستودع

```text
composebridge/
├── agent/       # مكتبة Android للـ runtime (:composebridge-agent)
├── server/      # خادم WebSocket + خادم MCP + مُعدّل الكود الجراحي
├── plugin/      # إضافة Android Studio (5 تبويبات)
└── docs/        # التوثيق المعماري وأدلة الإعداد
```

---

## 🛠️ التشغيل السريع (Android / KMP)

### 1. شغّل السيرفر المحلي
```bash
cd server
pip install -r requirements.txt
python server.py
```

### 2. أضف الـ Agent إلى مشروعك
```kotlin
// build.gradle.kts
debugImplementation("com.composebridge:agent:1.0.0")
```

### 3. قم بتهيئته في MainActivity
```kotlin
override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    ComposeBridgeAgent.start(serverUrl = "ws://127.0.0.1:8711")
    setContent {
        ComposeBridgeAgent.Root {
            App()
        }
    }
}
```

### 4. الاتصال والتعديل
```bash
adb reverse tcp:8711 tcp:8711
```
1. ثبّت التطبيق على جهاز Android الخاص بك.
2. اضغط على **الزر العائم 🔧** → وضع التصميم مفعل.
3. المس أي عنصر Composable → يفتح وضع التركيز.
4. عدّل الألوان/الأبعاد → اضغط **Sync**.

> **ملاحظة حول المعاينة الحية:** تغيير قيمة ثابتة أو تطبيق "توكن" جديد يتطلب **إعادة بناء واحدة** لتحديث الكود المترجم. بعد ذلك، ستكون جميع التعديلات المستقبلية عبر الـ Registry فورية.

---

## 🤖 خادم MCP (لوكلاء الذكاء الاصطناعي)

يعرض ComposeBridge أدواته لوكلاء الذكاء الاصطناعي عبر بروتوكول Model Context Protocol (MCP). **لا يُشترط وجود هاتف لاستخدام MCP.**

### العملاء المدعومون
- ✅ Antigravity IDE (Gemini)
- ✅ Claude Desktop
- ✅ Cursor
- ✅ Cline / Continue

### الإعداد

**1. تثبيت التبعيات**
```bash
cd server
pip install -r requirements.txt
```

**2. تهيئة عميل الذكاء الاصطناعي الخاص بك**
Antigravity IDE — قم بتعديل `~/.gemini/config/mcp_config.json`:
```json
{
  "mcpServers": {
    "composebridge": {
      "command": "python",
      "args": ["C:\\path\\to\\composebridge\\server\\mcp_server.py"]
    }
  }
}
```

### الأدوات المتاحة (أكثر من 17)

| الفئة | الأدوات |
|-------|---------|
| **الاستكشاف** | `list_tokens`, `find_token_by_color`, `get_token_impact`, `get_token_siblings`, `get_naming_convention` |
| **التعديل** | `set_token`, `add_token`, `rollback_last` |
| **إعادة الهيكلة** | `detect_conditional_variants`, `replace_pattern`, `rollback_pattern`, `global_color_edit`, `split_token_for_element` |
| **البناء** | `run_gradle_build`, `list_allowed_gradle_tasks` |
| **إدارة التغييرات**| `list_modified_files`, `approve_all_files`, `reject_all_files` |

---

## ⚠️ دعم المنصات (الإصدار v1.0.0)

| الميزة | Android | Desktop | iOS |
|--------|:-------:|:-------:|:---:|
| **خادم MCP (الذكاء الاصطناعي)** | ✅ | ✅ | ✅ |
| **إضافة بيئة التطوير** | ✅ | ✅ | ✅ |
| **التعديل الحي على الهاتف** | ✅ | ❌ | ❌ |

*التعديل الحي على سطح المكتب (Desktop) و iOS مخطط لهما في الإصدار v1.1.0.*

---

## 🔎 عبارات البحث التي يحلها هذا المشروع
- تعديل Jetpack Compose بدون إعادة تجميع
- بديل Hot Reload لـ Compose
- فاحص تخطيط تفاعلي لـ Android
- تعديل واجهة حي على جهاز Android حقيقي
- مزامنة design tokens إلى كود Kotlin
- توليد واجهة Compose من JSON

---

## 📜 الترخيص
موزّع تحت رخصة [Apache License 2.0](LICENSE).
