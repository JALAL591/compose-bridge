package com.student.app.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

val AppTypography = Typography(
 headlineLarge = TextStyle(
 fontWeight = FontWeight.Bold,
 fontSize = 28.sp,
 letterSpacing = 0.sp,
 ),
 headlineMedium = TextStyle(
 fontWeight = FontWeight.Bold,
 fontSize = 22.sp,
 letterSpacing = 0.sp,
 ),
 bodyLarge = TextStyle(
 fontWeight = FontWeight.Normal,
 fontSize = 16.sp,
 lineHeight = 24.sp,
 letterSpacing = 0.15.sp,
 ),
 bodySmall = TextStyle(
 fontWeight = FontWeight.Normal,
 fontSize = 12.sp,
 lineHeight = 16.sp,
 letterSpacing = 0.4.sp,
 ),
)