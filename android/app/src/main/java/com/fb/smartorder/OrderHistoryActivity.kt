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
import com.fb.smartorder.model.OrderDetailResponse
import com.fb.smartorder.ui.OrderHistoryAdapter
import com.fb.smartorder.ui.ProductViewModel

class OrderHistoryActivity : AppCompatActivity() {

    private lateinit var binding: ActivityOrderHistoryBinding
    private val viewModel: ProductViewModel by viewModels()
    private lateinit var adapter: OrderHistoryAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityOrderHistoryBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupRecyclerView()
        loadHistory()
    }

    private fun setupRecyclerView() {
        adapter = OrderHistoryAdapter { order ->
            handleWhatsAppClick(order)
        }
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

        if (suborders.size == 1) {
            val single = suborders[0]
            val waUrl = single.whatsappUrl
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
                    selectedSub.whatsappUrl?.let { url ->
                        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                        startActivity(intent)
                    }
                }
                .setPositiveButton("Cerrar", null)
                .show()
        }
    }
}

