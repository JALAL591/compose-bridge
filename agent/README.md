# ComposeBridge Agent

ComposeBridge Agent is a real-time on-device inspection and design-token synchronization library for **Jetpack Compose**.

## Features
- **Visual Element Picker**: Inspect and select any Composable on screen in real time.
- **Design Tokens Integration**: Live update colors, dimensions, and typography tokens.
- **Focus Mode & Token Splitting**: Dedicated token isolation to modify specific elements without unintended side effects.
- **Zero-Config Synchronization**: Connects seamlessly with the ComposeBridge IntelliJ / Android Studio plugin via WebSocket and ADB Reverse.

## Setup
Add the dependency to your Jetpack Compose Android application:

```kotlin
implementation(project(":composebridge-agent"))
```

And initialize in your debug application:

```kotlin
ComposeBridgeAgent.init(context)
```
