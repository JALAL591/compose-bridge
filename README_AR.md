# ComposeBridge 🌉

> 📖 **إلى أين تتجه أداة ComposeBridge؟** اقرأ [وثيقة الرؤية والمعمارية RFC](docs/architecture/RFC-001-vision.md).

**محرر بصري حي على الجهاز الحقيقي لتطبيقات Jetpack Compose + خادم MCP لوكلاء الذكاء الاصطناعي. تعديل الواجهة لحظياً + تعديل جراحي في الكود المصدري.**

[![Kotlin](https://img.shields.io/badge/Kotlin-2.1.20+-purple.svg)](https://kotlinlang.org)
[![Jetpack Compose](https://img.shields.io/badge/Jetpack%20Compose-1.7.3+-4285F4.svg)](https://developer.android.com/jetpack/compose)
[![Zero Rebuild](https://img.shields.io/badge/DevEx-Zero--Rebuild%20Preview-brightgreen.svg)]()
[![Latency](https://img.shields.io/badge/Latency-%3C50ms-success.svg)]()
[![Status](https://img.shields.io/badge/Status-Production%20Ready%20(v1.1.1)-success.svg)]()
[![Scanner Speed](https://img.shields.io/badge/Scanner%20Speed-137ms%20%2F%20146%20files-brightgreen.svg)]()
[![Version](https://img.shields.io/badge/Version-1.1.1-blue.svg)]()
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://github.com/JALAL591/compose-bridge/blob/main/LICENSE)
[![M8ven Score](https://m8ven.ai/badge/mcp/jalal591-compose-bridge-rapm1x)](https://m8ven.ai/mcp/jalal591-compose-bridge-rapm1x?s=readme)

## 📰 Featured In

<p align="left">
  <a href="https://androidweekly.net/issues/issue-746" title="Android Weekly Issue #746">
    <img alt="Android Weekly" src="https://androidweekly.net/issues/issue-746/badge" height="24">
  </a>
</p>

[English](https://github.com/JALAL591/compose-bridge/blob/main/README.md) | [العربية](https://github.com/JALAL591/compose-bridge/blob/main/README_AR.md)

---

### 📥 التحميل المباشر والتثبيت السريع (v1.1.3)

| الحزمة | ملف التثبيت (.zip / .aar) | طريقة التثبيت السريع |
|---|---|---|
| **إضافة بيئة التطوير (Android Studio / IntelliJ)** | [📥 **تحميل ComposeBridgeIntelliJ-1.1.4.zip**](dist/ComposeBridgeIntelliJ-1.1.4.zip) | في Android Studio: انتقل إلى `Settings` ➔ `Plugins` ➔ `⚙️` ➔ `Install Plugin from Disk...` |
| **مكتبة أندرويد لـ Jetpack Compose (Agent)** | [📦 **تحميل composebridge-agent-release.aar**](dist/composebridge-agent-release.aar) | انسخ الملف إلى مجلد `app/libs/` أو ضعه في `debugImplementation` |
| **مكتبة أندرويد الأساسية (Runtime)** | [📦 **تحميل composebridge-runtime-release.aar**](dist/composebridge-runtime-release.aar) | ضعه في `implementation` لضمان أمان البناء |
| **سيرفر بايثون و MCP** | [📦 **تحميل composebridge-server-1.1.4.zip**](dist/composebridge-server-1.1.4.zip) | خادم المزامنة ووكلاء الذكاء الاصطناعي |
| **الحزمة الشاملة المتكاملة (All-in-One)** | [📦 **تحميل ComposeBridge-v1.1.4-AllInOne.zip**](dist/ComposeBridge-v1.1.4-AllInOne.zip) | تجمع الإضافة، العميل، مكتبة الـ Runtime، والسيرفر |

**ComposeBridge** هي حزمة أدوات للمطورين تربط تطبيق Compose (KMP/Android) بمحرر الأكواد أو وكيل الذكاء الاصطناعي الخاص بك.

> [!NOTE]
> **حالة دعم KMP / Desktop**: دعم KMP/Desktop حالياً في مرحلة **Beta تجريبية**. التركيز الأساسي لإصدار v1.1.1 ينصب على **استقرار منصة أندرويد (Android stability)**.


### 🎯 ما الجديد في الإصدار v1.0.0؟
- **وضع التركيز (Focus Mode):** الآن، تعرض النافذة السفلية **فقط** ألوان وأبعاد العنصر الذي تم لمسه. لا مزيد من البحث في القوائم الطويلة.
- **تعديل الكل أو الفصل (Global vs. Split):** قم بتغيير قيمة في المشروع بأكمله، أو أنشئ "توكن" معزول لهذا العنصر فقط.
- **طابور التعديلات المعلقة (Queue):** اجمع عدة تعديلات للواجهة محلياً ثم اضغط **Sync** مرة واحدة.
- **دعم الأبعاد (Dimensions):** عدّل الارتفاع، العرض، الحشوات، وأحجام الخطوط لحظياً — وليس الألوان فقط.
- **المراجعة والتراجع (Review & Reject):** مراجعة كاملة تشبه `git status` داخل بيئة التطوير. اعتمد التغييرات (Approve) أو تراجع عنها بالبايت (Reject All).
- **أكثر من 17 أداة MCP:** يمكن لوكلاء الذكاء الاصطناعي الآن تشغيل بناء Gradle، واكتشاف الأنماط، والتراجع عن التغييرات بشكل مستقل.

### 🎬 شاهد المشروع أثناء العمل ولقطات الشاشة

اضغط على المعاينة لمشاهدة الفيديو التجريبي على YouTube وتعديل الواجهة لحظياً:

<p align="center">
  <a href="https://youtu.be/Hywyq7cBdDM">
    <img src="https://img.youtube.com/vi/Hywyq7cBdDM/hqdefault.jpg" alt="شاهد العرض الحي — ComposeBridge يعدل جهازاً حقيقياً" width="70%" style="border-radius: 8px;" />
  </a>
</p>

#### 📸 لقطات الشاشة وتكامل بيئة التطوير مع الهاتف

| 1. لوحة تحكم الإضافة وفاحص التوكنز | 2. التعديل الجراحي ومراجعة الفروقات (Diff) | 3. المعاينة المباشرة على شاشة الهاتف |
|:---:|:---:|:---:|
| <a href="https://github.com/JALAL591/compose-bridge/blob/main/docs/screenshots/1_composebridge_main_ui.jpg"><img src="https://raw.githubusercontent.com/JALAL591/compose-bridge/main/docs/screenshots/1_composebridge_main_ui.jpg" width="100%" alt="واجهة ComposeBridge الرئيسية" /></a> | <a href="https://github.com/JALAL591/compose-bridge/blob/main/docs/screenshots/2_composebridge_patterns_diff.jpg"><img src="https://raw.githubusercontent.com/JALAL591/compose-bridge/main/docs/screenshots/2_composebridge_patterns_diff.jpg" width="100%" alt="فروقات التعديل الجراحي" /></a> | <a href="https://github.com/JALAL591/compose-bridge/blob/main/docs/screenshots/3_composebridge_live_device_sync.jpg"><img src="https://raw.githubusercontent.com/JALAL591/compose-bridge/main/docs/screenshots/3_composebridge_live_device_sync.jpg" width="100%" alt="المزامنة الحية على الهاتف" /></a> |

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

يمكنك تشغيل ComposeBridge والاتصال به بطريقتين حسب بيئة عملك:

### 🔹 الخيار الأول: استخدام إضافة Android Studio Plugin (موصى به للمطورين)

لا حاجة لفتح الـ Terminal أو تشغيل أوامر يدوياً؛ تتكفل إضافة بيئة التطوير بإدارة الخادم وتوجيه المنافذ تلقائياً بنقرة زر واحدة.

1. **افتح نافذة الأدوات (ToolWindow)**: في Android Studio، افتح نافذة **ComposeBridge** من الشريط الجانبي الأيمن.
2. **شغّل السيرفر**: اضغط على زر **▶ Start Bridge**.
   - تقوم الإضافة بتشغيل `server.py` في الخلفية وتطبيق أمر `adb reverse tcp:8711 tcp:8711` تلقائياً.
   - تتغير الحالة مباشرة إلى `🟢 Bridge Running`.
   - *(اختياري)* يمكنك تفعيل **Auto-start Bridge Server** من **Settings → ComposeBridge** لتشغيل السيرفر تلقائياً بمجرد فتح المشروع.
3. **أضف الـ Agent** إلى مشروعك وقم بتهيئته (انظر الخطوات بالأسفل).

---

### 🔹 الخيار الثاني: التشغيل المستقل / وكلاء الذكاء الاصطناعي (Standalone MCP)

هذا الخيار مخصص لمساعدي البرمجة بالذكاء الاصطناعي (Claude Desktop، Cursor، Antigravity IDE، Cline) أو في حال أردت تشغيل الخادم يدوياً عبر الطرفية:

1. **تشغيل الخادم المحلي يدوياً**:
   ```bash
   cd server
   pip install -r requirements.txt
   python server.py
   ```
2. **توجيه المنفذ للهاتف عبر ADB**:
   ```bash
   adb reverse tcp:8711 tcp:8711
   ```
*(ملاحظة: إذا كنت تستخدم وكلاء الذكاء الاصطناعي عبر بروتوكول MCP فقط، فلا تحتاج لهاتف أو لأمر adb reverse؛ راجع قسم [خادم MCP](#-خادم-mcp-لوكلاء-الذكاء-الاصطناعي) أدناه).*

---

### 📲 خطوات دمج الـ Agent في تطبيقك

#### 1. أضف المكتبات إلى مشروعك (عزل بيئة الإنتاج)
انسخ مكتبي `composebridge-runtime-release.aar` و `composebridge-agent-release.aar` إلى مجلد `libs/` في تطبيقك:
```kotlin
// app/build.gradle.kts
dependencies {
    // 1. مكتبة Runtime الأساسية: تُترجم بأمان في نسختي Debug و Release
    implementation(files("libs/composebridge-runtime-release.aar"))

    // 2. مكتبة الـ Agent وأدوات التعديل التفاعلية: تُضاف في وضع Debug فقط
    debugImplementation(files("libs/composebridge-agent-release.aar"))
}
```

#### 2. قم بتهيئته في MainActivity
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

#### 3. الاتصال والتعديل
1. ثبّت التطبيق وشغّله على جهاز Android (أو المحاكي).
2. اضغط على **الزر العائم 🔧** → وضع التصميم مفعل.
3. المس أي عنصر Composable → يفتح وضع التركيز.
4. عدّل الألوان/الأبعاد مباشرة → اضغط **Sync**.

> **ملاحظة حول المعاينة الحية:** تغيير قيمة ثابتة أو تطبيق "توكن" جديد يتطلب **إعادة بناء واحدة** لتحديث الكود المترجم. بعد ذلك، ستكون جميع التعديلات المستقبلية عبر الـ Registry فورية.

---

## 🤖 AI Agent Integration (MCP) - تكامل وكلاء الذكاء الاصطناعي

يعرض ComposeBridge أدواته الـ 27 لوكلاء الذكاء الاصطناعي عبر بروتوكول Model Context Protocol (MCP). **لا يُشترط وجود هاتف لاستخدام MCP.**

> 💡 **كفاءة استهلاك السياق (Context Window):**
> "ComposeBridge uses Lazy Loading, so 27 MCP tools consume only ~176 tokens (<1% of context window)."

### العملاء المدعومون
- ✅ **Google Antigravity IDE**
- ✅ **Cursor**
- ✅ **Claude Desktop**
- ✅ **Cline / Continue**

### خطوات الإعداد والتكامل:

#### الخطوة 1: تشغيل سيرفر MCP
تأكد من تثبيت مكتبات السيرفر من مجلد `server`:
```bash
cd server
pip install -r requirements.txt
```

#### الخطوة 2: إعداد ملف `mcp_config.json`
أضف الإعداد التالي في ملف `mcp_config.json` داخل مجلد `.gemini/config/` أو مجلد إعدادات IDE / العميل الخاص بك:
```json
{
  "mcpServers": {
    "composebridge": {
      "command": "python",
      "args": ["-u", "C:\Users\thinkpad\StudioProjects\compose-bridge\server\mcp_server.py"],
      "env": {
        "COMPOSEBRIDGE_ROOT": "C:\Users\thinkpad\StudioProjects\MyTeacher-App",
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

> ⚠️ **ملاحظة هامة جداً:** أي تعديل على `mcp_config.json` يتطلب بدء محادثة جديدة (**New Chat**) في الوكيل حتى يتم تحميل الأدوات الـ 27 تلقائياً.

#### خطوات الإعداد داخل Android Studio / Antigravity (UI Steps):
1. افتح Android Studio / IntelliJ IDEA.
2. اذهب إلى **Settings** (أو Preferences في الماك) → **Tools** → **AI** → **MCP Servers**.
3. اضغط على تبويب **Installed**.
4. اضغط على زر **"Import JSON file"** (أو **"...Add via JSON"** حسب إصدار الـ IDE).
5. الصق كود الـ JSON المرفق أعلاه.
6. اضغط **OK** أو **Apply**.
7. ⚠️ **هام جداً:** ابدأ **محادثة جديدة (New Chat)** أو أعد تشغيل الوكيل لكي يتم تحميل الأدوات الـ 27 الجديدة وتصبح مرئية.

### الأدوات المتاحة (27 أداة MCP)

| الفئة | الأدوات |
|-------|---------|
| **الاستكشاف والتحليل** | `list_tokens`, `find_token_by_color`, `get_token_impact`, `get_token_siblings`, `get_all_token_groups`, `list_orphans`, `get_naming_convention` |
| **التعديل الجراحي** | `set_token`, `set_text`, `add_token`, `rollback_last` |
| **إعادة الهيكلة والأنماط** | `detect_conditional_variants`, `replace_pattern`, `list_applied_patterns`, `rollback_pattern`, `suggest_token_split` |
| **إدارة التغييرات** | `list_modified_files`, `get_file_diff`, `approve_file_changes`, `reject_file_changes`, `approve_all_files`, `reject_all_files`, `reject_all_files_force` |
| **البناء والمزامنة** | `run_gradle_build`, `list_allowed_gradle_tasks`, `trigger_user_sync`, `get_sync_status` |

---

## ⚠️ دعم المنصات (الإصدار v1.1.1)

| الميزة | Android | Desktop | iOS |
|--------|:-------:|:-------:|:---:|
| **خادم MCP (الذكاء الاصطناعي)** | ✅ | ✅ | ✅ |
| **إضافة بيئة التطوير** | ✅ | ✅ | ✅ |
| **التعديل الحي على الهاتف** | ✅ | ❌ | ❌ |

*التعديل الحي على سطح المكتب (Desktop) و iOS مخطط لهما في الإصدار v1.1.1.*

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
موزّع تحت رخصة [Apache License 2.0](https://github.com/JALAL591/compose-bridge/blob/main/LICENSE).
