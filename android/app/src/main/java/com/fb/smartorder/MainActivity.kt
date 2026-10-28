package com.fb.smartorder

import android.os.Bundle
import android.util.Log
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.fb.smartorder.data.network.RetrofitClient
import com.fb.smartorder.databinding.ActivityMainBinding
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    companion object {
        private const val TAG = "SmartOrderApp"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Prueba de conexión con FastAPI en segundo plano
        testFetchProducts()
    }

    private fun testFetchProducts() {
        lifecycleScope.launch {
            try {
                val response = RetrofitClient.apiService.getProducts()
                if (response.isSuccessful) {
                    val products = response.body()?.products ?: emptyList()
                    Log.d(TAG, "Conexión exitosa con FastAPI. Total productos: ${products.size}")
                    binding.tvStatus.text = "Conectado a FastAPI (${products.size} productos)"
                } else {
                    Log.e(TAG, "Error de respuesta HTTP ${response.code()}")
                    binding.tvStatus.text = "Error HTTP: ${response.code()}"
                }
            } catch (e: Exception) {
                Log.e(TAG, "Fallo al conectar con http://10.0.2.2:8000: ${e.message}", e)
                binding.tvStatus.text = "Sin conexión al Backend (Comprueba FastAPI)"
            }
        }
    }
}
