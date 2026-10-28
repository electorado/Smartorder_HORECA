package com.fb.smartorder.data.network

import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

/**
 * Cliente singleton de Retrofit para gestionar peticiones HTTP asíncronas.
 */
object RetrofitClient {

    // En el emulador AVD de Android, 10.0.2.2 mapea directamente al localhost del equipo anfitrión.
    private const val BASE_URL = "http://10.0.2.2:8000/"

    // Interceptor para depurar las peticiones y respuestas JSON en el Logcat de Android Studio
    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BODY
    }

    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(loggingInterceptor)
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()

    val apiService: ApiService by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ApiService::class.java)
    }
}

