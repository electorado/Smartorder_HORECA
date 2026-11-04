package com.fb.smartorder

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.fb.smartorder.databinding.ActivityLandingBinding

class LandingActivity : AppCompatActivity() {

    private lateinit var binding: ActivityLandingBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityLandingBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupListeners()
    }

    private fun setupListeners() {
        // 1. Nuevo Pedido -> Abre el catálogo y panel de selección
        binding.btnMenuNewOrder.setOnClickListener {
            val intent = Intent(this, MainActivity::class.java)
            startActivity(intent)
        }

        // 2. Historial de Pedidos
        binding.btnMenuHistory.setOnClickListener {
            val intent = Intent(this, OrderHistoryActivity::class.java)
            startActivity(intent)
        }

        // 3. Mis Proveedores
        binding.btnMenuSuppliers.setOnClickListener {
            val intent = Intent(this, SuppliersActivity::class.java)
            startActivity(intent)
        }

        // 4. Escanear Pizarra / Nevera directo con IA
        binding.btnMenuScanFridge.setOnClickListener {
            val intent = Intent(this, MainActivity::class.java).apply {
                putExtra("EXTRA_START_SCAN", true)
            }
            startActivity(intent)
        }
    }
}

