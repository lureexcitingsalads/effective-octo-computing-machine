@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.equipmenttracker.app.ui

import android.app.Application
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.equipmenttracker.app.data.AddCommentRequest
import com.equipmenttracker.app.data.AddLaborLineRequest
import com.equipmenttracker.app.data.AddPartLineRequest
import com.equipmenttracker.app.data.ApiClientFactory
import com.equipmenttracker.app.data.PartDto
import com.equipmenttracker.app.data.TokenStore
import com.equipmenttracker.app.data.WorkOrderCommentDto
import com.equipmenttracker.app.data.WorkOrderDetailDto
import com.equipmenttracker.app.data.WorkOrderStatusRequest
import kotlinx.coroutines.launch

class WorkOrderDetailViewModel(application: Application) : AndroidViewModel(application) {
    private val tokenStore = TokenStore(application)

    var detail by mutableStateOf<WorkOrderDetailDto?>(null)
        private set
    var parts by mutableStateOf<List<PartDto>>(emptyList())
        private set
    var isLoading by mutableStateOf(false)
        private set
    var isUpdating by mutableStateOf(false)
        private set
    var errorMessage by mutableStateOf<String?>(null)
        private set

    fun load(workOrderId: Int) {
        isLoading = true
        errorMessage = null
        viewModelScope.launch {
            try {
                val token = tokenStore.currentToken() ?: return@launch
                val api = ApiClientFactory.create(tokenStore.currentServerUrl())
                detail = api.getWorkOrder("Bearer $token", workOrderId)
                isLoading = false
                parts = runCatching { api.listParts("Bearer $token").parts }.getOrDefault(emptyList())
            } catch (e: Exception) {
                isLoading = false
                errorMessage = "Couldn't load this work order: ${e.message ?: "check your connection"}"
            }
        }
    }

    fun setStatus(workOrderId: Int, status: String) {
        isUpdating = true
        viewModelScope.launch {
            try {
                val token = tokenStore.currentToken() ?: return@launch
                val api = ApiClientFactory.create(tokenStore.currentServerUrl())
                api.updateWorkOrderStatus("Bearer $token", workOrderId, WorkOrderStatusRequest(status))
                isUpdating = false
                load(workOrderId)
            } catch (e: Exception) {
                isUpdating = false
                errorMessage = "Couldn't update status: ${e.message ?: "check your connection"}"
            }
        }
    }

    fun addLabor(workOrderId: Int, technician: String, hours: Double, rate: Double, note: String) {
        isUpdating = true
        viewModelScope.launch {
            try {
                val token = tokenStore.currentToken() ?: return@launch
                val api = ApiClientFactory.create(tokenStore.currentServerUrl())
                api.addLaborLine(
                    "Bearer $token", workOrderId,
                    AddLaborLineRequest(technician, hours, rate, note),
                )
                isUpdating = false
                load(workOrderId)
            } catch (e: Exception) {
                isUpdating = false
                errorMessage = "Couldn't add labor: ${e.message ?: "check your connection"}"
            }
        }
    }

    fun addPart(workOrderId: Int, partId: Int?, partName: String, quantity: Double, unitCost: Double?) {
        isUpdating = true
        viewModelScope.launch {
            try {
                val token = tokenStore.currentToken() ?: return@launch
                val api = ApiClientFactory.create(tokenStore.currentServerUrl())
                api.addPartLine(
                    "Bearer $token", workOrderId,
                    AddPartLineRequest(partId = partId, partName = partName, quantity = quantity, unitCost = unitCost),
                )
                isUpdating = false
                load(workOrderId)
            } catch (e: Exception) {
                isUpdating = false
                errorMessage = "Couldn't add part: ${e.message ?: "check your connection"}"
            }
        }
    }

    fun addComment(workOrderId: Int, text: String) {
        isUpdating = true
        viewModelScope.launch {
            try {
                val token = tokenStore.currentToken() ?: return@launch
                val api = ApiClientFactory.create(tokenStore.currentServerUrl())
                api.addWorkOrderComment("Bearer $token", workOrderId, AddCommentRequest(text))
                isUpdating = false
                load(workOrderId)
            } catch (e: Exception) {
                isUpdating = false
                errorMessage = "Couldn't add comment: ${e.message ?: "check your connection"}"
            }
        }
    }
}

