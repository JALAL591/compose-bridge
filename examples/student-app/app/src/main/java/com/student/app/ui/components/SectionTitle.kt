package com.student.app.ui.components

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import com.student.app.ui.theme.AppColors
import com.student.app.ui.theme.AppDimens

@Composable
fun SectionTitle(
 text: String,
 modifier: Modifier = Modifier,
) {
 Text(
 text = text,
 fontSize = 18.sp,
 fontWeight = FontWeight.Bold,
 color = AppColors.TextPrimary,
 modifier = modifier.padding(
 horizontal = AppDimens.screenPadding,
 vertical = AppDimens.md,
 ),
 )
}