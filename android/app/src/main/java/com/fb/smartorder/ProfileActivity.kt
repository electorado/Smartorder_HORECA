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
        val server = SessionManager.getServerUrl(this)

        binding.etProfileChefName.setText(chef)
        binding.etProfileRestaurant.setText(restaurant)
        binding.tvProfileEmail.text = email
        if (server.isNotBlank()) {
            binding.etProfileServer.setText(server)
        }
    }

    private fun setupListeners() {
        binding.btnProfileBack.setOnClickListener {
            finish()
        }

        binding.btnProfileSave.setOnClickListener {
            val chef = binding.etProfileChefName.text.toString().trim().ifEmpty { "Chef Pablo" }
            val restaurant = binding.etProfileRestaurant.text.toString().trim().ifEmpty { "Restaurante El Faro" }
            val server = binding.etProfileServer.text.toString().trim()
            val email = SessionManager.getUserEmail(this)

            // Guardar localmente
            SessionManager.setChefName(this, chef)
            SessionManager.setRestaurantName(this, restaurant)
            if (server.isNotEmpty()) {
                SessionManager.setServerUrl(this, server)
                RetrofitClient.updateBaseUrl(server)
            }

            // Sincronizar con el backend
            binding.pbProfileLoading.visibility = View.VISIBLE
            binding.btnProfileSave.isEnabled = false

            lifecycleScope.launch {
                try {
                    val updateReq = UserUpdateRequest(name = chef, restaurantName = restaurant)
                    RetrofitClient.apiService.updateProfile(email, updateReq)
                } catch (ignored: Exception) {
                    // Si el backend no responde, los cambios locales permanecen guardados
                } finally {
                    binding.pbProfileLoading.visibility = View.GONE
                    binding.btnProfileSave.isEnabled = true
                    Toast.makeText(this@ProfileActivity, "Perfil guardado correctamente 💾", Toast.LENGTH_SHORT).show()
                    finish()
                }
            }
        }

        binding.btnProfileLogout.setOnClickListener {
            SessionManager.logout(this)
            Toast.makeText(this, "Sesión cerrada correctamente", Toast.LENGTH_SHORT).show()

            val intent = Intent(this, LoginActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
            }
            startActivity(intent)
            finish()
        }
    }
}
