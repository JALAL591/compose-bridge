package {{PACKAGE}}.ui.panels

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.composebridge.agent.ComposeBridgeAgent
import com.composebridge.agent.DesignModeRegistry
import {{PACKAGE}}.ui.bridge.BridgeDimensionRegistry
import {{PACKAGE}}.ui.bridge.BridgeThemeRegistry

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GlobalPanels() {
    var showElementPanel by remember { mutableStateOf(false) }

    LaunchedEffect(DesignModeRegistry.selectedSourceFile) {
        val file = DesignModeRegistry.selectedSourceFile
        val line = DesignModeRegistry.selectedSourceLine
        if (file != null && line > 0) {
            showElementPanel = true
        }
    }

    if (showElementPanel) {
        ModalBottomSheet(
            onDismissRequest = {
                showElementPanel = false
                DesignModeRegistry.selectedSourceFile = null
                DesignModeRegistry.selectedSourceLine = 0
            }
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
                    .verticalScroll(rememberScrollState())
            ) {
                Text(
                    text = "🎯 Live Editing",
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    text = "${DesignModeRegistry.selectedSourceFile}:${DesignModeRegistry.selectedSourceLine}",
                    fontSize = 12.sp,
                    color = Color.Gray
                )
                Spacer(Modifier.height(20.dp))

                // ═══ Colors ═══
                SectionTitle("🎨 Colors")

                ColorPickerRow(
                    label = "Primary Color",
                    tokenName = "Primary",
                    currentHex = "#1E3A8A",
                )

                ColorPickerRow(
                    label = "Orange Accent",
                    tokenName = "AccentOrange",
                    currentHex = "#F59E0B",
                )

                ColorPickerRow(
                    label = "Green Accent",
                    tokenName = "AccentGreen",
                    currentHex = "#10B981",
                )

                ColorPickerRow(
                    label = "Purple Accent",
                    tokenName = "AccentPurple",
                    currentHex = "#8B5CF6",
                )

                Spacer(Modifier.height(20.dp))

                // ═══ Dimensions ═══
                SectionTitle("📏 Dimensions")

                TokenSlider(
                    tokenName = "welcomeCardHeight",
                    label = "Welcome Card Height",
                    defaultValue = 160f,
                )

                TokenSlider(
                    tokenName = "md",
                    label = "General Padding",
                    defaultValue = 16f,
                )

                TokenSlider(
                    tokenName = "welcomeCardCorner",
                    label = "Corner Radius",
                    defaultValue = 20f,
                )

                Spacer(Modifier.height(16.dp))

                OutlinedButton(
                    onClick = {
                        BridgeDimensionRegistry.clearAll()
                        BridgeThemeRegistry.clearAll()
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("♻️ Reset")
                }
                Spacer(Modifier.height(8.dp))
            }
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(
        text = text,
        fontSize = 15.sp,
        fontWeight = FontWeight.Bold,
        color = Color(0xFF6366F1),
        modifier = Modifier.padding(vertical = 8.dp)
    )
}

@Composable
private fun ColorPickerRow(
    label: String,
    tokenName: String,
    currentHex: String,
) {
    var selectedHex by remember { mutableStateOf(currentHex) }

    val palette = listOf(
        "#1E3A8A", // Dark Blue
        "#3B82F6", // Blue
        "#10B981", // Green
        "#F59E0B", // Orange
        "#EF4444", // Red
        "#8B5CF6", // Purple
        "#EC4899", // Pink
        "#14B8A6", // Teal
    )

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(text = label, fontSize = 13.sp, fontWeight = FontWeight.Medium)
            Text(
                text = selectedHex,
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF6366F1)
            )
        }
        Spacer(Modifier.height(6.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            palette.forEach { hex ->
                val isSelected = hex.equals(selectedHex, ignoreCase = true)
                Box(
                    modifier = Modifier
                        .size(32.dp)
                        .background(hexToColor(hex), CircleShape)
                        .border(
                            width = if (isSelected) 3.dp else 1.dp,
                            color = if (isSelected) Color.Black else Color(0xFFDDDDDD),
                            shape = CircleShape
                        )
                        .clickable {
                            selectedHex = hex
                            // 1) Live update
                            BridgeThemeRegistry.setColorHex(tokenName, hex)
                            // 2) Save to file
                            println("[Panel] 🎨 Committing $tokenName = $hex")
                            ComposeBridgeAgent.sendStateUpdate(
                                property = "AppColors.$tokenName",
                                value = hex,
                            )
                        }
                )
            }
        }
    }
}

@Composable
private fun TokenSlider(
    tokenName: String,
    label: String,
    defaultValue: Float,
) {
    var value by remember { mutableStateOf(defaultValue) }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(text = label, fontSize = 13.sp, fontWeight = FontWeight.Medium)
            Text(
                text = "${value.toInt()}.dp",
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF6366F1)
            )
        }
        Spacer(Modifier.height(4.dp))
        Slider(
            value = value,
            onValueChange = {
                value = it
                BridgeDimensionRegistry.setOverride(tokenName, it.dp)
            },
            onValueChangeFinished = {
                val intValue = value.toInt().toString()
                println("[Panel] 💾 Committing $tokenName = $intValue")
                ComposeBridgeAgent.sendTokenDefault(tokenName, intValue)
            },
            valueRange = 0f..400f,
            steps = 399,
        )
    }
}

private fun hexToColor(hex: String): Color {
    return try {
        val cleaned = hex.removePrefix("#").removePrefix("0x").removePrefix("0X")
        val argb = if (cleaned.length == 6) "FF$cleaned" else cleaned
        Color(argb.toLong(16))
    } catch (e: Exception) {
        Color.Gray
    }
}
