@file:OptIn(
    androidx.compose.foundation.ExperimentalFoundationApi::class,
    androidx.compose.material3.ExperimentalMaterial3Api::class,
)

/**
 * ComposeBridge Color Edit Panel.
 * لوحة فحص وتعديل ألوان عناصر واجهة المستخدم والتوكنات اللونية وتعديل الألوان المشتركة.
 */
package com.composebridge.agent.ui.panels

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.composebridge.agent.BridgeState
import com.composebridge.agent.BridgeThemeRegistry
import com.composebridge.agent.ComposeBridgeAgent
import com.composebridge.agent.DesignModeRegistry
import com.composebridge.agent.ElementColorInfo
import com.composebridge.agent.PendingEdit

/**
 * لوحة تعديل الألوان لعنصر Compose المحدد وإدارة الحوارات الخاصة بالألوان المشتركة.
 * Main Color Edit Panel composable displaying colors in the current element scope.
 */
@Composable
fun ColorEditPanel() {
    var colorPendingChange by remember { mutableStateOf<ElementColorInfo?>(null) }
    var pendingNewHex by remember { mutableStateOf<String?>(null) }

    Text(
        text = "🎨 Element Colors",
        fontSize = 14.sp,
        fontWeight = FontWeight.Bold,
        modifier = Modifier.padding(vertical = 4.dp)
    )

    if (BridgeState.elementAnalysisError != null) {
        Surface(
            color = Color(0xFFFFEBEE),
            shape = RoundedCornerShape(8.dp),
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 8.dp)
        ) {
            Text(
                text = "⚠️ ${BridgeState.elementAnalysisError}",
                fontSize = 12.sp,
                color = Color(0xFFC62828),
                modifier = Modifier.padding(10.dp)
            )
        }
    } else if (BridgeState.elementColors.isEmpty()) {
        Text(
            text = "No custom colors found in this element scope",
            fontSize = 12.sp,
            color = Color.Gray,
            modifier = Modifier.padding(vertical = 8.dp)
        )
    } else {
        BridgeState.elementColors.forEach { colorInfo ->
            if (colorInfo.isThemeDependent) {
                ThemeDependentColorCard(color = colorInfo)
            } else {
                FocusColorRow(
                    colorInfo = colorInfo,
                    onTapHeader = {
                        if (!colorInfo.isToken) {
                            BridgeState.hardcodedColorPending = colorInfo
                            BridgeState.hardcodedUsageGlobal = colorInfo.usageGlobal
                            BridgeState.hardcodedLocations = colorInfo.locations
                            BridgeState.hardcodedNewHex = null
                            BridgeState.showHardcodedDialog = true
                        }
                    },
                    onPickColor = { newHex ->
                        if (colorInfo.isToken) {
                            if (colorInfo.isShared) {
                                colorPendingChange = colorInfo
                                pendingNewHex = newHex
                            } else {
                                val edit = PendingEdit(
                                    type = "global_color",
                                    file = DesignModeRegistry.selectedSourceFile ?: "",
                                    line = colorInfo.lineInElement,
                                    property = colorInfo.property,
                                    oldValue = colorInfo.value,
                                    newValue = newHex,
                                    tokenName = colorInfo.name,
                                    originalToken = colorInfo.name,
                                    originalValue = colorInfo.value,
                                )
                                BridgeState.addPendingEdit(edit)
                                BridgeState.showSnackbar("📝 Added (${BridgeState.pendingCount})")
                            }
                        } else {
                            BridgeState.hardcodedColorPending = colorInfo
                            BridgeState.hardcodedUsageGlobal = colorInfo.usageGlobal
                            BridgeState.hardcodedLocations = colorInfo.locations
                            BridgeState.hardcodedNewHex = newHex
                            BridgeState.showHardcodedDialog = true
                        }
                    }
                )
            }
        }
    }

    // ═══ Dialog for Shared Colors and Tokens ═══
    val pendingColor = colorPendingChange
    val newHex = pendingNewHex
    if (pendingColor != null && newHex != null) {
        val isSharedValue = (pendingColor.isShared && pendingColor.usageGlobal > 1) || pendingColor.usageGlobal > 1
        if (isSharedValue) {
            val locations = pendingColor.locations
            AlertDialog(
                onDismissRequest = {
                    colorPendingChange = null
                    pendingNewHex = null
                },
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("🔗", fontSize = 24.sp)
                        Spacer(Modifier.width(8.dp))
                        Text(
                            "Shared Value",
                            fontWeight = FontWeight.Bold,
                            fontSize = 18.sp,
                        )
                    }
                },
                text = {
                    Column(
                        modifier = Modifier
                            .heightIn(max = 400.dp)
                            .verticalScroll(rememberScrollState()),
                    ) {
                        // ⭐ Value name and count
                        Text(
                            text = "Color '${pendingColor.name}' (${pendingColor.value})",
                            fontWeight = FontWeight.SemiBold,
                        )
                        Spacer(Modifier.height(4.dp))
                        Text(
                            text = "Used in ${pendingColor.usageGlobal} occurrences in project",
                            color = Color(0xFFE65100),
                            fontWeight = FontWeight.Bold,
                        )

                        Spacer(Modifier.height(12.dp))
                        HorizontalDivider()
                        Spacer(Modifier.height(12.dp))

                        // ⭐ Locations list
                        Text(
                            text = "📍 Locations:",
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 14.sp,
                        )
                        Spacer(Modifier.height(8.dp))

                        if (locations.isNotEmpty()) {
                            locations.take(10).forEach { loc ->
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 4.dp, horizontal = 8.dp),
                                ) {
                                    Text("•", color = Color(0xFF6366F1))
                                    Spacer(Modifier.width(6.dp))
                                    Column {
                                        Text(
                                            text = "${loc.file}:${loc.line}",
                                            fontSize = 12.sp,
                                            fontFamily = FontFamily.Monospace,
                                            color = Color(0xFF6366F1),
                                        )
                                        if (loc.property.isNotEmpty()) {
                                            Text(
                                                text = "  property: ${loc.property}",
                                                fontSize = 11.sp,
                                                color = Color.Gray,
                                            )
                                        }
                                    }
                                }
                            }

                            if (locations.size > 10) {
                                Text(
                                    text = "... and ${locations.size - 10} more locations",
                                    fontSize = 12.sp,
                                    color = Color.Gray,
                                    modifier = Modifier.padding(start = 20.dp, top = 4.dp),
                                )
                            }
                        } else {
                            Text(
                                text = "Appears across multiple files in the project",
                                fontSize = 12.sp,
                                color = Color.Gray,
                                modifier = Modifier.padding(start = 8.dp),
                            )
                        }

                        Spacer(Modifier.height(16.dp))
                        HorizontalDivider()
                        Spacer(Modifier.height(12.dp))

                        // ⭐ Explain both options
                        Text(
                            text = "🔀 Split for This Element (Recommended):",
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 13.sp,
                            color = Color(0xFF10B981),
                        )
                        Text(
                            text = "Creates a new dedicated token for this element only.\nOther occurrences retain the original color.",
                            fontSize = 11.sp,
                            color = Color.Gray,
                        )

                        Spacer(Modifier.height(12.dp))

                        Text(
                            text = "🌍 Edit Globally:",
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 13.sp,
                            color = Color(0xFFE65100),
                        )
                        Text(
                            text = "Updates all ${pendingColor.usageGlobal} occurrences.\n⚠️ Affects the entire application!",
                            fontSize = 11.sp,
                            color = Color.Gray,
                        )
                    }
                },
                confirmButton = {
                    Button(
                        onClick = {
                            if (BridgeState.syncInProgress) return@Button
                            val newTokenName = suggestLocalTokenName(BridgeState.elementComposableName, newHex, pendingColor)
                            val edit = PendingEdit(
                                type = "split_token",
                                file = DesignModeRegistry.selectedSourceFile ?: "",
                                line = pendingColor.lineInElement,
                                property = pendingColor.property,
                                oldValue = pendingColor.value,
                                newValue = newHex,
                                tokenName = newTokenName,
                                originalToken = if (pendingColor.isToken) pendingColor.name else pendingColor.value,
                                occurrences = pendingColor.occurrencesInElement,
                            )
                            BridgeState.addPendingEdit(edit)
                            BridgeState.showSnackbar("✂️ Split token ($newTokenName)")
                            colorPendingChange = null
                            pendingNewHex = null
                        },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Color(0xFF10B981),
                        )
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("🔀 Split for This Element", fontWeight = FontWeight.Bold, fontSize = 14.sp)
                            Text("Safe — does not affect others", fontSize = 10.sp)
                        }
                    }
                },
                dismissButton = {
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        OutlinedButton(
                            onClick = {
                                if (BridgeState.syncInProgress) return@OutlinedButton
                                val tokenName = if (pendingColor.isToken && isValidKotlinIdentifier(pendingColor.name)) {
                                    pendingColor.name
                                } else {
                                    suggestGlobalTokenName(pendingColor, newHex)
                                }
                                val edit = PendingEdit(
                                    type = "global_color",
                                    file = DesignModeRegistry.selectedSourceFile ?: "",
                                    line = pendingColor.lineInElement,
                                    property = "all",
                                    oldValue = pendingColor.value,
                                    newValue = newHex,
                                    tokenName = tokenName,
                                )
                                BridgeState.addPendingEdit(edit)
                                BridgeState.showSnackbar("🌍 Global edit added (${pendingColor.usageGlobal} occurrences)")
                                colorPendingChange = null
                                pendingNewHex = null
                            },
                            colors = ButtonDefaults.outlinedButtonColors(
                                contentColor = Color(0xFFE65100),
                            )
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text("🌍 Edit Globally", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                                Text("⚠️ ${pendingColor.usageGlobal} places", fontSize = 10.sp)
                            }
                        }
                        TextButton(
                            onClick = {
                                colorPendingChange = null
                                pendingNewHex = null
                            }
                        ) {
                            Text("Cancel", fontSize = 12.sp)
                        }
                    }
                }
            )
        } else if (pendingColor.isToken) {
            AlertDialog(
                onDismissRequest = {
                    colorPendingChange = null
                    pendingNewHex = null
                },
                title = {
                    Text(
                        text = "🔗 Edit Token",
                        fontWeight = FontWeight.Bold,
                        fontSize = 17.sp
                    )
                },
                text = {
                    Text(
                        text = "Color '${pendingColor.name}' (${pendingColor.value}) exists as a token.\n\nUpdating its value will affect this element.",
                        fontSize = 14.sp
                    )
                },
                confirmButton = {
                    Button(
                        onClick = {
                            val edit = PendingEdit(
                                type = "global_color",
                                file = DesignModeRegistry.selectedSourceFile ?: "",
                                line = pendingColor.lineInElement,
                                property = "all",
                                oldValue = pendingColor.value,
                                newValue = newHex,
                                tokenName = pendingColor.name,
                            )
                            BridgeState.addPendingEdit(edit)
                            BridgeState.showSnackbar("📝 Added (${BridgeState.pendingCount})")
                            colorPendingChange = null
                            pendingNewHex = null
                        },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Color(0xFF6366F1)
                        )
                    ) {
                        Text("Update Value", fontWeight = FontWeight.Bold)
                    }
                },
                dismissButton = {
                    TextButton(
                        onClick = {
                            colorPendingChange = null
                            pendingNewHex = null
                        }
                    ) {

                    }
                }
            )
        }
    }

    // ═══ Dialog: Convert Hardcoded to Token ═══
    val hardcodedColor = BridgeState.hardcodedColorPending
    if (BridgeState.showHardcodedDialog && hardcodedColor != null && !hardcodedColor.isThemeDependent) {
        AlertDialog(
            onDismissRequest = {
                BridgeState.showHardcodedDialog = false
                BridgeState.hardcodedColorPending = null
                BridgeState.hardcodedNewHex = null
            },
            title = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("🎨", fontSize = 24.sp)
                    Spacer(Modifier.width(8.dp))
                    Text(
                        "Hardcoded Color",
                        fontWeight = FontWeight.Bold,
                        fontSize = 17.sp,
                    )
                }
            },
            text = {
                Column(
                    modifier = Modifier
                        .heightIn(max = 400.dp)
                        .verticalScroll(rememberScrollState()),
                ) {
                    // ⭐ Color display
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Box(
                            modifier = Modifier
                                .size(32.dp)
                                .background(
                                    hexToColor(hardcodedColor.value),
                                    CircleShape,
                                )
                        )
                        Spacer(Modifier.width(12.dp))
                        Column {
                            Text(
                                text = hardcodedColor.name,
                                fontFamily = FontFamily.Monospace,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.SemiBold,
                            )
                            Text(
                                text = hardcodedColor.value,
                                fontSize = 12.sp,
                                color = Color.Gray,
                            )
                        }
                    }

                    Spacer(Modifier.height(12.dp))
                    HorizontalDivider()
                    Spacer(Modifier.height(12.dp))

                    // ⭐ Explanation
                    Text(
                        text = "⚠️ This color is hardcoded directly in source code",
                        fontSize = 13.sp,
                        color = Color(0xFFE65100),
                        fontWeight = FontWeight.SemiBold,
                    )
                    Spacer(Modifier.height(6.dp))
                    Text(
                        text = "To edit it, it must first be converted into a token.",
                        fontSize = 12.sp,
                        color = Color.Gray,
                    )

                    // ⭐ Count of locations
                    if (hardcodedColor.usageGlobal > 1) {
                        Spacer(Modifier.height(12.dp))
                        Text(
                            text = "📍 Used in ${hardcodedColor.usageGlobal} occurrences",
                            fontSize = 12.sp,
                            fontWeight = FontWeight.SemiBold,
                        )

                        // ⭐ Locations list (first 5)
                        hardcodedColor.locations.take(5).forEach { loc ->
                            Row(
                                modifier = Modifier.padding(
                                    start = 16.dp,
                                    top = 2.dp,
                                ),
                            ) {
                                Text("•", color = Color(0xFF6366F1), fontSize = 11.sp)
                                Spacer(Modifier.width(4.dp))
                                Text(
                                    text = "${loc.file.substringAfterLast("/")}:${loc.line}",
                                    fontSize = 11.sp,
                                    fontFamily = FontFamily.Monospace,
                                    color = Color(0xFF6366F1),
                                )
                            }
                        }

                        if (hardcodedColor.locations.size > 5) {
                            Text(
                                text = "... and ${hardcodedColor.locations.size - 5} more locations",
                                fontSize = 11.sp,
                                color = Color.Gray,
                                modifier = Modifier.padding(start = 20.dp, top = 2.dp),
                            )
                        }
                    }

                    Spacer(Modifier.height(12.dp))
                    HorizontalDivider()
                    Spacer(Modifier.height(12.dp))

                    // ⭐ Options explanation
                    Text(
                        text = "🔀 Convert for This Element (Recommended):",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = Color(0xFF10B981),
                    )
                    Text(
                        text = "Creates a new token dedicated to this element only.",
                        fontSize = 11.sp,
                        color = Color.Gray,
                    )

                    Spacer(Modifier.height(8.dp))

                    Text(
                        text = "🌍 Convert Globally:",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = Color(0xFFE65100),
                    )
                    Text(
                        text = "Replaces all ${hardcodedColor.usageGlobal} occurrences with a shared token.",
                        fontSize = 11.sp,
                        color = Color.Gray,
                    )

                    Spacer(Modifier.height(12.dp))
                    HorizontalDivider()
                    Spacer(Modifier.height(8.dp))

                    // ⭐ Rebuild note
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(
                                Color(0xFFFFF3E0),
                                RoundedCornerShape(8.dp),
                            )
                            .padding(8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text("⚠️", fontSize = 16.sp)
                        Spacer(Modifier.width(6.dp))
                        Text(
                            text = "Initial conversion requires a rebuild to apply. Subsequent edits will be instant.",
                            fontSize = 11.sp,
                            color = Color(0xFFE65100),
                        )
                    }
                }
            },
            confirmButton = {
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Button(
                        onClick = {
                            // ⭐ Split: for this element only
                            val color = BridgeState.hardcodedColorPending
                            if (color != null) {
                                performConvertHardcoded(
                                    color = color,
                                    mode = "split",  // ⭐ element-only
                                )
                            }
                            BridgeState.showHardcodedDialog = false
                            BridgeState.hardcodedColorPending = null
                            BridgeState.hardcodedNewHex = null
                        },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Color(0xFF10B981),
                        ),
                        shape = RoundedCornerShape(10.dp),
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Text(
                                "🔀 Convert for This Element",
                                fontWeight = FontWeight.Bold,
                                fontSize = 13.sp,
                            )
                            Text(
                                "Safe — does not affect others",
                                fontSize = 10.sp,
                            )
                        }
                    }

                    OutlinedButton(
                        onClick = {
                            val color = BridgeState.hardcodedColorPending
                            if (color != null) {
                                performConvertHardcoded(
                                    color = color,
                                    mode = "global",  // ⭐ all places
                                )
                            }
                            BridgeState.showHardcodedDialog = false
                            BridgeState.hardcodedColorPending = null
                            BridgeState.hardcodedNewHex = null
                        },
                        colors = ButtonDefaults.outlinedButtonColors(
                            contentColor = Color(0xFFE65100),
                        ),
                        shape = RoundedCornerShape(10.dp),
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Text(
                                "🌍 Convert Globally",
                                fontWeight = FontWeight.Bold,
                                fontSize = 12.sp,
                            )
                            Text(
                                "⚠️ ${hardcodedColor.usageGlobal} places",
                                fontSize = 10.sp,
                            )
                        }
                    }

                    TextButton(
                        onClick = {
                            BridgeState.showHardcodedDialog = false
                            BridgeState.hardcodedColorPending = null
                            BridgeState.hardcodedNewHex = null
                        },
                        contentPadding = PaddingValues(vertical = 2.dp),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("Cancel", fontSize = 12.sp, color = Color.Gray)
                    }
                }
            },
            dismissButton = null
        )
    }


}
private fun isValidKotlinIdentifier(name: String): Boolean {
    if (name.isEmpty()) return false
    if (!name[0].isLetter() && name[0] != '_') return false
    return name.all { it.isLetterOrDigit() || it == '_' }
}

