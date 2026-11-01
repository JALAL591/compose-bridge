# ⚠️ Known Limitations & Operational Boundaries

ComposeBridge is designed as a developer productivity bridge between Android Studio/IntelliJ, AI coding agents (via MCP), and running Jetpack Compose applications. 

To maintain transparency and help you decide where and how to deploy ComposeBridge safely, this document outlines known constraints, edge cases, and architectural boundaries.

---

### 1. Remote Connection (Tailscale / WAN)
- **Status:** **Experimental**
- **Details:** Remote debugging allows tuning over cellular networks or separate Wi-Fi routers using Tailscale Funnel (`tailscale funnel 8711` / `tailscale serve https / http://127.0.0.1:8711`) or secure WebSocket tunnels (`wss://`). Note that Tailscale Funnel requires configuring `nodeAttrs` with `"funnel"` capability in Tailscale Admin ACLs. While the IDE plugin generates quick-connect QR codes and links, network transitions (switching from Wi-Fi to LTE, corporate firewalls, aggressive carrier NATs, or phone battery saving/sleep modes) can cause socket dropouts.
- **Recommendation:** For zero-latency tuning (<50ms) and rock-solid stability during active production development, **a physical USB connection (`adb reverse tcp:8711 tcp:8711`)** remains the gold standard.

### 2. Live Preview Recomposition Requirements
- **Details:** Live on-device updates rely on Compose runtime state delegation (`BridgeThemeRegistry`, `BridgeDimensionRegistry`, `BridgeTextRegistry`).
- **Network Dependency:** If the device WebSocket disconnects while edits are applied from the IDE, code changes are still written safely to disk on the host machine, but the mobile screen will not re-render until reconnection occurs.
- **Cold Rebuilds:** If an edit converts a hardcoded value that requires creating new top-level declarations or modifying constructor signatures, a standard Gradle build (`assembleDebug`) is required before the app can display the change.

### 3. AI Agent Integration & Autonomous MCP Writes
- **Details:** ComposeBridge exposes Model Context Protocol (MCP) endpoints to AI agents (Claude, Cursor, Antigravity). While each tool incorporates AST syntax verification (via Tree-sitter) before saving, AI agents may still propose unexpected layout logic or invalid design tokens.
- **Recommendation:** Always review modifications in the IDE **"Changes"** tab before clicking **Approve**. Never execute bulk approves (`approve_all_files`) blindly on unreviewed AI outputs.

### 4. Rollback & Cascade Rejections (`Reject`)
- **Reliability:** 99% reliable in tracked Git repositories.
- **Edge Case (External Concurrent Edits):** If you manually modify a file inside your code editor while a ComposeBridge pending edit is active on the exact same line, AST conflict detection will flag the file (`EXTERNAL_MODIFICATION_DETECTED`). The IDE will present a warning dialog prompting you to choose between keeping the IDE buffer or reverting to the baseline backup.
- **Git Tracking:** ComposeBridge prioritizes `git checkout -- <file>` for rollback when the repository is clean. Untracked projects rely on `.bridge.bak` snapshots.

### 5. High-Frequency Slider Inputs & Rate Limiting
- **Details:** Dragging continuous color pickers or dimension sliders generates dozens of WebSocket frames per second.
- **Throttling:** The Python server applies token bucket rate limiting (100 msgs/10s burst window) to prevent server thread exhaustion. On poor Wi-Fi connections, rapid slider dragging may feel buffered. Using USB tethering or `adb reverse tcp:8711 tcp:8711` eliminates transport latency.

### 6. Cache Management (`Clean Cache`)
- **Safety:** The `clean_cache` tool clears AST parsing indexes, token resolution caches, and stale `.composebridge-state/scan_cache.json` artifacts.
- **Caution:** Do not trigger cache cleaning while an active multi-file batch update or an unconfirmed token split is in flight.

### 7. Active Development Lifecycle
- **Status:** ComposeBridge is under active development.
- **Edge Cases:** Deeply nested custom Compose modifiers, reflection-heavy design system wrappers, or non-standard multi-module setups may occasionally require manual token registration. Please report any anomalies via GitHub Issues.

### 8. Kotlin Multiplatform (KMP) `.aar` Limitation
- **Status:** **Architectural Boundary**
- **Details:** The provided precompiled `.aar` libraries (`composebridge-runtime-release.aar` and `composebridge-agent-release.aar`) are compiled for Android (AAR format) only.
- **KMP Desktop/iOS Targets:** If your project targets Kotlin Multiplatform (e.g. Android + Desktop/iOS) and you use ComposeBridge registries (`BridgeThemeRegistry`, `BridgeDimensionRegistry`, `BridgeTextRegistry`) inside `commonMain`, the desktop/JVM compiler cannot resolve Android `.aar` archives.
- **Resolution:** You must link the `composebridge-runtime` source module directly in your multiplatform project instead of the `.aar` file (using `api(project(":composebridge-runtime"))` in the agent and `implementation(project(":composebridge-agent"))` in your app's `commonMain`).

---

## 🇸🇦 القيود والتحذيرات التشغيلية (ملخص بالعربية)

1. **الاتصال عن بُعد (Tailscale Funnel):** ميزة تجريبية. يتطلب تفعيل `nodeAttrs` مع خاصية `"funnel"` في سياسات Tailscale (ACLs) للسماح بتشغيل الـ Funnel. تدعم مسح الرمز (QR Code) أو رابط `wss://` عبر الإنترنت. قد ينقطع الاتصال عند تبديل الشبكة (بين Wi-Fi وبيانات الهاتف) أو بسبب جدران الحماية أو دخول الهاتف في وضع توفير الطاقة (Sleep Mode). نوصي باستخدام كابل USB (`adb reverse tcp:8711 tcp:8711`) للحصول على أعلى استقرار وسرعة (<50ms).
2. **المعاينة الحية:** تتطلب اتصال الهاتف بالسيرفر لحظياً. إذا انقطع الاتصال، تظل التعديلات محفوظة بأمان على القرص ولكن لن تراها على الشاشة حتى يعود الاتصال.
3. **تكامل وكلاء الذكاء الاصطناعي (MCP):** الأدوات آمنة وتفحص قواعد الكود (AST)، ولكن الوكلاء قد يخطئون أحياناً. راجع دائماً تبويب `Changes` قبل الضغط على Approve.
4. **التراجع (Rollback):** يعمل بدقة 99%. إذا قمت بالتعديل اليدوي على نفس السطر في الـ IDE أثناء وجود تعديل معلق، سيعرض النظام تحذيراً لمنع فقدان كودك.
5. **معدل الطلبات (Rate Limiting):** تحريك السلايدرات بسرعة كبيرة على شبكة ضعيفة قد يسبب بطء استجابة طفيفاً؛ كابل الـ USB هو الخيار الأسرع دوماً.
6. **مرحلة التطوير:** الأداة قوية ومختبرة في مشاريع حقيقية، لكنها في تطوير مستمر ونرحب بأي بلاغ عن حالات طرفية (Edge Cases).
7. **مشاريع Kotlin Multiplatform (KMP) وملفات `.aar`:** حزم `.aar` مجمعة لنظام Android فقط. إذا كان مشروعك يستهدف الكمبيوتر (Desktop) أو أنظمة أخرى متعددة المنصات ويستخدم السجلات في `commonMain`، يجب تضمين الموديول المصدري `composebridge-runtime` بدلاً من ملفات `.aar` لتفادي أخطاء عدم التعرف على المراجع (Unresolved Reference).

