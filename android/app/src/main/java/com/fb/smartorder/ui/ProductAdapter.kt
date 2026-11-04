package com.fb.smartorder.ui

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.fb.smartorder.databinding.ItemIngredientBinding
import com.fb.smartorder.model.Product

class ProductAdapter(
    private val onQuantityChanged: ((Product, Int) -> Unit)? = null
) : RecyclerView.Adapter<ProductAdapter.ProductViewHolder>() {

    private val fullList = mutableListOf<Product>()
    private val displayedList = mutableListOf<Product>()
    private val quantities = mutableMapOf<String, Int>()
    private val selectedIds = mutableSetOf<String>()

    fun setProducts(products: List<Product>) {
        fullList.clear()
        fullList.addAll(products)
        displayedList.clear()
        displayedList.addAll(products)
        notifyDataSetChanged()
    }

    fun filter(query: String) {
        val cleanQuery = query.trim().lowercase()
        displayedList.clear()
        if (cleanQuery.isEmpty()) {
            displayedList.addAll(fullList)
        } else {
            displayedList.addAll(
                fullList.filter {
                    it.name.lowercase().contains(cleanQuery) ||
                            it.category.lowercase().contains(cleanQuery)
                }
            )
        }
        notifyDataSetChanged()
    }

    fun getSelectedQuantities(): Map<Product, Int> {
        val result = mutableMapOf<Product, Int>()
        for (prod in fullList) {
            val qty = quantities[prod.id] ?: 0
            if (qty > 0 && selectedIds.contains(prod.id)) {
                result[prod] = qty
            }
        }
        return result
    }

    fun setProductQuantity(productId: String, quantity: Int) {
        if (quantity > 0) {
            quantities[productId] = quantity
            selectedIds.add(productId)
        } else {
            quantities.remove(productId)
            selectedIds.remove(productId)
        }
        notifyDataSetChanged()
    }

    fun getProductById(id: String): Product? {
        return fullList.find { it.id == id }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ProductViewHolder {
        val binding = ItemIngredientBinding.inflate(
            LayoutInflater.from(parent.context),
            parent,
            false
        )
        return ProductViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ProductViewHolder, position: Int) {
        holder.bind(displayedList[position])
    }

    override fun getItemCount(): Int = displayedList.size

    inner class ProductViewHolder(
        private val binding: ItemIngredientBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(product: Product) {
            val qty = quantities[product.id] ?: 0
            val isChecked = selectedIds.contains(product.id)

            binding.tvProductName.text = product.name.uppercase()

            val priceFormatted = if (product.bestPrice != null && product.bestPrice > 0) {
                val supplier = product.bestSupplierName ?: "Oferta"
                "$supplier · ${String.format("%.2f", product.bestPrice)} €/${product.standardUnit}"
            } else {
                "Sin ofertas disponibles"
            }
            binding.tvProductSubtitle.text = priceFormatted

            // Badge de oferta / urgente si tiene más de 1 proveedor o precio ventajoso
            binding.tvUrgentBadge.visibility = if (product.availableOffers > 1) View.VISIBLE else View.GONE

            binding.tvQuantity.text = qty.toString()
            binding.cbSelected.isChecked = isChecked

            // Eventos de usuario
            binding.btnPlus.setOnClickListener {
                val newQty = (quantities[product.id] ?: 0) + 1
                quantities[product.id] = newQty
                selectedIds.add(product.id)
                binding.tvQuantity.text = newQty.toString()
                binding.cbSelected.isChecked = true
                onQuantityChanged?.invoke(product, newQty)
            }

            binding.btnMinus.setOnClickListener {
                val current = quantities[product.id] ?: 0
                if (current > 0) {
                    val newQty = current - 1
                    quantities[product.id] = newQty
                    if (newQty == 0) {
                        selectedIds.remove(product.id)
                        binding.cbSelected.isChecked = false
                    }
                    binding.tvQuantity.text = newQty.toString()
                    onQuantityChanged?.invoke(product, newQty)
                }
            }

            binding.cbSelected.setOnCheckedChangeListener { _, checked ->
                if (checked) {
                    selectedIds.add(product.id)
                    if ((quantities[product.id] ?: 0) == 0) {
                        quantities[product.id] = 1
                        binding.tvQuantity.text = "1"
                    }
                } else {
                    selectedIds.remove(product.id)
                    quantities[product.id] = 0
                    binding.tvQuantity.text = "0"
                }
                onQuantityChanged?.invoke(product, quantities[product.id] ?: 0)
            }
        }
    }
}

