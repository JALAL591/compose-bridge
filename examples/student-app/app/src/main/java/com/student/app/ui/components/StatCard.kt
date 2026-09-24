package com.student.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.student.app.ui.theme.AppColors
import com.student.app.ui.theme.AppDimens

@Composable
fun StatCard(
 icon: ImageVector,
 accentColor: Color,
 value: String,
 label: String,
 modifier: Modifier = Modifier,
) {
 Surface(
 modifier = modifier.height(AppDimens.statCardHeight),
 color = AppColors.Surface,
 shape = RoundedCornerShape(AppDimens.statCardCorner),
 shadowElevation = 4.dp,
 ) {
 Box(modifier = Modifier.fillMaxSize()) {
 Icon(
 imageVector = icon,
 contentDescription = null,
 tint = accentColor.copy(alpha = 0.06f),
 modifier = Modifier
 .size(100.dp)
 .align(Alignment.CenterEnd)
 .offset(x = 20.dp, y = 20.dp),
 )

 Column(
 modifier = Modifier
 .fillMaxSize()
 .padding(AppDimens.md),
 horizontalAlignment = Alignment.CenterHorizontally,
 verticalArrangement = Arrangement.Center,
 ) {
 Box(
 modifier = Modifier
 .size(AppDimens.statCardIconSize)
 .background(accentColor.copy(alpha = 0.15f), CircleShape),
 contentAlignment = Alignment.Center,
 ) {
 Icon(
 imageVector = icon,
 contentDescription = null,
 tint = accentColor,
 modifier = Modifier.size(AppDimens.statCardIconInner),
 )
 }
 Spacer(Modifier.height(AppDimens.sm))
 Text(
 text = value,
 fontSize = 24.sp,
 fontWeight = FontWeight.Bold,
 color = AppColors.TextPrimary,
 )
 Text(
 text = label,
 fontSize = 12.sp,
 color = AppColors.TextSecondary,
 )
 }

 Box(
 modifier = Modifier
 .align(Alignment.BottomCenter)
 .fillMaxWidth()
 .height(4.dp)
 .background(
 color = accentColor,
 shape = RoundedCornerShape(
 bottomStart = AppDimens.statCardCorner,
 bottomEnd = AppDimens.statCardCorner,
 )
 )
 )
 }
 }
}