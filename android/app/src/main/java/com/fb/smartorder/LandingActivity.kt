package com.fb.smartorder

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.fb.smartorder.data.network.RetrofitClient
import com.fb.smartorder.databinding.ActivityLandingBinding
import com.fb.smartorder.util.SessionManager

class LandingActivity : AppCompatActivity() {

    private lateinit var binding: ActivityLandingBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // 1. Verificar si hay sesión iniciada
        if (!SessionManager.isLoggedIn(this)) {
            val intent = Intent(this, LoginActivity::class.java)
            startActivity(intent)
            finish()
            return
        }

        binding = ActivityLandingBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Sincronizar URL guardada con RetrofitClient y asegurar activeEmail en memoria
        SessionManager.getUserEmail(this)
        val savedServer = SessionManager.getServerUrl(this)
        if (savedServer.isNotBlank()) {
            RetrofitClient.updateBaseUrl(savedServer)
        }

        updateChefProfileUI()
        setupListeners()
    }

    override fun onResume() {
        super.onResume()
        if (::binding.isInitialized) {
            updateChefProfileUI()
        }
    }

    private fun updateChefProfileUI() {
        val chef = SessionManager.getChefName(this)
        val restaurant = SessionManager.getRestaurantName(this)
        binding.tvChefName.text = "Chef en Turno: $chef"
        binding.tvServerStatus.text = "$restaurant · Perfil activo (toca para cambiar)"
    }

    private fun setupListeners() {
        // Tocar tarjeta de perfil para ver o editar datos
        binding.layoutChefCard.setOnClickListener {
            val intent = Intent(this, ProfileActivity::class.java)
            startActivity(intent)
        }

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

        setupBottomNavigation()
    }

    private fun setupBottomNavigation() {
        binding.navItemOrder.setOnClickListener {
            val intent = Intent(this, MainActivity::class.java).apply {
                putExtra("EXTRA_TAB_INDEX", 0)
            }
            startActivity(intent)
        }

        binding.navItemCatalog.setOnClickListener {
            val intent = Intent(this, MainActivity::class.java).apply {
                putExtra("EXTRA_TAB_INDEX", 1)
            }
            startActivity(intent)
        }

        binding.navItemCamera.setOnClickListener {
            val intent = Intent(this, MainActivity::class.java).apply {
                putExtra("EXTRA_START_SCAN", true)
            }
            startActivity(intent)
        }

        binding.navItemSuppliers.setOnClickListener {
            startActivity(Intent(this, SuppliersActivity::class.java))
        }

        binding.navItemSettings.setOnClickListener {
            startActivity(Intent(this, ProfileActivity::class.java))
        }
    }
}
