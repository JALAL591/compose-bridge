package com.composebridge.plugin.actions

import com.composebridge.plugin.services.PythonRunner
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.intellij.codeInsight.intention.IntentionAction
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.openapi.vfs.VfsUtil
import com.intellij.psi.PsiFile
import java.awt.BorderLayout
import javax.swing.*

class ConvertToTokenAction : IntentionAction {

    override fun getText(): String = "Convert to ComposeBridge token"
    override fun getFamilyName(): String = "ComposeBridge"
    override fun startInWriteAction(): Boolean = false

    override fun isAvailable(project: Project, editor: Editor?, file: PsiFile?): Boolean {
        if (editor == null || file == null) return false
        val value = extractHardcodedValue(editor)
        return value != null
    }

    override fun invoke(project: Project, editor: Editor?, file: PsiFile?) {
        if (editor == null || file == null) return

        val value = extractHardcodedValue(editor) ?: return
        val lineNumber = editor.caretModel.logicalPosition.line + 1
        val fileName = file.name

        val tokenType = if (value.contains("0x") || value.startsWith("#")) "color" else "dimension"

        // Dialog for entering token name
        val tokenName = JOptionPane.showInputDialog(
            null,
            "Enter token name for '$value':",
            "Convert to ComposeBridge Token",
            JOptionPane.PLAIN_MESSAGE
        ) as? String ?: return

        if (tokenName.isBlank()) return

        // Execute add_token
        val pythonRunner = PythonRunner(project)
        val result = pythonRunner.addToken(
            file = fileName,
            line = lineNumber,
            value = value,
            tokenName = tokenName.trim(),
            tokenType = tokenType
        )

        // Parse result
        try {
            val cleanJson = extractJson(result)
            val json = Gson().fromJson(cleanJson, JsonObject::class.java)
            val success = json.get("success")?.asBoolean ?: false

            if (success) {
                Messages.showInfoMessage(
                    "Token '$tokenName' added successfully!",
                    "ComposeBridge"
                )
                refreshFileFromDisk(project, file)
            } else {
                // ⭐ Check error type
                val errorType = json.get("error_type")?.asString
                val error = json.get("error")?.asString ?: "Unknown error"

                when (errorType) {
                    "same_base_different_value", "same_value_different_name" -> {
                        handleSemanticConflict(project, file, json, tokenName.trim(), value, tokenType, lineNumber, fileName)
                    }
                    "semantic_validation" -> {
                        handleSemanticValidation(project, file, json, value, tokenType, lineNumber, fileName)
                    }
                    else -> {
                        Messages.showErrorDialog(error, "ComposeBridge Error")
                    }
                }
            }
        } catch (e: Exception) {
            Messages.showErrorDialog("Error: ${e.message}", "ComposeBridge")
        }
    }

    private fun handleSemanticConflict(
        project: Project,
        file: PsiFile,
        json: JsonObject,
        originalTokenName: String,
        value: String,
        tokenType: String,
        lineNumber: Int,
        fileName: String
    ) {
        val info = json.getAsJsonObject("info")
        val existingToken = info?.get("existing_token")?.asString ?: "?"
        val existingValue = info?.get("existing_value")?.asString ?: "?"
        val message = json.get("error")?.asString ?: ""
        val recommendedName = json.get("recommended_name")?.asString
            ?: info?.get("safe_alternative")?.asString
            ?: info?.get("suggested_name")?.asString

        val options = mutableListOf<String>()
        if (recommendedName != null && recommendedName != originalTokenName) {
            options.add("Use recommended: $recommendedName")
        }
        options.add("Use existing: $existingToken ($existingValue)")
        options.add("Force create: $originalTokenName")
        options.add("Cancel")

        val choice = JOptionPane.showOptionDialog(
            null,
            "$message\n\nWhat would you like to do?",
            "ComposeBridge — Semantic Conflict",
            JOptionPane.DEFAULT_OPTION,
            JOptionPane.WARNING_MESSAGE,
            null,
            options.toTypedArray(),
            options[0]
        )

        when {
            choice < 0 -> return  // Cancel / close
            options[choice].startsWith("Use recommended") && recommendedName != null -> {
                executeAddToken(project, file, fileName, lineNumber, value, recommendedName, tokenType, forceCreate = false)
            }
            options[choice].startsWith("Use existing") -> {
                // Replace line with existing token
                executeAddToken(
                    project, file, fileName, lineNumber, value,
                    existingToken, tokenType, forceCreate = true
                )
            }
            options[choice].startsWith("Force create") -> {
                executeAddToken(project, file, fileName, lineNumber, value, originalTokenName, tokenType, forceCreate = true)
            }
            else -> return
        }
    }

