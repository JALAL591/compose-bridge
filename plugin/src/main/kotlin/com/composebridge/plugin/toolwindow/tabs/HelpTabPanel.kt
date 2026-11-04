package com.composebridge.plugin.toolwindow.tabs

import com.composebridge.plugin.ui.components.BridgeColors
import com.intellij.ide.BrowserUtil
import com.intellij.openapi.project.Project
import com.intellij.ui.components.JBScrollPane
import com.intellij.util.ui.UIUtil
import java.awt.BorderLayout
import java.awt.Color
import javax.swing.*
import javax.swing.event.HyperlinkEvent

/**
 * Help and Documentation Tab Panel.
 * Provides a categorized, interactive user guide and quick reference for ComposeBridge.
 */
class HelpTabPanel(private val project: Project) : JPanel(BorderLayout()) {

    private val editorPane = JEditorPane().apply {
        contentType = "text/html"
        isEditable = false
        isOpaque = true
        addHyperlinkListener { e ->
            if (e.eventType == HyperlinkEvent.EventType.ACTIVATED) {
                val url = e.url?.toExternalForm() ?: e.description
                if (!url.isNullOrBlank()) {
                    BrowserUtil.browse(url)
                }
            }
        }
    }

    init {
        background = BridgeColors.bgMain
        refreshContent()

        val scrollPane = JBScrollPane(editorPane).apply {
            border = BorderFactory.createEmptyBorder()
            verticalScrollBar.unitIncrement = 16
        }

        add(scrollPane, BorderLayout.CENTER)
    }

