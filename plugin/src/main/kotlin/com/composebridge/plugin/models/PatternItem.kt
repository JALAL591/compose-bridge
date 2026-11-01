package com.composebridge.plugin.models

data class PatternItem(
    val patternId: String,
    val description: String = "",
    val occurrences: Int = 0,
    val baseToken: String = "",
    val suggestedToken: String = ""
)

