package com.fb.smartorder.util

import android.content.Context
import android.content.SharedPreferences

/**
 * Gestor de sesión y configuración local de hostelería (SharedPreferences).
 *
 * Almacena el estado de autenticación, el perfil activo del cocinero en turno,
 * el nombre del establecimiento, email y la URL base del servidor backend.
 */
object SessionManager {

    private const val PREFS_NAME = "fb_smartorder_session"
    private const val KEY_IS_LOGGED_IN = "key_is_logged_in"
    private const val KEY_USER_EMAIL = "key_user_email"
    private const val KEY_CHEF_NAME = "key_chef_name"
    private const val KEY_RESTAURANT_NAME = "key_restaurant_name"
    private const val KEY_SERVER_URL = "key_server_url"
    const val DEFAULT_SERVER_URL = "https://smartorder-api-z4or.onrender.com/"

    @Volatile
    var activeEmail: String = ""

    fun init(context: Context) {
        getUserEmail(context)
    }

    private fun getPrefs(context: Context): SharedPreferences {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    fun isLoggedIn(context: Context): Boolean {
        return getPrefs(context).getBoolean(KEY_IS_LOGGED_IN, false)
    }

    fun getUserEmail(context: Context): String {
        val email = getPrefs(context).getString(KEY_USER_EMAIL, "") ?: ""
        if (email.isNotBlank()) {
            activeEmail = email.trim().lowercase()
        }
        return email
    }

    fun getChefName(context: Context): String {
        return getPrefs(context).getString(KEY_CHEF_NAME, "Pablo Moncayo") ?: "Pablo Moncayo"
    }

    fun setChefName(context: Context, chefName: String) {
        getPrefs(context).edit().putString(KEY_CHEF_NAME, chefName.trim()).apply()
    }

    fun getRestaurantName(context: Context): String {
        return getPrefs(context).getString(KEY_RESTAURANT_NAME, "Restaurante El Faro") ?: "Restaurante El Faro"
    }

    fun setRestaurantName(context: Context, restaurantName: String) {
        getPrefs(context).edit().putString(KEY_RESTAURANT_NAME, restaurantName.trim()).apply()
    }

    fun getServerUrl(context: Context): String {
        val saved = getPrefs(context).getString(KEY_SERVER_URL, "") ?: ""
        return if (saved.isNotBlank()) saved else DEFAULT_SERVER_URL
    }

    fun setServerUrl(context: Context, serverUrl: String) {
        val clean = serverUrl.trim()
        val formatted = if (clean.isNotEmpty() && !clean.endsWith("/")) "$clean/" else clean
        getPrefs(context).edit().putString(KEY_SERVER_URL, formatted).apply()
    }

    fun saveSession(
        context: Context,
        chefName: String,
        restaurantName: String,
        email: String,
        serverUrl: String = ""
    ) {
        val cleanEmail = email.trim().lowercase()
        activeEmail = cleanEmail
        val editor = getPrefs(context).edit()
            .putBoolean(KEY_IS_LOGGED_IN, true)
            .putString(KEY_CHEF_NAME, chefName.trim())
            .putString(KEY_RESTAURANT_NAME, restaurantName.trim())
            .putString(KEY_USER_EMAIL, cleanEmail)

        if (serverUrl.trim().isNotEmpty()) {
            val formatted = if (serverUrl.trim().endsWith("/")) serverUrl.trim() else "${serverUrl.trim()}/"
            editor.putString(KEY_SERVER_URL, formatted)
        }
        editor.apply()
    }

    fun logout(context: Context) {
        activeEmail = ""
        getPrefs(context).edit()
            .putBoolean(KEY_IS_LOGGED_IN, false)
            .putString(KEY_USER_EMAIL, "")
            .apply()
    }
}
