package com.equipmenttracker.app.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "equipment_tracker_prefs")

/** Persists the signed-in session and the chosen server address across app restarts. */
class TokenStore(private val context: Context) {
    private object Keys {
        val SERVER_URL = stringPreferencesKey("server_url")
        val TOKEN = stringPreferencesKey("auth_token")
        val DISPLAY_NAME = stringPreferencesKey("display_name")
        val ROLE = stringPreferencesKey("role")
    }

    val serverUrl: Flow<String> = context.dataStore.data.map { it[Keys.SERVER_URL] ?: DEFAULT_SERVER_URL }
    val token: Flow<String?> = context.dataStore.data.map { it[Keys.TOKEN] }
    val displayName: Flow<String?> = context.dataStore.data.map { it[Keys.DISPLAY_NAME] }
    val role: Flow<String?> = context.dataStore.data.map { it[Keys.ROLE] }

    suspend fun currentServerUrl(): String = serverUrl.first()
    suspend fun currentToken(): String? = token.first()

    suspend fun saveServerUrl(url: String) {
        context.dataStore.edit { it[Keys.SERVER_URL] = url.trimEnd('/') }
    }

    suspend fun saveSession(token: String, displayName: String, role: String) {
        context.dataStore.edit {
            it[Keys.TOKEN] = token
            it[Keys.DISPLAY_NAME] = displayName
            it[Keys.ROLE] = role
        }
    }

    suspend fun clearSession() {
        context.dataStore.edit {
            it.remove(Keys.TOKEN)
            it.remove(Keys.DISPLAY_NAME)
            it.remove(Keys.ROLE)
        }
    }

    companion object {
        const val DEFAULT_SERVER_URL = "https://equipment-tracker-a8t1.onrender.com"
    }
}
