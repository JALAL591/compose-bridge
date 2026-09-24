pluginManagement {
 repositories {
 google()
 mavenCentral()
 gradlePluginPortal()
 }
}
dependencyResolutionManagement {
 repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
 repositories {
 google()
 mavenCentral()
 }
}
rootProject.name = "StudentApp"
include(":app")
include(":composebridge-agent")