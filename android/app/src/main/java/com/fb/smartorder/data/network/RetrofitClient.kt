package com.fb.smartorder.data.network

import android.content.Context
import com.fb.smartorder.util.SessionManager
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object RetrofitClient {

    private var activeBaseUrl: String? = null
    private var cachedApiService: ApiService? = null

    fun getBaseUrl(context: Context? = null): String {
        if (!activeBaseUrl.isNullOrEmpty()) {
            return activeBaseUrl!!
        }

        if (context != null) {
            val savedUrl = SessionManager.getServerUrl(context)
            if (savedUrl.isNotBlank()) {
                activeBaseUrl = if (savedUrl.endsWith("/")) savedUrl else "$savedUrl/"
                return activeBaseUrl!!
            }
        }

        val isEmulator = (android.os.Build.FINGERPRINT.startsWith("generic")
                || android.os.Build.FINGERPRINT.startsWith("unknown")
                || android.os.Build.FINGERPRINT.contains("emu")
                || android.os.Build.MODEL.contains("google_sdk")
                || android.os.Build.MODEL.contains("Emulator")
                || android.os.Build.MODEL.contains("sdk")
                || android.os.Build.MODEL.contains("Android SDK built for x86")
                || android.os.Build.HARDWARE.contains("goldfish")
                || android.os.Build.HARDWARE.contains("ranchu"))
        // En emulador 10.0.2.2; en dispositivo físico real con 'adb reverse' 127.0.0.1
        activeBaseUrl = if (isEmulator) "http://10.0.2.2:8000/" else "http://127.0.0.1:8000/"
        return activeBaseUrl!!
    }

    fun updateBaseUrl(newUrl: String) {
        val clean = newUrl.trim()
        val formatted = if (clean.endsWith("/")) clean else "$clean/"
        if (activeBaseUrl != formatted) {
            activeBaseUrl = formatted
            cachedApiService = buildService(formatted)
        }
    }

    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BODY
    }

    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(loggingInterceptor)
        .connectTimeout(60, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS)
        .writeTimeout(120, TimeUnit.SECONDS)
        .build()

    private fun buildService(baseUrl: String): ApiService {
        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ApiService::class.java)
    }

    val apiService: ApiService
        get() {
            if (cachedApiService == null) {
                cachedApiService = buildService(getBaseUrl())
            }
            return cachedApiService!!
        }
}
