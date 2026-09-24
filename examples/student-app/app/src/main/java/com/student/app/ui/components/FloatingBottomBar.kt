package com.student.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.BarChart
import androidx.compose.material.icons.filled.ChatBubble
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.RocketLaunch
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

@Composable
fun FloatingBottomBar(
 modifier: Modifier = Modifier,
) {
 Box(
 modifier = modifier
 .fillMaxWidth()
 .padding(horizontal = 16.dp, vertical = 12.dp),
 contentAlignment = Alignment.BottomCenter,
 ) {
 Surface(
 modifier = Modifier
 .fillMaxWidth()
 .height(70.dp),
 color = Color.White,
 shape = RoundedCornerShape(35.dp),
 shadowElevation = 12.dp,
 ) {
 Row(
 modifier = Modifier.fillMaxSize(),
 horizontalArrangement = Arrangement.SpaceEvenly,
 verticalAlignment = Alignment.CenterVertically,
 ) {
 BottomNavItem(Icons.Default.Person, " ", AppColors.TextSecondary)
 BottomNavItem(Icons.Default.ChatBubble, " ", AppColors.TextSecondary)
 Spacer(Modifier.width(60.dp))
 BottomNavItem(Icons.Default.BarChart, " ", AppColors.TextSecondary)
 BottomNavItem(Icons.Default.Home, "Home", AppColors.AccentOrange)
 }
 }

 Box(
 modifier = Modifier
 .align(Alignment.TopCenter)
 .offset(y = (-20).dp)
 .size(64.dp)
 .background(AppColors.Primary, CircleShape),
 contentAlignment = Alignment.Center,
 ) {
 Icon(
 imageVector = Icons.Default.RocketLaunch,
 contentDescription = null,
 tint = Color.White,
 modifier = Modifier.size(28.dp),
 )
 }
 }
}

@Composable
private fun BottomNavItem(
 icon: ImageVector,
 label: String,
 tint: Color,
) {
 Column(
 horizontalAlignment = Alignment.CenterHorizontally,
 verticalArrangement = Arrangement.Center,
 ) {
 Icon(
 imageVector = icon,
 contentDescription = null,
 tint = tint,
 modifier = Modifier.size(22.dp),
 )
 Spacer(Modifier.height(4.dp))
 Text(
 text = label,
 fontSize = 10.sp,
 color = tint,
 fontWeight = FontWeight.Medium,
 )
 }
}