private fun hexToColorName(hex: String): String {
    val clean = hex.removePrefix("#").take(6)
    if (clean.length != 6) return "Custom"
    
    val r = clean.substring(0, 2).toIntOrNull(16) ?: return "Custom"
    val g = clean.substring(2, 4).toIntOrNull(16) ?: return "Custom"
    val b = clean.substring(4, 6).toIntOrNull(16) ?: return "Custom"
    
    return when {
        r > 230 && g > 230 && b > 230 -> "White"
        r < 30 && g < 30 && b < 30 -> "Black"
        kotlin.math.abs(r - g) < 20 && kotlin.math.abs(g - b) < 20 -> "Gray"
        g > r && g > b -> "Green"
        b > r && b > g -> "Blue"
        r > 200 && g in 100..180 && b < 100 -> "Orange"
        r > 200 && g > 200 && b < 100 -> "Yellow"
        r > 200 && b > 100 && g < 150 -> "Pink"
        r > 100 && b > 150 && g < r -> "Purple"
        g > 150 && b > 150 && r < 100 -> "Cyan"
        r > 180 && g < 100 && b < 100 -> "Red"
        else -> "Custom"
    }
}

private fun suggestGlobalTokenName(
    color: ElementColorInfo,
    newHex: String,
): String {
    // ⭐ 1. If token exists and valid, use its name
    if (color.isToken && isValidKotlinIdentifier(color.name)) {
        return color.name
    }
    
    // ⭐ 2. Derive name from color.name
    val baseName = when {
        color.name.startsWith("Color(0x") -> ""
        color.name.startsWith("Color.") -> color.name.removePrefix("Color.")
        isValidKotlinIdentifier(color.name) -> color.name
        else -> ""
    }
    
    // ⭐ 3. Compute color name from newHex
    val colorFromHex = hexToColorName(newHex)
    
    // ⭐ 4. Compose name
    val candidate = if (baseName.isNotEmpty()) {
        "Success${baseName}${colorFromHex}"
    } else {
        "Success${colorFromHex}"
    }
    
    // ⭐ 5. Validate name
    return if (isValidKotlinIdentifier(candidate)) {
        candidate
    } else {
        "SuccessCustom${System.currentTimeMillis() % 1000}"
    }
}

