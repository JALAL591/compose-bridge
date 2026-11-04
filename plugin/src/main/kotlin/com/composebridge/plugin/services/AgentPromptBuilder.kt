package com.composebridge.plugin.services

import com.composebridge.plugin.services.IdeDiagnosticsService.DiagnosticItem
import com.google.gson.Gson
import com.google.gson.GsonBuilder
import com.google.gson.JsonObject

/**
 * Builds AI instructions and requests for autonomous diagnostic remediation.
 */
object AgentPromptBuilder {

    private val gson: Gson = GsonBuilder().setPrettyPrinting().create()

    /**
     * Constructs a structured Markdown prompt for an AI agent (Claude, Cursor, Antigravity, etc.)
     * describing the exact issues in the target file and instructing the agent to fix them
     * using ComposeBridge MCP tools without modifying business logic.
     */
    fun buildFixPrompt(
        fileName: String,
        relativePath: String,
        issues: List<DiagnosticItem>
    ): String {
        val totalIssues = issues.size
        val errorsCount = issues.count { it.severity == "ERROR" }
        val warningsCount = issues.count { it.severity != "ERROR" }

        val breakdown = buildString {
            if (errorsCount > 0) append("$errorsCount error(s)")
            if (errorsCount > 0 && warningsCount > 0) append(" and ")
            if (warningsCount > 0) append("$warningsCount warning(s)/debt(s)")
        }

        return buildString {
            appendLine("Please fix the following $totalIssues issue(s) ($breakdown) in `$fileName` ($relativePath) using ComposeBridge MCP tools.")
            appendLine("Do not alter core business logic; focus strictly on resolving the reported diagnostics, unused variables, implicit scopes, and style debt.")
            appendLine()
            appendLine("### Diagnostic Issues:")
            for (issue in issues) {
                val sevBadge = when (issue.severity.uppercase()) {
                    "ERROR" -> "[ERROR]"
                    "WARNING" -> "[WARNING]"
                    "WEAK_WARNING" -> "[DEBT]"
                    else -> "[INFO]"
                }
                val rule = if (issue.inspectionId.isNotBlank()) " (${issue.inspectionId})" else ""
                appendLine("- Line ${issue.line}: $sevBadge ${issue.message}$rule")
            }
            appendLine()
            appendLine("### Instructions for AI Agent:")
            appendLine("1. Inspect `$relativePath` at the indicated lines.")
            appendLine("2. Apply surgical updates via ComposeBridge MCP tools (`set_text`, `replace_pattern`).")
            appendLine("3. Verify code compiles cleanly without regressions.")
        }
    }

    /**
     * Serializes an Auto-Fix Pro request payload into JSON for .composebridge/mcp_fix_request.json.
     */
    fun buildFixRequestJson(
        projectPath: String,
        fileName: String,
        relativePath: String,
        issues: List<DiagnosticItem>
    ): String {
        val root = JsonObject().apply {
            addProperty("action", "auto_fix_diagnostics")
            addProperty("timestamp", System.currentTimeMillis())
            addProperty("projectPath", projectPath)
            addProperty("fileName", fileName)
            addProperty("relativePath", relativePath)
            addProperty("totalIssues", issues.size)
            addProperty("prompt", buildFixPrompt(fileName, relativePath, issues))
            add("issues", gson.toJsonTree(issues))
        }
        return gson.toJson(root)
    }
}