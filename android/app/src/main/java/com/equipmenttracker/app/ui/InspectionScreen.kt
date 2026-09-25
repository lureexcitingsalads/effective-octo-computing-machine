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
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
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
import androidx.compose.ui.draw.clip
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
import com.equipmenttracker.app.data.ChecklistItemDto
import com.equipmenttracker.app.data.TokenStore
import com.equipmenttracker.app.data.bodyOf
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonPrimitive
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import java.io.File

private val SIDES = listOf("front", "back", "left", "right")

class InspectionViewModel(application: Application) : AndroidViewModel(application) {
    private val tokenStore = TokenStore(application)

    var items by mutableStateOf<List<ChecklistItemDto>>(emptyList())
        private set
    var responses by mutableStateOf<Map<String, String>>(emptyMap())
        private set
    var itemComments by mutableStateOf<Map<String, String>>(emptyMap())
        private set
    var itemPhotos by mutableStateOf<Map<String, File>>(emptyMap())
        private set
    var sidePhotos by mutableStateOf<Map<String, File>>(emptyMap())
        private set
    var hoursAtInspection by mutableStateOf("")
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
        if (value != "issue") {
            itemComments = itemComments.toMutableMap().apply { remove(key) }
            itemPhotos = itemPhotos.toMutableMap().apply { remove(key) }
        }
    }

    fun setItemComment(key: String, value: String) {
        itemComments = itemComments.toMutableMap().apply { put(key, value) }
    }

    fun setItemPhoto(key: String, file: File) {
        itemPhotos = itemPhotos.toMutableMap().apply { put(key, file) }
    }

    fun setSidePhoto(side: String, file: File) {
        sidePhotos = sidePhotos.toMutableMap().apply { put(side, file) }
    }

    fun onHoursChange(value: String) { hoursAtInspection = value }
    fun onNotesChange(value: String) { notes = value }

    fun submit(equipmentId: Int) {
        isSubmitting = true
        errorMessage = null
        viewModelScope.launch {
            try {
                val token = tokenStore.currentToken() ?: return@launch
                val api = ApiClientFactory.create(tokenStore.currentServerUrl())

                // JsonObject.toString() already renders compact JSON text -- no need to round-trip
                // through Json.encodeToString, which can't infer a serializer for a raw JsonObject.
                val responsesJson = kotlinx.serialization.json.JsonObject(responses.mapValues { JsonPrimitive(it.value) }).toString()
                val commentsJson = kotlinx.serialization.json.JsonObject(itemComments.mapValues { JsonPrimitive(it.value) }).toString()

                val photoParts = itemPhotos.map { (key, file) -> filePart("photo_$key", file) } +
                    sidePhotos.map { (side, file) -> filePart("side_$side", file) }

                api.submitInspectionMultipart(
                    "Bearer $token",
                    equipmentId,
                    bodyOf(responsesJson),
                    bodyOf(commentsJson),
                    bodyOf(notes.trim()),
                    bodyOf(hoursAtInspection.trim()),
                    photoParts,
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

private fun filePart(fieldName: String, file: File): MultipartBody.Part {
    val body = file.asRequestBody("image/jpeg".toMediaType())
    return MultipartBody.Part.createFormData(fieldName, file.name, body)
}

private fun createImageFile(context: Context, prefix: String): File {
    val dir = File(context.cacheDir, "inspection_photos").apply { mkdirs() }
    return File.createTempFile("${prefix}_${System.currentTimeMillis()}_", ".jpg", dir)
}

@Composable
fun InspectionScreen(equipmentId: Int, onDone: () -> Unit, viewModel: InspectionViewModel = viewModel()) {
    val context = LocalContext.current
    var pendingKey by remember { mutableStateOf<String?>(null) }
    var pendingFile by remember { mutableStateOf<File?>(null) }

    val cameraLauncher = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { success ->
        val key = pendingKey
        val file = pendingFile
        if (success && key != null && file != null) {
            if (key.startsWith("item_")) viewModel.setItemPhoto(key.removePrefix("item_"), file)
            else if (key.startsWith("side_")) viewModel.setSidePhoto(key.removePrefix("side_"), file)
        }
        pendingKey = null
        pendingFile = null
    }

    fun launchCamera(key: String, filePrefix: String) {
        val file = createImageFile(context, filePrefix)
        pendingKey = key
        pendingFile = file
        val uri: Uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        cameraLauncher.launch(uri)
    }

    LaunchedEffect(Unit) { viewModel.load() }
    LaunchedEffect(viewModel.submitted) { if (viewModel.submitted) onDone() }

    Scaffold(topBar = { TopAppBar(title = { Text("Pre-shift inspection") }) }) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            if (viewModel.isLoading) {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
            } else {
                Column(modifier = Modifier.fillMaxSize()) {
                    LazyColumn(modifier = Modifier.weight(1f), contentPadding = PaddingValues(16.dp)) {
                        item {
                            OutlinedTextField(
                                value = viewModel.hoursAtInspection,
                                onValueChange = viewModel::onHoursChange,
                                label = { Text("Hour meter reading (optional)") },
                                singleLine = true,
                                modifier = Modifier.fillMaxWidth().padding(bottom = 4.dp),
                            )
                            Text(
                                "Enter this if you're looking at the meter -- it logs a fresh reading and updates the machine's status.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Spacer(Modifier.height(8.dp))
                        }
                        items(viewModel.items, key = { it.key }) { item ->
                            ChecklistRow(
                                item = item,
                                selected = viewModel.responses[item.key] ?: "na",
                                comment = viewModel.itemComments[item.key] ?: "",
                                photo = viewModel.itemPhotos[item.key],
                                onSelect = { viewModel.setResponse(item.key, it) },
                                onCommentChange = { viewModel.setItemComment(item.key, it) },
                                onTakePhoto = { launchCamera("item_${item.key}", item.key) },
                            )
                        }
                        item {
                            Spacer(Modifier.height(8.dp))
                            Text("Walkaround photos", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                            Text(
                                "Optional, but a quick photo of all four sides documents the machine's condition at shift start.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Spacer(Modifier.height(8.dp))
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                SIDES.forEach { side ->
                                    SidePhotoButton(
                                        label = side.replaceFirstChar { it.uppercase() },
                                        photo = viewModel.sidePhotos[side],
                                        onClick = { launchCamera("side_$side", side) },
                                    )
                                }
                            }
                            Spacer(Modifier.height(16.dp))
                            OutlinedTextField(
                                value = viewModel.notes,
                                onValueChange = viewModel::onNotesChange,
                                label = { Text("Notes (optional)") },
                                modifier = Modifier.fillMaxWidth(),
                                minLines = 2,
                            )
                        }
                    }
                    viewModel.errorMessage?.let {
                        Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(horizontal = 16.dp))
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
private fun ChecklistRow(
    item: ChecklistItemDto,
    selected: String,
    comment: String,
    photo: File?,
    onSelect: (String) -> Unit,
    onCommentChange: (String) -> Unit,
    onTakePhoto: () -> Unit,
) {
    Column(modifier = Modifier.padding(vertical = 10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(item.label, fontWeight = FontWeight.Medium, modifier = Modifier.weight(1f))
            if (item.critical) {
                Text(
                    "CRITICAL",
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                )
            }
        }
        Spacer(Modifier.height(6.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            SegmentButton("OK", selected == "ok") { onSelect("ok") }
            SegmentButton("Issue", selected == "issue") { onSelect("issue") }
            SegmentButton("N/A", selected == "na") { onSelect("na") }
        }
        if (selected == "issue") {
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = comment,
                onValueChange = onCommentChange,
                label = { Text("What's wrong?") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(6.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedButton(onClick = onTakePhoto) {
                    Icon(Icons.Default.CameraAlt, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text(if (photo != null) "Retake photo" else "Add photo")
                }
                if (photo != null) {
                    Spacer(Modifier.width(10.dp))
                    AsyncImage(
                        model = photo,
                        contentDescription = null,
                        contentScale = ContentScale.Crop,
                        modifier = Modifier.size(44.dp).clip(RoundedCornerShape(6.dp)),
                    )
                }
            }
        }
    }
}

@Composable
private fun SidePhotoButton(label: String, photo: File?, onClick: () -> Unit) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        if (photo != null) {
            Box {
                AsyncImage(
                    model = photo,
                    contentDescription = label,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.size(64.dp).clip(RoundedCornerShape(8.dp)),
                )
                Icon(
                    Icons.Default.Check,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.align(Alignment.TopEnd).size(18.dp),
                )
            }
            Spacer(Modifier.height(4.dp))
            OutlinedButton(onClick = onClick, modifier = Modifier.size(width = 64.dp, height = 32.dp)) {
                Text(label, style = MaterialTheme.typography.labelSmall)
            }
        } else {
            OutlinedButton(onClick = onClick, modifier = Modifier.size(64.dp)) {
                Icon(Icons.Default.CameraAlt, contentDescription = label, modifier = Modifier.size(18.dp))
            }
            Spacer(Modifier.height(4.dp))
            Text(label, style = MaterialTheme.typography.labelSmall)
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
