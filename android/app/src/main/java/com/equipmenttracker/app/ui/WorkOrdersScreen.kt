@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.equipmenttracker.app.ui

import android.app.Application
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.equipmenttracker.app.data.ApiClientFactory
import com.equipmenttracker.app.data.TokenStore
import com.equipmenttracker.app.data.WorkOrderSummaryDto
import com.equipmenttracker.app.ui.theme.statusColor
import kotlinx.coroutines.launch

class WorkOrdersViewModel(application: Application) : AndroidViewModel(application) {
    private val tokenStore = TokenStore(application)

    var workOrders by mutableStateOf<List<WorkOrderSummaryDto>>(emptyList())
        private set
    var isLoading by mutableStateOf(false)
        private set
    var errorMessage by mutableStateOf<String?>(null)
        private set

    fun load() {
        isLoading = true
        errorMessage = null
        viewModelScope.launch {
            try {
                val token = tokenStore.currentToken() ?: return@launch
                val api = ApiClientFactory.create(tokenStore.currentServerUrl())
                workOrders = api.listWorkOrders("Bearer $token").workOrders
                isLoading = false
            } catch (e: Exception) {
                isLoading = false
                errorMessage = "Couldn't load work orders: ${e.message ?: "check your connection"}"
            }
        }
    }
}

/** Same status-color semantics as elsewhere, but work order status isn't the maintenance
 * overdue/due_soon/ok vocabulary -- map it onto the same palette so the app stays consistent. */
private fun workOrderStatusColor(status: String) = when (status) {
    "open" -> statusColor("due_soon")
    "in_progress" -> statusColor("unknown")
    "completed" -> statusColor("ok")
    "cancelled" -> statusColor("unknown")
    else -> statusColor("unknown")
}

private fun workOrderStatusLabel(status: String) = when (status) {
    "open" -> "Open"
    "in_progress" -> "In progress"
    "completed" -> "Completed"
    "cancelled" -> "Cancelled"
    else -> status
}

@Composable
fun WorkOrdersScreen(
    onBack: () -> Unit,
    onOpenWorkOrder: (Int) -> Unit,
    viewModel: WorkOrdersViewModel = viewModel(),
) {
    LaunchedEffect(Unit) { viewModel.load() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Work orders") },
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
                viewModel.isLoading && viewModel.workOrders.isEmpty() ->
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
                viewModel.errorMessage != null -> Text(
                    viewModel.errorMessage.orEmpty(),
                    modifier = Modifier.align(Alignment.Center).padding(24.dp),
                    color = MaterialTheme.colorScheme.error,
                )
                viewModel.workOrders.isEmpty() -> Text(
                    "No open work orders right now",
                    modifier = Modifier.align(Alignment.Center),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                else -> LazyColumn(
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(viewModel.workOrders, key = { it.id }) { wo ->
                        WorkOrderRow(wo, onClick = { onOpenWorkOrder(wo.id) })
                    }
                }
            }
        }
    }
}

@Composable
private fun WorkOrderRow(wo: WorkOrderSummaryDto, onClick: () -> Unit) {
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(wo.title, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.titleMedium)
                Text(
                    workOrderStatusLabel(wo.status),
                    color = workOrderStatusColor(wo.status),
                    fontWeight = FontWeight.SemiBold,
                    style = MaterialTheme.typography.labelMedium,
                )
            }
            Text(
                wo.equipmentLabel + if (wo.assignedTo.isNotBlank()) " · ${wo.assignedTo}" else "",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (wo.equipmentDown) {
                Text(
                    "Equipment down",
                    color = statusColor("overdue"),
                    style = MaterialTheme.typography.labelSmall,
                )
            }
            if (wo.totalCost > 0) {
                Text("$${"%.2f".format(wo.totalCost)}", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