private fun suggestLocalTokenName(
    elementName: String,
    newHex: String,
    color: ElementColorInfo,
): String {
    // ⭐ Clean elementName
    val cleanElement = elementName
        .replace(Regex("[^A-Za-z0-9_]"), "")
        .ifEmpty { "Element" }
    
    val colorName = hexToColorName(newHex)
    val candidate = "${cleanElement}${colorName}Accent"
    
    return if (isValidKotlinIdentifier(candidate)) {
        candidate
    } else {
        "Accent${System.currentTimeMillis() % 1000}"
    }
}

private fun propertyLabel(prop: String): String = when (prop.lowercase()) {
    "c1" -> "Primary Color (c1)"
    "c2" -> "Secondary Color (c2)"
    "background" -> "Background Color (background)"
    "color" -> "Color"
    "containercolor" -> "Container Color (containerColor)"
    "contentcolor" -> "Content Color (contentColor)"
    "tint" -> "Icon Tint (tint)"
    "textcolor" -> "Text Color (textColor)"
    "border" -> "Border Color (border)"
    else -> prop
}

@Composable
private fun ThemeDependentColorCard(
    color: ElementColorInfo,
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp)
            .clickable {
                BridgeState.showSnackbar("⚠️ This color follows app theme — cannot be edited directly")
            },
        shape = RoundedCornerShape(8.dp),
        color = Color(0xFFF3F4F6),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("🎨", fontSize = 18.sp)
                Spacer(Modifier.width(8.dp))
                Column {
                    Text(
                        text = propertyLabel(color.property),
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 14.sp,
                        color = Color(0xFF1E293B),
                    )
                    Text(
                        text = color.name,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace,
                        color = Color.Gray,
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
            Row(
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("⚠️", fontSize = 14.sp)
                Spacer(Modifier.width(4.dp))
                Text(
                    text = "Follows app theme — updates automatically",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFFE65100),
                )
            }
            Text(
                text = "For independent edits, use Split after converting",
                fontSize = 10.sp,
                color = Color.Gray,
                modifier = Modifier.padding(top = 4.dp),
            )
        }
    }
}

