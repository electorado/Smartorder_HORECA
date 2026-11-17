package com.fb.smartorder

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.fb.smartorder.data.network.RetrofitClient
import com.fb.smartorder.databinding.ActivityLoginBinding
import com.fb.smartorder.model.UserLoginRequest
import com.fb.smartorder.util.SessionManager
import kotlinx.coroutines.launch

class LoginActivity : AppCompatActivity() {

    private lateinit var binding: ActivityLoginBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityLoginBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Cargar email previo o demo por defecto
        val savedEmail = SessionManager.getUserEmail(this)
        binding.etLoginEmail.setText(if (savedEmail.isNotBlank()) savedEmail else "pablo@horeca.com")
        binding.etLoginPassword.setText("password123")

        val currentServer = SessionManager.getServerUrl(this)
        if (currentServer.isNotBlank()) {
            binding.etLoginServer.setText(currentServer)
        }

        setupListeners()
    }

    private fun setupListeners() {
        // Alternar ajustes avanzados de servidor
        binding.btnToggleServerSettings.setOnClickListener {
            val isVisible = binding.layoutServerSettings.visibility == View.VISIBLE
            binding.layoutServerSettings.visibility = if (isVisible) View.GONE else View.VISIBLE
        }

        // Navegar a Registro
        binding.btnGoToRegister.setOnClickListener {
            val intent = Intent(this, RegisterActivity::class.java)
            startActivity(intent)
        }

        // Iniciar Sesión
        binding.btnLoginEnter.setOnClickListener {
            val email = binding.etLoginEmail.text.toString().trim()
            val password = binding.etLoginPassword.text.toString().trim()
            val server = binding.etLoginServer.text.toString().trim()

            if (email.isEmpty() || password.isEmpty()) {
                Toast.makeText(this, "Por favor, introduce email y contraseña.", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            if (server.isNotEmpty()) {
                RetrofitClient.updateBaseUrl(server)
            }

            binding.pbLoginLoading.visibility = View.VISIBLE
            binding.btnLoginEnter.isEnabled = false

            lifecycleScope.launch {
                try {
                    val response = RetrofitClient.apiService.login(UserLoginRequest(email, password))
                    binding.pbLoginLoading.visibility = View.GONE
                    binding.btnLoginEnter.isEnabled = true

                    if (response.isSuccessful && response.body()?.user != null) {
                        val user = response.body()!!.user!!
                        SessionManager.saveSession(
                            this@LoginActivity,
                            chefName = user.name,
                            restaurantName = user.restaurantName,
                            email = user.email,
                            serverUrl = server
                        )
                        Toast.makeText(this@LoginActivity, "¡Bienvenido, ${user.name}!", Toast.LENGTH_SHORT).show()
                        goToDashboard()
                    } else {
                        val errMsg = response.errorBody()?.string() ?: "Credenciales incorrectas"
                        Toast.makeText(this@LoginActivity, "Error: $errMsg", Toast.LENGTH_LONG).show()
                    }
                } catch (e: Exception) {
                    binding.pbLoginLoading.visibility = View.GONE
                    binding.btnLoginEnter.isEnabled = true

                    // Modo de rescate / Offline: Si el servidor no responde pero es el usuario demo, permitir acceso
                    if (email.equals("pablo@horeca.com", ignoreCase = true) && password == "password123") {
                        SessionManager.saveSession(
                            this@LoginActivity,
                            chefName = "Pablo Moncayo",
                            restaurantName = "Restaurante El Faro",
                            email = email,
                            serverUrl = server
                        )
                        Toast.makeText(this@LoginActivity, "Sesión local iniciada (Modo Autónomo)", Toast.LENGTH_SHORT).show()
                        goToDashboard()
                    } else {
                        Toast.makeText(this@LoginActivity, "No se pudo conectar con el servidor: ${e.message}", Toast.LENGTH_LONG).show()
                    }
                }
            }
        }
    }

    private fun goToDashboard() {
        val intent = Intent(this, LandingActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK
        }
        startActivity(intent)
        finish()
    }
}
