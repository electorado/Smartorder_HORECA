package com.fb.smartorder.ui

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.fb.smartorder.databinding.ItemSupplierBinding
import com.fb.smartorder.model.Supplier

class SuppliersAdapter(
    private val onSupplierClick: ((Supplier) -> Unit)? = null,
    private val onSupplierLongClick: ((Supplier) -> Unit)? = null
) : RecyclerView.Adapter<SuppliersAdapter.SupplierViewHolder>() {

    private val suppliersList = mutableListOf<Supplier>()

    fun setSuppliers(suppliers: List<Supplier>) {
        suppliersList.clear()
        suppliersList.addAll(suppliers)
        notifyDataSetChanged()
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): SupplierViewHolder {
        val binding = ItemSupplierBinding.inflate(
            LayoutInflater.from(parent.context),
            parent,
            false
        )
        return SupplierViewHolder(binding)
    }

    override fun onBindViewHolder(holder: SupplierViewHolder, position: Int) {
        holder.bind(suppliersList[position])
    }

    override fun getItemCount(): Int = suppliersList.size

    inner class SupplierViewHolder(
        private val binding: ItemSupplierBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(supplier: Supplier) {
            binding.tvSupplierItemName.text = supplier.name
            val isEmail = supplier.preferredChannel?.lowercase() == "email"
            if (isEmail) {
                binding.tvSupplierChannelBadge.setBackgroundResource(com.fb.smartorder.R.drawable.bg_badge_email)
                binding.tvSupplierChannelBadge.setTextColor(android.graphics.Color.parseColor("#1565C0"))
                binding.tvSupplierChannelBadge.text = "EMAIL ✉️"
            } else {
                binding.tvSupplierChannelBadge.setBackgroundResource(com.fb.smartorder.R.drawable.bg_badge_whatsapp)
                binding.tvSupplierChannelBadge.setTextColor(android.graphics.Color.parseColor("#2E7D32"))
                binding.tvSupplierChannelBadge.text = "WHATSAPP 📲"
            }
            binding.tvSupplierItemPhone.text = "Teléfono: ${supplier.phone ?: "No configurado"}"
            val emailText = if (supplier.email.isNullOrBlank()) "No disponible (Solo WhatsApp)" else supplier.email
            binding.tvSupplierItemEmail.text = "Email: $emailText"

            binding.root.setOnClickListener {
                onSupplierClick?.invoke(supplier)
            }
            binding.root.setOnLongClickListener {
                onSupplierLongClick?.invoke(supplier)
                true
            }
        }
    }
}

