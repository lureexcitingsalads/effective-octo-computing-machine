@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.equipmenttracker.app.ui

import android.app.Application
import android.content.Context
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage
import com.equipmenttracker.app.data.ApiClientFactory
import com.equipmenttracker.app.data.TokenStore
import com.equipmenttracker.app.data.bodyOf
import com.equipmenttracker.app.data.photoPart
import kotlinx.coroutines.launch
import java.io.File

class ReportIssueViewModel(application: Application) : AndroidViewModel(application) {
    private val tokenStore = TokenStore(application)

    var severity by mutableStateOf("medium")
        private set
    var description by mutableStateOf("")
        private set
    var photoFiles by mutableStateOf<List<File>>(emptyList())
        private set
    var isSubmitting by mutableStateOf(false)
        private set
    var errorMessage by mutableStateOf<String?>(null)
        private set
    var submitted by mutableStateOf(false)
        private set

    fun onSeverityChange(value: String) { severity = value }
    fun onDescriptionChange(value: String) { description = value }
    fun addPhoto(file: File) { photoFiles = photoFiles + file }
    fun removePhoto(file: File) { photoFiles = photoFiles - file }

    fun submit(equipmentId: Int) {
        if (description.isBlank()) {
            errorMessage = "Describe the issue first"
            return
        }
        isSubmitting = true
        errorMessage = null
        viewModelScope.launch {
            try {
                val token = tokenStore.currentToken() ?: return@launch
                val api = ApiClientFactory.create(tokenStore.currentServerUrl())
                api.reportIssue(
                    "Bearer $token",
                    equipmentId,
                    bodyOf(severity),
                    bodyOf(description.trim()),
                    photoFiles.map { photoPart(it) },
                )
                isSubmitting = false
                submitted = true
            } catch (e: Exception) {
                isSubmitting = false
                errorMessage = "Couldn't submit: ${e.message ?: "check your connection"}"
            }
        }
    }
}

private fun createImageFile(context: Context): File {
    val dir = File(context.cacheDir, "issue_photos").apply { mkdirs() }
    return File.createTempFile("issue_${System.currentTimeMillis()}_", ".jpg", dir)
}

@Composable
fun ReportIssueScreen(equipmentId: Int, onDone: () -> Unit, viewModel: ReportIssueViewModel = viewModel()) {
    val context = LocalContext.current
    var pendingPhotoFile by remember { mutableStateOf<File?>(null) }

    val cameraLauncher = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { success ->
        val file = pendingPhotoFile
        if (success && file != null) viewModel.addPhoto(file)
        pendingPhotoFile = null
    }

    LaunchedEffect(viewModel.submitted) { if (viewModel.submitted) onDone() }

    Scaffold(topBar = { TopAppBar(title = { Text("Report an issue") }) }) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
        ) {
            Text("Severity", fontWeight = FontWeight.Medium)
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("low" to "Low", "medium" to "Medium", "high" to "High").forEach { (value, label) ->
                    FilterChip(
                        selected = viewModel.severity == value,
                        onClick = { viewModel.onSeverityChange(value) },
                        label = { Text(label) },
                    )
                }
            }

            Spacer(Modifier.height(16.dp))
            OutlinedTextField(
                value = viewModel.description,
                onValueChange = viewModel::onDescriptionChange,
                label = { Text("What's wrong?") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 4,
            )

            Spacer(Modifier.height(16.dp))
            Text("Photos (optional)", fontWeight = FontWeight.Medium)
            Spacer(Modifier.height(8.dp))
            val rowCount = (viewModel.photoFiles.size / 3) + 1
            LazyVerticalGrid(
                columns = GridCells.Fixed(3),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth().height((rowCount * 98).dp),
            ) {
                items(viewModel.photoFiles) { file ->
                    Box(modifier = Modifier.size(90.dp)) {
                        AsyncImage(
                            model = file,
                            contentDescription = null,
                            contentScale = ContentScale.Crop,
                            modifier = Modifier.fillMaxSize(),
                        )
                        IconButton(
                            onClick = { viewModel.removePhoto(file) },
                            modifier = Modifier.align(Alignment.TopEnd).size(24.dp),
                        ) {
                            Icon(Icons.Default.Close, contentDescription = "Remove", tint = Color.White)
                        }
                    }
                }
                item {
                    OutlinedButton(
                        onClick = {
                            val file = createImageFile(context)
                            pendingPhotoFile = file
                            val uri: Uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
                            cameraLauncher.launch(uri)
                        },
                        shape = RoundedCornerShape(8.dp),
                        modifier = Modifier.size(90.dp),
                    ) {
                        Icon(Icons.Default.CameraAlt, contentDescription = "Take photo")
                    }
                }
            }

            viewModel.errorMessage?.let {
                Spacer(Modifier.height(12.dp))
                Text(it, color = MaterialTheme.colorScheme.error)
            }

            Spacer(Modifier.height(24.dp))
            Button(
                onClick = { viewModel.submit(equipmentId) },
                enabled = !viewModel.isSubmitting,
                modifier = Modifier.fillMaxWidth().height(48.dp),
            ) {
                Text(if (viewModel.isSubmitting) "Submitting…" else "Submit")
            }
        }
    }
}
