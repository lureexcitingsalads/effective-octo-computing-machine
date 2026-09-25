@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.equipmenttracker.app.ui

import android.app.Application
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.equipmenttracker.app.data.ApiClientFactory
import com.equipmenttracker.app.data.EquipmentSummaryDto
import com.equipmenttracker.app.data.TokenStore
import com.equipmenttracker.app.ui.theme.statusColor
import kotlinx.coroutines.launch
import retrofit2.HttpException

class EquipmentListViewModel(application: Application) : AndroidViewModel(application) {
    private val tokenStore = TokenStore(application)

    var equipment by mutableStateOf<List<EquipmentSummaryDto>>(emptyList())
        private set
    var isLoading by mutableStateOf(false)
        private set
    var errorMessage by mutableStateOf<String?>(null)
        private set

    fun load(onUnauthorized: () -> Unit) {
        isLoading = true
        errorMessage = null
        viewModelScope.launch {
            val token = tokenStore.currentToken()
            if (token == null) {
                isLoading = false
                onUnauthorized()
                return@launch
            }
            try {
                val api = ApiClientFactory.create(tokenStore.currentServerUrl())
                val response = api.listEquipment("Bearer $token")
                equipment = response.equipment
                isLoading = false
            } catch (e: HttpException) {
                isLoading = false
                if (e.code() == 401) {
                    tokenStore.clearSession()
                    onUnauthorized()
                } else {
                    errorMessage = "Server error (${e.code()})"
                }
            } catch (e: Exception) {
                isLoading = false
                errorMessage = "Couldn't load equipment: ${e.message ?: "check your connection"}"
            }
        }
    }

    fun logout(onLoggedOut: () -> Unit) {
        viewModelScope.launch {
            tokenStore.clearSession()
            onLoggedOut()
        }
    }
}

@Composable
fun EquipmentListScreen(
    onOpenEquipment: (Int) -> Unit,
    onOpenWorkOrders: () -> Unit,
    onLoggedOut: () -> Unit,
    viewModel: EquipmentListViewModel = viewModel(),
) {
    LaunchedEffect(Unit) { viewModel.load(onUnauthorized = onLoggedOut) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Equipment") },
                actions = {
                    IconButton(onClick = onOpenWorkOrders) {
                        Icon(Icons.Default.Build, contentDescription = "Work orders")
                    }
                    IconButton(onClick = { viewModel.load(onUnauthorized = onLoggedOut) }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                    TextButton(onClick = { viewModel.logout(onLoggedOut) }) { Text("Sign out") }
                },
            )
        },
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            when {
                viewModel.isLoading && viewModel.equipment.isEmpty() -> {
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
                }
                viewModel.errorMessage != null -> {
                    Text(
                        viewModel.errorMessage.orEmpty(),
                        modifier = Modifier.align(Alignment.Center).padding(24.dp),
                        color = MaterialTheme.colorScheme.error,
                    )
                }
                else -> {
                    LazyColumn(
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        items(viewModel.equipment, key = { it.id }) { item ->
                            EquipmentRow(item, onClick = { onOpenEquipment(item.id) })
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun EquipmentRow(item: EquipmentSummaryDto, onClick: () -> Unit) {
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(12.dp)
                    .clip(CircleShape)
                    .background(statusColor(item.status)),
            )
            Spacer(Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(item.label, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.titleMedium)
                Text(
                    listOfNotNull(item.customer, item.site).joinToString(" · "),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Column(horizontalAlignment = Alignment.End) {
                item.latestHours?.let { Text("${it.toInt()} h", style = MaterialTheme.typography.bodySmall) }
                if (item.openFaultCount > 0) {
                    Text(
                        "${item.openFaultCount} fault${if (item.openFaultCount == 1) "" else "s"}",
                        color = statusColor("overdue"),
                        style = MaterialTheme.typography.labelSmall,
                    )
                }
                if (item.openIssueCount > 0) {
                    Text(
                        "${item.openIssueCount} issue${if (item.openIssueCount == 1) "" else "s"}",
                        color = statusColor("due_soon"),
                        style = MaterialTheme.typography.labelSmall,
                    )
                }
            }
        }
    }
}
