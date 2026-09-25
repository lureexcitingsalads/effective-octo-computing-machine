plugins {
    // Kotlin support is built into AGP 9.0+, so org.jetbrains.kotlin.android is neither
    // needed nor allowed here -- only Compose and serialization remain separate plugins.
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.kotlin.serialization) apply false
}
