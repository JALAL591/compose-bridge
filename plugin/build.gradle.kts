plugins {
    id("java")
    id("org.jetbrains.kotlin.jvm") version "2.0.21"
    id("org.jetbrains.intellij") version "1.17.3"
}

group = "com.composebridge.plugin"
version = "1.0.0"

repositories {
    mavenCentral()
    google()
}

dependencies {
    implementation("com.google.code.gson:gson:2.10.1")
}

intellij {
    localPath.set("C:/Users/thinkpad/AndroidStudioLocal")
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
        projectExecutable.set("C:/Users/thinkpad/AndroidStudioLocal/jbr/bin/java.exe")
        jvmArgs("-Xbootclasspath/a:C:/Users/thinkpad/AndroidStudioLocal/lib/nio-fs.jar")
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
