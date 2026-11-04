package com.fb.smartorder.ui

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.fb.smartorder.databinding.ItemOrderHistoryBinding
import com.fb.smartorder.model.OrderDetailResponse

class OrderHistoryAdapter(
    private val onReopenWhatsApp: (OrderDetailResponse) -> Unit
) : RecyclerView.Adapter<OrderHistoryAdapter.HistoryViewHolder>() {

    private val allOrders = mutableListOf<OrderDetailResponse>()
    private val filteredOrders = mutableListOf<OrderDetailResponse>()

    fun setOrders(orders: List<OrderDetailResponse>) {
        allOrders.clear()
        allOrders.addAll(orders)
        filteredOrders.clear()
        filteredOrders.addAll(orders)
        notifyDataSetChanged()
    }

    fun filterBySupplier(supplierId: String?) {
        filteredOrders.clear()
        if (supplierId.isNullOrEmpty() || supplierId == "TODOS") {
            filteredOrders.addAll(allOrders)
        } else {
            filteredOrders.addAll(
                allOrders.filter { order ->
                    order.supplierSuborders?.any { it.supplierId == supplierId || it.supplierName.contains(supplierId, ignoreCase = true) } == true
                }
            )
        }
        notifyDataSetChanged()
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): HistoryViewHolder {
        val binding = ItemOrderHistoryBinding.inflate(
            LayoutInflater.from(parent.context),
            parent,
            false
        )
        return HistoryViewHolder(binding)
    }

    override fun onBindViewHolder(holder: HistoryViewHolder, position: Int) {
        holder.bind(filteredOrders[position])
    }

    override fun getItemCount(): Int = filteredOrders.size

    inner class HistoryViewHolder(
        private val binding: ItemOrderHistoryBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(order: OrderDetailResponse) {
            val shortId = if (!order.id.isNullOrEmpty() && order.id.length > 6) {
                order.id.takeLast(6).uppercase()
            } else {
                order.id ?: "---"
            }
            binding.tvHistoryOrderId.text = "PEDIDO #$shortId"

            val statusText = (order.status ?: "pending").uppercase()
            binding.tvHistoryStatus.text = if (statusText == "SENT") "ENVIADO" else "REGISTRADO"

            binding.tvHistoryDate.text = "Fecha: ${order.createdAt?.take(16)?.replace("T", " ") ?: "Reciente"}"
            binding.tvHistoryTotal.text = String.format("%.2f €", order.totalAmount)

            val suborders = order.supplierSuborders ?: emptyList()
            val supplierNames = suborders.map { it.supplierName }.distinct().joinToString(", ")
            binding.tvHistorySuppliers.text = "Proveedores: ${supplierNames.ifEmpty { "General" }}"

            if (!order.chefNotes.isNullOrEmpty()) {
                binding.tvHistoryChefNotes.visibility = View.VISIBLE
                binding.tvHistoryChefNotes.text = "Nota: ${order.chefNotes}"
            } else {
                binding.tvHistoryChefNotes.visibility = View.GONE
            }

            binding.btnReopenWhatsApp.setOnClickListener {
                onReopenWhatsApp(order)
            }
        }
    }
}

