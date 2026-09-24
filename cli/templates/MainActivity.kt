package {{PACKAGE}}

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.composebridge.agent.BridgeState
import com.composebridge.agent.ComposeBridgeAgent
import com.composebridge.agent.DesignModeRegistry
import {{PACKAGE}}.ui.bridge.BridgeDimensionRegistry
import {{PACKAGE}}.ui.bridge.BridgeThemeRegistry
import {{PACKAGE}}.ui.pages.DashboardPage
import {{PACKAGE}}.ui.panels.GlobalPanels
import {{PACKAGE}}.ui.theme.AppColors

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        BridgeState.onThemeColorUpdate = { key, hex ->
            BridgeThemeRegistry.setColorHex(key, hex)
        }
        BridgeState.onDimensionOverride = { key, value ->
            BridgeDimensionRegistry.setOverride(key, value.dp)
        }

        ComposeBridgeAgent.start("ws://127.0.0.1:8711")

        setContent {
            MaterialTheme {
                Surface(color = AppColors.Background) {
                    ComposeBridgeAgent.Root {
                        Box(modifier = Modifier.fillMaxSize()) {
                            DashboardPage()
                            DesignModeButton(
                                modifier = Modifier
                                    .align(Alignment.TopEnd)
                                    .padding(16.dp)
                            )
                            GlobalPanels()
                        }
                    }
                }
            }
        }

        window.decorView.post {
            ComposeBridgeAgent.attachOverlay(this)
        }
    }

    override fun onDestroy() {
        ComposeBridgeAgent.detachOverlay()
        ComposeBridgeAgent.stop()
        super.onDestroy()
    }
}

@Composable
private fun DesignModeButton(modifier: Modifier = Modifier) {
    val isActive = DesignModeRegistry.isActive

    FloatingActionButton(
        onClick = {
            DesignModeRegistry.toggle()
        },
        containerColor = if (isActive) Color(0xFFE53935) else Color(0xFF6366F1),
        shape = CircleShape,
        modifier = modifier,
    ) {
        Icon(
            imageVector = if (isActive) Icons.Default.Close else Icons.Default.Build,
            contentDescription = null,
            tint = Color.White,
        )
    }
}
