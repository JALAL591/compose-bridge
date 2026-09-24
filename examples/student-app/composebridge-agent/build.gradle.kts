plugins {
 alias(libs.plugins.kotlinMultiplatform)
 alias(libs.plugins.androidLibrary)
 alias(libs.plugins.composeMultiplatform)
 alias(libs.plugins.composeCompiler)
}

kotlin {
 androidTarget {
 compilations.all {
 kotlinOptions {
 jvmTarget = "17"
 }
 }
 }

 sourceSets {
 val commonMain by getting {
 dependencies {
 implementation(compose.runtime)
 implementation(compose.foundation)
 implementation(compose.ui)
 implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.8.0")
 }
 }

 val androidMain by getting {
 dependencies {
 implementation("androidx.compose.ui:ui-tooling-data:1.6.7")
 implementation("com.squareup.okhttp3:okhttp:4.12.0")
 implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")
 }
 }
 }
}

android {
 namespace = "com.composebridge.agent"
 compileSdk = 34
 defaultConfig {
 minSdk = 24
 }
 compileOptions {
 sourceCompatibility = JavaVersion.VERSION_17
 targetCompatibility = JavaVersion.VERSION_17
 }
}