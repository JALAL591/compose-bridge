package com.composebridge.plugin.settings

import com.intellij.openapi.options.Configurable
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.ui.components.JBCheckBox
import com.intellij.ui.components.JBTextField
import com.intellij.util.ui.FormBuilder
import javax.swing.JButton
import javax.swing.JComponent
import javax.swing.JPanel
import java.io.File

class ComposeBridgeConfigurable(private val project: Project) : Configurable {

    private var pythonField: JBTextField? = null
    private var bridgeField: JBTextField? = null
    private var autoStartCheckBox: JBCheckBox? = null
    private var mainPanel: JPanel? = null

    override fun getDisplayName(): String = "ComposeBridge"

    override fun createComponent(): JComponent {
        pythonField = JBTextField()
        bridgeField = JBTextField()

        val settings = ComposeBridgeSettings.getInstance(project)
        pythonField?.text = settings.state.pythonPath.ifBlank { "python" }
        bridgeField?.text = settings.state.bridgePath
        autoStartCheckBox = JBCheckBox("Auto-start Bridge Server (Zero-Config)", settings.state.autoStartBridge)

        // Auto-detect if bridge path is empty
        javax.swing.SwingUtilities.invokeLater {
            if (bridgeField?.text.isNullOrBlank()) {
                val detectedBridge = detectBridge()
                if (detectedBridge != null) {
                    bridgeField?.text = detectedBridge
                }
            }
        }

        val testButton = JButton("Test Connection")
        testButton.addActionListener { testConnection() }

        mainPanel = FormBuilder.createFormBuilder()
            .addLabeledComponent("Python executable:", pythonField!!)
            .addLabeledComponent("Bridge directory:", bridgeField!!)
            .addComponent(autoStartCheckBox!!)
            .addComponent(testButton)
            .addComponentFillVertically(JPanel(), 0)
            .panel

        return mainPanel!!
    }

    override fun isModified(): Boolean {
        val settings = ComposeBridgeSettings.getInstance(project)
        return (pythonField?.text ?: "") != settings.state.pythonPath ||
               (bridgeField?.text ?: "") != settings.state.bridgePath ||
               (autoStartCheckBox?.isSelected ?: true) != settings.state.autoStartBridge
    }

    override fun apply() {
        val settings = ComposeBridgeSettings.getInstance(project)
        settings.state.pythonPath = pythonField?.text ?: ""
        settings.state.bridgePath = bridgeField?.text ?: ""
        settings.state.autoStartBridge = autoStartCheckBox?.isSelected ?: true
    }

    override fun reset() {
        val settings = ComposeBridgeSettings.getInstance(project)
        pythonField?.text = settings.state.pythonPath.ifBlank { "python" }
        bridgeField?.text = settings.state.bridgePath.ifBlank { detectBridge() ?: "" }
        autoStartCheckBox?.isSelected = settings.state.autoStartBridge
    }

    private fun detectBridge(): String? {
        val projectRoot = project.basePath ?: return null
        val candidates = listOf(
            "$projectRoot/bridge",
            "$projectRoot/server",
            "$projectRoot/tools/bridge",
            "$projectRoot/.bridge"
        )
        for (path in candidates) {
            val dir = File(path)
            if (dir.exists() && File(dir, "mcp_server.py").exists()) {
                return dir.absolutePath
            }
        }
        return null
    }

    private fun testConnection() {
        val python = pythonField?.text?.trim() ?: ""
        val bridge = bridgeField?.text?.trim() ?: ""

        if (python.isBlank() || bridge.isBlank()) {
            Messages.showErrorDialog("Please fill both fields", "ComposeBridge")
            return
        }

        val bridgeDir = File(bridge)
        if (!bridgeDir.exists()) {
            Messages.showErrorDialog("Bridge directory does not exist", "ComposeBridge")
            return
        }

        val script = File(bridgeDir, "scanner_cli.py")
        if (!script.exists()) {
            Messages.showErrorDialog("scanner_cli.py not found", "ComposeBridge")
            return
        }

        Thread {
            try {
                val process = ProcessBuilder(python, "--version").start()
                val exit = process.waitFor()
                javax.swing.SwingUtilities.invokeLater {
                    if (exit == 0) {
                        Messages.showInfoMessage(
                            "Connection successful!\n\nPython: $python\nBridge: $bridge",
                            "ComposeBridge"
                        )
                    } else {
                        Messages.showErrorDialog("Python check failed", "ComposeBridge")
                    }
                }
            } catch (e: Exception) {
                javax.swing.SwingUtilities.invokeLater {
                    Messages.showErrorDialog("Error: ${e.message}", "ComposeBridge")
                }
            }
        }.start()
    }
}