@Composable
private fun FocusColorRow(
    colorInfo: ElementColorInfo,
    onTapHeader: (() -> Unit)? = null,
    onPickColor: (String) -> Unit,
) {
    if (colorInfo.isThemeDependent) {
        ThemeDependentColorCard(color = colorInfo)
        return
    }

    val currentEffectiveHex = BridgeState.previewColors[colorInfo.name] ?: colorInfo.value
    var selectedHex by remember(currentEffectiveHex) { mutableStateOf(currentEffectiveHex) }

    val basePalette = listOf(
        "#1E3A8A", // Dark Blue
        "#3B82F6", // Blue
        "#10B981", // Green
        "#F59E0B", // Orange
        "#EF4444", // Red
        "#8B5CF6", // Purple
        "#EC4899", // Pink
        "#14B8A6", // Teal
        "#FFFFFF", // White
        "#1E293B", // Dark Slate
    )

    val palette = remember(colorInfo.value) {
        val clean = colorInfo.value.trim().uppercase()
        if (clean.startsWith("#") && basePalette.none { it.equals(clean, ignoreCase = true) }) {
            listOf(clean) + basePalette
        } else {
            basePalette
        }
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 10.dp)
    ) {
        // ⭐ Title and badge
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .then(
                    if (!colorInfo.isToken) Modifier.clickable { onTapHeader?.invoke() }
                    else Modifier
                ),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text(
                    text = "${propertyLabel(colorInfo.property)}:",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF1E293B)
                )

                if (!colorInfo.isToken) {
                    Text(
                        text = colorInfo.name,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                        fontFamily = FontFamily.Monospace,
                        color = Color(0xFF475569)
                    )
                }

                // ⭐ Status badge
                when {
                    colorInfo.isToken && colorInfo.isShared -> {
                        Surface(
                            shape = RoundedCornerShape(4.dp),
                            color = Color(0xFF6366F1).copy(alpha = 0.12f),
                        ) {
                            Text(
                                text = "🔗 Shared Token (${colorInfo.usageGlobal})",
                                fontSize = 10.sp,
                                color = Color(0xFF6366F1),
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            )
                        }
                    }
                    colorInfo.isToken -> {
                        Surface(
                            shape = RoundedCornerShape(4.dp),
                            color = Color(0xFF10B981).copy(alpha = 0.12f),
                        ) {
                            Text(
                                text = "🔗 Standalone Token",
                                fontSize = 10.sp,
                                color = Color(0xFF10B981),
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            )
                        }
                    }
                    else -> {
                        // ⭐ hardcoded
                        Surface(
                            shape = RoundedCornerShape(4.dp),
                            color = Color(0xFFE65100).copy(alpha = 0.12f),
                            modifier = Modifier.clickable {
                                onTapHeader?.invoke()
                            }
                        ) {
                            Text(
                                text = "⚠️ Hardcoded — Tap to Convert",
                                fontSize = 10.sp,
                                color = Color(0xFFE65100),
                                fontWeight = FontWeight.SemiBold,
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            )
                        }
                    }
                }
            }

            Text(
                text = selectedHex,
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF6366F1)
            )
        }

        Spacer(Modifier.height(8.dp))

        // ⭐ Color bar with highlight and scroll
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState())
                .padding(vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            palette.forEach { hex ->
                val isSelected = hex.equals(selectedHex, ignoreCase = true)
                val isWhiteOrLight = hex.equals("#FFFFFF", ignoreCase = true) || hex.equals("#F1F5F9", ignoreCase = true)
                Box(
                    modifier = Modifier
                        .size(40.dp)
                        .clip(CircleShape)
                        .background(hexToColor(hex))
                        .border(
                            width = if (isSelected) 3.dp else 1.dp,
                            color = if (isSelected) Color(0xFF6366F1) else Color.Gray.copy(alpha = 0.3f),
                            shape = CircleShape
                        )
                        .clickable {
                            selectedHex = hex
                            onPickColor(hex)
                        },
                    contentAlignment = Alignment.Center
                ) {
                    if (isSelected) {
                        Icon(
                            imageVector = Icons.Default.Check,
                            contentDescription = "Selected",
                            tint = if (isWhiteOrLight) Color(0xFF1E293B) else Color.White,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                }
            }
        }
    }
}

