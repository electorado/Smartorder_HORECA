package com.fb.smartorder.ui

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.fb.smartorder.databinding.ItemSupplierBinding
import com.fb.smartorder.model.Supplier

class SuppliersAdapter(
    private val onSupplierClick: ((Supplier) -> Unit)? = null
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
            binding.tvSupplierChannelBadge.text = (supplier.preferredChannel ?: "whatsapp").uppercase()
            binding.tvSupplierItemPhone.text = "Teléfono: ${supplier.phone ?: "No configurado"}"
            binding.tvSupplierItemEmail.text = "Email: ${supplier.email ?: "pedidos@proveedor.com"}"

            binding.root.setOnClickListener {
                onSupplierClick?.invoke(supplier)
            }
        }
    }
}

