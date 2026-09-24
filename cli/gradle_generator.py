# -*- coding: utf-8 -*-
from pathlib import Path


def generate_gradle_files(screen_json):
    output = Path(screen_json["output_dir"])
    package = screen_json["package"]
    package_path = Path(screen_json["package_path"])
    app_name = "StudentApp"

    (output / "settings.gradle.kts").write_text(f"""pluginManagement {{
    repositories {{
        google()
        mavenCentral()
        gradlePluginPortal()
    }}
}}
dependencyResolutionManagement {{
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {{
        google()
        mavenCentral()
    }}
}}
rootProject.name = "{app_name}"
include(":app")
""", encoding="utf-8")

    (output / "build.gradle.kts").write_text("""plugins {
    id("com.android.application") version "8.5.0" apply false
    id("org.jetbrains.kotlin.android") version "1.9.24" apply false
}
""", encoding="utf-8")

    (output / "gradle.properties").write_text("""android.useAndroidX=true
kotlin.code.style=official
android.nonTransitiveRClass=true
org.gradle.jvmargs=-Xmx2048m
""", encoding="utf-8")

    (output / "app").mkdir(parents=True, exist_ok=True)
    (output / "app/build.gradle.kts").write_text(f"""plugins {{
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}}

android {{
    namespace = "{package}"
    compileSdk = 34

    defaultConfig {{
        applicationId = "{package}"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }}

    buildFeatures {{
        compose = true
    }}

    composeOptions {{
        kotlinCompilerExtensionVersion = "1.5.14"
    }}

    compileOptions {{
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }}

    kotlinOptions {{
        jvmTarget = "17"
    }}
}}

dependencies {{
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.4")
    implementation("androidx.activity:activity-compose:1.9.1")

    implementation(platform("androidx.compose:compose-bom:2024.09.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")

    debugImplementation("androidx.compose.ui:ui-tooling")
}}
""", encoding="utf-8")

    manifest_dir = output / "app" / "src" / "main"
    manifest_dir.mkdir(parents=True, exist_ok=True)

    (manifest_dir / "AndroidManifest.xml").write_text(f"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <application
        android:allowBackup="true"
        android:label="{app_name}"
        android:supportsRtl="true"
        android:theme="@android:style/Theme.Material.Light.NoActionBar">
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
""", encoding="utf-8")

    (package_path / "MainActivity.kt").write_text(f"""package {package}

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import {package}.ui.pages.DashboardPage
import {package}.ui.theme.AppColors

class MainActivity : ComponentActivity() {{
    override fun onCreate(savedInstanceState: Bundle?) {{
        super.onCreate(savedInstanceState)
        setContent {{
            MaterialTheme {{
                Surface(color = AppColors.Background) {{
                    DashboardPage()
                }}
            }}
        }}
    }}
}}
""", encoding="utf-8")

    res_dir = manifest_dir / "res" / "values"
    res_dir.mkdir(parents=True, exist_ok=True)

    (res_dir / "themes.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="AppTheme" parent="android:Theme.Material.Light.NoActionBar" />
</resources>
""", encoding="utf-8")

    print("  Gradle + Manifest + MainActivity generated")
