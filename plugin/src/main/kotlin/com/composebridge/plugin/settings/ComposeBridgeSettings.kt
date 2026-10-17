package com.composebridge.plugin.settings

import com.intellij.openapi.components.PersistentStateComponent
import com.intellij.openapi.components.Service
import com.intellij.openapi.components.State
import com.intellij.openapi.components.Storage
import com.intellij.openapi.components.service
import com.intellij.openapi.project.Project
import com.intellij.util.xmlb.XmlSerializerUtil

@Service(Service.Level.PROJECT)
@State(
    name = "ComposeBridgeSettings",
    storages = [Storage("ComposeBridge.xml")]
)
class ComposeBridgeSettings : PersistentStateComponent<ComposeBridgeSettings.State> {

    data class State(
        var pythonPath: String = "",
        var bridgePath: String = "",
        var autoStartBridge: Boolean = true
    )

    private var myState = State()

    override fun getState(): State = myState

    override fun loadState(state: State) {
        XmlSerializerUtil.copyBean(state, myState)
    }

    companion object {
        fun getInstance(project: Project): ComposeBridgeSettings =
            project.service()
    }
}
