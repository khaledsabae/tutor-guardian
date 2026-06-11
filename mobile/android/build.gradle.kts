plugins {
    id("com.google.gms.google-services") version "4.4.4" apply false
    id("com.google.firebase.crashlytics") version "3.0.3" apply false
}

allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
subprojects {
    // Force every Android plugin module to compile against SDK 36. Some P1
    // plugins (file_picker 8.x, etc.) pin an older compileSdk (android-34)
    // while their transitive androidx deps now require 36 — without this the
    // release AAR-metadata check fails. afterEvaluate is registered BEFORE
    // evaluationDependsOn below so it runs after the plugin sets its own
    // compileSdk but while the project is still mid-evaluation.
    afterEvaluate {
        extensions.findByType(com.android.build.gradle.BaseExtension::class.java)
            ?.compileSdkVersion(36)
    }
    project.evaluationDependsOn(":app")
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
