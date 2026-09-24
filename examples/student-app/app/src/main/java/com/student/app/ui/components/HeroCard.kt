package com.student.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.student.app.ui.theme.AppColors
import com.student.app.ui.theme.AppDimens

@Composable
fun HeroCard(
 title: String,
 subtitle: String,
 progress: Float,
 icon: ImageVector,
 modifier: Modifier = Modifier,
) {
 val gradient = Brush.linearGradient(
 colors = listOf(
 AppColors.Primary,
 AppColors.PrimaryGradientEnd,
 )
 )

 Box(
 modifier = modifier
 .fillMaxWidth()
 .height(AppDimens.welcomeCardHeight)
 .background(gradient, RoundedCornerShape(AppDimens.welcomeCardCorner))
 .padding(AppDimens.welcomeCardPadding)
 ) {
 Column(
 modifier = Modifier.fillMaxSize(),
 verticalArrangement = Arrangement.SpaceBetween,
 ) {
 Row(
 modifier = Modifier.fillMaxWidth(),
 horizontalArrangement = Arrangement.SpaceBetween,
 verticalAlignment = Alignment.CenterVertically,
 ) {
 Text(
 text = title,
 fontSize = 20.sp,
 fontWeight = FontWeight.Bold,
 color = Color.White,
 )
 Icon(
 imageVector = icon,
 contentDescription = null,
 tint = AppColors.AccentOrange,
 modifier = Modifier.size(28.dp),
 )
 }

 Box(
 modifier = Modifier
 .background(Color.White.copy(alpha = 0.15f), RoundedCornerShape(8.dp))
 .padding(horizontal = 12.dp, vertical = 6.dp)
 ) {
 Text(
 text = subtitle,
 fontSize = 12.sp,
 color = Color.White.copy(alpha = 0.9f),
 )
 }

 Row(
 modifier = Modifier.fillMaxWidth(),
 verticalAlignment = Alignment.CenterVertically,
 ) {
 Text(
 text = "${(progress * 100).toInt()}%",
 fontSize = 14.sp,
 fontWeight = FontWeight.Bold,
 color = Color.White,
 )
 Spacer(Modifier.width(12.dp))
 LinearProgressIndicator(
 progress = progress,
 color = Color.White,
 trackColor = Color.White.copy(alpha = 0.2f),
 modifier = Modifier
 .weight(1f)
 .height(6.dp),
 )
 }
 }
 }
}