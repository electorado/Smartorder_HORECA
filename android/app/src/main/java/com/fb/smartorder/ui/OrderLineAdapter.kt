package com.fb.smartorder.ui

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.fb.smartorder.databinding.ItemOrderLineBinding
import com.fb.smartorder.model.Product

data class OrderLine(
    val product: Product,
    var quantity: Int
)

class OrderLineAdapter(
    private val onQuantityChanged: (Product, Int) -> Unit,
    private val onDeleteClicked: (Product) -> Unit
) : RecyclerView.Adapter<OrderLineAdapter.OrderLineViewHolder>() {

    private val lines = mutableListOf<OrderLine>()

    fun setLines(newLines: List<OrderLine>) {
        lines.clear()
        lines.addAll(newLines)
        notifyDataSetChanged()
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): OrderLineViewHolder {
        val binding = ItemOrderLineBinding.inflate(
            LayoutInflater.from(parent.context),
            parent,
            false
        )
        return OrderLineViewHolder(binding)
    }

    override fun onBindViewHolder(holder: OrderLineViewHolder, position: Int) {
        holder.bind(lines[position])
    }

    override fun getItemCount(): Int = lines.size

    inner class OrderLineViewHolder(
        private val binding: ItemOrderLineBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(line: OrderLine) {
            val prod = line.product
            val qty = line.quantity

            val isNote = prod.id.startsWith("custom_note_") || prod.standardUnit == "nota"

            if (isNote) {
                binding.tvLineName.text = "[NOTA] \"${prod.name}\""
                binding.tvLineSubtitle.text = "Nota para: ${prod.bestSupplierName ?: "Proveedor"} · Indicación especial"
                binding.layoutLineStepper.visibility = View.GONE
            } else {
                binding.tvLineName.text = prod.name.uppercase()

                val price = prod.bestPrice ?: 0.0
                val subtotal = price * qty
                val supp = prod.bestSupplierName ?: "Proveedor General"

                val priceInfo = if (price > 0) {
                    String.format("%s · %.2f €/%s · Subtotal: %.2f €", supp, price, prod.standardUnit, subtotal)
                } else {
                    "$supp · Precio especial a consultar"
                }
                binding.tvLineSubtitle.text = priceInfo
                binding.tvLineQuantity.text = qty.toString()
                binding.layoutLineStepper.visibility = View.VISIBLE

                binding.btnLinePlus.setOnClickListener {
                    val newQty = line.quantity + 1
                    line.quantity = newQty
                    binding.tvLineQuantity.text = newQty.toString()
                    onQuantityChanged(prod, newQty)
                }

                binding.btnLineMinus.setOnClickListener {
                    if (line.quantity > 1) {
                        val newQty = line.quantity - 1
                        line.quantity = newQty
                        binding.tvLineQuantity.text = newQty.toString()
                        onQuantityChanged(prod, newQty)
                    } else {
                        onDeleteClicked(prod)
                    }
                }
            }

            binding.btnDeleteLine.setOnClickListener {
                onDeleteClicked(prod)
            }
        }
    }
}

