@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.equipmenttracker.app.ui

import android.app.Application
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.equipmenttracker.app.data.ApiClientFactory
import com.equipmenttracker.app.data.EquipmentDetailDto
import com.equipmenttracker.app.data.TokenStore
import com.equipmenttracker.app.ui.theme.statusColor
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

class EquipmentDetailViewModel(application: Application) : AndroidViewModel(application) {
    private val tokenStore = TokenStore(application)

    var detail by mutableStateOf<EquipmentDetailDto?>(null)
        private set
    var isLoading by mutableStateOf(false)
        private set
    var errorMessage by mutableStateOf<String?>(null)
        private set
    var isOperator by mutableStateOf(false)
        private set

    fun load(equipmentId: Int) {
        isLoading = true
        errorMessage = null
        viewModelScope.launch {
            try {
                val token = tokenStore.currentToken() ?: return@launch
                isOperator = tokenStore.role.first() == "operator"
                val api = ApiClientFactory.create(tokenStore.currentServerUrl())
                detail = api.getEquipment("Bearer $token", equipmentId)
                isLoading = false
            } catch (e: Exception) {
                isLoading = false
                errorMessage = "Couldn't load this machine: ${e.message ?: "check your connection"}"
            }
        }
    }
}

@Composable
fun EquipmentDetailScreen(
    equipmentId: Int,
    onBack: () -> Unit,
    onNewInspection: () -> Unit,
    onReportIssue: () -> Unit,
    viewModel: EquipmentDetailViewModel = viewModel(),
) {
    LaunchedEffect(equipmentId) { viewModel.load(equipmentId) }
    val detail = viewModel.detail

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(detail?.label ?: "Equipment") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            when {
                viewModel.isLoading && detail == null ->
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
                viewModel.errorMessage != null -> Text(
                    viewModel.errorMessage.orEmpty(),
                    modifier = Modifier.align(Alignment.Center).padding(24.dp),
                    color = MaterialTheme.colorScheme.error,
                )
                detail != null -> EquipmentDetailContent(detail, viewModel.isOperator, onNewInspection, onReportIssue)
            }
        }
    }
}

@Composable
private fun EquipmentDetailContent(
    detail: EquipmentDetailDto,
    isOperator: Boolean,
    onNewInspection: () -> Unit,
    onReportIssue: () -> Unit,
) {
    LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item {
            Surface(
                color = statusColor(detail.overallStatus),
                shape = RoundedCornerShape(16.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Text(
                        heroLabel(detail),
                        color = Color.White,
                        fontWeight = FontWeight.Bold,
                        style = MaterialTheme.typography.titleLarge,
                    )
                    Text(
                        detail.customer + (detail.site?.let { " · $it" } ?: ""),
                        color = Color.White.copy(alpha = 0.9f),
                    )
                    Spacer(Modifier.height(16.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(24.dp)) {
                        StatBlock("Hours", detail.latestHours?.let { "${it.toInt()}" } ?: "—")
                        StatBlock("Faults", "${detail.openFaultCount}")
                        StatBlock("Issues", "${detail.openIssueCount}")
                        StatBlock("Util.", detail.utilizationPct?.let { "$it%" } ?: "—")
                    }
                }
            }
        }

        if (detail.lifecycleSignals.isNotEmpty()) {
            item {
                SectionCard(title = "Worth a look: replacement economics") {
                    detail.lifecycleSignals.forEach { signal ->
                        Text(
                            "• $signal",
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier.padding(vertical = 4.dp),
                        )
                    }
                }
            }
        }

        item {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                Button(onClick = onNewInspection, modifier = Modifier.weight(1f)) { Text("New inspection") }
                if (!isOperator) {
                    OutlinedButton(onClick = onReportIssue, modifier = Modifier.weight(1f)) { Text("Report issue") }
                }
            }
        }

        if (detail.openIssues.isNotEmpty()) {
            item {
                SectionCard(title = "Open issues") {
                    detail.openIssues.forEach { issue ->
                        Column(modifier = Modifier.padding(vertical = 6.dp)) {
                            Text(
                                "${issue.severity.uppercase()} · ${issue.reportedBy}",
                                style = MaterialTheme.typography.labelMedium,
                                color = statusColor(if (issue.severity == "high") "overdue" else "due_soon"),
                            )
                            Text(issue.description, style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
            }
        }

        if (detail.forecast.isNotEmpty()) {
            item {
                SectionCard(title = "Maintenance forecast") {
                    detail.forecast.forEach { f ->
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                        ) {
                            Text(f.taskName, style = MaterialTheme.typography.bodyMedium)
                            Text(
                                f.hoursRemaining?.let { "${it}h" } ?: f.status,
                                color = statusColor(f.status),
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.SemiBold,
                            )
                        }
                    }
                }
            }
        }
    }
}

private fun heroLabel(detail: EquipmentDetailDto): String = when {
    detail.isDown -> "Down for maintenance"
    detail.overallStatus == "overdue" -> "Needs attention"
    detail.overallStatus == "due_soon" -> "Due soon"
    detail.overallStatus == "ok" -> "Running well"
    else -> "No service history yet"
}

@Composable
private fun StatBlock(label: String, value: String) {
    Column {
        Text(value, color = Color.White, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
        Text(label, color = Color.White.copy(alpha = 0.85f), style = MaterialTheme.typography.labelSmall)
    }
}

@Composable
private fun SectionCard(title: String, content: @Composable ColumnScope.() -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(title, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            content()
        }
    }
}
