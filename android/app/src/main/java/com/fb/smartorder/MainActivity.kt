package com.fb.smartorder

import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.ContactsContract
import android.text.Editable
import android.text.TextWatcher
import android.view.View
import android.widget.*
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.LinearLayoutManager
import com.fb.smartorder.databinding.ActivityMainBinding
import com.fb.smartorder.util.SessionManager
import com.fb.smartorder.model.OrderDetailResponse
import com.fb.smartorder.model.OrderItem
import com.fb.smartorder.model.Product
import com.fb.smartorder.model.Supplier
import com.fb.smartorder.model.SupplierSubOrderResponse
import com.fb.smartorder.ui.OrderLineAdapter
import com.fb.smartorder.ui.ProductAdapter
import com.fb.smartorder.ui.ProductViewModel
import com.fb.smartorder.ui.ProductsUiState
import java.io.File
import java.io.FileOutputStream

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val viewModel: ProductViewModel by viewModels()

    // Adaptadores
    private lateinit var catalogAdapter: ProductAdapter
    private lateinit var orderLineAdapter: OrderLineAdapter

    // Estado de Pestaña activa (0 = Comanda, 1 = Catálogo)
    private var currentTabIndex = 0

    // Launcher de Imagen de Galería
    private val galleryImageLauncher = registerForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        uri?.let { handleFridgePhotoPicked(it) }
    }

    // Launcher de Cámara de Fotos
    private val cameraLauncher = registerForActivityResult(
        ActivityResultContracts.TakePicturePreview()
    ) { bitmap: android.graphics.Bitmap? ->
        bitmap?.let { handleCameraBitmap(it) }
    }

    // Permiso de Cámara en tiempo de ejecución (Android 14)
    private val requestCameraPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted: Boolean ->
        if (isGranted) {
            cameraLauncher.launch(null)
        } else {
            Toast.makeText(this, "Permiso de cámara denegado. Puedes elegir la foto desde la galería.", Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        SessionManager.getUserEmail(this)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupRecyclerViews()
        setupSearch()
        setupBottomNavigation()
        setupOffCatalogButtons()
        setupOrderSubmitButton()
        binding.btnRetryConnection.setOnClickListener {
            viewModel.loadProducts()
        }
        observeViewModel()

        val startTab = intent.getIntExtra("EXTRA_TAB_INDEX", 0)
        switchTab(startTab)

        if (intent.getBooleanExtra("EXTRA_START_SCAN", false)) {
            checkAndLaunchCamera()
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        val tab = intent.getIntExtra("EXTRA_TAB_INDEX", -1)
        if (tab >= 0) {
            switchTab(tab)
        }
        if (intent.getBooleanExtra("EXTRA_START_SCAN", false)) {
            checkAndLaunchCamera()
        }
    }

    private fun setupRecyclerViews() {
        // 1. Adaptador del Catálogo completo
        catalogAdapter = ProductAdapter { _, _ ->
            refreshOrderView()
        }
        binding.rvIngredients.layoutManager = LinearLayoutManager(this)
        binding.rvIngredients.adapter = catalogAdapter

        // 2. Adaptador de la Comanda Activa (Líneas de pedido)
        orderLineAdapter = OrderLineAdapter(
            onQuantityChanged = { product, newQty ->
                catalogAdapter.setProductQuantity(product.id, newQty)
                refreshOrderView()
            },
            onDeleteClicked = { product ->
                catalogAdapter.setProductQuantity(product.id, 0)
                refreshOrderView()
            }
        )
        binding.rvOrderLines.layoutManager = LinearLayoutManager(this)
        binding.rvOrderLines.adapter = orderLineAdapter
    }

    private fun setupBottomNavigation() {
        // Tab 1: Mi Pedido / Comanda
        binding.navItemOrder.setOnClickListener {
            switchTab(0)
        }

        // Tab 2: Catálogo de productos
        binding.navItemCatalog.setOnClickListener {
            switchTab(1)
        }

        // Tab 3: Botón central Cámara (1 toque = Cámara directa, Long Click = Galería)
        binding.navItemCamera.setOnClickListener {
            checkAndLaunchCamera()
        }
        binding.navItemCamera.setOnLongClickListener {
            Toast.makeText(this, "Abriendo galería...", Toast.LENGTH_SHORT).show()
            galleryImageLauncher.launch("image/*")
            true
        }

        // Tab 4: Historial de pedidos
        binding.navItemHistory.setOnClickListener {
            startActivity(Intent(this, OrderHistoryActivity::class.java))
        }

        // Tab 5: Directorio de Proveedores
        binding.navItemSuppliers.setOnClickListener {
            startActivity(Intent(this, SuppliersActivity::class.java))
        }

        // Botones en estado vacío de la comanda
        binding.btnEmptyScanCamera.setOnClickListener {
            checkAndLaunchCamera()
        }
        binding.btnEmptyScanCamera.setOnLongClickListener {
            Toast.makeText(this, "Abriendo galería...", Toast.LENGTH_SHORT).show()
            galleryImageLauncher.launch("image/*")
            true
        }
        binding.btnEmptyOpenCatalog.setOnClickListener {
            switchTab(1)
        }
        binding.btnEmptyAddNote.setOnClickListener {
            showAddOffCatalogDialog()
        }
    }

    private fun setupOffCatalogButtons() {
        binding.btnAddActiveOffCatalog.setOnClickListener {
            showAddOffCatalogDialog()
        }
    }

    private fun showAddOffCatalogDialog() {
        val dialogView = layoutInflater.inflate(R.layout.dialog_add_off_catalog, null)
        val etDesc = dialogView.findViewById<EditText>(R.id.etOffCatalogDesc)
        val spinnerSupplier = dialogView.findViewById<Spinner>(R.id.spinnerOffCatalogSupplier)
        val btnCancel = dialogView.findViewById<Button>(R.id.btnOffCatalogCancel)
        val btnAdd = dialogView.findViewById<Button>(R.id.btnOffCatalogAdd)

        var loadedSuppliers: List<Supplier> = emptyList()

        val dialog = AlertDialog.Builder(this)
            .setView(dialogView)
            .create()

        viewModel.getSuppliers { suppliers ->
            loadedSuppliers = suppliers
            val supplierNames = if (suppliers.isNotEmpty()) {
                suppliers.map { it.name }
            } else {
                listOf("DIALVA Hostelería S.L.")
            }
            val supplierAdapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, supplierNames)
            spinnerSupplier.adapter = supplierAdapter
        }

        btnCancel.setOnClickListener {
            dialog.dismiss()
        }

        btnAdd.setOnClickListener {
            val text = etDesc.text?.toString()?.trim().orEmpty()
            if (text.isEmpty()) {
                etDesc.error = "Escribe una nota o indicación"
                return@setOnClickListener
            }

            val selectedIndex = spinnerSupplier.selectedItemPosition
            val selectedSupplier = if (loadedSuppliers.isNotEmpty() && selectedIndex in loadedSuppliers.indices) {
                loadedSuppliers[selectedIndex]
            } else {
                null
            }

            val supplierId = selectedSupplier?.id ?: "prov_dialva_04"
            val supplierName = selectedSupplier?.name ?: "DIALVA Hostelería S.L."

            val customNote = Product(
                id = "custom_note_${System.currentTimeMillis()}",
                name = text,
                category = "Nota / Observación",
                standardUnit = "nota",
                bestPrice = 0.0,
                bestSupplierId = supplierId,
                bestSupplierName = supplierName,
                availableOffers = 1
            )

            catalogAdapter.addCustomProduct(customNote, 1)
            refreshOrderView()
            Toast.makeText(this, "Nota asignada a $supplierName", Toast.LENGTH_SHORT).show()
            dialog.dismiss()
        }

        dialog.show()
    }

    private fun switchTab(tabIndex: Int) {
        currentTabIndex = tabIndex
        if (tabIndex == 0) {
            // Ver Comanda Actual
            binding.layoutOrderView.visibility = View.VISIBLE
            binding.layoutCatalogView.visibility = View.GONE
            binding.tvSectionTitle.text = "COMANDA ACTUAL"

            // Estilos de la barra inferior
            binding.ivNavOrderIcon.setColorFilter(getColor(R.color.stamp_red))
            binding.tvNavOrderLabel.setTextColor(getColor(R.color.stamp_red))
            binding.tvNavOrderLabel.setTypeface(null, android.graphics.Typeface.BOLD)

            binding.ivNavCatalogIcon.setColorFilter(getColor(R.color.text_secondary))
            binding.tvNavCatalogLabel.setTextColor(getColor(R.color.text_secondary))
            binding.tvNavCatalogLabel.setTypeface(null, android.graphics.Typeface.NORMAL)

            refreshOrderView()
        } else if (tabIndex == 1) {
            // Ver Catálogo Completo
            binding.layoutOrderView.visibility = View.GONE
            binding.layoutCatalogView.visibility = View.VISIBLE
            binding.tvSectionTitle.text = "CATÁLOGO DE INGREDIENTES"

            // En catálogo se muestran todos los ingredientes maestros para añadir
            catalogAdapter.setOnlySelectedFilter(false)

            // Estilos de la barra inferior
            binding.ivNavCatalogIcon.setColorFilter(getColor(R.color.stamp_red))
            binding.tvNavCatalogLabel.setTextColor(getColor(R.color.stamp_red))
            binding.tvNavCatalogLabel.setTypeface(null, android.graphics.Typeface.BOLD)

            binding.ivNavOrderIcon.setColorFilter(getColor(R.color.text_secondary))
            binding.tvNavOrderLabel.setTextColor(getColor(R.color.text_secondary))
            binding.tvNavOrderLabel.setTypeface(null, android.graphics.Typeface.NORMAL)
        }
    }

    private fun refreshOrderView() {
        val lines = catalogAdapter.getOrderLines()

        // Actualizar Badge en barra inferior
        if (lines.isNotEmpty()) {
            binding.tvNavOrderBadge.visibility = View.VISIBLE
            binding.tvNavOrderBadge.text = lines.size.toString()
        } else {
            binding.tvNavOrderBadge.visibility = View.GONE
        }

        if (lines.isEmpty()) {
            binding.layoutEmptyOrder.visibility = View.VISIBLE
            binding.layoutActiveOrder.visibility = View.GONE
        } else {
            binding.layoutEmptyOrder.visibility = View.GONE
            binding.layoutActiveOrder.visibility = View.VISIBLE

            orderLineAdapter.setLines(lines)

            val productLines = lines.filter { !it.product.id.startsWith("custom_note_") && it.product.standardUnit != "nota" }
            val noteLines = lines.filter { it.product.id.startsWith("custom_note_") || it.product.standardUnit == "nota" }
            val totalUnits = productLines.sumOf { it.quantity }

            val summaryCount = when {
                productLines.isNotEmpty() && noteLines.isNotEmpty() ->
                    "${productLines.size} productos (${totalUnits} uds) + ${noteLines.size} ${if (noteLines.size == 1) "nota" else "notas"}"
                productLines.isNotEmpty() ->
                    "${productLines.size} líneas (${totalUnits} unidades)"
                else ->
                    "${noteLines.size} ${if (noteLines.size == 1) "nota para proveedor" else "notas para proveedores"}"
            }

            var estimatedTotal = 0.0
            for (line in lines) {
                val price = line.product.bestPrice ?: 0.0
                estimatedTotal += (price * line.quantity)
            }

            binding.tvOrderSummaryCount.text = summaryCount
            binding.tvOrderSummaryTotal.text = String.format("Total: %.2f €", estimatedTotal)
            binding.tvButtonText.text = "DESPACHAR PEDIDO (${lines.size}) 🚀"
        }
    }

    private fun setupSearch() {
        binding.etSearch.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                val query = s?.toString().orEmpty()
                catalogAdapter.filter(query)
                binding.btnClearSearch.visibility = if (query.isNotEmpty()) View.VISIBLE else View.GONE
            }
            override fun afterTextChanged(s: Editable?) {}
        })

        binding.btnClearSearch.setOnClickListener {
            binding.etSearch.text?.clear()
        }
    }

    private fun setupOrderSubmitButton() {
        binding.btnSubmitOrder.setOnClickListener {
            val lines = catalogAdapter.getOrderLines()
            if (lines.isEmpty()) {
                Toast.makeText(this, "Tu comanda está vacía", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            val notes = binding.etOrderNotes.text.toString().trim()
            viewModel.chefNotes = notes

            // Crear lista de OrderItems
            var totalAmount = 0.0
            val itemsList = mutableListOf<OrderItem>()

            for (line in lines) {
                val prod = line.product
                val unitPrice = prod.bestPrice ?: 0.0
                val subtotal = unitPrice * line.quantity
                totalAmount += subtotal

                val isNote = prod.id.startsWith("custom_note_") || prod.standardUnit == "nota"
                val isOff = prod.id.startsWith("custom_")
                itemsList.add(
                    OrderItem(
                        masterIngredientId = if (isOff) null else prod.id,
                        ingredientName = prod.name,
                        supplierId = prod.bestSupplierId ?: "prov_dialva_04",
                        supplierName = prod.bestSupplierName ?: "DIALVA Hostelería S.L.",
                        quantity = if (isNote) 1.0 else line.quantity.toDouble(),
                        unit = if (isNote) "nota" else prod.standardUnit,
                        unitPrice = unitPrice,
                        totalPrice = subtotal,
                        isOffCatalog = isOff,
                        notes = if (isNote) "Indicación para proveedor" else if (isOff) "Nota de cocina / Foto" else null
                    )
                )
            }

            binding.pbLoading.visibility = View.VISIBLE
            viewModel.submitOrder(itemsList, totalAmount) { result ->
                binding.pbLoading.visibility = View.GONE
                result.onSuccess { orderResponse ->
                    Toast.makeText(this, "Pedido registrado #${orderResponse.orderId}", Toast.LENGTH_SHORT).show()
                    val suborders = orderResponse.order?.supplierSuborders ?: emptyList()
                    handleOrderDispatched(orderResponse.orderId, suborders, orderResponse.order)
                }.onFailure { err ->
                    Toast.makeText(this, "Error enviando pedido: ${err.message}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun handleOrderDispatched(
        orderId: String?,
        suborders: List<SupplierSubOrderResponse>,
        orderDetail: OrderDetailResponse? = null
    ) {
        if (suborders.isEmpty()) {
            Toast.makeText(this, "Pedido completado.", Toast.LENGTH_SHORT).show()
            return
        }

        val dialogView = layoutInflater.inflate(R.layout.dialog_dispatch_checklist, null)
        val tvOrderRef = dialogView.findViewById<TextView>(R.id.tvOrderRef)
        val container = dialogView.findViewById<LinearLayout>(R.id.layoutSubordersContainer)
        val tvProgress = dialogView.findViewById<TextView>(R.id.tvDispatchProgress)
        val btnViewPdf = dialogView.findViewById<Button>(R.id.btnViewPdfDispatch)
        val btnFinish = dialogView.findViewById<Button>(R.id.btnFinishDispatch)
        val btnDismiss = dialogView.findViewById<Button>(R.id.btnDismissDispatch)

        btnViewPdf?.setOnClickListener {
            val fullOrder = orderDetail ?: OrderDetailResponse(
                id = orderId,
                supplierSuborders = suborders,
                totalAmount = suborders.sumOf { it.subtotal }
            )
            val prefs = getSharedPreferences("session_prefs", Context.MODE_PRIVATE)
            val restaurantName = prefs.getString("KEY_RESTAURANT_NAME", "F&B SMARTORDER RESTAURANT") ?: "F&B SMARTORDER RESTAURANT"
            val chefName = prefs.getString("KEY_CHEF_NAME", "Chef de Turno") ?: "Chef de Turno"
            try {
                val pdfFile = com.fb.smartorder.util.PdfOrderGenerator.generateOrderPdf(this, fullOrder, restaurantName, chefName)
                com.fb.smartorder.util.PdfOrderGenerator.openPdfViewer(this, pdfFile)
            } catch (e: Exception) {
                Toast.makeText(this, "Error generando PDF: ${e.message}", Toast.LENGTH_SHORT).show()
            }
        }

        val refShort = orderId?.takeLast(6)?.uppercase() ?: "N/A"
        val totalEur = suborders.sumOf { it.subtotal }
        tvOrderRef.text = "Pedido #$refShort · Total: ${String.format("%.2f", totalEur)} €"

        val dispatchedSet = mutableSetOf<String>()

        // Los que sean EMAIL ya vienen despachados automáticamente por el backend (Opción C)
        for (so in suborders) {
            val isEmail = so.preferredChannel?.lowercase() == "email" || so.emailDispatched == true
            if (isEmail) {
                dispatchedSet.add(so.supplierId ?: so.supplierName)
            }
        }

        fun updateProgress() {
            val total = suborders.size
            val done = dispatchedSet.size
            if (done >= total) {
                tvProgress.text = "✅ ¡Todos los pedidos despachados! ($total de $total)"
                tvProgress.setTextColor(ContextCompat.getColor(this, R.color.stamp_red))
                btnFinish.text = "FINALIZAR Y LIMPIAR COMANDA ✅"
            } else {
                tvProgress.text = "$done de $total pedidos despachados (${total - done} pendientes de WhatsApp)"
                tvProgress.setTextColor(ContextCompat.getColor(this, R.color.text_primary))
                btnFinish.text = "FINALIZAR COMANDA"
            }
        }

        val dialog = AlertDialog.Builder(this)
            .setView(dialogView)
            .setCancelable(false)
            .create()

        // Inflar cada subpedido en el contenedor
        for (so in suborders) {
            val itemView = layoutInflater.inflate(R.layout.item_dispatch_suborder, container, false)
            val tvName = itemView.findViewById<TextView>(R.id.tvSuborderSupplierName)
            val tvAmount = itemView.findViewById<TextView>(R.id.tvSuborderAmount)
            val tvBadge = itemView.findViewById<TextView>(R.id.tvSuborderChannelBadge)
            val tvSummary = itemView.findViewById<TextView>(R.id.tvSuborderItemsSummary)
            val layoutSent = itemView.findViewById<LinearLayout>(R.id.layoutSuborderSent)
            val tvSentText = itemView.findViewById<TextView>(R.id.tvSuborderSentText)
            val btnSend = itemView.findViewById<Button>(R.id.btnSendWhatsAppSuborder)

            val sKey = so.supplierId ?: so.supplierName
            val isEmail = so.preferredChannel?.lowercase() == "email" || so.emailDispatched == true

            tvName.text = so.supplierName
            tvAmount.text = String.format("%.2f €", so.subtotal)

            // Resumen de productos del subpedido
            val itemsLines = so.whatsappText?.lines()
                ?.filter { it.trim().startsWith("•") }
                ?.joinToString("\n")
            tvSummary.text = if (!itemsLines.isNullOrEmpty()) itemsLines else "Productos seleccionados de la comanda"

            if (isEmail) {
                tvBadge.text = "EMAIL ✉️"
                tvBadge.setBackgroundResource(R.drawable.bg_badge_email)
                tvBadge.setTextColor(ContextCompat.getColor(this, R.color.button_retro_bg))

                if (so.emailDispatched == true) {
                    btnSend.visibility = View.GONE
                    layoutSent.visibility = View.VISIBLE
                    tvSentText.text = "✅ ENVIADO POR SERVIDOR (EMAIL)"
                } else {
                    btnSend.text = "✉️ Enviar Email"
                    btnSend.visibility = View.VISIBLE
                    layoutSent.visibility = View.GONE
                    btnSend.setOnClickListener {
                        promptSaveContactIfNeeded(so) {
                            val emailIntent = Intent(Intent.ACTION_SENDTO).apply {
                                data = Uri.parse("mailto:${so.supplierEmail ?: ""}")
                                putExtra(Intent.EXTRA_SUBJECT, "Pedido F&B SmartOrder - ${so.supplierName}")
                                putExtra(Intent.EXTRA_TEXT, so.whatsappText ?: "Pedido de cocina")
                            }
                            try {
                                startActivity(emailIntent)
                            } catch (e: Exception) {
                                Toast.makeText(this, "No se encontró aplicación de correo", Toast.LENGTH_SHORT).show()
                            }
                            dispatchedSet.add(sKey)
                            btnSend.visibility = View.GONE
                            layoutSent.visibility = View.VISIBLE
                            tvSentText.text = "✅ ENVIADO POR EMAIL"
                            updateProgress()
                        }
                    }
                }
            } else {
                tvBadge.text = "WHATSAPP 📲"
                tvBadge.setBackgroundResource(R.drawable.bg_badge_whatsapp)
                tvBadge.setTextColor(ContextCompat.getColor(this, R.color.stamp_red))

                if (dispatchedSet.contains(sKey)) {
                    btnSend.visibility = View.GONE
                    layoutSent.visibility = View.VISIBLE
                    tvSentText.text = "✅ ENVIADO POR WHATSAPP"
                } else {
                    btnSend.visibility = View.VISIBLE
                    layoutSent.visibility = View.GONE

                    btnSend.setOnClickListener {
                        promptSaveContactIfNeeded(so) {
                            val waUrl = so.whatsappUrl
                            if (!waUrl.isNullOrEmpty()) {
                                val intent = Intent(Intent.ACTION_VIEW, Uri.parse(waUrl))
                                try {
                                    startActivity(intent)
                                } catch (e: Exception) {
                                    val shareIntent = Intent(Intent.ACTION_SEND).apply {
                                        type = "text/plain"
                                        putExtra(Intent.EXTRA_TEXT, so.whatsappText ?: "Pedido F&B SmartOrder")
                                    }
                                    startActivity(Intent.createChooser(shareIntent, "Compartir pedido con ${so.supplierName}"))
                                }
                            } else {
                                val intent = Intent(Intent.ACTION_SEND).apply {
                                    type = "text/plain"
                                    putExtra(Intent.EXTRA_TEXT, so.whatsappText ?: "Pedido F&B SmartOrder")
                                    `package` = "com.whatsapp"
                                }
                                try {
                                    startActivity(intent)
                                } catch (e: Exception) {
                                    startActivity(Intent.createChooser(intent, "Compartir pedido con ${so.supplierName}"))
                                }
                            }
                            dispatchedSet.add(sKey)
                            btnSend.visibility = View.GONE
                            layoutSent.visibility = View.VISIBLE
                            tvSentText.text = "✅ ENVIADO POR WHATSAPP"
                            updateProgress()
                        }
                    }
                }
            }

            container.addView(itemView)
        }

        updateProgress()

        btnFinish.setOnClickListener {
            val total = suborders.size
            val done = dispatchedSet.size
            if (done < total) {
                AlertDialog.Builder(this)
                    .setTitle("Pedidos pendientes ⚠️")
                    .setMessage("Aún te quedan ${total - done} pedidos de WhatsApp sin enviar. ¿Deseas limpiar la comanda de todas formas?")
                    .setPositiveButton("Sí, finalizar") { _, _ ->
                        clearComandaAndRefresh()
                        dialog.dismiss()
                    }
                    .setNegativeButton("Continuar enviando", null)
                    .show()
            } else {
                clearComandaAndRefresh()
                dialog.dismiss()
                Toast.makeText(this, "¡Comanda finalizada y pedidos despachados! 🎉", Toast.LENGTH_LONG).show()
            }
        }

        btnDismiss.setOnClickListener {
            dialog.dismiss()
        }

        dialog.show()
    }

    private fun isSupplierInPhoneContacts(phone: String?, email: String?): Boolean {
        if (phone.isNullOrBlank() && email.isNullOrBlank()) return true

        if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.READ_CONTACTS) == android.content.pm.PackageManager.PERMISSION_GRANTED) {
            try {
                if (!phone.isNullOrBlank()) {
                    val cleanDigits = phone.filter { it.isDigit() || it == '+' }
                    if (cleanDigits.length >= 6) {
                        val uri = Uri.withAppendedPath(ContactsContract.PhoneLookup.CONTENT_FILTER_URI, Uri.encode(cleanDigits))
                        contentResolver.query(uri, arrayOf(ContactsContract.PhoneLookup._ID), null, null, null)?.use { cursor ->
                            if (cursor.moveToFirst()) return true
                        }
                    }
                }
                if (!email.isNullOrBlank()) {
                    val uri = Uri.withAppendedPath(ContactsContract.CommonDataKinds.Email.CONTENT_LOOKUP_URI, Uri.encode(email))
                    contentResolver.query(uri, arrayOf(ContactsContract.CommonDataKinds.Email._ID), null, null, null)?.use { cursor ->
                        if (cursor.moveToFirst()) return true
                    }
                }
            } catch (e: Exception) {
                // Fallthrough
            }
        }

        val sp = getSharedPreferences("phone_contacts_cache", MODE_PRIVATE)
        val cacheKey = "contact_" + (phone ?: email ?: "")
        return sp.getBoolean(cacheKey, false)
    }

    private fun markSupplierContactHandled(phone: String?, email: String?) {
        val sp = getSharedPreferences("phone_contacts_cache", MODE_PRIVATE)
        val cacheKey = "contact_" + (phone ?: email ?: "")
        if (cacheKey.isNotEmpty()) {
            sp.edit().putBoolean(cacheKey, true).apply()
        }
    }

    private fun promptSaveContactIfNeeded(so: SupplierSubOrderResponse, onProceed: () -> Unit) {
        val phone = so.supplierPhone
        val email = so.supplierEmail

        if (isSupplierInPhoneContacts(phone, email)) {
            onProceed()
            return
        }

        val contactDetails = when {
            !phone.isNullOrBlank() && !email.isNullOrBlank() -> "Tel: $phone · Email: $email"
            !phone.isNullOrBlank() -> "Tel: $phone"
            !email.isNullOrBlank() -> "Email: $email"
            else -> ""
        }

        AlertDialog.Builder(this)
            .setTitle("Añadir a Contactos 📱")
            .setMessage("El proveedor '${so.supplierName}' ($contactDetails) aún no está guardado en la agenda de tu teléfono.\n\n¿Deseas añadirlo a tus contactos?")
            .setPositiveButton("Guardar en Agenda") { _, _ ->
                markSupplierContactHandled(phone, email)
                val insertIntent = Intent(Intent.ACTION_INSERT).apply {
                    type = ContactsContract.RawContacts.CONTENT_TYPE
                    putExtra(ContactsContract.Intents.Insert.NAME, so.supplierName)
                    if (!phone.isNullOrBlank()) {
                        putExtra(ContactsContract.Intents.Insert.PHONE, phone)
                    }
                    if (!email.isNullOrBlank()) {
                        putExtra(ContactsContract.Intents.Insert.EMAIL, email)
                    }
                }
                try {
                    startActivity(insertIntent)
                } catch (e: Exception) {
                    Toast.makeText(this, "No se pudo abrir la agenda de contactos", Toast.LENGTH_SHORT).show()
                }
                onProceed()
            }
            .setNegativeButton("Solo Enviar Pedido") { _, _ ->
                markSupplierContactHandled(phone, email)
                onProceed()
            }
            .setCancelable(true)
            .show()
    }

    private fun clearComandaAndRefresh() {
        catalogAdapter.clearOrder()
        viewModel.chefNotes = ""
        binding.etOrderNotes.text?.clear()
        refreshOrderView()
    }

    private fun checkAndLaunchCamera() {
        if (ContextCompat.checkSelfPermission(
                this,
                android.Manifest.permission.CAMERA
            ) == android.content.pm.PackageManager.PERMISSION_GRANTED
        ) {
            cameraLauncher.launch(null)
        } else {
            requestCameraPermissionLauncher.launch(android.Manifest.permission.CAMERA)
        }
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
        val progressDialog = AlertDialog.Builder(this)
            .setTitle("Digitalizando lista de cocina 📷")
            .setMessage("Analizando notas manuscritas con IA (Gemini) y asignando mejores ofertas de proveedores...")
            .setCancelable(false)
            .create()
        progressDialog.show()

        viewModel.scanKitchenNotes(file) { result ->
            progressDialog.dismiss()
            result.onSuccess { scanResp ->
                val items = scanResp.items
                if (items.isEmpty()) {
                    Toast.makeText(this, "No se detectaron ingredientes en la foto.", Toast.LENGTH_LONG).show()
                    return@onSuccess
                }

                var matchedCount = 0
                val unmatchedNames = mutableListOf<String>()

                for ((idx, item) in items.withIndex()) {
                    val mId = item.masterIngredientId
                    val qty = item.quantity.toInt().coerceAtLeast(1)
                    val prodId = item.bestOffer?.productId

                    // 1. Buscar en el catálogo local por product_id o por masterIngredientId
                    val catalogProd = if (!prodId.isNullOrEmpty()) {
                        catalogAdapter.getProductById(prodId)
                    } else if (!mId.isNullOrEmpty()) {
                        catalogAdapter.getProductById(mId)
                    } else null

                    if (catalogProd != null) {
                        catalogAdapter.setProductQuantity(catalogProd.id, qty)
                        matchedCount++
                    } else if (item.bestOffer != null && (item.bestOffer.price ?: 0.0) > 0.0) {
                        // El backend encontró una oferta real con precio y proveedor en el catálogo
                        val offName = item.bestOffer.rawName ?: item.cleanName ?: item.rawText
                        val matchedProd = Product(
                            id = prodId ?: "scan_matched_${System.currentTimeMillis()}_$idx",
                            name = offName,
                            category = item.bestOffer.category ?: "Catálogo",
                            standardUnit = item.bestOffer.unit ?: item.unit ?: "kg",
                            bestPrice = item.bestOffer.price,
                            bestSupplierId = item.bestOffer.supplierId,
                            bestSupplierName = item.bestOffer.supplierName,
                            availableOffers = 1
                        )
                        catalogAdapter.addCustomProduct(matchedProd, qty)
                        matchedCount++
                    } else {
                        // Ítem no encontrado en ningún catálogo ni con precio:
                        // No lo forzamos a la comanda con Dialva ni con 0€ para no molestar al cocinero
                        val unmatchName = item.cleanName ?: item.rawText
                        unmatchedNames.add(unmatchName)
                    }
                }

                // Salto automático a la pestaña de Comanda para ver el resultado
                switchTab(0)
                refreshOrderView()

                val summaryMsg = StringBuilder()
                if (matchedCount > 0) {
                    summaryMsg.append("✅ Se han añadido $matchedCount productos encontrados en tus catálogos a la comanda.\n\n")
                } else {
                    summaryMsg.append("ℹ️ No se encontraron productos de la foto en tus catálogos actuales.\n\n")
                }

                if (unmatchedNames.isNotEmpty()) {
                    summaryMsg.append("⚠️ Ítems de la foto no encontrados en tus catálogos (no añadidos para no ensuciar el pedido):\n")
                    unmatchedNames.forEach { summaryMsg.append(" • $it\n") }
                }

                AlertDialog.Builder(this)
                    .setTitle("Digitalización completada 📋")
                    .setMessage(summaryMsg.toString())
                    .setPositiveButton("Ver Comanda", null)
                    .show()

            }.onFailure { err ->
                Toast.makeText(this, "Error procesando foto: ${err.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun observeViewModel() {
        viewModel.uiState.observe(this) { state ->
            when (state) {
                is ProductsUiState.Loading -> {
                    binding.pbLoading.visibility = View.VISIBLE
                    binding.layoutConnectionWarning.visibility = View.GONE
                    binding.tvEmptyMessage.visibility = View.GONE
                }
                is ProductsUiState.Success -> {
                    binding.pbLoading.visibility = View.GONE
                    binding.layoutConnectionWarning.visibility = View.GONE
                    if (state.products.isEmpty()) {
                        binding.tvEmptyMessage.visibility = View.VISIBLE
                        binding.tvEmptyMessage.text = getString(R.string.empty_catalog)
                        binding.rvIngredients.visibility = View.GONE
                    } else {
                        binding.tvEmptyMessage.visibility = View.GONE
                        binding.rvIngredients.visibility = View.VISIBLE
                        catalogAdapter.setProducts(state.products)
                        val suppPairs = state.products
                            .mapNotNull { if (!it.bestSupplierId.isNullOrEmpty() && !it.bestSupplierName.isNullOrEmpty()) Pair(it.bestSupplierId!!, it.bestSupplierName!!) else null }
                            .distinctBy { it.first }
                        setupSupplierFilterChips(suppPairs)
                        refreshOrderView()
                    }
                }
                is ProductsUiState.Error -> {
                    binding.pbLoading.visibility = View.GONE
                    binding.layoutConnectionWarning.visibility = View.VISIBLE
                    binding.tvConnectionWarningText.text = "⚠️ Error conectando con el catálogo"
                    binding.tvEmptyMessage.visibility = View.VISIBLE
                    binding.tvEmptyMessage.text = "No se pudo sincronizar el catálogo. Comprueba tu conexión y pulsa Reintentar."
                    binding.rvIngredients.visibility = View.GONE
                }
            }
        }
    }

    private var activeFilterSupplierId: String? = null

    private fun setupSupplierFilterChips(suppliers: List<Pair<String, String>>) {
        binding.layoutSupplierChips.removeAllViews()
        if (suppliers.isEmpty()) {
            binding.hsvSupplierFilter.visibility = View.GONE
            return
        }
        binding.hsvSupplierFilter.visibility = View.VISIBLE

        val allItems = mutableListOf<Pair<String?, String>>(Pair(null, "📦 Todos"))
        suppliers.forEach { allItems.add(Pair(it.first, it.second)) }

        for (item in allItems) {
            val suppId = item.first
            val suppName = item.second
            val isSelected = suppId == activeFilterSupplierId

            val chipView = TextView(this).apply {
                text = suppName
                textSize = 12f
                typeface = android.graphics.Typeface.DEFAULT_BOLD
                setPadding(26, 12, 26, 12)
                val params = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                ).apply {
                    setMargins(6, 0, 6, 0)
                }
                layoutParams = params

                updateChipStyle(this, isSelected)

                setOnClickListener {
                    activeFilterSupplierId = suppId
                    catalogAdapter.filterBySupplier(suppId)
                    for (i in 0 until binding.layoutSupplierChips.childCount) {
                        val child = binding.layoutSupplierChips.getChildAt(i) as? TextView
                        val childSelected = (child?.tag as? String) == suppId
                        if (child != null) updateChipStyle(child, childSelected)
                    }
                }
                tag = suppId
            }
            binding.layoutSupplierChips.addView(chipView)
        }
    }

    private fun updateChipStyle(tv: TextView, isSelected: Boolean) {
        if (isSelected) {
            tv.setBackgroundResource(R.drawable.bg_btn_retro)
            tv.setTextColor(getColor(R.color.white))
        } else {
            tv.setBackgroundResource(R.drawable.bg_btn_secondary_retro)
            tv.setTextColor(getColor(R.color.text_primary))
        }
    }
}