@Composable
fun WorkOrderDetailScreen(
    workOrderId: Int,
    onBack: () -> Unit,
    viewModel: WorkOrderDetailViewModel = viewModel(),
) {
    LaunchedEffect(workOrderId) { viewModel.load(workOrderId) }
    var showLaborDialog by remember { mutableStateOf(false) }
    var showPartDialog by remember { mutableStateOf(false) }
    val detail = viewModel.detail

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(detail?.title ?: "Work order") },
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
                viewModel.errorMessage != null && detail == null -> Text(
                    viewModel.errorMessage.orEmpty(),
                    modifier = Modifier.align(Alignment.Center).padding(24.dp),
                    color = MaterialTheme.colorScheme.error,
                )
                detail != null -> WorkOrderDetailContent(
                    detail = detail,
                    isUpdating = viewModel.isUpdating,
                    errorMessage = viewModel.errorMessage,
                    onSetStatus = { viewModel.setStatus(workOrderId, it) },
                    onAddLaborClick = { showLaborDialog = true },
                    onAddPartClick = { showPartDialog = true },
                    onAddComment = { viewModel.addComment(workOrderId, it) },
                )
            }
        }
    }

    if (showLaborDialog) {
        AddLaborDialog(
            onDismiss = { showLaborDialog = false },
            onConfirm = { technician, hours, rate, note ->
                viewModel.addLabor(workOrderId, technician, hours, rate, note)
                showLaborDialog = false
            },
        )
    }
    if (showPartDialog) {
        AddPartDialog(
            availableParts = viewModel.parts,
            onDismiss = { showPartDialog = false },
            onConfirm = { partId, partName, quantity, unitCost ->
                viewModel.addPart(workOrderId, partId, partName, quantity, unitCost)
                showPartDialog = false
            },
        )
    }
}

@Composable
private fun WorkOrderDetailContent(
    detail: WorkOrderDetailDto,
    isUpdating: Boolean,
    errorMessage: String?,
    onSetStatus: (String) -> Unit,
    onAddLaborClick: () -> Unit,
    onAddPartClick: () -> Unit,
    onAddComment: (String) -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) {
        Text(detail.equipmentLabel + " · " + detail.customer, style = MaterialTheme.typography.bodyMedium)
        if (detail.assignedTo.isNotBlank()) {
            Text("Assigned to ${detail.assignedTo}", style = MaterialTheme.typography.bodySmall)
        }
        if (detail.equipmentDown) {
            Text(
                "Equipment down while this is open",
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
            )
        }
        if (detail.description.isNotBlank()) {
            Spacer(Modifier.height(8.dp))
            Text(detail.description, style = MaterialTheme.typography.bodyMedium)
        }

        Spacer(Modifier.height(16.dp))
        when (detail.status) {
            "open" -> Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button(onClick = { onSetStatus("in_progress") }, enabled = !isUpdating, modifier = Modifier.weight(1f)) {
                    Text("Start work")
                }
                OutlinedButton(onClick = { onSetStatus("cancelled") }, enabled = !isUpdating, modifier = Modifier.weight(1f)) {
                    Text("Cancel")
                }
            }
            "in_progress" -> Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button(onClick = { onSetStatus("completed") }, enabled = !isUpdating, modifier = Modifier.weight(1f)) {
                    Text("Mark complete")
                }
                OutlinedButton(onClick = { onSetStatus("cancelled") }, enabled = !isUpdating, modifier = Modifier.weight(1f)) {
                    Text("Cancel")
                }
            }
            else -> Text(
                if (detail.status == "completed") "Completed" else "Cancelled",
                fontWeight = FontWeight.SemiBold,
                style = MaterialTheme.typography.titleMedium,
            )
        }

        errorMessage?.let {
            Spacer(Modifier.height(8.dp))
            Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        }

        Spacer(Modifier.height(20.dp))
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp)) {
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("Labor", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                    TextButton(onClick = onAddLaborClick) { Text("+ Add") }
                }
                detail.laborLines.forEach { line ->
                    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                        Column {
                            Text(line.technician, style = MaterialTheme.typography.bodyMedium)
                            Text(
                                "${line.hours}h @ $${"%.2f".format(line.rate)}${if (line.note.isNotBlank()) " · ${line.note}" else ""}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        Text("$${"%.2f".format(line.lineTotal)}", style = MaterialTheme.typography.bodyMedium)
                    }
                }
                Spacer(Modifier.height(4.dp))
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("Labor total", fontWeight = FontWeight.SemiBold)
                    Text("$${"%.2f".format(detail.laborTotal)}", fontWeight = FontWeight.SemiBold)
                }
            }
        }

        Spacer(Modifier.height(12.dp))
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp)) {
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("Parts", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                    TextButton(onClick = onAddPartClick) { Text("+ Add") }
                }
                detail.partLines.forEach { line ->
                    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("${line.partName} ×${line.quantity}", style = MaterialTheme.typography.bodyMedium)
                        Text("$${"%.2f".format(line.lineTotal)}", style = MaterialTheme.typography.bodyMedium)
                    }
                }
                Spacer(Modifier.height(4.dp))
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("Parts total", fontWeight = FontWeight.SemiBold)
                    Text("$${"%.2f".format(detail.partsTotal)}", fontWeight = FontWeight.SemiBold)
                }
            }
        }

        Spacer(Modifier.height(12.dp))
        Row(modifier = Modifier.fillMaxWidth().padding(horizontal = 4.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("Total cost", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
            Text(
                "$${"%.2f".format(detail.totalCost)}",
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.titleMedium,
            )
        }

        Spacer(Modifier.height(12.dp))
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("Comments", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                detail.comments.forEach { comment -> CommentRow(comment) }
                if (detail.comments.isEmpty()) {
                    Text(
                        "No comments yet.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 6.dp),
                    )
                }
                Spacer(Modifier.height(8.dp))
                CommentInput(onAddComment)
            }
        }
    }
}

