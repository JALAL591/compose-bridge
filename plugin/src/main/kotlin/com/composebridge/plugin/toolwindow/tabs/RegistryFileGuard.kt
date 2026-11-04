package com.composebridge.plugin.toolwindow.tabs

import java.io.File

/**
 * RegistryFileGuard: Identifies design system and token registry files.
 * These files represent dependencies for UI components and cannot be rejected
 * or approved independently; they are managed atomically with UI files.
 */
object RegistryFileGuard {
    private val REGISTRY_FILENAMES = setOf(
        "designsystem.kt",
        "appcolors.kt",
        "theme.kt",
        "appdimens.kt",
        "appstrings.kt",
        "themetokens.kt",
        "colors.kt",
        "dimens.kt",
        "strings.kt"
    )

    /**
     * Returns true if the file is a design system or token registry file.
     */
    fun isRegistryFile(filePath: String): Boolean {
        if (filePath.isBlank()) return false
        val name = File(filePath).name.lowercase()
        return name in REGISTRY_FILENAMES
    }
}

