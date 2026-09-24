package com.composebridge.agent

import androidx.compose.runtime.tooling.CompositionData
import java.util.Collections
import java.util.WeakHashMap

/**
 * CompositionData tables .
 *
 * WeakHashMap Dialogs/Subcompositions.
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