package com.student.app.ui.pages

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.student.app.ui.components.DashboardHeader
import com.student.app.ui.components.FloatingBottomBar
import com.student.app.ui.components.HeroCard
import com.student.app.ui.components.SectionTitle
import com.student.app.ui.components.StatCard
import com.student.app.ui.theme.AppColors
import com.student.app.ui.theme.AppDimens

@Composable
fun DashboardPage(
 modifier: Modifier = Modifier,
) {
 Box(modifier = modifier.fillMaxSize()) {
 Column(
 modifier = Modifier
 .fillMaxSize()
 .verticalScroll(rememberScrollState())
 ) {
 Column(
 modifier = Modifier
 .fillMaxWidth()
 .background(AppColors.Primary)
 ) {
 DashboardHeader(
 name = "Siraj Abbas",
 level = "Level 3 - Engineering",
 )


 Spacer(Modifier.height(AppDimens.md))

 HeroCard(
 title = "✨ Siraj Abbas!",
 subtitle = "Academic ID: STD_14272200",
 progress = 0.0f,
 icon = Icons.Default.AutoAwesome,
 modifier = Modifier
 .fillMaxWidth()
 .padding(horizontal = AppDimens.screenPadding),
 )


 Spacer(Modifier.height(AppDimens.md))
 }

 Column(
 modifier = Modifier
 .fillMaxWidth()
 .padding(top = AppDimens.md, bottom = 100.dp)
 ) {
 Row(
 modifier = Modifier
 .fillMaxWidth()
 .padding(horizontal = AppDimens.screenPadding),
 horizontalArrangement = Arrangement.spacedBy(AppDimens.sm),
 ) {
 Box(modifier = Modifier.weight(1f)) {
 StatCard(
 icon = Icons.Default.EmojiEvents,
 accentColor = AppColors.AccentPurple,
 value = "1",
 label = " ",
 )
 }
 Box(modifier = Modifier.weight(1f)) {
 StatCard(
 icon = Icons.Default.Star,
 accentColor = AppColors.AccentOrange,
 value = "0",
 label = " ",
 )
 }
 Box(modifier = Modifier.weight(1f)) {
 StatCard(
 icon = Icons.Default.MenuBook,
 accentColor = AppColors.AccentGreen,
 value = "3",
 label = "Courses",
 )
 }
 }

 Spacer(Modifier.height(AppDimens.md))
 Row(
 modifier = Modifier
 .fillMaxWidth()
 .padding(horizontal = AppDimens.screenPadding),
 horizontalArrangement = Arrangement.spacedBy(AppDimens.sm),
 ) {
 Box(modifier = Modifier.weight(1f)) {
 StatCard(
 icon = Icons.Default.Book,
 accentColor = AppColors.AccentGreen,
 value = " ",
 label = " ",
 )
 }
 Box(modifier = Modifier.weight(1f)) {
 StatCard(
 icon = Icons.Default.PlayArrow,
 accentColor = AppColors.Primary,
 value = " ",
 label = " ",
 )
 }
 Box(modifier = Modifier.weight(1f)) {
 StatCard(
 icon = Icons.Default.BarChart,
 accentColor = AppColors.Primary,
 value = " ",
 label = "Lecture Schedule",
 )
 }
 }

 Spacer(Modifier.height(AppDimens.md))
 SectionTitle(
 text = "Courses List",
 )

 }
 }

 FloatingBottomBar(
 modifier = Modifier.align(Alignment.BottomCenter),
 )
 }
}