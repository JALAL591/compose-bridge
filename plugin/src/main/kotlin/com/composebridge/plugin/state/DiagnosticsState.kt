package com.composebridge.plugin.state

import com.intellij.openapi.components.PersistentStateComponent
import com.intellij.openapi.components.Service
import com.intellij.openapi.components.State
import com.intellij.openapi.components.Storage
import com.intellij.openapi.components.service
import com.intellij.openapi.project.Project
import com.intellij.util.xmlb.XmlSerializerUtil

/**
 * Persistent storage for IDE diagnostics results.
 * Preserves error & warning findings across tab switches and IDE restarts.
 */
@Service(Service.Level.PROJECT)
@State(
    name = "ComposeBridgeDiagnosticsState",
    storages = [Storage("composebridge_diagnostics.xml")]
)
class DiagnosticsState : PersistentStateComponent<DiagnosticsState.State> {

    data class StoredDiagnosticItem(
        var file: String = "",
        var relativePath: String = "",
        var line: Int = 1,
        var column: Int = 1,
        var severity: String = "",
        var message: String = "",
        var inspectionId: String = ""
    )

    data class State(
        var summaryText: String = "",
        var totalErrors: Int = 0,
        var totalWarnings: Int = 0,
        var items: MutableList<StoredDiagnosticItem> = mutableListOf(),
        var lastScanTimestamp: Long = 0L
    )

    private var myState = State()

    override fun getState(): State = myState

    override fun loadState(state: State) {
        XmlSerializerUtil.copyBean(state, myState)
    }

    companion object {
        fun getInstance(project: Project): DiagnosticsState = project.service()
    }
}

