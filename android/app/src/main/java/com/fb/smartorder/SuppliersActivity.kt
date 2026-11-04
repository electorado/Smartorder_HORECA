package com.fb.smartorder

import android.app.AlertDialog
import android.net.Uri
import android.os.Bundle
import android.provider.ContactsContract
import android.view.View
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import com.fb.smartorder.databinding.ActivitySuppliersBinding
import com.fb.smartorder.model.Supplier
import com.fb.smartorder.ui.ProductViewModel
import com.fb.smartorder.ui.SuppliersAdapter

class SuppliersActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySuppliersBinding
    private val viewModel: ProductViewModel by viewModels()
    private lateinit var adapter: SuppliersAdapter

    // Selector de contactos del teléfono
    private val contactPickerLauncher = registerForActivityResult(
        ActivityResultContracts.PickContact()
    ) { uri: Uri? ->
        uri?.let { handleContactPicked(it) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySuppliersBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupRecyclerView()
        setupButtons()
        loadSuppliers()
    }

    private fun setupRecyclerView() {
        adapter = SuppliersAdapter { supplier ->
            Toast.makeText(this, "${supplier.name}: Canal ${supplier.preferredChannel}", Toast.LENGTH_SHORT).show()
        }
        binding.rvSuppliers.layoutManager = LinearLayoutManager(this)
        binding.rvSuppliers.adapter = adapter
    }

    private fun setupButtons() {
        binding.btnAddSupplier.setOnClickListener {
            showAddSupplierDialog(null, null)
        }

        binding.btnImportContact.setOnClickListener {
            contactPickerLauncher.launch(null)
        }
    }

    private fun loadSuppliers() {
        binding.pbSuppliersLoading.visibility = View.VISIBLE
        viewModel.getSuppliers { list ->
            binding.pbSuppliersLoading.visibility = View.GONE
            adapter.setSuppliers(list)
        }
    }

    private fun handleContactPicked(uri: Uri) {
        val cursor = contentResolver.query(uri, null, null, null, null)
        cursor?.use {
            if (it.moveToFirst()) {
                var name: String? = null
                var phone: String? = null

                val nameIdx = it.getColumnIndex(ContactsContract.Contacts.DISPLAY_NAME)
                if (nameIdx >= 0) {
                    name = it.getString(nameIdx)
                }

                val idIdx = it.getColumnIndex(ContactsContract.Contacts._ID)
                if (idIdx >= 0) {
                    val id = it.getString(idIdx)
                    val phoneCursor = contentResolver.query(
                        ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                        null,
                        "${ContactsContract.CommonDataKinds.Phone.CONTACT_ID} = ?",
                        arrayOf(id),
                        null
                    )
                    phoneCursor?.use { pCur ->
                        if (pCur.moveToFirst()) {
                            val pIdx = pCur.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)
                            if (pIdx >= 0) {
                                phone = pCur.getString(pIdx)
                            }
                        }
                    }
                }

                showAddSupplierDialog(name, phone)
            }
        }
    }

    private fun showAddSupplierDialog(initialName: String?, initialPhone: String?) {
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(40, 20, 40, 10)
        }

        val etName = EditText(this).apply {
            hint = "Nombre del proveedor *"
            setText(initialName ?: "")
        }

        val etPhone = EditText(this).apply {
            hint = "Teléfono / WhatsApp (+34...)"
            inputType = android.text.InputType.TYPE_CLASS_PHONE
            setText(initialPhone ?: "")
        }

        val etEmail = EditText(this).apply {
            hint = "Email para pedidos (opcional)"
            inputType = android.text.InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS
        }

        layout.addView(TextView(this).apply { text = "Datos del Proveedor:"; setTypeface(typeface, android.graphics.Typeface.BOLD) })
        layout.addView(etName)
        layout.addView(etPhone)
        layout.addView(etEmail)

        AlertDialog.Builder(this)
            .setTitle("Alta de Proveedor")
            .setView(layout)
            .setPositiveButton("Guardar") { _, _ ->
                val name = etName.text.toString().trim()
                if (name.isNotEmpty()) {
                    val phone = etPhone.text.toString().trim().ifEmpty { null }
                    val email = etEmail.text.toString().trim().ifEmpty { null }
                    val cleanId = "prov_" + name.lowercase().replace(Regex("[^a-z0-9]"), "_")

                    val supplier = Supplier(
                        id = cleanId,
                        name = name,
                        phone = phone,
                        email = email,
                        preferredChannel = "whatsapp"
                    )

                    binding.pbSuppliersLoading.visibility = View.VISIBLE
                    viewModel.saveSupplier(supplier) { result ->
                        binding.pbSuppliersLoading.visibility = View.GONE
                        result.onSuccess {
                            Toast.makeText(this, "Proveedor guardado con éxito", Toast.LENGTH_SHORT).show()
                            loadSuppliers()
                        }.onFailure { err ->
                            Toast.makeText(this, "Error guardando: ${err.message}", Toast.LENGTH_LONG).show()
                        }
                    }
                } else {
                    Toast.makeText(this, "El nombre es obligatorio", Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton("Cancelar", null)
            .show()
    }
}

