# -*- coding: utf-8 -*-
from pathlib import Path


def generate_hero_card_kt(package, source_root):
    content = f"""package {package}.ui.components

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
import {package}.ui.theme.AppColors
import {package}.ui.theme.AppDimens

@Composable
fun HeroCard(
    title: String,
    subtitle: String,
    progress: Float,
    icon: ImageVector,
    modifier: Modifier = Modifier,
) {{
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
    ) {{
        Column(
            modifier = Modifier.fillMaxSize(),
            verticalArrangement = Arrangement.SpaceBetween,
        ) {{
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {{
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
            }}

            Box(
                modifier = Modifier
                    .background(Color.White.copy(alpha = 0.15f), RoundedCornerShape(8.dp))
                    .padding(horizontal = 12.dp, vertical = 6.dp)
            ) {{
                Text(
                    text = subtitle,
                    fontSize = 12.sp,
                    color = Color.White.copy(alpha = 0.9f),
                )
            }}

            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {{
                Text(
                    text = "${{(progress * 100).toInt()}}%",
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
            }}
        }}
    }}
}}
"""
    path = Path(source_root) / "ui/components/HeroCard.kt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate_stat_card_kt(package, source_root):
    content = f"""package {package}.ui.components

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
import {package}.ui.theme.AppColors
import {package}.ui.theme.AppDimens

@Composable
fun StatCard(
    icon: ImageVector,
    accentColor: Color,
    value: String,
    label: String,
    modifier: Modifier = Modifier,
) {{
    Surface(
        modifier = modifier.height(AppDimens.statCardHeight),
        color = AppColors.Surface,
        shape = RoundedCornerShape(AppDimens.statCardCorner),
        shadowElevation = 4.dp,
    ) {{
        Box(modifier = Modifier.fillMaxSize()) {{
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
            ) {{
                Box(
                    modifier = Modifier
                        .size(AppDimens.statCardIconSize)
                        .background(accentColor.copy(alpha = 0.15f), CircleShape),
                    contentAlignment = Alignment.Center,
                ) {{
                    Icon(
                        imageVector = icon,
                        contentDescription = null,
                        tint = accentColor,
                        modifier = Modifier.size(AppDimens.statCardIconInner),
                    )
                }}
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
            }}

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
        }}
    }}
}}
"""
    path = Path(source_root) / "ui/components/StatCard.kt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate_section_title_kt(package, source_root):
    content = f"""package {package}.ui.components

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import {package}.ui.theme.AppColors
import {package}.ui.theme.AppDimens

@Composable
fun SectionTitle(
    text: String,
    modifier: Modifier = Modifier,
) {{
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
}}
"""
    path = Path(source_root) / "ui/components/SectionTitle.kt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate_dashboard_header_kt(package, source_root):
    content = f"""package {package}.ui.components

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
import {package}.ui.theme.AppDimens

@Composable
fun DashboardHeader(
    name: String,
    level: String,
    modifier: Modifier = Modifier,
) {{
    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(AppDimens.screenPadding),
        verticalAlignment = Alignment.CenterVertically,
    ) {{
        Box(
            modifier = Modifier
                .size(AppDimens.headerIconSize)
                .background(Color.White.copy(alpha = 0.15f), CircleShape),
            contentAlignment = Alignment.Center,
        ) {{
            Icon(
                imageVector = Icons.Default.Person,
                contentDescription = null,
                tint = Color.White,
                modifier = Modifier.size(24.dp),
            )
        }}

        Spacer(Modifier.width(AppDimens.sm))

        Column(modifier = Modifier.weight(1f)) {{
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
        }}

        HeaderIcon(Icons.Default.Notifications)
        HeaderIcon(Icons.Default.Wifi)
        HeaderIcon(Icons.Default.CloudDownload)
        HeaderIcon(Icons.Default.DarkMode)
    }}
}}

@Composable
private fun HeaderIcon(icon: ImageVector) {{
    Box(
        modifier = Modifier
            .padding(start = AppDimens.sm)
            .size(AppDimens.headerIconSize)
            .background(Color.White.copy(alpha = 0.15f), CircleShape),
        contentAlignment = Alignment.Center,
    ) {{
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = Color.White,
            modifier = Modifier.size(18.dp),
        )
    }}
}}
"""
    path = Path(source_root) / "ui/components/DashboardHeader.kt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate_floating_bottom_bar_kt(package, source_root):
    content = f"""package {package}.ui.components

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
import {package}.ui.theme.AppColors

@Composable
fun FloatingBottomBar(
    modifier: Modifier = Modifier,
) {{
    Box(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 12.dp),
        contentAlignment = Alignment.BottomCenter,
    ) {{
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .height(70.dp),
            color = Color.White,
            shape = RoundedCornerShape(35.dp),
            shadowElevation = 12.dp,
        ) {{
            Row(
                modifier = Modifier.fillMaxSize(),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically,
            ) {{
                BottomNavItem(Icons.Default.Person, "Settings", AppColors.TextSecondary)
                BottomNavItem(Icons.Default.ChatBubble, "Chat", AppColors.TextSecondary)
                Spacer(Modifier.width(60.dp))
                BottomNavItem(Icons.Default.BarChart, "Stats", AppColors.TextSecondary)
                BottomNavItem(Icons.Default.Home, "Home", AppColors.AccentOrange)
            }}
        }}

        Box(
            modifier = Modifier
                .align(Alignment.TopCenter)
                .offset(y = (-20).dp)
                .size(64.dp)
                .background(AppColors.Primary, CircleShape),
            contentAlignment = Alignment.Center,
        ) {{
            Icon(
                imageVector = Icons.Default.RocketLaunch,
                contentDescription = null,
                tint = Color.White,
                modifier = Modifier.size(28.dp),
            )
        }}
    }}
}}

@Composable
private fun BottomNavItem(
    icon: ImageVector,
    label: String,
    tint: Color,
) {{
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {{
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
    }}
}}
"""
    path = Path(source_root) / "ui/components/FloatingBottomBar.kt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


KOTLIN_COMPONENT_GENERATORS = {
    "HeroCard": generate_hero_card_kt,
    "StatCard": generate_stat_card_kt,
    "StatGrid": generate_stat_card_kt,
    "SectionTitle": generate_section_title_kt,
    "DashboardHeader": generate_dashboard_header_kt,
    "FloatingBottomBar": generate_floating_bottom_bar_kt,
}


def generate_components_from_json(screen_json, source_root):
    package = screen_json["package"]

    used_types = set()

    if "header" in screen_json:
        used_types.add(screen_json["header"]["type"])
    if "hero" in screen_json:
        used_types.add(screen_json["hero"]["type"])
    if "bottom_bar" in screen_json:
        used_types.add(screen_json["bottom_bar"]["type"])

    for comp in screen_json.get("components", []):
        used_types.add(comp["type"])

    generated = []
    for comp_type in used_types:
        generator = KOTLIN_COMPONENT_GENERATORS.get(comp_type)
        if generator:
            generator(package, source_root)
            generated.append(comp_type)

    print(f"  Generated: {', '.join(sorted(generated))}")
