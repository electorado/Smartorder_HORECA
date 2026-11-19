package com.fb.smartorder.ui.dialogs

import android.app.Activity
import android.app.AlertDialog
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import com.fb.smartorder.R
import com.fb.smartorder.model.Product
import com.fb.smartorder.model.ProductOverrideRequest
import com.fb.smartorder.model.Supplier
import com.fb.smartorder.ui.ProductViewModel
import java.util.Locale

/**
 * Diálogos modales para gestión de productos: notas fuera de catálogo y personalización.
 */
object ProductDialogs {

    fun showAddOffCatalogDialog(
        activity: Activity,
        viewModel: ProductViewModel,
        onProductAdded: (Product) -> Unit
    ) {
        val dialogView = activity.layoutInflater.inflate(R.layout.dialog_add_off_catalog, null)
        val etDesc = dialogView.findViewById<EditText>(R.id.etOffCatalogDesc)
        val spinnerSupplier = dialogView.findViewById<Spinner>(R.id.spinnerOffCatalogSupplier)
        val btnCancel = dialogView.findViewById<Button>(R.id.btnOffCatalogCancel)
        val btnAdd = dialogView.findViewById<Button>(R.id.btnOffCatalogAdd)

        var loadedSuppliers: List<Supplier> = emptyList()

        val dialog = AlertDialog.Builder(activity)
            .setView(dialogView)
            .create()

        viewModel.getSuppliers { suppliers ->
            loadedSuppliers = suppliers
            val supplierNames = if (suppliers.isNotEmpty()) {
                suppliers.map { it.name }
            } else {
                listOf("DIALVA Hostelería S.L.")
            }
            val supplierAdapter = ArrayAdapter(activity, android.R.layout.simple_spinner_dropdown_item, supplierNames)
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

            onProductAdded(customNote)
            Toast.makeText(activity, "Nota asignada a $supplierName", Toast.LENGTH_SHORT).show()
            dialog.dismiss()
        }

        dialog.show()
    }

    fun showEditProductDialog(
        activity: Activity,
        product: Product,
        viewModel: ProductViewModel,
        onProductUpdated: () -> Unit
    ) {
        val dialogView = activity.layoutInflater.inflate(R.layout.dialog_edit_product, null)
        val tvOriginal = dialogView.findViewById<TextView>(R.id.tvOriginalInfo)
        val etName = dialogView.findViewById<EditText>(R.id.etEditProductName)
        val etPrice = dialogView.findViewById<EditText>(R.id.etEditProductPrice)
        val spinnerUnit = dialogView.findViewById<Spinner>(R.id.spinnerEditProductUnit)
        val cbHidden = dialogView.findViewById<CheckBox>(R.id.cbEditIsHidden)
        val btnReset = dialogView.findViewById<Button>(R.id.btnEditReset)
        val btnCancel = dialogView.findViewById<Button>(R.id.btnEditCancel)
        val btnSave = dialogView.findViewById<Button>(R.id.btnEditSave)

        val units = listOf("kg", "ud", "bolsa", "caja", "estuche", "bandeja", "tarrina", "lote")
        val unitAdapter = ArrayAdapter(activity, android.R.layout.simple_spinner_dropdown_item, units)
        spinnerUnit.adapter = unitAdapter

        val origName = product.originalName ?: product.name
        val origPrice = product.bestPrice?.let { String.format(Locale.US, "%.2f", it) } ?: "0.00"
        val origCode = product.supplierProductCode ?: product.id
        tvOriginal.text = "Original: $origCode · $origName ($origPrice €/${product.standardUnit})"

        etName.setText(product.customName ?: product.name)
        etPrice.setText(if (product.bestPrice != null) String.format(Locale.US, "%.2f", product.bestPrice) else "")
        val currentUnitIdx = units.indexOf(product.standardUnit).let { if (it >= 0) it else 0 }
        spinnerUnit.setSelection(currentUnitIdx)
        cbHidden.isChecked = product.isHidden

        val dialog = AlertDialog.Builder(activity)
            .setView(dialogView)
            .create()

        btnReset.setOnClickListener {
            viewModel.updateProductOverride(
                product.id,
                ProductOverrideRequest(
                    customName = null,
                    customPrice = null,
                    customUnit = null,
                    isHidden = false
                )
            ) { success ->
                if (success) {
                    Toast.makeText(activity, "Valores originales restablecidos", Toast.LENGTH_SHORT).show()
                    dialog.dismiss()
                }
            }
        }

        btnCancel.setOnClickListener { dialog.dismiss() }

        btnSave.setOnClickListener {
            val newName = etName.text.toString().trim()
            val newPriceStr = etPrice.text.toString().trim().replace(',', '.')
            val newPrice = newPriceStr.toDoubleOrNull()
            val selectedUnit = spinnerUnit.selectedItem.toString()
            val isHidden = cbHidden.isChecked

            val req = ProductOverrideRequest(
                customName = if (newName.isNotBlank()) newName else null,
                customPrice = newPrice,
                customUnit = selectedUnit,
                isHidden = isHidden
            )

            viewModel.updateProductOverride(product.id, req) { success ->
                if (success) {
                    product.name = newName.ifBlank { origName }
                    if (newPrice != null) product.bestPrice = newPrice
                    product.standardUnit = selectedUnit
                    product.isHidden = isHidden
                    onProductUpdated()
                    Toast.makeText(activity, "Producto personalizado guardado", Toast.LENGTH_SHORT).show()
                    dialog.dismiss()
                } else {
                    Toast.makeText(activity, "Error guardando cambios", Toast.LENGTH_SHORT).show()
                }
            }
        }

        dialog.show()
    }
}
