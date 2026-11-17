package com.fb.smartorder

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.fb.smartorder.data.network.RetrofitClient
import com.fb.smartorder.databinding.ActivityRegisterBinding
import com.fb.smartorder.model.UserRegisterRequest
import com.fb.smartorder.util.SessionManager
import kotlinx.coroutines.launch

class RegisterActivity : AppCompatActivity() {

    private lateinit var binding: ActivityRegisterBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityRegisterBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupListeners()
    }

    private fun setupListeners() {
        binding.btnRegBackToLogin.setOnClickListener {
            finish()
        }

        binding.btnRegSubmit.setOnClickListener {
            val chefName = binding.etRegChefName.text.toString().trim()
            val restaurant = binding.etRegRestaurant.text.toString().trim()
            val email = binding.etRegEmail.text.toString().trim()
            val password = binding.etRegPassword.text.toString().trim()

            if (chefName.isEmpty() || restaurant.isEmpty() || email.isEmpty() || password.isEmpty()) {
                Toast.makeText(this, "Por favor, completa todos los campos.", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            if (password.length < 4) {
                Toast.makeText(this, "La contraseña debe tener al menos 4 caracteres.", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            binding.pbRegLoading.visibility = View.VISIBLE
            binding.btnRegSubmit.isEnabled = false

            lifecycleScope.launch {
                try {
                    val req = UserRegisterRequest(
                        name = chefName,
                        email = email,
                        password = password,
                        restaurantName = restaurant
                    )
                    val response = RetrofitClient.apiService.register(req)
                    binding.pbRegLoading.visibility = View.GONE
                    binding.btnRegSubmit.isEnabled = true

                    if (response.isSuccessful && response.body()?.user != null) {
                        val user = response.body()!!.user!!
                        SessionManager.saveSession(
                            this@RegisterActivity,
                            chefName = user.name,
                            restaurantName = user.restaurantName,
                            email = user.email
                        )
                        Toast.makeText(this@RegisterActivity, "¡Cuenta creada exitosamente!", Toast.LENGTH_SHORT).show()

                        val intent = Intent(this@RegisterActivity, LandingActivity::class.java).apply {
                            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
                        }
                        startActivity(intent)
                        finish()
                    } else {
                        val errMsg = response.errorBody()?.string() ?: "Error creando cuenta"
                        Toast.makeText(this@RegisterActivity, errMsg, Toast.LENGTH_LONG).show()
                    }
                } catch (e: Exception) {
                    binding.pbRegLoading.visibility = View.GONE
                    binding.btnRegSubmit.isEnabled = true
                    Toast.makeText(this@RegisterActivity, "Error de conexión: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }
}
