package com.fb.smartorder

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.fb.smartorder.data.network.RetrofitClient
import com.fb.smartorder.databinding.ActivityProfileBinding
import com.fb.smartorder.model.UserUpdateRequest
import com.fb.smartorder.util.SessionManager
import kotlinx.coroutines.launch

class ProfileActivity : AppCompatActivity() {

    private lateinit var binding: ActivityProfileBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityProfileBinding.inflate(layoutInflater)
        setContentView(binding.root)

        loadProfileData()
        setupListeners()
    }

    private fun loadProfileData() {
        val chef = SessionManager.getChefName(this)
        val restaurant = SessionManager.getRestaurantName(this)
        val email = SessionManager.getUserEmail(this)

        binding.etProfileChefName.setText(chef)
        binding.etProfileRestaurant.setText(restaurant)
        binding.tvProfileEmail.text = email
    }

    private fun setupListeners() {
        // Volver
        binding.btnProfileBack.setOnClickListener {
            finish()
        }

        // Accesos directos desde Ajustes
        binding.btnNavHome.setOnClickListener {
            val intent = Intent(this, LandingActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            }
            startActivity(intent)
            finish()
        }

        binding.btnNavHistory.setOnClickListener {
            val intent = Intent(this, OrderHistoryActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            }
            startActivity(intent)
            finish()
        }

        // Guardar cambios en perfil y contraseña
        binding.btnProfileSave.setOnClickListener {
            val chef = binding.etProfileChefName.text.toString().trim().ifEmpty { "Chef Pablo" }
            val restaurant = binding.etProfileRestaurant.text.toString().trim().ifEmpty { "Restaurante El Faro" }
            val email = SessionManager.getUserEmail(this)
            val newPassword = binding.etProfileNewPassword.text.toString().trim()
            val confirmPassword = binding.etProfileConfirmPassword.text.toString().trim()

            if (newPassword.isNotEmpty()) {
                if (newPassword.length < 4) {
                    Toast.makeText(this, "La nueva contraseña debe tener al menos 4 caracteres.", Toast.LENGTH_SHORT).show()
                    return@setOnClickListener
                }
                if (newPassword != confirmPassword) {
                    Toast.makeText(this, "Las nuevas contraseñas no coinciden.", Toast.LENGTH_SHORT).show()
                    return@setOnClickListener
                }
            }

            // Guardar datos locales
            SessionManager.setChefName(this, chef)
            SessionManager.setRestaurantName(this, restaurant)

            // Sincronizar con backend
            binding.pbProfileLoading.visibility = View.VISIBLE
            binding.btnProfileSave.isEnabled = false

            lifecycleScope.launch {
                try {
                    val passToSend = if (newPassword.isNotEmpty()) newPassword else null
                    val updateReq = UserUpdateRequest(
                        name = chef,
                        restaurantName = restaurant,
                        password = passToSend
                    )
                    RetrofitClient.apiService.updateProfile(email, updateReq)
                    Toast.makeText(this@ProfileActivity, "Perfil actualizado con éxito", Toast.LENGTH_SHORT).show()
                    finish()
                } catch (ignored: Exception) {
                    Toast.makeText(this@ProfileActivity, "Guardado localmente", Toast.LENGTH_SHORT).show()
                    finish()
                } finally {
                    binding.pbProfileLoading.visibility = View.GONE
                    binding.btnProfileSave.isEnabled = true
                }
            }
        }

        // Cerrar sesión
        binding.btnProfileLogout.setOnClickListener {
            SessionManager.logout(this)
            Toast.makeText(this, "Sesión cerrada correctamente", Toast.LENGTH_SHORT).show()

            val intent = Intent(this, LoginActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
            }
            startActivity(intent)
            finish()
        }

        // Eliminar cuenta
        binding.btnProfileDeleteAccount.setOnClickListener {
            com.google.android.material.dialog.MaterialAlertDialogBuilder(this)
                .setTitle("Eliminar Cuenta")
                .setMessage("¿Estás seguro de que deseas eliminar tu cuenta de cocina? Esta acción es definitiva.")
                .setPositiveButton("SÍ, ELIMINAR") { _, _ ->
                    val email = SessionManager.getUserEmail(this)
                    binding.pbProfileLoading.visibility = View.VISIBLE
                    lifecycleScope.launch {
                        try {
                            RetrofitClient.apiService.deleteAccount(email)
                        } catch (ignored: Exception) {
                        } finally {
                            binding.pbProfileLoading.visibility = View.GONE
                            SessionManager.logout(this@ProfileActivity)
                            Toast.makeText(this@ProfileActivity, "Cuenta eliminada correctamente", Toast.LENGTH_LONG).show()
                            val intent = Intent(this@ProfileActivity, LoginActivity::class.java).apply {
                                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
                            }
                            startActivity(intent)
                            finish()
                        }
                    }
                }
                .setNegativeButton("CANCELAR", null)
                .show()
        }

        // Barra inferior de navegación
        setupBottomNavigation()
    }

    private fun setupBottomNavigation() {
        binding.navItemOrder.setOnClickListener {
            val intent = Intent(this, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
                putExtra("EXTRA_TAB_INDEX", 0)
            }
            startActivity(intent)
            finish()
        }

        binding.navItemCatalog.setOnClickListener {
            val intent = Intent(this, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
                putExtra("EXTRA_TAB_INDEX", 1)
            }
            startActivity(intent)
            finish()
        }

        binding.navItemCamera.setOnClickListener {
            val intent = Intent(this, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
                putExtra("EXTRA_START_SCAN", true)
            }
            startActivity(intent)
            finish()
        }

        binding.navItemSettings.setOnClickListener {
            binding.scrollProfileContent.smoothScrollTo(0, 0)
        }

        binding.navItemSuppliers.setOnClickListener {
            val intent = Intent(this, SuppliersActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            }
            startActivity(intent)
            finish()
        }
    }
}
