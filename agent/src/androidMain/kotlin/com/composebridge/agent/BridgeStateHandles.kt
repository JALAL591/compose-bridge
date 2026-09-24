package com.composebridge.agent

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Popup

@Composable
fun BoxScope.CardHandlesOverlay(
 onPaddingChange: (Float) -> Unit,
 onColorChange: (String) -> Unit,
 onTextChange: ((String) -> Unit)? = null
) {
 CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Ltr) {
 val density = LocalDensity.current
 var showColors by remember { mutableStateOf(false) }
 var showTextEditor by remember { mutableStateOf(false) }
 var dragAccumulator by remember { mutableFloatStateOf(0f) }

 val currentPadding = BridgeState.cardPadding

 Box(Modifier.matchParentSize()) {

 // ═══ 4 ═══
 HandleDot(
 alignment = Alignment.TopStart,
 dx = (-12).dp, dy = (-12).dp,
 onDrag = { dX, dY ->
 dragAccumulator = -(dX + dY) / 2f
 val deltaDp = with(density) { dragAccumulator.toDp().value }
 val newPadding = (currentPadding.value + deltaDp).coerceIn(0f, 100f)
 onPaddingChange(newPadding)
 },
 onDragEnd = { dragAccumulator = 0f }
 )
 HandleDot(
 alignment = Alignment.TopEnd,
 dx = 12.dp, dy = (-12).dp,
 onDrag = { dX, dY ->
 dragAccumulator = (dX - dY) / 2f
 val deltaDp = with(density) { dragAccumulator.toDp().value }
 val newPadding = (currentPadding.value + deltaDp).coerceIn(0f, 100f)
 onPaddingChange(newPadding)
 },
 onDragEnd = { dragAccumulator = 0f }
 )
 HandleDot(
 alignment = Alignment.BottomStart,
 dx = (-12).dp, dy = 12.dp,
 onDrag = { dX, dY ->
 dragAccumulator = (dY - dX) / 2f
 val deltaDp = with(density) { dragAccumulator.toDp().value }
 val newPadding = (currentPadding.value + deltaDp).coerceIn(0f, 100f)
 onPaddingChange(newPadding)
 },
 onDragEnd = { dragAccumulator = 0f }
 )
 HandleDot(
 alignment = Alignment.BottomEnd,
 dx = 12.dp, dy = 12.dp,
 onDrag = { dX, dY ->
 dragAccumulator = (dX + dY) / 2f
 val deltaDp = with(density) { dragAccumulator.toDp().value }
 val newPadding = (currentPadding.value + deltaDp).coerceIn(0f, 100f)
 onPaddingChange(newPadding)
 },
 onDragEnd = { dragAccumulator = 0f }
 )

 // ═══ ( ) ═══
 Row(
 modifier = Modifier
 .align(Alignment.TopCenter)
 .padding(top = 10.dp)
 .background(Color(0xFF1E1E2C), RoundedCornerShape(24.dp))
 .border(1.dp, Color.White.copy(alpha = 0.2f), RoundedCornerShape(24.dp))
 .padding(horizontal = 10.dp, vertical = 6.dp),
 horizontalArrangement = Arrangement.spacedBy(10.dp),
 verticalAlignment = Alignment.CenterVertically
 ) {
 // 1) ↔
 Box(
 modifier = Modifier
 .requiredSize(width = 40.dp, height = 32.dp)
 .clip(RoundedCornerShape(10.dp))
 .background(Color(0xFF6366F1))
 .pointerInput(Unit) {
 detectDragGestures { change, _ ->
 change.consume()
 }
 },
 contentAlignment = Alignment.Center
 ) {
 BasicText("↔", style = TextStyle(color = Color.White, fontSize = 15.sp))
 }

 // 2) 🎨
 Box(
 modifier = Modifier
 .requiredSize(32.dp)
 .clip(CircleShape)
 .background(Color(0xFF4C4CD9))
 .clickable {
 showColors = !showColors
 if (showColors) showTextEditor = false
 },
 contentAlignment = Alignment.Center
 ) {
 BasicText("🎨", style = TextStyle(fontSize = 15.sp))
 }

 // 3) 📝
 if (onTextChange != null) {
 Box(
 modifier = Modifier
 .requiredSize(30.dp)
 .clip(CircleShape)
 .background(Color(0xFF2196F3))
 .clickable {
 showTextEditor = !showTextEditor
 if (showTextEditor) showColors = false
 },
 contentAlignment = Alignment.Center
 ) {
 BasicText("📝", style = TextStyle(fontSize = 15.sp))
 }
 }
 }

 // ═══ ( Popup ) ═══
 if (showColors) {
 Popup(
 alignment = Alignment.Center,
 onDismissRequest = { showColors = false }
 ) {
 BridgeColorPicker(
 onPick = { hex ->
 onColorChange(hex)
 showColors = false
 }
 )
 }
 }

 // ═══ ( Popup ) ═══
 if (showTextEditor && onTextChange != null) {
 Popup(
 alignment = Alignment.Center,
 onDismissRequest = { showTextEditor = false }
 ) {
 BridgeTextEditorPopup(
 initialText = BridgeState.titleText,
 onSave = { newText ->
 onTextChange(newText)
 showTextEditor = false
 },
 onCancel = { showTextEditor = false }
 )
 }
 }
 }
 }
}

