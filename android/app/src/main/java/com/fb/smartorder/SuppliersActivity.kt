package com.fb.smartorder

import android.app.AlertDialog
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.ContactsContract
import android.provider.OpenableColumns
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import com.fb.smartorder.databinding.ActivitySuppliersBinding
import com.fb.smartorder.util.SessionManager
import com.fb.smartorder.model.Supplier
import com.fb.smartorder.ui.ProductViewModel
import com.fb.smartorder.ui.SuppliersAdapter
import java.io.File
import java.io.FileOutputStream

class SuppliersActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySuppliersBinding
    private val viewModel: ProductViewModel by viewModels()
    private lateinit var adapter: SuppliersAdapter

    private var pendingUploadSupplierId: String = ""
    private var pendingIsAnnex: Boolean = false
    private var pendingTargetForContact: ((String?, String?) -> Unit)? = null

    // Selector de contactos del teléfono
    private val contactPickerLauncher = registerForActivityResult(
        ActivityResultContracts.PickContact()
    ) { uri: Uri? ->
        uri?.let { handleContactPicked(it) }
    }

    // Selector de PDF de catálogo
    private val pdfPickerLauncher = registerForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        uri?.let { handlePdfPicked(it) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        SessionManager.getUserEmail(this)
        binding = ActivitySuppliersBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupRecyclerView()
        setupButtons()
        setupBottomNavigation()
        loadSuppliers()
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
            val intent = Intent(this, ProfileActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            }
            startActivity(intent)
            finish()
        }

        binding.navItemSuppliers.setOnClickListener {
            binding.rvSuppliers.smoothScrollToPosition(0)
        }
    }

    private fun setupRecyclerView() {
        adapter = SuppliersAdapter(
            onSupplierClick = { supplier ->
                showEditSupplierDialog(supplier)
            },
            onSupplierLongClick = { supplier ->
                confirmDeleteSupplier(supplier)
            },
            onChannelToggle = { supplier ->
                val current = supplier.preferredChannel?.lowercase() ?: "whatsapp"
                val newChannel = if (current == "email") "whatsapp" else "email"
                val updated = supplier.copy(preferredChannel = newChannel)
                binding.pbSuppliersLoading.visibility = View.VISIBLE
                viewModel.saveSupplier(updated) { result ->
                    binding.pbSuppliersLoading.visibility = View.GONE
                    result.onSuccess {
                        val badge = if (newChannel == "whatsapp") "WhatsApp" else "Email"
                        Toast.makeText(this, "${supplier.name} cambiado a $badge", Toast.LENGTH_SHORT).show()
                        loadSuppliers()
                    }.onFailure { err ->
                        Toast.makeText(this, "Error: ${err.message}", Toast.LENGTH_LONG).show()
                    }
                }
            }
        )
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

        binding.btnUploadCatalogAutoDetect.setOnClickListener {
            promptUploadCatalogMode("auto")
        }
    }

    private fun promptUploadCatalogMode(supplierId: String = "auto") {
        val options = arrayOf(
            "Sustituir Tarifa Completa\n(Borra los productos viejos para evitar descatalogados)",
            "Anexo / Folleto de Ofertas\n(Añade o actualiza precios puntuales sin borrar el catálogo base)"
        )
        AlertDialog.Builder(this)
            .setTitle("¿Qué tipo de catálogo vas a subir?")
            .setItems(options) { _, which ->
                pendingUploadSupplierId = supplierId
                pendingIsAnnex = (which == 1)
                pdfPickerLauncher.launch("application/pdf")
            }
            .setNegativeButton("Cancelar", null)
            .show()
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

                if (pendingTargetForContact != null) {
                    val cb = pendingTargetForContact
                    pendingTargetForContact = null
                    cb?.invoke(name, phone)
                } else {
                    showAddSupplierDialog(name, phone)
                }
            }
        }
    }

    private fun getFileName(uri: Uri): String {
        var name = "catalogo.pdf"
        try {
            contentResolver.query(uri, null, null, null, null)?.use { cursor ->
                val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (nameIndex != -1 && cursor.moveToFirst()) {
                    name = cursor.getString(nameIndex)
                }
            }
        } catch (_: Exception) {}
        return name
    }

    private fun handlePdfPicked(uri: Uri) {
        try {
            val originalName = getFileName(uri)
            val inputStream = contentResolver.openInputStream(uri)
            val tempFile = File(cacheDir, originalName)
            FileOutputStream(tempFile).use { out ->
                inputStream?.copyTo(out)
            }

            val progressDialog = AlertDialog.Builder(this)
                .setTitle("Cargando Catálogo")
                .setMessage("Extrayendo productos, actualizando tarifas y registrando datos del proveedor...")
                .setCancelable(false)
                .create()
            progressDialog.show()

            viewModel.uploadCatalog(pendingUploadSupplierId, tempFile, pendingIsAnnex) { result ->
                progressDialog.dismiss()
                binding.pbSuppliersLoading.visibility = View.GONE
                result.onSuccess { resp ->
                    loadSuppliers()
                    showConfirmUploadedSupplierDialog(
                        supplierId = resp.supplierId ?: "",
                        initialName = resp.supplierName ?: "Proveedor",
                        initialPhone = resp.detectedPhone,
                        initialEmail = resp.detectedEmail,
                        productsCount = resp.productsLoaded,
                        isNew = resp.isNewSupplier == true,
                        isAnnex = pendingIsAnnex
                    )
                }.onFailure { err ->
                    Toast.makeText(this, "Error procesando catálogo: ${err.message}", Toast.LENGTH_LONG).show()
                }
            }
        } catch (e: Exception) {
            Toast.makeText(this, "Error leyendo PDF: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun showConfirmUploadedSupplierDialog(
        supplierId: String,
        initialName: String,
        initialPhone: String?,
        initialEmail: String?,
        productsCount: Int,
        isNew: Boolean,
        isAnnex: Boolean
    ) {
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(40, 20, 40, 10)
        }

        val tvInfo = TextView(this).apply {
            text = if (isAnnex) {
                "Se han procesado $productsCount productos de oferta.\nRevisa los datos del proveedor:"
            } else {
                "Se han cargado $productsCount productos en el catálogo.\nConfirma o ajusta los datos del proveedor:"
            }
            textSize = 13f
            setPadding(0, 0, 0, 16)
        }

        val etName = EditText(this).apply {
            hint = "Nombre Comercial *"
            setText(initialName)
        }

        val etPhone = EditText(this).apply {
            hint = "Teléfono / WhatsApp (+34...)"
            inputType = android.text.InputType.TYPE_CLASS_PHONE
            setText(initialPhone ?: "")
        }

        val etEmail = EditText(this).apply {
            hint = "Email para pedidos (opcional)"
            inputType = android.text.InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS
            setText(initialEmail ?: "")
        }

        val btnPickFromAgenda = Button(this).apply {
            text = "Buscar en Contactos del Teléfono"
            textSize = 12f
            setOnClickListener {
                pendingTargetForContact = { cName, cPhone ->
                    if (cName != null && etName.text.isNullOrBlank()) etName.setText(cName)
                    if (cPhone != null) etPhone.setText(cPhone)
                }
                contactPickerLauncher.launch(null)
            }
        }

        val tvChannelLabel = TextView(this).apply {
            text = "Canal preferido para enviar pedidos:"
            textSize = 13f
            setPadding(0, 16, 0, 4)
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }

        val rgChannel = RadioGroup(this).apply {
            orientation = RadioGroup.HORIZONTAL
        }
        val isEmailDefault = !initialEmail.isNullOrBlank() && initialPhone.isNullOrBlank()
        val rbWhatsapp = RadioButton(this).apply {
            id = View.generateViewId()
            text = "WhatsApp"
        }
        val rbEmail = RadioButton(this).apply {
            id = View.generateViewId()
            text = "Email"
        }
        rgChannel.addView(rbWhatsapp)
        rgChannel.addView(rbEmail)
        rgChannel.check(if (isEmailDefault) rbEmail.id else rbWhatsapp.id)

        layout.addView(tvInfo)
        layout.addView(etName)
        layout.addView(etPhone)
        layout.addView(etEmail)
        layout.addView(btnPickFromAgenda)
        layout.addView(tvChannelLabel)
        layout.addView(rgChannel)

        val dialogTitle = if (isNew) "¡Nuevo Proveedor Detectado!" else "Tarifa de Proveedor Actualizada"

        AlertDialog.Builder(this)
            .setTitle(dialogTitle)
            .setView(layout)
            .setPositiveButton("Confirmar y Guardar") { _, _ ->
                val name = etName.text.toString().trim()
                if (name.isNotEmpty()) {
                    val phone = etPhone.text.toString().trim().ifEmpty { null }
                    val email = etEmail.text.toString().trim().ifEmpty { null }
                    val channel = if (rgChannel.checkedRadioButtonId == rbEmail.id) "email" else "whatsapp"

                    val supplier = Supplier(
                        id = supplierId.ifEmpty { "prov_" + name.lowercase().replace(Regex("[^a-z0-9]"), "_") },
                        name = name,
                        phone = phone,
                        email = email,
                        preferredChannel = channel
                    )

                    binding.pbSuppliersLoading.visibility = View.VISIBLE
                    viewModel.saveSupplier(supplier) { result ->
                        binding.pbSuppliersLoading.visibility = View.GONE
                        result.onSuccess {
                            Toast.makeText(this, "Proveedor '$name' confirmado", Toast.LENGTH_SHORT).show()
                            loadSuppliers()
                        }.onFailure { err ->
                            Toast.makeText(this, "Error actualizando proveedor: ${err.message}", Toast.LENGTH_LONG).show()
                        }
                    }
                }
            }
            .setNegativeButton("Dejar como está", null)
            .show()
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

        val tvChannelLabel = TextView(this).apply {
            text = "Canal preferido para enviar pedidos:"
            textSize = 13f
            setPadding(0, 16, 0, 4)
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }

        val rgChannel = RadioGroup(this).apply {
            orientation = RadioGroup.HORIZONTAL
        }
        val rbWhatsapp = RadioButton(this).apply {
            id = View.generateViewId()
            text = "WhatsApp"
        }
        val rbEmail = RadioButton(this).apply {
            id = View.generateViewId()
            text = "Email"
        }
        rgChannel.addView(rbWhatsapp)
        rgChannel.addView(rbEmail)
        rgChannel.check(rbWhatsapp.id)

        layout.addView(TextView(this).apply { text = "Datos del Proveedor:"; setTypeface(typeface, android.graphics.Typeface.BOLD) })
        layout.addView(etName)
        layout.addView(etPhone)
        layout.addView(etEmail)
        layout.addView(tvChannelLabel)
        layout.addView(rgChannel)

        AlertDialog.Builder(this)
            .setTitle("Alta de Proveedor")
            .setView(layout)
            .setPositiveButton("Guardar") { _, _ ->
                val name = etName.text.toString().trim()
                if (name.isNotEmpty()) {
                    val phone = etPhone.text.toString().trim().ifEmpty { null }
                    val email = etEmail.text.toString().trim().ifEmpty { null }
                    val cleanId = "prov_" + name.lowercase().replace(Regex("[^a-z0-9]"), "_")
                    val channel = if (rgChannel.checkedRadioButtonId == rbEmail.id) "email" else "whatsapp"

                    val supplier = Supplier(
                        id = cleanId,
                        name = name,
                        phone = phone,
                        email = email,
                        preferredChannel = channel
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

    private fun showEditSupplierDialog(supplier: Supplier) {
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(40, 20, 40, 10)
        }

        val etName = EditText(this).apply {
            hint = "Nombre del proveedor *"
            setText(supplier.name)
        }

        val etPhone = EditText(this).apply {
            hint = "Teléfono / WhatsApp (+34...)"
            inputType = android.text.InputType.TYPE_CLASS_PHONE
            setText(supplier.phone ?: "")
        }

        val etEmail = EditText(this).apply {
            hint = "Email para pedidos"
            inputType = android.text.InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS
            setText(supplier.email ?: "")
        }

        val tvChannelLabel = TextView(this).apply {
            text = "Canal preferido para enviar pedidos:"
            textSize = 13f
            setPadding(0, 16, 0, 4)
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }

        val rgChannel = RadioGroup(this).apply {
            orientation = RadioGroup.HORIZONTAL
        }
        val isEmail = supplier.preferredChannel?.lowercase() == "email"
        val rbWhatsapp = RadioButton(this).apply {
            id = View.generateViewId()
            text = "WhatsApp"
        }
        val rbEmail = RadioButton(this).apply {
            id = View.generateViewId()
            text = "Email"
        }
        rgChannel.addView(rbWhatsapp)
        rgChannel.addView(rbEmail)
        rgChannel.check(if (isEmail) rbEmail.id else rbWhatsapp.id)

        val btnUploadPdf = Button(this).apply {
            text = "Subir Catálogo / Tarifa (PDF)"
            setOnClickListener {
                promptUploadCatalogMode(supplier.id ?: ("prov_" + supplier.name.lowercase().replace(Regex("[^a-z0-9]"), "_")))
            }
        }

        val btnSaveToPhone = Button(this).apply {
            text = "Guardar en Contactos del Teléfono"
            setOnClickListener {
                val insertIntent = android.content.Intent(android.content.Intent.ACTION_INSERT).apply {
                    type = ContactsContract.RawContacts.CONTENT_TYPE
                    putExtra(ContactsContract.Intents.Insert.NAME, supplier.name)
                    if (!supplier.phone.isNullOrBlank()) {
                        putExtra(ContactsContract.Intents.Insert.PHONE, supplier.phone)
                    }
                    if (!supplier.email.isNullOrBlank()) {
                        putExtra(ContactsContract.Intents.Insert.EMAIL, supplier.email)
                    }
                }
                try {
                    startActivity(insertIntent)
                } catch (e: Exception) {
                    Toast.makeText(this@SuppliersActivity, "No se pudo abrir la agenda de contactos", Toast.LENGTH_SHORT).show()
                }
            }
        }

        layout.addView(TextView(this).apply { text = "Configuración de Proveedor:"; setTypeface(typeface, android.graphics.Typeface.BOLD) })
        layout.addView(etName)
        layout.addView(etPhone)
        layout.addView(etEmail)
        layout.addView(tvChannelLabel)
        layout.addView(rgChannel)
        layout.addView(btnUploadPdf)
        layout.addView(btnSaveToPhone)

        AlertDialog.Builder(this)
            .setTitle("Editar: ${supplier.name}")
            .setView(layout)
            .setPositiveButton("Guardar Cambios") { _, _ ->
                val name = etName.text.toString().trim()
                if (name.isNotEmpty()) {
                    val phone = etPhone.text.toString().trim().ifEmpty { null }
                    val email = etEmail.text.toString().trim().ifEmpty { null }
                    val channel = if (rgChannel.checkedRadioButtonId == rbEmail.id) "email" else "whatsapp"

                    val updatedSupplier = Supplier(
                        id = supplier.id,
                        name = name,
                        phone = phone,
                        email = email,
                        preferredChannel = channel
                    )

                    binding.pbSuppliersLoading.visibility = View.VISIBLE
                    viewModel.saveSupplier(updatedSupplier) { result ->
                        binding.pbSuppliersLoading.visibility = View.GONE
                        result.onSuccess {
                            Toast.makeText(this, "Proveedor actualizado", Toast.LENGTH_SHORT).show()
                            loadSuppliers()
                        }.onFailure { err ->
                            Toast.makeText(this, "Error actualizando: ${err.message}", Toast.LENGTH_LONG).show()
                        }
                    }
                }
            }
            .setNeutralButton("Eliminar") { _, _ ->
                confirmDeleteSupplier(supplier)
            }
            .setNegativeButton("Cerrar", null)
            .show()
    }

    private fun confirmDeleteSupplier(supplier: Supplier) {
        val sId = supplier.id ?: ""
        if (sId.isEmpty()) return

        AlertDialog.Builder(this)
            .setTitle("¿Eliminar ${supplier.name}?")
            .setMessage("Se eliminará este proveedor del directorio y se retirarán todos sus productos asociados del catálogo general.")
            .setIcon(android.R.drawable.ic_dialog_alert)
            .setPositiveButton("Sí, Eliminar") { _, _ ->
                binding.pbSuppliersLoading.visibility = View.VISIBLE
                viewModel.deleteSupplier(sId) { result ->
                    binding.pbSuppliersLoading.visibility = View.GONE
                    result.onSuccess {
                        Toast.makeText(this, "Proveedor '${supplier.name}' eliminado", Toast.LENGTH_SHORT).show()
                        loadSuppliers()
                    }.onFailure { err ->
                        Toast.makeText(this, "Error eliminando: ${err.message}", Toast.LENGTH_LONG).show()
                    }
                }
            }
            .setNegativeButton("Cancelar", null)
            .show()
    }
}
