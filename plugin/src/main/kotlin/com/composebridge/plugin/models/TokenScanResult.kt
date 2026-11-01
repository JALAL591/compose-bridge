package com.composebridge.plugin.models

data class TokenScanResult(
    val tokenName: String,
    val file: String,
    val line: Int,
    val isOrphan: Boolean = false,
    val value: String = "",
    val type: String = "Token"
)

