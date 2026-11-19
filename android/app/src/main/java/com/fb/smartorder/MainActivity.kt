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
import com.fb.smartorder.ui.dialogs.OrderDispatchDialog
import com.fb.smartorder.ui.dialogs.ProductDialogs
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
        setupCatalogFilterTabs()
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
        catalogAdapter = ProductAdapter(
            onQuantityChanged = { prod, qty ->
                if (qty > 0 && !prod.isFavorite) {
                    viewModel.toggleFavorite(prod)
                }
                refreshOrderView()
            },
            onFavoriteToggle = { prod ->
                viewModel.toggleFavorite(prod) { success ->
                    if (success) {
                        catalogAdapter.notifyDataSetChanged()
                    }
                }
            },
            onEditProduct = { prod ->
                showEditProductDialog(prod)
            }
        )
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

        // Tab 4: Ajustes / Perfil
        binding.navItemSettings.setOnClickListener {
            startActivity(Intent(this, ProfileActivity::class.java))
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
        ProductDialogs.showAddOffCatalogDialog(this, viewModel) { customNote ->
            catalogAdapter.addCustomProduct(customNote, 1)
            refreshOrderView()
        }
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
            binding.tvButtonText.text = "DESPACHAR PEDIDO (${lines.size})"
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
        OrderDispatchDialog.show(this, orderId, suborders, orderDetail) {
            clearComandaAndRefresh()
        }
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
            .setTitle("Digitalizando lista de cocina")
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
                    .setTitle("Digitalización completada")
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

        val allItems = mutableListOf<Pair<String?, String>>(Pair(null, "TODOS"))
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
            tv.setTextColor(getColor(R.color.bg_paper))
        } else {
            tv.setBackgroundResource(R.drawable.bg_btn_secondary_retro)
            tv.setTextColor(getColor(R.color.text_primary))
        }
    }

    private fun setupCatalogFilterTabs() {
        binding.tabFilterFavorites.setOnClickListener {
            selectCatalogFilterTab("favorites")
        }
        binding.tabFilterAll.setOnClickListener {
            selectCatalogFilterTab("all")
        }
        binding.tabFilterHidden.setOnClickListener {
            selectCatalogFilterTab("hidden")
        }
    }

    private fun selectCatalogFilterTab(mode: String) {
        catalogAdapter.setFilterMode(mode)
        val activeBg = ContextCompat.getDrawable(this, R.drawable.bg_btn_retro)
        val inactiveBg = null
        val paperColor = ContextCompat.getColor(this, R.color.bg_paper)
        val mutedColor = ContextCompat.getColor(this, R.color.text_secondary)

        binding.tabFilterFavorites.background = if (mode == "favorites") activeBg else inactiveBg
        binding.tabFilterFavorites.setTextColor(if (mode == "favorites") paperColor else mutedColor)

        binding.tabFilterAll.background = if (mode == "all") activeBg else inactiveBg
        binding.tabFilterAll.setTextColor(if (mode == "all") paperColor else mutedColor)

        binding.tabFilterHidden.background = if (mode == "hidden") activeBg else inactiveBg
        binding.tabFilterHidden.setTextColor(if (mode == "hidden") paperColor else mutedColor)
    }

    private fun showEditProductDialog(product: Product) {
        ProductDialogs.showEditProductDialog(this, product, viewModel) {
            catalogAdapter.notifyDataSetChanged()
        }
    }
}
