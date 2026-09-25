package com.equipmenttracker.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path
import java.io.File
import java.util.concurrent.TimeUnit

@Serializable
data class LoginRequest(val username: String, val password: String)

@Serializable
data class UserDto(
    val id: Int,
    val username: String,
    @SerialName("display_name") val displayName: String,
    val role: String,
)

@Serializable
data class LoginResponse(val token: String, val user: UserDto)

@Serializable
data class EquipmentSummaryDto(
    val id: Int,
    val label: String,
    val customer: String,
    val site: String? = null,
    val status: String,
    @SerialName("latest_hours") val latestHours: Double? = null,
    @SerialName("open_fault_count") val openFaultCount: Int,
    @SerialName("open_issue_count") val openIssueCount: Int,
)

@Serializable
data class EquipmentListResponse(val equipment: List<EquipmentSummaryDto>)

@Serializable
data class ForecastItemDto(
    @SerialName("task_name") val taskName: String,
    val status: String,
    @SerialName("hours_remaining") val hoursRemaining: Double? = null,
    @SerialName("forecast_date") val forecastDate: String? = null,
)

@Serializable
data class OpenIssueDto(
    val id: Int,
    val severity: String,
    val description: String,
    @SerialName("reported_by") val reportedBy: String,
    @SerialName("reported_at") val reportedAt: String,
)

@Serializable
data class EquipmentDetailDto(
    val id: Int,
    val label: String,
    val customer: String,
    val site: String? = null,
    val status: String,
    @SerialName("latest_hours") val latestHours: Double? = null,
    @SerialName("open_fault_count") val openFaultCount: Int,
    @SerialName("open_issue_count") val openIssueCount: Int,
    @SerialName("overall_status") val overallStatus: String,
    @SerialName("is_down") val isDown: Boolean,
    @SerialName("utilization_pct") val utilizationPct: Double? = null,
    @SerialName("lifecycle_signals") val lifecycleSignals: List<String> = emptyList(),
    val forecast: List<ForecastItemDto> = emptyList(),
    @SerialName("open_issues") val openIssues: List<OpenIssueDto> = emptyList(),
)

@Serializable
data class ChecklistItemDto(val key: String, val label: String, val critical: Boolean)

@Serializable
data class ChecklistResponse(val items: List<ChecklistItemDto>)

@Serializable
data class InspectionRequest(val responses: Map<String, String>, val notes: String)

@Serializable
data class InspectionResponse(val id: Int, @SerialName("has_issues") val hasIssues: Boolean)

@Serializable
data class IssueCreatedResponse(val id: Int)

interface ApiService {
    @POST("api/login/")
    suspend fun login(@Body request: LoginRequest): LoginResponse

    @GET("api/equipment/")
    suspend fun listEquipment(@Header("Authorization") auth: String): EquipmentListResponse

    @GET("api/equipment/{id}/")
    suspend fun getEquipment(@Header("Authorization") auth: String, @Path("id") id: Int): EquipmentDetailDto

    @GET("api/checklist/")
    suspend fun getChecklist(@Header("Authorization") auth: String): ChecklistResponse

    @POST("api/equipment/{id}/inspections/")
    suspend fun submitInspection(
        @Header("Authorization") auth: String,
        @Path("id") id: Int,
        @Body request: InspectionRequest,
    ): InspectionResponse

    @Multipart
    @POST("api/equipment/{id}/issues/")
    suspend fun reportIssue(
        @Header("Authorization") auth: String,
        @Path("id") id: Int,
        @Part("severity") severity: RequestBody,
        @Part("description") description: RequestBody,
        @Part photos: List<MultipartBody.Part>,
    ): IssueCreatedResponse
}

object ApiClientFactory {
    private val json = Json { ignoreUnknownKeys = true }
    private val cache = mutableMapOf<String, ApiService>()

    fun create(baseUrl: String): ApiService = cache.getOrPut(baseUrl) {
        val normalizedBase = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
        val logging = HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BASIC }
        val client = OkHttpClient.Builder()
            .addInterceptor(logging)
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(20, TimeUnit.SECONDS)
            .build()
        val contentType = "application/json".toMediaType()
        Retrofit.Builder()
            .baseUrl(normalizedBase)
            .client(client)
            .addConverterFactory(json.asConverterFactory(contentType))
            .build()
            .create(ApiService::class.java)
    }
}

fun bodyOf(value: String): RequestBody = value.toRequestBody("text/plain".toMediaType())

fun photoPart(file: File): MultipartBody.Part {
    val requestBody = file.asRequestBody("image/jpeg".toMediaType())
    return MultipartBody.Part.createFormData("photos", file.name, requestBody)
}
