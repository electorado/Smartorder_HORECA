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
    var showOnlySelected: Boolean = false
    private var currentQuery: String = ""
    private var selectedSupplierId: String? = null

    fun setProducts(products: List<Product>) {
        fullList.clear()
        fullList.addAll(products)
        applyFilters()
    }

    fun addCustomProduct(product: Product, quantity: Int) {
        if (fullList.none { it.id == product.id }) {
            fullList.add(0, product)
        }
        setProductQuantity(product.id, quantity)
    }

    fun filter(query: String) {
        currentQuery = query
        applyFilters()
    }

    fun filterBySupplier(supplierId: String?) {
        selectedSupplierId = supplierId
        applyFilters()
    }

    fun setOnlySelectedFilter(onlySelected: Boolean) {
        showOnlySelected = onlySelected
        applyFilters()
    }

    private fun normalize(text: String): String {
        return java.text.Normalizer.normalize(text, java.text.Normalizer.Form.NFD)
            .replace("\\p{InCombiningDiacriticalMarks}+".toRegex(), "")
            .lowercase()
            .trim()
    }

    private fun applyFilters() {
        val cleanQuery = normalize(currentQuery)
        val queryWords = cleanQuery.split("\\s+".toRegex()).filter { it.isNotEmpty() }

        displayedList.clear()
        displayedList.addAll(
            fullList.filter { prod ->
                // Las notas, observaciones e ítems ad-hoc fuera de catálogo NO deben mostrarse en el catálogo oficial
                if (!showOnlySelected && prod.id.startsWith("custom_")) {
                    return@filter false
                }

                val normName = normalize(prod.name)
                val normCategory = normalize(prod.category)
                val normSupplier = normalize(prod.bestSupplierName.orEmpty())

                val matchesQuery = if (queryWords.isEmpty()) {
                    true
                } else {
                    queryWords.all { word ->
                        normName.contains(word) ||
                        normCategory.contains(word) ||
                        normSupplier.contains(word)
                    }
                }

                val matchesSelection = !showOnlySelected || ((quantities[prod.id] ?: 0) > 0 && selectedIds.contains(prod.id))
                val matchesSupplier = selectedSupplierId == null || prod.bestSupplierId == selectedSupplierId
                matchesQuery && matchesSelection && matchesSupplier
            }
        )
        notifyDataSetChanged()
    }

    fun getSelectedQuantities(): Map<Product, Int> {
        val result = mutableMapOf<Product, Int>()
        for (prod in fullList) {
            val qty = quantities[prod.id] ?: 0
            if (qty > 0) {
                result[prod] = qty
            }
        }
        return result
    }

    fun getOrderLines(): List<OrderLine> {
        val result = mutableListOf<OrderLine>()
        for (prod in fullList) {
            val qty = quantities[prod.id] ?: 0
            if (qty > 0) {
                result.add(OrderLine(prod, qty))
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
            if (productId.startsWith("custom_")) {
                fullList.removeAll { it.id == productId }
            }
        }
        applyFilters()
    }

    fun clearOrder() {
        quantities.clear()
        selectedIds.clear()
        fullList.removeAll { it.id.startsWith("custom_") }
        applyFilters()
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

            // Desvincular listener antes de asignar estado para evitar disparos accidentales en reciclado
            binding.cbSelected.setOnCheckedChangeListener(null)
            binding.cbSelected.isChecked = isChecked
            binding.tvQuantity.text = qty.toString()

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
                    if (newQty > 0) {
                        quantities[product.id] = newQty
                    } else {
                        quantities.remove(product.id)
                        selectedIds.remove(product.id)
                        binding.cbSelected.isChecked = false
                    }
                    binding.tvQuantity.text = newQty.toString()
                    onQuantityChanged?.invoke(product, newQty)
                }
            }

            binding.cbSelected.setOnClickListener {
                val checked = binding.cbSelected.isChecked
                if (checked) {
                    selectedIds.add(product.id)
                    val current = quantities[product.id] ?: 0
                    val newQty = if (current > 0) current else 1
                    quantities[product.id] = newQty
                    binding.tvQuantity.text = newQty.toString()
                    onQuantityChanged?.invoke(product, newQty)
                } else {
                    selectedIds.remove(product.id)
                    quantities.remove(product.id)
                    binding.tvQuantity.text = "0"
                    onQuantityChanged?.invoke(product, 0)
                }
            }
        }
    }
}

