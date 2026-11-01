package com.composebridge.plugin.services

import com.composebridge.plugin.settings.ComposeBridgeSettings
import com.intellij.openapi.project.Project
import java.io.BufferedReader
import java.io.File
import java.io.InputStreamReader

class PythonRunner(private val project: Project) {

    private val settings = ComposeBridgeSettings.getInstance(project)

    private fun getPython(): String {
        val saved = settings.state.pythonPath
        return if (saved.isNotBlank()) saved else "python"
    }

    fun getBridgePath(): String {
        val saved = settings.state.bridgePath.trim()
        if (saved.isNotBlank() && File(saved).exists()) return saved

        val projectRoot = project.basePath ?: "."

        // 1. Check composebridge.json in project root
        val configCandidates = listOf(
            File(projectRoot, "composebridge.json"),
            File(projectRoot, ".composebridge/config.json")
        )
        for (cfg in configCandidates) {
            if (cfg.exists()) {
                try {
                    val text = cfg.readText(Charsets.UTF_8)
                    val match = Regex(""""server"\s*:\s*"([^"]+)"""").find(text)
                    if (match != null) {
                        val serverRel = match.groupValues[1]
                        val serverDir = File(projectRoot, serverRel)
                        if (serverDir.exists() && (File(serverDir, "server.py").exists() || File(serverDir, "mcp_server.py").exists())) {
                            return serverDir.absolutePath
                        }
                    }
                } catch (_: Exception) {}
            }
        }

        // 2. Fallback: auto-detect within the project root
        val candidates = listOf(
            "$projectRoot/bridge",
            "$projectRoot/server",
            "$projectRoot/tools/bridge",
            "$projectRoot/.bridge"
        )
        for (path in candidates) {
            val f = File(path)
            if (f.exists() && File(f, "mcp_server.py").exists()) {
                return f.absolutePath
            }
        }
                val parent = File(projectRoot).parentFile
        if (parent != null) {
            val siblingCandidates = listOf(
                File(parent, "compose-bridge/server"),
                File(parent, "compose-bridge/bridge"),
                File(project.basePath ?: projectRoot, "bridge")
            )
            for (sib in siblingCandidates) {
                if (sib.exists() && File(sib, "server.py").exists()) {
                    return sib.absolutePath
                }
            }
        }
        return if (saved.isNotBlank()) saved else ""
    }

    fun runScanner(projectRoot: String): String {
        val bridge = getBridgePath()
        println("[PythonRunner] projectRoot = $projectRoot")
        println("[PythonRunner] bridgePath = $bridge")

        val script = "$bridge\\scanner_cli.py"
        val command = listOf(
            getPython(),
            script,
            "--root", projectRoot,
            "--format", "json",
            "--no-config"
        )
        return executeCommand(command, bridge)
    }

    fun getTokenImpact(tokenName: String): String {
        val bridge = getBridgePath()
        val script = """
            import mcp_server
            result = mcp_server.get_token_impact('$tokenName')
            print(result)
        """.trimIndent()

        val command = listOf(getPython(), "-c", script)
        return executeCommand(command, bridge)
    }

    fun getSuggestions(projectRoot: String): String {
        val bridge = getBridgePath()
        println("[PythonRunner] getSuggestions projectRoot = $projectRoot")
        val script = """
            import mcp_server
            result = mcp_server.suggest_token_split()
            print(result)
        """.trimIndent()

        val command = listOf(getPython(), "-c", script)
        return executeCommand(command, bridge)
    }

    fun detectPatterns(tokenName: String? = null): String {
        val bridge = getBridgePath()
        println("[PythonRunner] detectPatterns")
        val arg = if (tokenName != null) "token_name='$tokenName'" else ""
        val script = """
            import mcp_server
            result = mcp_server.detect_conditional_variants($arg)
            print(result)
        """.trimIndent()

        val command = listOf(getPython(), "-c", script)
        return executeCommand(command, bridge)
    }

    fun replacePattern(patternId: String): String {
        val bridge = getBridgePath()
        println("[PythonRunner] replacePattern patternId = $patternId")
        val script = """
            import mcp_server
            result = mcp_server.replace_pattern('$patternId')
            print(result)
        """.trimIndent()

        val command = listOf(getPython(), "-c", script)
        return executeCommand(command, bridge)
    }

    fun addToken(
        file: String,
        line: Int,
        value: String,
        tokenName: String,
        tokenType: String,
        forceCreate: Boolean = false
    ): String {
        val bridge = getBridgePath()
        val forceArg = if (forceCreate) ", force_create=True" else ""
        val script = """
            import mcp_server
            result = mcp_server.add_token(
                file='$file',
                line=$line,
                value='$value',
                token_name='$tokenName',
                token_type='$tokenType'$forceArg
            )
            print(result)
        """.trimIndent()

        val command = listOf(getPython(), "-c", script)
        return executeCommand(command, bridge)
    }

    fun runAddToken(
        file: String,
        line: Int,
        value: String,
        tokenName: String,
        tokenType: String,
        forceCreate: Boolean = false
    ): String {
        return addToken(file, line, value, tokenName, tokenType, forceCreate)
    }

    fun getTokenSiblings(tokenName: String): String {
        val bridge = getBridgePath()
        val script = """
            import mcp_server
            result = mcp_server.get_token_siblings('$tokenName')
            print(result)
        """.trimIndent()
        return executeCommand(listOf(getPython(), "-c", script), bridge)
    }

    fun listAppliedPatterns(): String {
        val bridge = getBridgePath()
        val script = """
            import mcp_server
            result = mcp_server.list_applied_patterns()
            print(result)
        """.trimIndent()
        return executeCommand(listOf(getPython(), "-c", script), bridge)
    }

    fun rollbackPattern(patternId: String): String {
        val bridge = getBridgePath()
        val script = """
            import mcp_server
            result = mcp_server.rollback_pattern('$patternId')
            print(result)
        """.trimIndent()
        return executeCommand(listOf(getPython(), "-c", script), bridge)
    }


    fun cleanTempFiles(): String {
        val bridge = getBridgePath()
        val pRoot = project.basePath ?: "."
        val safeRoot = pRoot.replace("\\", "\\\\").replace("'", "\\'")
        val script = """
            import sys, os, json
            from pathlib import Path
            sys.path.insert(0, os.path.abspath('.'))
            root = Path(r'$safeRoot')
            from core.project_root import clean_temp_files
            result = clean_temp_files(root)
            print(json.dumps(result, ensure_ascii=False))
        """.trimIndent()
        return executeCommand(listOf(getPython(), "-c", script), bridge)
    }

    fun listModifiedFiles(): String {
        val bridge = getBridgePath()
        val pRoot = project.basePath ?: "."
        val safeRoot = pRoot.replace("\\", "\\\\").replace("'", "\\'")
        val script = """
            import sys, os, json
            from pathlib import Path
            sys.path.insert(0, os.path.abspath('.'))
            root = Path(r'$safeRoot')
            from core.pattern_journal import PatternJournal
            journal = PatternJournal(root)
            files = journal.list_modified_files()
            print(json.dumps({'success': True, 'count': len(files), 'files': files}, ensure_ascii=False))
        """.trimIndent()
        return executeCommand(listOf(getPython(), "-c", script), bridge)
    }

    fun analyzeDesignScatter(): String {
        val bridge = getBridgePath()
        val pRoot = project.basePath ?: "."
        val safeRoot = pRoot.replace("\\", "\\\\").replace("'", "\\'")
        val script = """
            import sys, os, json
            from pathlib import Path
            sys.path.insert(0, os.path.abspath('.'))
            root = Path(r'$safeRoot')
            from analysis.universal_scanner import scan_design_scatter
            result = scan_design_scatter(root)
            print(json.dumps(result, ensure_ascii=False))
        """.trimIndent()
        return executeCommand(listOf(getPython(), "-c", script), bridge)
    }

    fun setDesignFileMapping(tokenType: String, filePath: String): String {
        val bridge = getBridgePath()
        val pRoot = project.basePath ?: "."
        val safeRoot = pRoot.replace("\\", "\\\\").replace("'", "\\'")
        val safeType = tokenType.replace("'", "\\'")
        val safePath = filePath.replace("\\", "\\\\").replace("'", "\\'")
        val script = """
            import sys, os, json
            from pathlib import Path
            sys.path.insert(0, os.path.abspath('.'))
            root = Path(r'$safeRoot')
            from analysis.universal_scanner import save_design_file_mapping
            result = save_design_file_mapping('$safeType', r'$safePath', root)
            print(json.dumps(result, ensure_ascii=False))
        """.trimIndent()
        return executeCommand(listOf(getPython(), "-c", script), bridge)
    }

    fun getDesignFileMappings(): String {
        val bridge = getBridgePath()
        val pRoot = project.basePath ?: "."
        val safeRoot = pRoot.replace("\\", "\\\\").replace("'", "\\'")
        val script = """
            import sys, os, json
            from pathlib import Path
            sys.path.insert(0, os.path.abspath('.'))
            root = Path(r'$safeRoot')
            from analysis.universal_scanner import get_design_file_mappings
            result = get_design_file_mappings(root)
            print(json.dumps({'success': True, 'mappings': result}, ensure_ascii=False))
        """.trimIndent()
        return executeCommand(listOf(getPython(), "-c", script), bridge)
    }

    fun approveChange(filePath: String, changeId: String): String {
        val bridge = getBridgePath()
        val pRoot = project.basePath ?: "."
        val safeRoot = pRoot.replace("\\", "\\\\").replace("'", "\\'")
        val safePath = filePath.replace("\\", "\\\\").replace("'", "\\'")
        val safeId = changeId.replace("'", "\\'")
        val script = """
            import sys, os, json
            from pathlib import Path
            sys.path.insert(0, os.path.abspath('.'))
            root = Path(r'$safeRoot')
            from core.diff_engine import approve_change
            result = approve_change(r'$safePath', '$safeId', root)
            print(json.dumps(result, ensure_ascii=False))
        """.trimIndent()
        return executeCommand(listOf(getPython(), "-c", script), bridge)
    }

    fun rejectChange(filePath: String, changeId: String): String {
        val bridge = getBridgePath()
        val pRoot = project.basePath ?: "."
        val safeRoot = pRoot.replace("\\", "\\\\").replace("'", "\\'")
        val safePath = filePath.replace("\\", "\\\\").replace("'", "\\'")
        val safeId = changeId.replace("'", "\\'")
        val script = """
            import sys, os, json
            from pathlib import Path
            sys.path.insert(0, os.path.abspath('.'))
            root = Path(r'$safeRoot')
            from core.diff_engine import reject_change
            result = reject_change(r'$safePath', '$safeId', root)
            print(json.dumps(result, ensure_ascii=False))
        """.trimIndent()
        return executeCommand(listOf(getPython(), "-c", script), bridge)
    }

    fun rejectFileChanges(filePath: String, force: Boolean = false): String {
        val bridge = getBridgePath()
        val pRoot = project.basePath ?: "."
        val safeRoot = pRoot.replace("\\", "\\\\").replace("'", "\\'")
        val safePath = filePath.replace("\\", "\\\\").replace("'", "\\'")
        val forceArg = if (force) "True" else "False"
        val script = """
            import sys, os, json
            from pathlib import Path
            sys.path.insert(0, os.path.abspath('.'))
            root = Path(r'$safeRoot')
            from core.pattern_journal import PatternJournal
            journal = PatternJournal(root)
            result = journal.reject_file_changes(r'$safePath', force=$forceArg)
            print(json.dumps(result, ensure_ascii=False))
        """.trimIndent()
        return executeCommand(listOf(getPython(), "-c", script), bridge)
    }

    fun approveFileChanges(filePath: String): String {
        val bridge = getBridgePath()
        val pRoot = project.basePath ?: "."
        val safeRoot = pRoot.replace("\\", "\\\\").replace("'", "\\'")
        val safePath = filePath.replace("\\", "\\\\").replace("'", "\\'")
        val script = """
            import sys, os, json
            from pathlib import Path
            sys.path.insert(0, os.path.abspath('.'))
            root = Path(r'$safeRoot')
            from core.pattern_journal import PatternJournal
            journal = PatternJournal(root)
            result = journal.approve_file_changes(r'$safePath')
            print(json.dumps(result, ensure_ascii=False))
        """.trimIndent()
        return executeCommand(listOf(getPython(), "-c", script), bridge)
    }

    fun approveAllFiles(): String {
        val bridge = getBridgePath()
        val script = """
            import mcp_server
            result = mcp_server.approve_all_files()
            print(result)
        """.trimIndent()
        return executeCommand(listOf(getPython(), "-c", script), bridge)
    }

    
    fun rejectAllFilesForce(): String {
        val bridge = getBridgePath()
        val script = """
            import mcp_server
            result = mcp_server.reject_all_files_force()
            print(result)
        """.trimIndent()
        return executeCommand(listOf(getPython(), "-c", script), bridge)
    }

    fun rejectAllFiles(): String {
        val bridge = getBridgePath()
        val script = """
            import mcp_server
            result = mcp_server.reject_all_files()
            print(result)
        """.trimIndent()
        return executeCommand(listOf(getPython(), "-c", script), bridge)
    }

    fun getFileDiff(filePath: String): String {
        val bridge = getBridgePath()
        val safePath = filePath.replace("\\", "\\\\").replace("'", "\\'")
        val script = """
            import mcp_server
            result = mcp_server.get_file_diff('$safePath')
            print(result)
        """.trimIndent()
        return executeCommand(listOf(getPython(), "-c", script), bridge)
    }

    fun runGradleBuild(task: String = "compileDebugKotlin", timeoutSeconds: Int = 300): String {
        val bridge = getBridgePath()
        val script = """
            import mcp_server
            result = mcp_server.run_gradle_build('$task', $timeoutSeconds)
            print(result)
        """.trimIndent()
        return executeCommand(listOf(getPython(), "-c", script), bridge)
    }

    fun triggerUserSync(): String {
        val bridge = getBridgePath()
        val script = """
            import mcp_server
            result = mcp_server.trigger_user_sync()
            print(result)
        """.trimIndent()
        return executeCommand(listOf(getPython(), "-c", script), bridge)
    }

    fun listTokens(projectPath: String? = null): String {
        val bridge = getBridgePath()
        val pathArg = if (projectPath != null) "r'$projectPath'" else "None"
        val script = """
            import mcp_server
            result = mcp_server.list_tokens(%s)
            print(result)
        """.trimIndent().format(pathArg)
        return executeCommand(listOf(getPython(), "-c", script), bridge)
    }

    fun getSyncStatus(): String {
        val bridge = getBridgePath()
        val script = """
            import mcp_server
            result = mcp_server.get_sync_status()
            print(result)
        """.trimIndent()
        return executeCommand(listOf(getPython(), "-c", script), bridge)
    }

        fun checkSyntaxFile(filePath: String): String {
        val bridge = getBridgePath()
        val script = "$bridge\\check_syntax_cli.py"
        val command = listOf(
            getPython(),
            script,
            filePath
        )
        return executeCommand(command, bridge)
    }

    fun syncDirtyFilesToDisk() {
        try {
            val fdm = com.intellij.openapi.fileEditor.FileDocumentManager.getInstance()
            val projectRoot = project.basePath ?: return
            val dirtyList = mutableListOf<String>()
            val baseDir = File(projectRoot)

            for (doc in fdm.unsavedDocuments) {
                val vFile = fdm.getFile(doc) ?: continue
                val path = vFile.path
                val rel = try {
                    File(path).relativeTo(baseDir).path.replace('\\', '/')
                } catch (e: Exception) {
                    vFile.name
                }
                dirtyList.add(rel)
            }

            val stateDir = File(projectRoot, ".composebridge-state")
            if (!stateDir.exists()) stateDir.mkdirs()
            val dirtyFile = File(stateDir, "dirty_files.json")
            val json = com.google.gson.Gson().toJson(dirtyList)
            dirtyFile.writeText(json, Charsets.UTF_8)
        } catch (e: Exception) {
            // ignore
        }
    }

    fun <T> runPythonJson(script: String, classOfT: Class<T>, workingDir: String? = null): T? {
        val raw = executeCommand(listOf(getPython(), "-c", script), workingDir ?: getBridgePath())
        return try {
            val start = raw.indexOf('{')
            val end = raw.lastIndexOf('}')
            val clean = if (start != -1 && end != -1 && end >= start) raw.substring(start, end + 1) else raw
            com.google.gson.Gson().fromJson(clean, classOfT)
        } catch (_: Exception) {
            null
        }
    }

    private fun executeCommand(command: List<String>, workingDir: String): String {
        syncDirtyFilesToDisk()
        if (workingDir.isBlank() || !File(workingDir).exists()) {
            return """{"status": "error", "error": "ComposeBridge path is not configured or not found. Please configure it in Settings -> Tools -> ComposeBridge."}"""
        }
        return try {
            val processBuilder = ProcessBuilder(command)
            processBuilder.directory(File(workingDir))
            val currentProjectRoot = project.basePath ?: "."
            processBuilder.environment()["COMPOSEBRIDGE_ROOT"] = currentProjectRoot
            processBuilder.redirectErrorStream(false)

            processBuilder.environment()["PYTHONIOENCODING"] = "utf-8"
            processBuilder.environment()["PYTHONUTF8"] = "1"
            processBuilder.redirectErrorStream(true)

            val process = processBuilder.start()
            val reader = BufferedReader(InputStreamReader(process.inputStream, Charsets.UTF_8))
            val output = StringBuilder()
            var line: String?
            while (reader.readLine().also { line = it } != null) {
                output.append(line).append("\n")
            }
            try {
                process.waitFor(15, java.util.concurrent.TimeUnit.SECONDS)
            } catch (_: Exception) {}
            output.toString()
        } catch (e: Exception) {
            "Error: ${e.message}"
        }
    }
}