    private fun handleSemanticValidation(
        project: Project,
        file: PsiFile,
        json: JsonObject,
        value: String,
        tokenType: String,
        lineNumber: Int,
        fileName: String
    ) {
        val info = json.getAsJsonObject("info")
        val suggested = info?.get("suggested_name")?.asString
        val message = json.get("error")?.asString ?: ""

        if (suggested != null) {
            val choice = JOptionPane.showConfirmDialog(
                null,
                "$message\n\nUse suggested name: $suggested ?",
                "ComposeBridge — Token Naming",
                JOptionPane.YES_NO_OPTION,
                JOptionPane.QUESTION_MESSAGE
            )
            if (choice == JOptionPane.YES_OPTION) {
                executeAddToken(project, file, fileName, lineNumber, value, suggested, tokenType, forceCreate = false)
            }
        } else {
            Messages.showErrorDialog(message, "ComposeBridge Error")
        }
    }

    private fun executeAddToken(
        project: Project,
        file: PsiFile,
        fileName: String,
        lineNumber: Int,
        value: String,
        tokenName: String,
        tokenType: String,
        forceCreate: Boolean
    ) {
        val runner = PythonRunner(project)
        val bridgePath = runner.getBridgePath()
        if (bridgePath.isBlank() || !java.io.File(bridgePath).exists()) {
            val res = Messages.showYesNoDialog(
                project,
                "ComposeBridge path is not configured. Would you like to open Settings now?",
                "ComposeBridge Setup",
                "Open Settings",
                "Cancel",
                Messages.getWarningIcon()
            )
            if (res == Messages.YES) {
                com.intellij.openapi.options.ShowSettingsUtil.getInstance()
                    .showSettingsDialog(project, com.composebridge.plugin.settings.ComposeBridgeConfigurable::class.java)
            }
            return
        }

        Thread {
            val pythonRunner = PythonRunner(project)
            val result = pythonRunner.addToken(
                file = fileName,
                line = lineNumber,
                value = value,
                tokenName = tokenName,
                tokenType = tokenType,
                forceCreate = forceCreate
            )
            com.intellij.openapi.application.ApplicationManager.getApplication().invokeLater {
                try {
                    val cleanJson = extractJson(result)
                    val json = Gson().fromJson(cleanJson, JsonObject::class.java)
                    val success = json.get("success")?.asBoolean ?: false
                    if (success) {
                        Messages.showInfoMessage(
                            "Token '$tokenName' added successfully!",
                            "ComposeBridge"
                        )
                        refreshFileFromDisk(project, file)
                    } else {
                        val error = json.get("error")?.asString ?: "Unknown"
                        Messages.showErrorDialog(error, "ComposeBridge Error")
                    }
                } catch (e: Exception) {
                    Messages.showErrorDialog("Error: ${e.message}", "ComposeBridge")
                }
            }
        }.start()
    }

    private fun refreshFileFromDisk(project: Project, file: PsiFile) {
        val virtualFile = file.virtualFile ?: return
        val app = com.intellij.openapi.application.ApplicationManager.getApplication()
        app.invokeLater {
            com.intellij.openapi.command.WriteCommandAction.runWriteCommandAction(project) {
                try {
                    VfsUtil.markDirtyAndRefresh(false, true, true, virtualFile)
                    FileDocumentManager.getInstance().reloadFiles(virtualFile)
                } catch (e: Exception) {
                    try {
                        VfsUtil.markDirtyAndRefresh(false, true, false, virtualFile)
                    } catch (e2: Exception) {
                        // ignore
                    }
                }
            }
        }
    }

    private fun extractHardcodedValue(editor: Editor): String? {
        val document = editor.document
        val offset = editor.caretModel.offset
        val line = document.getLineNumber(offset)
        val lineStart = document.getLineStartOffset(line)
        val lineEnd = document.getLineEndOffset(line)
        val lineText = document.getText(com.intellij.openapi.util.TextRange(lineStart, lineEnd))

        // Find .dp, Color(0x...), or .sp in line
        val dpMatch = Regex("""(\d+(?:\.\d+)?)\.dp""").find(lineText)
        if (dpMatch != null) return dpMatch.value

        val spMatch = Regex("""(\d+(?:\.\d+)?)\.sp""").find(lineText)
        if (spMatch != null) return spMatch.value

        val colorMatch = Regex("""Color\((0x[0-9A-Fa-f]{8})\)""").find(lineText)
        if (colorMatch != null) return colorMatch.groupValues[1]

        return null
    }

    private fun extractJson(rawOutput: String): String {
        val start = rawOutput.indexOf('{')
        val end = rawOutput.lastIndexOf('}')
        return if (start >= 0 && end > start) rawOutput.substring(start, end + 1) else rawOutput
    }
}
