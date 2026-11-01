package com.composebridge.plugin.models

data class ModifiedFile(
    val file: String,
    val changeCount: Int,
    val firstLine: Int = 1,
    val patternIds: List<String> = emptyList()
)

