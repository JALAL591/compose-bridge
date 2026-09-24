package com.composebridge.agent

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import kotlin.math.roundToInt

/**
 * DesignHandlesOverlay — .
 *
 * - → 
 * - BridgeState
 */
@Composable
fun DesignHandlesOverlay() {
 if (!DesignModeRegistry.isActive) return

 val selectedName = DesignModeRegistry.selectedElement ?: return
 val bounds = DesignModeRegistry.elementBounds[selectedName] ?: return

 Box(Modifier.fillMaxSize()) {
 // bounds Dp
 val density = LocalDensity.current
 val leftPx = bounds.left
 val topPx = bounds.top
 val widthPx = bounds.width
 val heightPx = bounds.height

 // 
 Box(
 Modifier
 .offset {
 IntOffset(leftPx.roundToInt(), topPx.roundToInt())
 }
 .size(
 width = with(density) { widthPx.toDp() },
 height = with(density) { heightPx.toDp() }
 )
 .border(2.dp, Color(0xFF00C896))
 )

 // 
 PaddingHandle(
 alignment = Alignment.TopStart,
 boundsLeft = leftPx,
 boundsTop = topPx,
 boundsWidth = widthPx,
 boundsHeight = heightPx
 )
 PaddingHandle(
 alignment = Alignment.TopEnd,
 boundsLeft = leftPx,
 boundsTop = topPx,
 boundsWidth = widthPx,
 boundsHeight = heightPx
 )
 PaddingHandle(
 alignment = Alignment.BottomStart,
 boundsLeft = leftPx,
 boundsTop = topPx,
 boundsWidth = widthPx,
 boundsHeight = heightPx
 )
 PaddingHandle(
 alignment = Alignment.BottomEnd,
 boundsLeft = leftPx,
 boundsTop = topPx,
 boundsWidth = widthPx,
 boundsHeight = heightPx
 )
 }
}

@Composable
private fun BoxScope.PaddingHandle(
 alignment: Alignment,
 boundsLeft: Float,
 boundsTop: Float,
 boundsWidth: Float,
 boundsHeight: Float,
) {
 val density = LocalDensity.current
 val handleSize = 24.dp
 val handleSizePx = with(density) { handleSize.toPx() }

 // 
 val handleX = when (alignment) {
 Alignment.TopStart, Alignment.BottomStart -> boundsLeft
 else -> boundsLeft + boundsWidth
 }
 val handleY = when (alignment) {
 Alignment.TopStart, Alignment.TopEnd -> boundsTop
 else -> boundsTop + boundsHeight
 }

 // BridgeState
 val currentPadding = BridgeState.cardPadding
 var dragAccumulator by remember { mutableFloatStateOf(0f) }

 // padding
 val latestPaddingState = rememberUpdatedState(currentPadding)

 Box(
 Modifier
 .offset {
 IntOffset(
 (handleX - handleSizePx / 2).roundToInt(),
 (handleY - handleSizePx / 2).roundToInt()
 )
 }
 .size(handleSize)
 .clip(CircleShape)
 .background(Color.White)
 .border(2.dp, Color(0xFF00C896), CircleShape)
 .pointerInput(Unit) {
 detectDragGestures(
 onDragStart = {
 dragAccumulator = 0f
 },
 onDrag = { change, dragAmount ->
 change.consume()
 dragAccumulator += when (alignment) {
 Alignment.TopStart -> -(dragAmount.x + dragAmount.y) / 2
 Alignment.TopEnd -> (dragAmount.x - dragAmount.y) / 2
 Alignment.BottomStart -> (dragAmount.y - dragAmount.x) / 2
 Alignment.BottomEnd -> (dragAmount.x + dragAmount.y) / 2
 else -> 0f
 }

 // px → dp
 val deltaDp = with(density) { dragAccumulator.toDp().value }
 val basePadding = latestPaddingState.value.value
 val newPadding = (basePadding + deltaDp).coerceIn(0f, 100f)

 // ⭐ BridgeState — UI 
 BridgeState.cardPadding = newPadding.dp
 },
 onDragEnd = {
 // ⭐ Python ( File)
 val finalValue = latestPaddingState.value.value
 ComposeBridgeAgent.sendStateUpdate(
 property = "cardPadding",
 value = finalValue.toInt().toString()
 )
 dragAccumulator = 0f
 }
 )
 }
 )
}