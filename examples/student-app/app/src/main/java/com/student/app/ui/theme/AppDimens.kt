package com.student.app.ui.theme

import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.student.app.ui.bridge.BridgeDimensionRegistry

object AppDimens {
 val xs: Dp get() = BridgeDimensionRegistry.get("xs", 4.dp)
 val sm: Dp get() = BridgeDimensionRegistry.get("sm", 8.dp)
 val md: Dp get() = BridgeDimensionRegistry.get("md", 48.dp)
 val lg: Dp get() = BridgeDimensionRegistry.get("lg", 24.dp)
 val xl: Dp get() = BridgeDimensionRegistry.get("xl", 32.dp)

 val screenPadding: Dp get() = BridgeDimensionRegistry.get("screenPadding", 16.dp)

 val welcomeCardHeight: Dp get() = BridgeDimensionRegistry.get("welcomeCardHeight", 183.dp)
 val welcomeCardCorner: Dp get() = BridgeDimensionRegistry.get("welcomeCardCorner", 108.dp)
 val welcomeCardPadding: Dp get() = BridgeDimensionRegistry.get("welcomeCardPadding", 20.dp)

 val statCardHeight: Dp get() = BridgeDimensionRegistry.get("statCardHeight", 120.dp)
 val statCardCorner: Dp get() = BridgeDimensionRegistry.get("statCardCorner", 16.dp)
 val statCardIconSize: Dp get() = BridgeDimensionRegistry.get("statCardIconSize", 40.dp)
 val statCardIconInner: Dp get() = BridgeDimensionRegistry.get("statCardIconInner", 24.dp)

 val headerIconSize: Dp get() = BridgeDimensionRegistry.get("headerIconSize", 40.dp)
}