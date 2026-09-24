package com.student.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CloudDownload
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.student.app.ui.theme.AppDimens

@Composable
fun DashboardHeader(
 name: String,
 level: String,
 modifier: Modifier = Modifier,
) {
 Row(
 modifier = modifier
 .fillMaxWidth()
 .padding(AppDimens.screenPadding),
 verticalAlignment = Alignment.CenterVertically,
 ) {
 Box(
 modifier = Modifier
 .size(AppDimens.headerIconSize)
 .background(Color.White.copy(alpha = 0.15f), CircleShape),
 contentAlignment = Alignment.Center,
 ) {
 Icon(
 imageVector = Icons.Default.Person,
 contentDescription = null,
 tint = Color.White,
 modifier = Modifier.size(24.dp),
 )
 }

 Spacer(Modifier.width(AppDimens.sm))

 Column(modifier = Modifier.weight(1f)) {
 Text(
 text = name,
 fontSize = 16.sp,
 fontWeight = FontWeight.Bold,
 color = Color.White,
 )
 Text(
 text = level,
 fontSize = 12.sp,
 color = Color.White.copy(alpha = 0.7f),
 )
 }

 HeaderIcon(Icons.Default.Notifications)
 HeaderIcon(Icons.Default.Wifi)
 HeaderIcon(Icons.Default.CloudDownload)
 HeaderIcon(Icons.Default.DarkMode)
 }
}

@Composable
private fun HeaderIcon(icon: ImageVector) {
 Box(
 modifier = Modifier
 .padding(start = AppDimens.sm)
 .size(AppDimens.headerIconSize)
 .background(Color.White.copy(alpha = 0.15f), CircleShape),
 contentAlignment = Alignment.Center,
 ) {
 Icon(
 imageVector = icon,
 contentDescription = null,
 tint = Color.White,
 modifier = Modifier.size(18.dp),
 )
 }
}