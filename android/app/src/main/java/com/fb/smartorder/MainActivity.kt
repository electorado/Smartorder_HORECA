package com.fb.smartorder

import android.app.AlertDialog
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.ContactsContract
import android.text.Editable
import android.text.TextWatcher
import android.view.LayoutInflater
import android.view.View
import android.widget.*
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import com.fb.smartorder.databinding.ActivityMainBinding
import com.fb.smartorder.model.OrderItem
import com.fb.smartorder.model.Supplier
import com.fb.smartorder.model.SupplierSubOrderResponse
import com.fb.smartorder.ui.ProductAdapter
import com.fb.smartorder.ui.ProductViewModel
import com.fb.smartorder.ui.ProductsUiState
import java.io.File
import java.io.FileOutputStream

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val viewModel: ProductViewModel by viewModels()
    private lateinit var adapter: ProductAdapter

    // Variables temporales para el diálogo de subida de catálogo
    private var tempContactName: String? = null
    private var tempContactPhone: String? = null
    private var activeSupplierEt: EditText? = null
    private var activeSupplierPhoneEt: EditText? = null
    private var pendingUploadSupplierId: String = "prov_dialva_04"

    // Selector de contactos del teléfono (Android nativo)
    private val contactPickerLauncher = registerForActivityResult(
        ActivityResultContracts.PickContact()
    ) { uri: Uri? ->
        uri?.let { handleContactPicked(it) }
    }

    // Selector de archivos PDF del almacenamiento (Android SAF)
    private val pdfPickerLauncher = registerForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        uri?.let { handlePdfPicked(it) }
    }

    // Selector de fotos de la nevera (Galería)
    private val galleryImageLauncher = registerForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        uri?.let { handleFridgePhotoPicked(it) }
    }

    // Captura de foto con cámara
    private val cameraLauncher = registerForActivityResult(
        ActivityResultContracts.TakePicturePreview()
    ) { bitmap: android.graphics.Bitmap? ->
        bitmap?.let { handleCameraBitmap(it) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupRecyclerView()
        setupSearch()
        setupQuickActionButtons()
        setupBottomButton()
        observeViewModel()

        if (intent.getBooleanExtra("EXTRA_START_SCAN", false)) {
            showCameraOptionsDialog()
        }
    }

    private fun setupRecyclerView() {
        adapter = ProductAdapter { _, _ ->
            updateOrderSummary()
        }
        binding.rvIngredients.layoutManager = LinearLayoutManager(this)
        binding.rvIngredients.adapter = adapter
    }

    private fun setupSearch() {
        binding.etSearch.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                val query = s?.toString().orEmpty()
                adapter.filter(query)
                binding.btnClearSearch.visibility = if (query.isNotEmpty()) View.VISIBLE else View.GONE
            }
            override fun afterTextChanged(s: Editable?) {}
        })

        binding.btnClearSearch.setOnClickListener {
            binding.etSearch.text?.clear()
        }
    }

    private fun setupQuickActionButtons() {
        binding.btnNotesAdditionals.setOnClickListener {
            showNotesAndAdditionalsDialog()
        }

        binding.btnCameraScan.setOnClickListener {
            showCameraOptionsDialog()
        }

        binding.btnUploadCatalog.setOnClickListener {
            showUploadCatalogDialog()
        }
    }

    private fun showCameraOptionsDialog() {
        val options = arrayOf("Hacer foto con la cámara 📷", "Elegir foto de la galería 🖼️")
        AlertDialog.Builder(this)
            .setTitle("Escanear lista de la nevera / pizarra")
            .setItems(options) { _, which ->
                if (which == 0) {
                    cameraLauncher.launch(null)
                } else {
                    galleryImageLauncher.launch("image/*")
                }
            }
            .setNegativeButton("Cancelar", null)
            .show()
    }

    private fun handleCameraBitmap(bitmap: android.graphics.Bitmap) {
        val tempFile = File(cacheDir, "temp_fridge_camera.jpg")
        FileOutputStream(tempFile).use { out ->
            bitmap.compress(android.graphics.Bitmap.CompressFormat.JPEG, 90, out)
        }
        processFridgePhotoFile(tempFile)
    }

    private fun handleFridgePhotoPicked(uri: Uri) {
        try {
            val inputStream = contentResolver.openInputStream(uri)
            val tempFile = File(cacheDir, "temp_fridge_gallery.jpg")
            FileOutputStream(tempFile).use { out ->
                inputStream?.copyTo(out)
            }
            processFridgePhotoFile(tempFile)
        } catch (e: Exception) {
            Toast.makeText(this, "Error leyendo imagen: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun processFridgePhotoFile(file: File) {
        binding.pbLoading.visibility = View.VISIBLE
        Toast.makeText(this, "Analizando lista con IA (Gemini 1.5 Flash)...", Toast.LENGTH_LONG).show()

        viewModel.scanKitchenNotes(file) { result ->
            binding.pbLoading.visibility = View.GONE
            result.onSuccess { scanResp ->
                val items = scanResp.items
                if (items.isEmpty()) {
                    Toast.makeText(this, "No se detectaron ingredientes en la imagen", Toast.LENGTH_LONG).show()
                    return@onSuccess
                }

                var matchedCount = 0
                val addedOffCatalog = mutableListOf<String>()

                for (item in items) {
                    val mId = item.masterIngredientId
                    if (!mId.isNullOrEmpty() && adapter.getProductById(mId) != null) {
                        adapter.setProductQuantity(mId, item.quantity.toInt().coerceAtLeast(1))
                        matchedCount++
                    } else {
                        val offName = item.cleanName ?: item.rawText
                        viewModel.offCatalogItems.add(
                            OrderItem(
                                masterIngredientId = null,
                                ingredientName = offName,
                                supplierId = "prov_dialva_04",
                                supplierName = "Proveedor Asignado",
                                quantity = item.quantity,
                                unit = item.unit,
                                unitPrice = 0.0,
                                totalPrice = 0.0,
                                notes = "Extraído de foto de la nevera",
                                isOffCatalog = true
                            )
                        )
                        addedOffCatalog.add(offName)
                    }
                }

                updateOrderSummary()

                val summaryMsg = StringBuilder()
                summaryMsg.append("Se detectaron ${items.size} ítems en la foto:\n")
                if (matchedCount > 0) {
                    summaryMsg.append("• $matchedCount productos marcados en el catálogo.\n")
                }
                if (addedOffCatalog.isNotEmpty()) {
                    summaryMsg.append("• ${addedOffCatalog.size} ítems añadidos como notas fuera de catálogo.\n")
                }

                AlertDialog.Builder(this)
                    .setTitle("Reconocimiento completado")
                    .setMessage(summaryMsg.toString())
                    .setPositiveButton("Aceptar", null)
                    .show()

            }.onFailure { err ->
                Toast.makeText(this, "Error procesando foto: ${err.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun setupBottomButton() {
        binding.btnSubmitOrder.setOnClickListener {
            val selected = adapter.getSelectedQuantities()
            val offCatalog = viewModel.offCatalogItems

            if (selected.isEmpty() && offCatalog.isEmpty()) {
                Toast.makeText(this, "Selecciona al menos un ingrediente o añade una nota", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            // Construir las líneas del pedido
            val items = mutableListOf<OrderItem>()
            var totalAmount = 0.0

            for ((product, qty) in selected) {
                val unitPrice = product.bestPrice ?: 0.0
                val lineTotal = unitPrice * qty
                totalAmount += lineTotal
                items.add(
                    OrderItem(
                        masterIngredientId = product.id,
                        ingredientName = product.name,
                        supplierId = product.bestSupplierId ?: "prov_dialva_04",
                        supplierName = product.bestSupplierName ?: "DIALVA Hostelería S.L.",
                        quantity = qty.toDouble(),
                        unit = product.standardUnit,
                        unitPrice = unitPrice,
                        totalPrice = lineTotal,
                        isOffCatalog = false
                    )
                )
            }

            // Añadir ítems fuera de catálogo
            for (offItem in offCatalog) {
                totalAmount += offItem.totalPrice
                items.add(offItem)
            }

            binding.pbLoading.visibility = View.VISIBLE
            viewModel.submitOrder(items, totalAmount) { result ->
                binding.pbLoading.visibility = View.GONE
                result.onSuccess { orderResponse ->
                    Toast.makeText(this, "Pedido registrado #${orderResponse.orderId}", Toast.LENGTH_SHORT).show()
                    val suborders = orderResponse.order?.supplierSuborders ?: emptyList()
                    handleOrderDispatched(suborders)
                }.onFailure { err ->
                    Toast.makeText(this, "Error enviando pedido: ${err.message}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun handleOrderDispatched(suborders: List<SupplierSubOrderResponse>) {
        if (suborders.isEmpty()) {
            Toast.makeText(this, "Pedido completado sin proveedores asignados.", Toast.LENGTH_SHORT).show()
            return
        }

        if (suborders.size == 1) {
            val single = suborders[0]
            val waUrl = single.whatsappUrl
            if (!waUrl.isNullOrEmpty()) {
                val intent = Intent(Intent.ACTION_VIEW, Uri.parse(waUrl))
                startActivity(intent)
            } else {
                Toast.makeText(this, "Pedido guardado para ${single.supplierName}", Toast.LENGTH_SHORT).show()
            }
        } else {
            // Pedido multilínea dividido entre varios proveedores
            val names = suborders.map { "${it.supplierName} (${String.format("%.2f", it.subtotal)} €)" }.toTypedArray()
            AlertDialog.Builder(this)
                .setTitle("Pedido dividido en ${suborders.size} proveedores")
                .setItems(names) { _, which ->
                    val selectedSub = suborders[which]
                    selectedSub.whatsappUrl?.let { url ->
                        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                        startActivity(intent)
                    }
                }
                .setPositiveButton("Cerrar", null)
                .show()
        }
    }

    private fun updateOrderSummary() {
        val selected = adapter.getSelectedQuantities()
        val count = selected.values.sum() + viewModel.offCatalogItems.size
        val hasNotes = viewModel.chefNotes.isNotBlank()

        if (count > 0 || hasNotes) {
            val suffix = if (hasNotes) " [Con Nota]" else ""
            binding.tvButtonText.text = "ENVIAR PEDIDO ($count)$suffix"
        } else {
            binding.tvButtonText.text = getString(R.string.btn_send_order)
        }
    }

    private fun showNotesAndAdditionalsDialog() {
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(40, 20, 40, 10)
        }

        val tvNotesLabel = TextView(this).apply {
            text = "Instrucciones de entrega para el proveedor:"
            textSize = 14f
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }
        val etNotes = EditText(this).apply {
            hint = "Ej: Venid mañana antes de las 10:00 h"
            setText(viewModel.chefNotes)
        }

        val tvOffCatalogTitle = TextView(this).apply {
            text = "\nProducto fuera de catálogo (opcional):"
            textSize = 14f
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }
        val etItemName = EditText(this).apply {
            hint = "Ej: Lechón lechal o costillitas frescas"
        }
        val etItemQty = EditText(this).apply {
            hint = "Cantidad (ej. 2)"
            inputType = android.text.InputType.TYPE_CLASS_NUMBER or android.text.InputType.TYPE_NUMBER_FLAG_DECIMAL
        }
        val etItemSupplier = EditText(this).apply {
            hint = "Proveedor asignado (ej. Carnes Gómez)"
        }

        layout.addView(tvNotesLabel)
        layout.addView(etNotes)
        layout.addView(tvOffCatalogTitle)
        layout.addView(etItemName)
        layout.addView(etItemQty)
        layout.addView(etItemSupplier)

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.dialog_notes_title))
            .setView(layout)
            .setPositiveButton("Guardar") { _, _ ->
                viewModel.chefNotes = etNotes.text.toString().trim()
                val offName = etItemName.text.toString().trim()
                if (offName.isNotEmpty()) {
                    val qty = etItemQty.text.toString().toDoubleOrNull() ?: 1.0
                    val suppName = etItemSupplier.text.toString().trim().ifEmpty { "Proveedor General" }
                    val cleanId = "prov_" + suppName.lowercase().replace(Regex("[^a-z0-9]"), "_")

                    viewModel.offCatalogItems.add(
                        OrderItem(
                            masterIngredientId = null,
                            ingredientName = offName,
                            supplierId = cleanId,
                            supplierName = suppName,
                            quantity = qty,
                            unit = "ud",
                            unitPrice = 0.0,
                            totalPrice = 0.0,
                            notes = "Pedido especial fuera de catálogo",
                            isOffCatalog = true
                        )
                    )
                    Toast.makeText(this, "Añadido fuera de catálogo: $offName", Toast.LENGTH_SHORT).show()
                }
                updateOrderSummary()
            }
            .setNegativeButton("Cancelar", null)
            .show()
    }

    private fun showUploadCatalogDialog() {
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(40, 20, 40, 10)
        }

        val tvSuppLabel = TextView(this).apply {
            text = "Proveedor del Catálogo:"
            textSize = 14f
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }

        val etSupplierName = EditText(this).apply {
            hint = "Nombre del proveedor (ej. Frutas Paco)"
        }
        activeSupplierEt = etSupplierName

        val etSupplierPhone = EditText(this).apply {
            hint = "Teléfono / WhatsApp (+34...)"
            inputType = android.text.InputType.TYPE_CLASS_PHONE
        }
        activeSupplierPhoneEt = etSupplierPhone

        val btnPickContact = Button(this).apply {
            text = getString(R.string.btn_pick_contact)
            setOnClickListener {
                contactPickerLauncher.launch(null)
            }
        }

        val btnPickPdf = Button(this).apply {
            text = getString(R.string.btn_pick_pdf)
            setOnClickListener {
                val name = etSupplierName.text.toString().trim()
                if (name.isEmpty()) {
                    Toast.makeText(this@MainActivity, "Introduce o selecciona un proveedor primero", Toast.LENGTH_SHORT).show()
                } else {
                    val cleanId = "prov_" + name.lowercase().replace(Regex("[^a-z0-9]"), "_")
                    pendingUploadSupplierId = cleanId
                    val phone = etSupplierPhone.text.toString().trim()
                    // Guardar o registrar el proveedor en backend
                    viewModel.saveSupplier(
                        Supplier(
                            id = cleanId,
                            name = name,
                            phone = phone.ifEmpty { null },
                            preferredChannel = "whatsapp"
                        )
                    ) {}
                    pdfPickerLauncher.launch("application/pdf")
                }
            }
        }

        layout.addView(tvSuppLabel)
        layout.addView(etSupplierName)
        layout.addView(etSupplierPhone)
        layout.addView(btnPickContact)
        layout.addView(btnPickPdf)

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.dialog_catalog_title))
            .setView(layout)
            .setNegativeButton("Cerrar", null)
            .show()
    }

    private fun handleContactPicked(uri: Uri) {
        val cursor = contentResolver.query(uri, null, null, null, null)
        cursor?.use {
            if (it.moveToFirst()) {
                val nameIdx = it.getColumnIndex(ContactsContract.Contacts.DISPLAY_NAME)
                if (nameIdx >= 0) {
                    val name = it.getString(nameIdx)
                    activeSupplierEt?.setText(name)
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
                                val phone = pCur.getString(pIdx)
                                activeSupplierPhoneEt?.setText(phone)
                            }
                        }
                    }
                }
            }
        }
    }

    private fun handlePdfPicked(uri: Uri) {
        try {
            val inputStream = contentResolver.openInputStream(uri)
            val tempFile = File(cacheDir, "temp_catalog.pdf")
            val outputStream = FileOutputStream(tempFile)
            inputStream?.use { input ->
                outputStream.use { output ->
                    input.copyTo(output)
                }
            }

            binding.pbLoading.visibility = View.VISIBLE
            Toast.makeText(this, "Subiendo y procesando catálogo con backend...", Toast.LENGTH_LONG).show()

            viewModel.uploadCatalog(pendingUploadSupplierId, tempFile) { result ->
                binding.pbLoading.visibility = View.GONE
                result.onSuccess { resp ->
                    Toast.makeText(
                        this,
                        "Catálogo procesado: ${resp.productsExtracted} productos extraídos (${resp.productsLoaded} guardados)",
                        Toast.LENGTH_LONG
                    ).show()
                }.onFailure { err ->
                    Toast.makeText(this, "Error procesando catálogo: ${err.message}", Toast.LENGTH_LONG).show()
                }
            }
        } catch (e: Exception) {
            Toast.makeText(this, "Error leyendo PDF: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun observeViewModel() {
        viewModel.uiState.observe(this) { state ->
            when (state) {
                is ProductsUiState.Loading -> {
                    binding.pbLoading.visibility = View.VISIBLE
                    binding.rvIngredients.visibility = View.GONE
                    binding.tvEmptyMessage.visibility = View.GONE
                }
                is ProductsUiState.Success -> {
                    binding.pbLoading.visibility = View.GONE
                    if (state.products.isEmpty()) {
                        binding.tvEmptyMessage.visibility = View.VISIBLE
                        binding.rvIngredients.visibility = View.GONE
                    } else {
                        binding.tvEmptyMessage.visibility = View.GONE
                        binding.rvIngredients.visibility = View.VISIBLE
                        adapter.setProducts(state.products)
                    }
                }
                is ProductsUiState.Error -> {
                    binding.pbLoading.visibility = View.GONE
                    binding.rvIngredients.visibility = View.GONE
                    binding.tvEmptyMessage.visibility = View.VISIBLE
                    binding.tvEmptyMessage.text = "Sin conexión con FastAPI: ${state.message}"
                }
            }
        }
    }
}
