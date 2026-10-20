plugins {
    id("java")
    id("org.jetbrains.kotlin.jvm") version "2.0.21"
    id("org.jetbrains.intellij") version "1.17.3"
}

group = "com.composebridge.plugin"
version = "1.1.0"

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
    ?: "C:/Users/thinkpad/AndroidStudioLocal"

intellij {
    localPath.set(studioHome)
    plugins.set(listOf("android", "Kotlin", "com.intellij.java"))
}

tasks {
    patchPluginXml {
        sinceBuild.set("241")
        untilBuild.set(provider { null })
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
