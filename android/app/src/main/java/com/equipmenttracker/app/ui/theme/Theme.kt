package com.equipmenttracker.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Same indigo accent as the web app's 2026-09-22 visual refresh, so the two clients feel
// like one product rather than two unrelated apps.
val Indigo = Color(0xFF4F46E5)
val IndigoLight = Color(0xFF6366F1)
val StatusRed = Color(0xFFDC2626)
val StatusAmber = Color(0xFFD97706)
val StatusGreen = Color(0xFF16A34A)
val StatusGray = Color(0xFF6B7280)
val SurfaceLight = Color(0xFFF8FAFC)
val SurfaceDark = Color(0xFF0F172A)

private val LightColors = lightColorScheme(
    primary = Indigo,
    onPrimary = Color.White,
    secondary = Indigo,
    background = SurfaceLight,
    surface = Color.White,
)

private val DarkColors = darkColorScheme(
    primary = IndigoLight,
    onPrimary = Color.White,
    secondary = IndigoLight,
    background = SurfaceDark,
    surface = Color(0xFF1E293B),
)

private val AppTypography = Typography()

@Composable
fun EquipmentTrackerTheme(content: @Composable () -> Unit) {
    val colors = if (isSystemInDarkTheme()) DarkColors else LightColors
    MaterialTheme(colorScheme = colors, typography = AppTypography, content = content)
}

/** Same status semantics as the web app: red/amber/green/gray for overdue/due_soon/ok/unknown. */
fun statusColor(status: String): Color = when (status) {
    "overdue" -> StatusRed
    "due_soon" -> StatusAmber
    "ok" -> StatusGreen
    else -> StatusGray
}
