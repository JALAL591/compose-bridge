plugins {
    id("java")
    id("org.jetbrains.kotlin.jvm") version "2.0.21"
    id("org.jetbrains.intellij") version "1.17.3"
}

group = "com.composebridge.plugin"
version = "1.1.5"

repositories {
    mavenCentral()
    google()
}

dependencies {
    implementation("com.google.code.gson:gson:2.10.1")
}

// Resolved dynamically from ANDROID_STUDIO_HOME env var or androidStudioLocalPath in gradle.properties
val studioHome: String = System.getenv("ANDROID_STUDIO_HOME")
    ?: (project.findProperty("androidStudioLocalPath") as? String)
    ?: (System.getProperty("user.home") + "/AndroidStudioLocal")

intellij {
    localPath.set(studioHome)
    plugins.set(listOf("android", "Kotlin", "com.intellij.java"))
}

tasks {
    patchPluginXml {
        sinceBuild.set("241")
        untilBuild.set(provider { null })
                changeNotes.set("""
<h3>v1.1.3 - AI Agent Integration (MCP) & Extreme Performance</h3>
<ul>
  <li><b>AI Agent Ready (MCP):</b> Model Context Protocol server exposing 27 deep-inspection and surgical AST refactoring tools for Antigravity, Cursor, and Claude Desktop.</li>
  <li><b>60x Faster Performance:</b> Ultra-fast In-Memory Project Cache reducing element analysis latency from 8.9s to ~0.15s (zero scandir calls).</li>
  <li><b>Full Toolbar & Sync:</b> Restored 4-icon visual toolbar and instant sync button integration.</li>
  <li><b>Human-in-the-Loop Diff:</b> Side-by-side review of AI & on-device changes inside Android Studio before applying.</li>
</ul>
<h3>v1.1.2 - Complete Refactoring & Critical Fixes</h3>
<ul>
  <li><b>Architectural Refactoring:</b> Split monolithic files into 25+ specialized modules (source_analyzer: 2116→72 lines).</li>
  <li><b>Text Editing Fixed:</b> Resolved relative imports and AppStrings resolution issues.</li>
  <li><b>Multi-Registry Dimensions:</b> Fixed padding edits on complex lines.</li>
  <li><b>Release Builds:</b> Added <code>composebridge-runtime</code> for flawless <code>assembleRelease</code>.</li>
</ul>
        """.trimIndent())
    }
    
    buildSearchableOptions {
        enabled = false
    }

    runIde {
        projectExecutable.set("$studioHome/jbr/bin/java.exe")
        jvmArgs("-Xbootclasspath/a:$studioHome/lib/nio-fs.jar")
        coroutinesJavaAgentPath.set(file("dummy-agent.jar").toPath())
    }
    
    withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile> {
        kotlinOptions {
            jvmTarget = "17"
            freeCompilerArgs = listOf(
                "-Xskip-metadata-version-check",
                "-Xskip-prerelease-check"
            )
        }
    }
}

java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(17))
    }
}
