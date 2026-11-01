package com.composebridge.plugin.models

data class DiffHunk(
    val id: String,
    val lineStart: Int,
    val lineEnd: Int,
    val oldText: String,
    val newText: String
)