    fun refreshContent() {
        val isDark = UIUtil.isUnderDarcula()
        val bgHex = if (isDark) "#1E1F22" else "#F8FAFC"
        val textHex = if (isDark) "#DFE1E5" else "#1E293B"
        val cardBgHex = if (isDark) "#26282D" else "#FFFFFF"
        val borderHex = if (isDark) "#393B40" else "#E2E8F0"
        val headerText = if (isDark) "#60A5FA" else "#2563EB"
        val summaryHex = if (isDark) "#93C5FD" else "#1D4ED8"
        val codeBgHex = if (isDark) "#2E3036" else "#EDF2F7"
        val codeTextHex = if (isDark) "#F43F5E" else "#BE123C"
        val tableHeadHex = if (isDark) "#2D3035" else "#E2E8F0"

        editorPane.background = if (isDark) Color(0x1E, 0x1F, 0x22) else Color(0xF8, 0xFA, 0xFC)

        editorPane.text = """
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                        font-size: 13px;
                        line-height: 1.6;
                        color: $textHex;
                        background-color: $bgHex;
                        margin: 16px;
                    }
                    h2 {
                        color: $headerText;
                        font-size: 18px;
                        margin-top: 4px;
                        margin-bottom: 12px;
                        padding-bottom: 6px;
                        border-bottom: 1px solid $borderHex;
                    }
                    h3 {
                        color: $headerText;
                        font-size: 15px;
                        margin-top: 10px;
                        margin-bottom: 6px;
                    }
                    details {
                        background-color: $cardBgHex;
                        border: 1px solid $borderHex;
                        border-radius: 6px;
                        padding: 10px 14px;
                        margin-bottom: 12px;
                    }
                    summary {
                        font-size: 14px;
                        font-weight: bold;
                        color: $summaryHex;
                        cursor: pointer;
                        padding: 4px 0;
                    }
                    table {
                        width: 100%;
                        border-collapse: collapse;
                        margin-top: 8px;
                        margin-bottom: 8px;
                    }
                    th {
                        background-color: $tableHeadHex;
                        color: $textHex;
                        text-align: left;
                        padding: 6px 10px;
                        border: 1px solid $borderHex;
                        font-size: 12px;
                    }
                    td {
                        padding: 6px 10px;
                        border: 1px solid $borderHex;
                        color: $textHex;
                        font-size: 12px;
                    }
                    code {
                        background-color: $codeBgHex;
                        color: $codeTextHex;
                        padding: 2px 5px;
                        font-family: 'JetBrains Mono', Consolas, monospace;
                        font-size: 11px;
                    }
                    pre {
                        background-color: $codeBgHex;
                        padding: 10px;
                        border: 1px solid $borderHex;
                        font-family: 'JetBrains Mono', Consolas, monospace;
                        font-size: 11px;
                        margin: 6px 0;
                    }
                    a {
                        color: #38BDF8;
                        text-decoration: underline;
                    }
                    ul, ol {
                        margin-top: 6px;
                        margin-bottom: 6px;
                        padding-left: 20px;
                    }
                    li {
                        margin-bottom: 4px;
                    }
                    .footer-box {
                        text-align: center;
                        margin-top: 24px;
                        padding: 18px;
                        border-top: 1px solid $borderHex;
                        background-color: $cardBgHex;
                        border: 1px solid $borderHex;
                    }
                </style>
            </head>
            <body>
                <h2>📖 ComposeBridge Reference & Help Guide</h2>
                <p>Welcome to ComposeBridge! This guide provides comprehensive documentation on features, workflows, and integrations.</p>

                <details open>
                    <summary>🚀 Quick Start & Setup</summary>
                    <div style="margin-top: 8px;">
                        <ol>
                            <li><b>Install Plugin & Server:</b> Build or install the plugin zip package via <code>Settings &gt; Plugins &gt; Install Plugin from Disk</code>. Ensure Python 3.10+ is available with required dependencies.</li>
                            <li><b>Integrate Android Runtime:</b> Add <code>composebridge-runtime.aar</code> to your Android module dependencies and initialize <code>ComposeBridge.init(context)</code> in your application class.</li>
                            <li><b>Start Bridge Daemon:</b> Click <b>Start Bridge</b> in the header toolbar (or enable Auto-start in Settings). The daemon will listen on <code>127.0.0.1:8765</code>.</li>
                            <li><b>Connect Device:</b> Connect your physical phone or emulator via USB (<code>adb forward tcp:8765 tcp:8765</code>) or over local Wi-Fi / VPN. Run your app in debug mode to establish live communication.</li>
                        </ol>
                    </div>
                </details>

                <details>
                    <summary>🎛️ Header Buttons & Functions Glossary</summary>
                    <div style="margin-top: 8px;">
                        <table>
                            <tr>
                                <th style="width: 25%;">Button</th>
                                <th>Purpose & Behavior</th>
                            </tr>
                            <tr>
                                <td><b>Scan Project</b></td>
                                <td>Runs a parallel high-performance scan across the entire project (Kotlin AST and inspections) to locate hardcoded values, theme tokens, and syntax issues.</td>
                            </tr>
                            <tr>
                                <td><b>Start / Stop Bridge</b></td>
                                <td>Starts or terminates the local WebSocket/HTTP server process (<code>server.py</code>) controlling device synchronization.</td>
                            </tr>
                            <tr>
                                <td><b>Share Remote</b></td>
                                <td>Displays local network and Tailscale IP addresses with clear pairing instructions for remote live design sessions.</td>
                            </tr>
                            <tr>
                                <td><b>Token</b></td>
                                <td>Opens the Token Management dialog to view, inspect, or declare new theme tokens and dimension variables.</td>
                            </tr>
                            <tr>
                                <td><b>Sync Now</b></td>
                                <td>Forces immediate bidirectional state synchronization between open IDE files and all connected devices.</td>
                            </tr>
                            <tr>
                                <td><b>Settings</b></td>
                                <td>Opens ComposeBridge preferences to configure Python path, server path, default port, and auto-start options.</td>
                            </tr>
                            <tr>
                                <td><b>Clean Cache</b></td>
                                <td>Flushes temporary cache files, AST journals, and dirty buffer trackers located in <code>.composebridge-state</code>.</td>
                            </tr>
                        </table>
                    </div>
                </details>

                <details>
                    <summary>🛡️ Safety, AST Splicing & Instant Rollback</summary>
                    <div style="margin-top: 8px;">
                        <ul>
                            <li><b>Surgical Precision:</b> Edits are performed using AST syntax tree matching rather than naive regex replacement, keeping code indentation and structure untouched.</li>
                            <li><b>Automatic Backup:</b> Every modified file is automatically backed up as <code>&lt;filename&gt;.bridge.bak</code> prior to any write operation.</li>
                            <li><b>Changes Tab:</b> Displays live unified diffs of all modified files.</li>
                            <li><b>Approve:</b> Commits the modification and removes the backup file.</li>
                            <li><b>Reject:</b> Instantly restores the original file content from <code>.bridge.bak</code> with zero data loss.</li>
                        </ul>
                    </div>
                </details>

                <details>
                    <summary>🤖 AI Agents & Model Context Protocol (MCP)</summary>
                    <div style="margin-top: 8px;">
                        <p>ComposeBridge exposes <b>34 structured MCP tools</b> over stdio/JSON-RPC for autonomous AI coding agents (Antigravity, Cursor, Claude):</p>
                        <ul>
                            <li><b>Lazy Loading:</b> Consumes &lt;1% of the AI agent's context window (~176 tokens).</li>
                            <li><b>Capabilities:</b> Token discovery, orphan detection, impact analysis, pattern refactoring, and safe Gradle build validation.</li>
                        </ul>
                        <p><b>Agent Configuration (<code>mcp_config.json</code>):</b></p>
                        <pre>{
  "mcpServers": {
    "composebridge": {
      "command": "python",
      "args": ["-u", "/path/to/compose-bridge/server/mcp_server.py"]
    }
  }
}</pre>
                        <p><b>Diagnostics AI Actions:</b> In the <b>Diagnostics</b> tab, use <b>📋 Copy</b> to copy structured fix prompts, or <b>🚀 Auto-Fix</b> to dispatch automated repairs via MCP tools.</p>
                    </div>
                </details>

                <div class="footer-box">
                    <h3>🐞 Found a bug or have a feature request?</h3>
                    <p>We welcome contributions and feedback on our GitHub repository:</p>
                    <p><a href="https://github.com/JALAL591/compose-bridge/issues"><b>Open an Issue on GitHub &rarr;</b></a></p>
                </div>
            </body>
            </html>
        """.trimIndent()

        editorPane.caretPosition = 0
    }
}