@Composable
private fun CommentRow(comment: WorkOrderCommentDto) {
    Column(modifier = Modifier.padding(vertical = 6.dp)) {
        Text(
            comment.author + " · " + comment.createdAt.take(16).replace("T", " "),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(comment.text, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun CommentInput(onAddComment: (String) -> Unit) {
    var text by remember { mutableStateOf("") }
    Row(verticalAlignment = Alignment.Bottom) {
        OutlinedTextField(
            value = text,
            onValueChange = { text = it },
            label = { Text("Add a comment") },
            modifier = Modifier.weight(1f),
            minLines = 1,
        )
        Spacer(Modifier.width(8.dp))
        Button(onClick = {
            if (text.isNotBlank()) {
                onAddComment(text.trim())
                text = ""
            }
        }) { Text("Post") }
    }
}

@Composable
private fun AddLaborDialog(onDismiss: () -> Unit, onConfirm: (String, Double, Double, String) -> Unit) {
    var technician by remember { mutableStateOf("") }
    var hours by remember { mutableStateOf("") }
    var rate by remember { mutableStateOf("120") }
    var note by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Add labor") },
        text = {
            Column {
                OutlinedTextField(
                    value = technician,
                    onValueChange = { technician = it },
                    label = { Text("Technician (defaults to you)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = hours,
                    onValueChange = { hours = it },
                    label = { Text("Hours") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = rate,
                    onValueChange = { rate = it },
                    label = { Text("Rate ($/hr)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it },
                    label = { Text("Note (optional)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = {
                val h = hours.toDoubleOrNull()
                val r = rate.toDoubleOrNull() ?: 120.0
                if (h != null) onConfirm(technician, h, r, note)
            }) { Text("Add") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun AddPartDialog(
    availableParts: List<PartDto>,
    onDismiss: () -> Unit,
    onConfirm: (Int?, String, Double, Double?) -> Unit,
) {
    var selectedPart by remember { mutableStateOf<PartDto?>(null) }
    var expanded by remember { mutableStateOf(false) }
    var partName by remember { mutableStateOf("") }
    var quantity by remember { mutableStateOf("1") }
    var unitCost by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Add part") },
        text = {
            Column {
                if (availableParts.isNotEmpty()) {
                    Box {
                        OutlinedButton(onClick = { expanded = true }, modifier = Modifier.fillMaxWidth()) {
                            Text(
                                selectedPart?.let { "${it.name} (${it.quantityOnHand.toInt()} on hand)" }
                                    ?: "Pick from inventory (optional)",
                            )
                        }
                        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                            DropdownMenuItem(
                                text = { Text("— free-text part below —") },
                                onClick = { selectedPart = null; expanded = false },
                            )
                            availableParts.forEach { part ->
                                DropdownMenuItem(
                                    text = { Text("${part.name} (${part.quantityOnHand.toInt()} on hand)") },
                                    onClick = {
                                        selectedPart = part
                                        unitCost = part.unitCost.toString()
                                        expanded = false
                                    },
                                )
                            }
                        }
                    }
                    Spacer(Modifier.height(8.dp))
                }
                OutlinedTextField(
                    value = partName,
                    onValueChange = { partName = it },
                    label = { Text(if (selectedPart != null) "Part name (optional override)" else "Part name") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = quantity,
                    onValueChange = { quantity = it },
                    label = { Text("Quantity") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = unitCost,
                    onValueChange = { unitCost = it },
                    label = { Text("Unit cost ($)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = {
                val q = quantity.toDoubleOrNull() ?: 1.0
                val c = unitCost.toDoubleOrNull()
                if (selectedPart != null || partName.isNotBlank()) {
                    onConfirm(selectedPart?.id, partName, q, c)
                }
            }) { Text("Add") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}
