package com.composebridge.agent

import androidx.compose.runtime.tooling.CompositionData
import java.util.Collections
import java.util.WeakHashMap

/**
 * Registry tracking all active CompositionData tables.
 *
 * Uses WeakHashMap to avoid memory leaks when Dialogs/Subcompositions are destroyed.
 */
class CompositionRegistry {

    val tables: MutableSet<CompositionData> =
        Collections.synchronizedSet(
            Collections.newSetFromMap(
                WeakHashMap<CompositionData, Boolean>()
            )
        )

    fun register(data: CompositionData) {
        tables.add(data)
    }

    fun snapshot(): List<CompositionData> =
        synchronized(tables) {
            tables.toList()
        }

    fun size(): Int = tables.size
}
