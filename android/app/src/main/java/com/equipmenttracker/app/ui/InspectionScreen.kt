@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.equipmenttracker.app.ui

import android.app.Application
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import com.equipmenttracker.app.data.ChecklistItemDto
import com.equipmenttracker.app.data.InspectionRequest
import com.equipmenttracker.app.data.TokenStore
import kotlinx.coroutines.launch

class InspectionViewModel(application: Application) : AndroidViewModel(application) {
    private val tokenStore = TokenStore(application)

    var items by mutableStateOf<List<ChecklistItemDto>>(emptyList())
        private set
    var responses by mutableStateOf<Map<String, String>>(emptyMap())
        private set
    var notes by mutableStateOf("")
        private set
    var isLoading by mutableStateOf(false)
        private set
    var isSubmitting by mutableStateOf(false)
        private set
    var errorMessage by mutableStateOf<String?>(null)
        private set
    var submitted by mutableStateOf(false)
        private set

    fun load() {
        isLoading = true
        viewModelScope.launch {
            try {
                val token = tokenStore.currentToken() ?: return@launch
                val api = ApiClientFactory.create(tokenStore.currentServerUrl())
                items = api.getChecklist("Bearer $token").items
                responses = items.associate { it.key to "na" }
                isLoading = false
            } catch (e: Exception) {
                isLoading = false
                errorMessage = "Couldn't load checklist: ${e.message ?: "check your connection"}"
            }
        }
    }

    fun setResponse(key: String, value: String) {
        responses = responses.toMutableMap().apply { put(key, value) }
    }

    fun onNotesChange(value: String) { notes = value }

    fun submit(equipmentId: Int) {
        isSubmitting = true
        errorMessage = null
        viewModelScope.launch {
            try {
                val token = tokenStore.currentToken() ?: return@launch
                val api = ApiClientFactory.create(tokenStore.currentServerUrl())
                api.submitInspection("Bearer $token", equipmentId, InspectionRequest(responses, notes.trim()))
                isSubmitting = false
                submitted = true
            } catch (e: Exception) {
                isSubmitting = false
                errorMessage = "Couldn't submit: ${e.message ?: "check your connection"}"
            }
        }
    }
}

@Composable
fun InspectionScreen(equipmentId: Int, onDone: () -> Unit, viewModel: InspectionViewModel = viewModel()) {
    LaunchedEffect(Unit) { viewModel.load() }
    LaunchedEffect(viewModel.submitted) { if (viewModel.submitted) onDone() }

    Scaffold(topBar = { TopAppBar(title = { Text("Pre-shift inspection") }) }) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            if (viewModel.isLoading) {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
            } else {
                Column(modifier = Modifier.fillMaxSize()) {
                    LazyColumn(modifier = Modifier.weight(1f), contentPadding = PaddingValues(16.dp)) {
                        items(viewModel.items, key = { it.key }) { item ->
                            ChecklistRow(
                                item = item,
                                selected = viewModel.responses[item.key] ?: "na",
                                onSelect = { viewModel.setResponse(item.key, it) },
                            )
                        }
                        item {
                            OutlinedTextField(
                                value = viewModel.notes,
                                onValueChange = viewModel::onNotesChange,
                                label = { Text("Notes (optional)") },
                                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                                minLines = 2,
                            )
                        }
                    }
                    viewModel.errorMessage?.let {
                        Text(
                            it,
                            color = MaterialTheme.colorScheme.error,
                            modifier = Modifier.padding(horizontal = 16.dp),
                        )
                    }
                    Button(
                        onClick = { viewModel.submit(equipmentId) },
                        enabled = !viewModel.isSubmitting,
                        modifier = Modifier.fillMaxWidth().padding(16.dp).height(48.dp),
                    ) {
                        Text(if (viewModel.isSubmitting) "Submitting…" else "Submit inspection")
                    }
                }
            }
        }
    }
}

@Composable
private fun ChecklistRow(item: ChecklistItemDto, selected: String, onSelect: (String) -> Unit) {
    Column(modifier = Modifier.padding(vertical = 10.dp)) {
        Text(item.label, fontWeight = FontWeight.Medium)
        Spacer(Modifier.height(6.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            SegmentButton("OK", selected == "ok") { onSelect("ok") }
            SegmentButton("Issue", selected == "issue") { onSelect("issue") }
            SegmentButton("N/A", selected == "na") { onSelect("na") }
        }
    }
}

@Composable
private fun RowScope.SegmentButton(label: String, selected: Boolean, onClick: () -> Unit) {
    if (selected) {
        Button(onClick = onClick, modifier = Modifier.weight(1f)) { Text(label) }
    } else {
        OutlinedButton(onClick = onClick, modifier = Modifier.weight(1f)) { Text(label) }
    }
}
