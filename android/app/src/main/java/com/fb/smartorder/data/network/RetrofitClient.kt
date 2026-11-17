package com.fb.smartorder.data.network

import android.content.Context
import com.fb.smartorder.util.SessionManager
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object RetrofitClient {

    private var activeBaseUrl: String? = null
    private var cachedApiService: ApiService? = null

    const val CLOUD_DEFAULT_URL = "https://smartorder-api-z4or.onrender.com/"

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

        // Por defecto conectar a la API Cloud en Render para funcionamiento universal en cualquier teléfono
        activeBaseUrl = CLOUD_DEFAULT_URL
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

    private val authHeaderInterceptor = Interceptor { chain ->
        val original = chain.request()
        val email = SessionManager.activeEmail
        if (email.isNotBlank()) {
            val req = original.newBuilder()
                .header("X-User-Email", email)
                .build()
            chain.proceed(req)
        } else {
            chain.proceed(original)
        }
    }

    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(authHeaderInterceptor)
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
