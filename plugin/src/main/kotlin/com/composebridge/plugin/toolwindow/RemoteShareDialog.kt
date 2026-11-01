package com.composebridge.plugin.toolwindow

import com.composebridge.plugin.services.QrCodeGenerator
import com.google.gson.JsonObject
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.DialogWrapper
import com.intellij.openapi.ui.Messages
import java.awt.*
import java.awt.datatransfer.StringSelection
import java.awt.image.BufferedImage
import javax.swing.*

class RemoteShareDialog(
    project: Project?,
    private var remoteUrl: String,
    private val token: String,
    private val onStopFunnel: (() -> Unit)? = null
) : DialogWrapper(project, true) {

    private val qrLabel = JLabel().apply {
        horizontalAlignment = SwingConstants.CENTER
    }

    private val urlField = JTextField(sanitizeUrl(remoteUrl), 32)
    private val tokenField = JTextField(token, 32)

    companion object {
        fun sanitizeUrl(raw: String): String {
            var clean = raw.trim()
            // Strip port like :8711 or :443
            clean = clean.replace(Regex(":[0-9]+"), "")
            if (!clean.endsWith("/")) {
                clean += "/"
            }
            return clean
        }
    }

    init {
        title = "ComposeBridge Remote Access (Tailscale Funnel)"
        setOKButtonText("Done")
        remoteUrl = sanitizeUrl(remoteUrl)
        urlField.text = remoteUrl
        updateQrCode()
        init()
    }

    private fun updateQrCode() {
        val cleanUrl = sanitizeUrl(urlField.text)
        val cleanToken = tokenField.text.trim()

        val payload = JsonObject().apply {
            addProperty("url", cleanUrl)
            addProperty("token", cleanToken)
        }.toString()

        try {
            val img: BufferedImage = QrCodeGenerator.generateQrCode(payload, 300, 300)
            qrLabel.icon = ImageIcon(img)
            qrLabel.text = null
        } catch (e: Exception) {
            qrLabel.icon = null
            qrLabel.text = "Failed to render QR Code: ${e.message}"
        }
    }

    override fun createCenterPanel(): JComponent {
        val mainPanel = JPanel().apply {
            layout = BoxLayout(this, BoxLayout.Y_AXIS)
            border = BorderFactory.createEmptyBorder(12, 16, 12, 16)
        }

        // 1. Instructions
        val infoLabel = JLabel("<html><b>Scan this QR code from ComposeBridge Agent</b> on your Android phone to connect over Tailscale Remote Access.</html>").apply {
            alignmentX = Component.CENTER_ALIGNMENT
            border = BorderFactory.createEmptyBorder(0, 0, 10, 0)
        }
        mainPanel.add(infoLabel)

        // 2. QR Code Display
        val qrContainer = JPanel(BorderLayout()).apply {
            alignmentX = Component.CENTER_ALIGNMENT
            border = BorderFactory.createCompoundBorder(
                BorderFactory.createLineBorder(Color(0x3B, 0x82, 0xF6), 2, true),
                BorderFactory.createEmptyBorder(8, 8, 8, 8)
            )
            background = Color.WHITE
            add(qrLabel, BorderLayout.CENTER)
        }
        mainPanel.add(qrContainer)
        mainPanel.add(Box.createVerticalStrut(16))

        // 3. Remote URL Row
        val urlPanel = JPanel(BorderLayout(8, 0)).apply {
            alignmentX = Component.CENTER_ALIGNMENT
        }
        urlPanel.add(JLabel("Remote URL: "), BorderLayout.WEST)
        urlField.isEditable = true
        urlField.toolTipText = "WebSocket URL (wss://.../)"
        urlPanel.add(urlField, BorderLayout.CENTER)
        val copyUrlBtn = JButton("Copy URL").apply {
            addActionListener {
                val clean = sanitizeUrl(urlField.text)
                val sel = StringSelection(clean)
                Toolkit.getDefaultToolkit().systemClipboard.setContents(sel, sel)
                Messages.showInfoMessage("Copied Remote URL to clipboard: $clean", "ComposeBridge")
            }
        }
        urlPanel.add(copyUrlBtn, BorderLayout.EAST)
        mainPanel.add(urlPanel)
        mainPanel.add(Box.createVerticalStrut(8))

        // 4. Token Row
        val tokenPanel = JPanel(BorderLayout(8, 0)).apply {
            alignmentX = Component.CENTER_ALIGNMENT
        }
        tokenPanel.add(JLabel("Auth Token: "), BorderLayout.WEST)
        tokenField.isEditable = false
        tokenPanel.add(tokenField, BorderLayout.CENTER)
        val copyTokenBtn = JButton("Copy Token").apply {
            addActionListener {
                val sel = StringSelection(tokenField.text.trim())
                Toolkit.getDefaultToolkit().systemClipboard.setContents(sel, sel)
                Messages.showInfoMessage("Copied dynamic auth token to clipboard!", "ComposeBridge")
            }
        }
        tokenPanel.add(copyTokenBtn, BorderLayout.EAST)
        mainPanel.add(tokenPanel)
        mainPanel.add(Box.createVerticalStrut(14))

        // 5. Stop Funnel Button
        if (onStopFunnel != null) {
            val stopBtn = JButton("⏹ Stop Sharing (Tailscale Funnel Off)").apply {
                alignmentX = Component.CENTER_ALIGNMENT
                foreground = Color(0xDC, 0x26, 0x26)
                font = font.deriveFont(Font.BOLD)
                addActionListener {
                    onStopFunnel.invoke()
                    close(OK_EXIT_CODE)
                }
            }
            mainPanel.add(stopBtn)
        }

        urlField.addActionListener { updateQrCode() }

        return mainPanel
    }
}
