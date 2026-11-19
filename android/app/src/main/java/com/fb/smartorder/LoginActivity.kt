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
        binding.etLoginEmail.setText(if (savedEmail.isNotBlank()) savedEmail else "cuisto@horeca.com")
        binding.etLoginPassword.setText("password123")

        setupListeners()
    }

    private fun setupListeners() {
        // ¿Has olvidado la contraseña?
        binding.btnForgotPassword.setOnClickListener {
            showForgotPasswordDialog()
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

            if (email.isEmpty() || password.isEmpty()) {
                Toast.makeText(this, "Por favor, introduce email y contraseña.", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
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
                            email = user.email
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
                    if ((email.equals("cuisto@horeca.com", ignoreCase = true) || email.equals("pablo@horeca.com", ignoreCase = true)) && password == "password123") {
                        SessionManager.saveSession(
                            this@LoginActivity,
                            chefName = if (email.startsWith("cuisto", ignoreCase = true)) "Chef Cuisto" else "Pablo Moncayo",
                            restaurantName = "Restaurante El Faro",
                            email = email
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

    private fun showForgotPasswordDialog() {
        val dialogView = layoutInflater.inflate(R.layout.dialog_forgot_password, null)
        val etEmail = dialogView.findViewById<android.widget.EditText>(R.id.etForgotEmail)

        val currentEmail = binding.etLoginEmail.text.toString().trim()
        if (currentEmail.isNotEmpty()) {
            etEmail.setText(currentEmail)
        }

        com.google.android.material.dialog.MaterialAlertDialogBuilder(this)
            .setView(dialogView)
            .setPositiveButton("ENVIAR EMAIL") { _, _ ->
                val email = etEmail.text.toString().trim()

                if (email.isEmpty()) {
                    Toast.makeText(this, "Introduce el correo de tu cuenta.", Toast.LENGTH_SHORT).show()
                    return@setPositiveButton
                }

                binding.pbLoginLoading.visibility = View.VISIBLE
                lifecycleScope.launch {
                    try {
                        val response = RetrofitClient.apiService.forgotPassword(
                            com.fb.smartorder.model.ForgotPasswordRequest(email)
                        )
                        binding.pbLoginLoading.visibility = View.GONE
                        if (response.isSuccessful) {
                            val msg = response.body()?.get("message") as? String 
                                ?: "Email enviado con Brevo. Revisa tu bandeja de entrada."
                            Toast.makeText(this@LoginActivity, msg, Toast.LENGTH_LONG).show()
                            binding.etLoginEmail.setText(email)
                            binding.etLoginPassword.setText("")
                        } else {
                            val err = response.errorBody()?.string() ?: "Error al enviar email"
                            Toast.makeText(this@LoginActivity, "Error: $err", Toast.LENGTH_LONG).show()
                        }
                    } catch (e: Exception) {
                        binding.pbLoginLoading.visibility = View.GONE
                        Toast.makeText(this@LoginActivity, "No se pudo conectar: ${e.message}", Toast.LENGTH_LONG).show()
                    }
                }
            }
            .setNegativeButton("CANCELAR", null)
            .show()
    }
}