@Composable
private fun BoxScope.HandleDot(
 alignment: Alignment,
 dx: Dp,
 dy: Dp,
 onDrag: (Float, Float) -> Unit,
 onDragEnd: () -> Unit,
) {
 val latestOnDrag by rememberUpdatedState(onDrag)
 val latestOnDragEnd by rememberUpdatedState(onDragEnd)

 Box(
 modifier = Modifier
 .align(alignment)
 .absoluteOffset(x = dx, y = dy)
 .requiredSize(28.dp)
 .clip(CircleShape)
 .background(Color.White)
 .border(3.dp, Color(0xFF00C896), CircleShape)
 .pointerInput(Unit) {
 detectDragGestures(
 onDragStart = { },
 onDrag = { change, dragAmount ->
 change.consume()
 latestOnDrag(dragAmount.x, dragAmount.y)
 },
 onDragEnd = { latestOnDragEnd() }
 )
 }
 )
}

@Composable
private fun BridgeColorPicker(
 modifier: Modifier = Modifier,
 onPick: (String) -> Unit,
) {
 val colors = listOf(
 "#FFFFFF", "#E53935", "#00C896", "#4C4CD9",
 "#FFB300", "#9C27B0", "#00BCD4", "#212121"
 )

 Column(
 modifier = modifier
 .requiredWidth(240.dp)
 .background(Color.White, RoundedCornerShape(16.dp))
 .border(1.5.dp, Color(0xFFDDDDDD), RoundedCornerShape(16.dp))
 .padding(14.dp),
 verticalArrangement = Arrangement.spacedBy(10.dp),
 horizontalAlignment = Alignment.CenterHorizontally
 ) {
 BasicText(
 text = "🎨 ",
 style = TextStyle(fontWeight = FontWeight.Bold, fontSize = 13.sp, color = Color(0xFF222222))
 )

 colors.chunked(4).forEach { row ->
 Row(
 horizontalArrangement = Arrangement.spacedBy(8.dp),
 verticalAlignment = Alignment.CenterVertically
 ) {
 row.forEach { hex ->
 Box(
 Modifier
 .requiredSize(36.dp)
 .clip(RoundedCornerShape(8.dp))
 .background(parseHexColor(hex))
 .border(1.5.dp, Color(0xFFCCCCCC), RoundedCornerShape(8.dp))
 .clickable { onPick(hex) }
 )
 }
 }
 }
 }
}

@Composable
private fun BridgeTextEditorPopup(
 initialText: String,
 modifier: Modifier = Modifier,
 onSave: (String) -> Unit,
 onCancel: () -> Unit
) {
 var text by remember(initialText) { mutableStateOf(initialText) }

 Column(
 modifier = modifier
 .requiredWidth(250.dp)
 .background(Color.White, RoundedCornerShape(16.dp))
 .border(1.5.dp, Color(0xFFDDDDDD), RoundedCornerShape(16.dp))
 .padding(14.dp),
 verticalArrangement = Arrangement.spacedBy(10.dp)
 ) {
 BasicText(
 text = "📝 ",
 style = TextStyle(fontWeight = FontWeight.Bold, fontSize = 13.sp, color = Color(0xFF222222))
 )

 BasicTextField(
 value = text,
 onValueChange = { text = it },
 modifier = Modifier
 .fillMaxWidth()
 .requiredHeight(42.dp)
 .background(Color(0xFFF5F5F5), RoundedCornerShape(8.dp))
 .border(1.dp, Color(0xFFCCCCCC), RoundedCornerShape(8.dp))
 .padding(8.dp),
 textStyle = TextStyle(fontSize = 14.sp, color = Color.Black)
 )

 Row(
 horizontalArrangement = Arrangement.spacedBy(8.dp),
 modifier = Modifier.fillMaxWidth()
 ) {
 Box(
 Modifier
 .weight(1f)
 .requiredHeight(34.dp)
 .clip(RoundedCornerShape(8.dp))
 .background(Color(0xFFEEEEEE))
 .clickable { onCancel() },
 contentAlignment = Alignment.Center
 ) {
 BasicText(" ", style = TextStyle(fontSize = 12.sp, color = Color.Black, fontWeight = FontWeight.Medium))
 }
 Box(
 Modifier
 .weight(1f)
 .requiredHeight(34.dp)
 .clip(RoundedCornerShape(8.dp))
 .background(Color(0xFF00C896))
 .clickable { onSave(text) }
 .padding(vertical = 6.dp),
 contentAlignment = Alignment.Center
 ) {
 BasicText(" ", style = TextStyle(fontSize = 12.sp, color = Color.White, fontWeight = FontWeight.Bold))
 }
 }
 }
}

private fun parseHexColor(hex: String): Color {
 val cleaned = hex.removePrefix("#").removePrefix("0x")
 val argb = if (cleaned.length == 6) "FF$cleaned" else cleaned
 return Color(argb.toLong(16))
}