private fun parseHexColor(hex: String): Color = com.composebridge.agent.util.ColorUtils.parseHexColor(hex)

private fun hexToColor(hex: String): Color = com.composebridge.agent.util.ColorUtils.hexToColor(hex)

private fun performConvertHardcoded(
    color: ElementColorInfo,
    mode: String,  // "split" | "global"
) {
    if (BridgeState.syncInProgress) {
        BridgeState.showSnackbar("⏳ Sync in progress...")
        return
    }

    // ⭐ 1. Compute token name
    val elementName = BridgeState.elementComposableName
    val targetHex = BridgeState.hardcodedNewHex ?: color.value
    val suggestedName = if (mode == "split") {
        // ⭐ Dedicated to this element
        suggestLocalTokenName(elementName, targetHex, color)
    } else {
        // ⭐ Shared — generic name
        suggestGlobalTokenName(color, targetHex)
    }

    android.util.Log.i("ComposeBridge", "🎨 performConvertHardcoded:")
    android.util.Log.i("ComposeBridge", "   mode=$mode")
    android.util.Log.i("ComposeBridge", "   color=${color.name} ${color.value}")
    android.util.Log.i("ComposeBridge", "   suggestedName=$suggestedName")

    // ⭐ 2. Build occurrences JSON
    val occsJson = color.occurrencesInElement.joinToString(",", "[", "]") {
        """{"line":${it.line},"property":"${it.property}"}"""
    }

    // ⭐ 3. PendingEdit
    val edit = PendingEdit(
        id = java.util.UUID.randomUUID().toString(),
        type = if (mode == "split") "split_token" else "global_color",
        file = DesignModeRegistry.selectedSourceFile ?: "",
        line = color.lineInElement,
        property = color.property,
        oldValue = color.value,
        newValue = targetHex,  // ⭐ Value for conversion
        tokenName = suggestedName,
        timestamp = System.currentTimeMillis(),
        occurrencesJson = if (mode == "split") occsJson else null,
        occurrences = if (mode == "split") color.occurrencesInElement else emptyList(),
        originalToken = color.name,
        originalValue = color.value,
    )

    BridgeState.addPendingEdit(edit)
    BridgeState.hardcodedNewHex = null

    val modeText = if (mode == "split") "for this element" else "globally"
    BridgeState.showSnackbar(
        "📝 Added ($modeText) — ${BridgeState.pendingCount}\n⚠️ Rebuild required first time"
    )

    android.util.Log.i("ComposeBridge", "✅ Convert hardcoded added to queue")
}
