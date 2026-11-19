package com.fb.smartorder

import android.app.AlertDialog
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Toast
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import com.fb.smartorder.databinding.ActivityOrderHistoryBinding
import com.fb.smartorder.util.SessionManager
import com.fb.smartorder.model.*
import com.fb.smartorder.ui.OrderHistoryAdapter
import com.fb.smartorder.ui.ProductViewModel

class OrderHistoryActivity : AppCompatActivity() {

    private lateinit var binding: ActivityOrderHistoryBinding
    private val viewModel: ProductViewModel by viewModels()
    private lateinit var adapter: OrderHistoryAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        SessionManager.getUserEmail(this)
        binding = ActivityOrderHistoryBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupRecyclerView()
        setupBottomNavigation()
        loadHistory()
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
            val intent = Intent(this, SuppliersActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            }
            startActivity(intent)
            finish()
        }
    }

    private fun setupRecyclerView() {
        adapter = OrderHistoryAdapter(
            onViewOrder = { order ->
                showOrderDetailDialog(order)
            }
        )
        binding.rvOrderHistory.layoutManager = LinearLayoutManager(this)
        binding.rvOrderHistory.adapter = adapter
    }

    private fun loadHistory() {
        binding.pbHistoryLoading.visibility = View.VISIBLE
        binding.tvEmptyHistory.visibility = View.GONE

        viewModel.getOrdersHistory { orders ->
            binding.pbHistoryLoading.visibility = View.GONE
            if (orders.isEmpty()) {
                binding.tvEmptyHistory.visibility = View.VISIBLE
            } else {
                binding.tvEmptyHistory.visibility = View.GONE
                adapter.setOrders(orders)
                setupSupplierFilter(orders)
            }
        }
    }

    private fun setupSupplierFilter(orders: List<OrderDetailResponse>) {
        val suppliers = mutableSetOf("TODOS")
        for (o in orders) {
            o.supplierSuborders?.forEach {
                suppliers.add(it.supplierName)
            }
        }
        val spinnerAdapter = ArrayAdapter(
            this,
            android.R.layout.simple_spinner_dropdown_item,
            suppliers.toList()
        )
        binding.spinnerSupplierFilter.adapter = spinnerAdapter

        binding.spinnerSupplierFilter.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                val selected = suppliers.toList()[position]
                adapter.filterBySupplier(if (selected == "TODOS") null else selected)
            }

            override fun onNothingSelected(parent: AdapterView<*>?) {}
        }
    }

    private fun handleWhatsAppClick(order: OrderDetailResponse) {
        val suborders = order.supplierSuborders ?: emptyList()
        if (suborders.isEmpty()) {
            Toast.makeText(this, "Este pedido no tiene subpedidos generados", Toast.LENGTH_SHORT).show()
            return
        }

        fun buildSafeWaUrl(so: SupplierSubOrderResponse): String? {
            val phone = so.supplierPhone
            if (!phone.isNullOrBlank()) {
                val parts = phone.split(Regex("[/,;\\n|y\\-]"))
                val cands = mutableListOf<String>()
                for (p in parts) {
                    var digits = p.filter { it.isDigit() }
                    if (digits.startsWith("0034")) digits = digits.substring(4)
                    else if (digits.startsWith("34") && digits.length == 11) digits = digits.substring(2)
                    if (digits.length == 9 || (digits.length in 10..15)) {
                        cands.add(digits)
                    }
                }
                if (cands.isEmpty()) {
                    val allDigits = phone.filter { it.isDigit() }
                    if (allDigits.length in 9..15) cands.add(allDigits)
                }
                val mobile = cands.firstOrNull { it.startsWith("6") || it.startsWith("7") } ?: cands.firstOrNull()
                val cleanPhone = if (mobile != null && mobile.length == 9) "34$mobile" else mobile
                if (!cleanPhone.isNullOrBlank()) {
                    val waText = so.whatsappText ?: "Pedido F&B SmartOrder"
                    return "https://api.whatsapp.com/send?phone=$cleanPhone&text=${Uri.encode(waText)}"
                }
            }
            return so.whatsappUrl
        }

        if (suborders.size == 1) {
            val single = suborders[0]
            val waUrl = buildSafeWaUrl(single)
            if (!waUrl.isNullOrEmpty()) {
                val intent = Intent(Intent.ACTION_VIEW, Uri.parse(waUrl))
                startActivity(intent)
            } else {
                Toast.makeText(this, "Sin URL de WhatsApp para ${single.supplierName}", Toast.LENGTH_SHORT).show()
            }
        } else {
            val names = suborders.map { "${it.supplierName} (${String.format("%.2f", it.subtotal)} €)" }.toTypedArray()
            AlertDialog.Builder(this)
                .setTitle("Seleccionar proveedor para WhatsApp")
                .setItems(names) { _, which ->
                    val selectedSub = suborders[which]
                    val waUrl = buildSafeWaUrl(selectedSub)
                    if (!waUrl.isNullOrEmpty()) {
                        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(waUrl))
                        startActivity(intent)
                    }
                }
                .setPositiveButton("Cerrar", null)
                .show()
        }
    }

    private fun handleViewPdf(order: OrderDetailResponse) {
        val prefs = getSharedPreferences("session_prefs", MODE_PRIVATE)
        val restaurantName = prefs.getString("KEY_RESTAURANT_NAME", "F&B SMARTORDER RESTAURANT") ?: "F&B SMARTORDER RESTAURANT"
        val chefName = prefs.getString("KEY_CHEF_NAME", "Chef de Turno") ?: "Chef de Turno"
        try {
            val pdfFile = com.fb.smartorder.util.PdfOrderGenerator.generateOrderPdf(this, order, restaurantName, chefName)
            com.fb.smartorder.util.PdfOrderGenerator.openPdfViewer(this, pdfFile)
        } catch (e: Exception) {
            Toast.makeText(this, "Error generando PDF: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun showOrderDetailDialog(order: OrderDetailResponse) {
        val dialogView = layoutInflater.inflate(R.layout.dialog_order_detail_pdf, null)
        val dialog = AlertDialog.Builder(this)
            .setView(dialogView)
            .create()

        val shortId = if (!order.id.isNullOrEmpty() && order.id.length > 6) {
            order.id.takeLast(6).uppercase()
        } else {
            order.id ?: "---"
        }

        dialogView.findViewById<android.widget.TextView>(R.id.tvDialogOrderTitle).text = "ALBARÁN DE PEDIDO #$shortId"
        dialogView.findViewById<android.widget.TextView>(R.id.tvDialogOrderSubtitle).text =
            String.format(java.util.Locale.US, "%.2f € · %s", order.totalAmount, order.createdAt?.take(16)?.replace("T", " ") ?: "Reciente")

        val statusText = (order.status ?: "pending").uppercase()
        dialogView.findViewById<android.widget.TextView>(R.id.tvDialogOrderStatus).text =
            if (statusText == "SENT") "ENVIADO" else "REGISTRADO"

        val suborders = order.supplierSuborders ?: emptyList()
        val supplierNames = suborders.map { it.supplierName }.distinct().joinToString(", ")
        dialogView.findViewById<android.widget.TextView>(R.id.tvDialogSuppliers).text =
            "Proveedores: ${supplierNames.ifEmpty { "General" }}"

        val tvChefNotes = dialogView.findViewById<android.widget.TextView>(R.id.tvDialogChefNotes)
        if (!order.chefNotes.isNullOrEmpty()) {
            tvChefNotes.visibility = View.VISIBLE
            tvChefNotes.text = "Nota: ${order.chefNotes}"
        } else {
            tvChefNotes.visibility = View.GONE
        }

        val ivPreview = dialogView.findViewById<android.widget.ImageView>(R.id.ivDialogPdfPreview)
        val pbRendering = dialogView.findViewById<android.widget.ProgressBar>(R.id.pbPdfRendering)

        // Generar albarán PDF y renderizar primera página
        val prefs = getSharedPreferences("session_prefs", MODE_PRIVATE)
        val restaurantName = prefs.getString("KEY_RESTAURANT_NAME", "F&B SMARTORDER RESTAURANT") ?: "F&B SMARTORDER RESTAURANT"
        val chefName = prefs.getString("KEY_CHEF_NAME", "Chef de Turno") ?: "Chef de Turno"

        var pdfFile: java.io.File? = null
        try {
            pdfFile = com.fb.smartorder.util.PdfOrderGenerator.generateOrderPdf(this, order, restaurantName, chefName)
            val thumbnail = com.fb.smartorder.util.PdfOrderGenerator.renderPdfFirstPage(pdfFile, 1.5f)
            if (thumbnail != null) {
                ivPreview.setImageBitmap(thumbnail)
                ivPreview.visibility = View.VISIBLE
            } else {
                ivPreview.visibility = View.GONE
            }
        } catch (e: Exception) {
            ivPreview.visibility = View.GONE
        } finally {
            pbRendering.visibility = View.GONE
        }

        // Tocar la vista previa abre el PDF completo
        ivPreview.setOnClickListener {
            pdfFile?.let { com.fb.smartorder.util.PdfOrderGenerator.openPdfViewer(this, it) }
        }

        // Botón abrir PDF externo
        dialogView.findViewById<android.widget.Button>(R.id.btnDialogOpenPdf).setOnClickListener {
            pdfFile?.let { com.fb.smartorder.util.PdfOrderGenerator.openPdfViewer(this, it) }
        }

        // Botón reenviar por WhatsApp
        dialogView.findViewById<android.widget.Button>(R.id.btnDialogWhatsApp).setOnClickListener {
            handleWhatsAppClick(order)
        }

        // Botón cerrar
        dialogView.findViewById<android.widget.Button>(R.id.btnDialogClose).setOnClickListener {
            dialog.dismiss()
        }

        dialog.show()
    }
}

