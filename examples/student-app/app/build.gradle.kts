plugins {
 alias(libs.plugins.androidApplication)
 alias(libs.plugins.kotlinAndroid)
 alias(libs.plugins.kotlinSerialization)
 alias(libs.plugins.composeCompiler)
}

android {
 namespace = "com.student.app"
 compileSdk = 34

 defaultConfig {
 applicationId = "com.student.app"
 minSdk = 24
 targetSdk = 34
 versionCode = 1
 versionName = "1.0"
 }

 buildFeatures {
 compose = true
 }

 compileOptions {
 sourceCompatibility = JavaVersion.VERSION_17
 targetCompatibility = JavaVersion.VERSION_17
 }

 kotlinOptions {
 jvmTarget = "17"
 }
}

dependencies {
 implementation("androidx.core:core-ktx:1.13.1")
 implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.4")
 implementation("androidx.activity:activity-compose:1.9.1")

 implementation(platform("androidx.compose:compose-bom:2024.09.00"))
 implementation("androidx.compose.ui:ui")
 implementation("androidx.compose.ui:ui-graphics")
 implementation("androidx.compose.ui:ui-tooling-preview")
 implementation("androidx.compose.material3:material3")
 implementation("androidx.compose.material:material-icons-extended")

 // ⭐ ComposeBridge Agent
 implementation(project(":composebridge-agent"))

 // ⭐ OkHttp — Agent WebSocket
 implementation(libs.okhttp)

 // ⭐ Kotlin Serialization — JSON
 implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")

 debugImplementation("androidx.compose.ui:ui-tooling")
}