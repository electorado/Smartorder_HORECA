package com.fb.smartorder.ui.dialogs

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.view.View
import android.widget.Button
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.core.content.ContextCompat
import com.fb.smartorder.R
import com.fb.smartorder.model.OrderDetailResponse
import com.fb.smartorder.model.SupplierSubOrderResponse
import com.fb.smartorder.ui.ProductViewModel
import com.fb.smartorder.util.PdfOrderGenerator
import com.fb.smartorder.util.SupplierContactManager
import java.util.Locale

/**
 * Diálogo modal para la gestión del checklist de despacho de pedidos a proveedores
 * por WhatsApp, Email (Brevo SMTP directo) y generación de PDF.
 */
object OrderDispatchDialog {

    fun show(
        activity: Activity,
        orderId: String?,
        suborders: List<SupplierSubOrderResponse>,
        orderDetail: OrderDetailResponse? = null,
        viewModel: ProductViewModel? = null,
        onClearComanda: () -> Unit
    ) {
        if (suborders.isEmpty()) {
            Toast.makeText(activity, "Pedido completado.", Toast.LENGTH_SHORT).show()
            return
        }

        val dialogView = activity.layoutInflater.inflate(R.layout.dialog_dispatch_checklist, null)
        val tvOrderRef = dialogView.findViewById<TextView>(R.id.tvOrderRef)
        val container = dialogView.findViewById<LinearLayout>(R.id.layoutSubordersContainer)
        val tvProgress = dialogView.findViewById<TextView>(R.id.tvDispatchProgress)
        val btnViewPdf = dialogView.findViewById<Button>(R.id.btnViewPdfDispatch)
        val btnFinish = dialogView.findViewById<Button>(R.id.btnFinishDispatch)
        val btnDismiss = dialogView.findViewById<Button>(R.id.btnDismissDispatch)

        btnViewPdf?.setOnClickListener {
            val fullOrder = orderDetail ?: OrderDetailResponse(
                id = orderId,
                supplierSuborders = suborders,
                totalAmount = suborders.sumOf { it.subtotal }
            )
            val prefs = activity.getSharedPreferences("session_prefs", Context.MODE_PRIVATE)
            val restaurantName = prefs.getString("KEY_RESTAURANT_NAME", "F&B SMARTORDER RESTAURANT") ?: "F&B SMARTORDER RESTAURANT"
            val chefName = prefs.getString("KEY_CHEF_NAME", "Chef de Turno") ?: "Chef de Turno"
            try {
                val pdfFile = PdfOrderGenerator.generateOrderPdf(activity, fullOrder, restaurantName, chefName)
                PdfOrderGenerator.openPdfViewer(activity, pdfFile)
            } catch (e: Exception) {
                Toast.makeText(activity, "Error generando PDF: ${e.message}", Toast.LENGTH_SHORT).show()
            }
        }

        val refShort = orderId?.takeLast(6)?.uppercase() ?: "N/A"
        val totalEur = suborders.sumOf { it.subtotal }
        tvOrderRef.text = "Pedido #$refShort · Total: ${String.format(Locale.US, "%.2f", totalEur)} €"

        val dispatchedSet = mutableSetOf<String>()

        // Subpedidos despachados automáticamente por SMTP en backend
        for (so in suborders) {
            if (so.emailDispatched == true) {
                dispatchedSet.add(so.supplierId ?: so.supplierName)
            }
        }

        fun updateProgress() {
            val total = suborders.size
            val done = dispatchedSet.size
            if (done >= total) {
                tvProgress.text = "¡Todos los pedidos despachados! ($total de $total)"
                tvProgress.setTextColor(ContextCompat.getColor(activity, R.color.stamp_red))
                btnFinish.text = "FINALIZAR Y LIMPIAR COMANDA"
            } else {
                tvProgress.text = "$done de $total pedidos despachados (${total - done} pendientes de WhatsApp)"
                tvProgress.setTextColor(ContextCompat.getColor(activity, R.color.text_primary))
                btnFinish.text = "FINALIZAR COMANDA"
            }
        }

        val dialog = AlertDialog.Builder(activity)
            .setView(dialogView)
            .setCancelable(false)
            .create()

        // Inflar cada subpedido en el contenedor
        for (so in suborders) {
            val itemView = activity.layoutInflater.inflate(R.layout.item_dispatch_suborder, container, false)
            val tvName = itemView.findViewById<TextView>(R.id.tvSuborderSupplierName)
            val tvAmount = itemView.findViewById<TextView>(R.id.tvSuborderAmount)
            val ivBadge = itemView.findViewById<ImageView>(R.id.ivSuborderChannelBadge)
            val tvSummary = itemView.findViewById<TextView>(R.id.tvSuborderItemsSummary)
            val layoutSent = itemView.findViewById<LinearLayout>(R.id.layoutSuborderSent)
            val tvSentText = itemView.findViewById<TextView>(R.id.tvSuborderSentText)
            val btnSend = itemView.findViewById<Button>(R.id.btnSendWhatsAppSuborder)

            val sKey = so.supplierId ?: so.supplierName
            val isEmail = so.preferredChannel?.lowercase() == "email" || so.emailDispatched == true

            tvName.text = so.supplierName
            tvAmount.text = String.format(Locale.US, "%.2f €", so.subtotal)

            // Resumen de productos
            val itemsLines = so.whatsappText?.lines()
                ?.filter { it.trim().startsWith("•") }
                ?.joinToString("\n")
            tvSummary.text = if (!itemsLines.isNullOrEmpty()) itemsLines else "Productos seleccionados de la comanda"

            if (isEmail) {
                ivBadge.setImageResource(R.drawable.ic_logo_email)

                if (so.emailDispatched == true) {
                    layoutSent.visibility = View.VISIBLE
                    tvSentText.text = "ENVIADO (EMAIL · BREVO)"
                    if (!so.supplierPhone.isNullOrBlank()) {
                        btnSend.visibility = View.VISIBLE
                        btnSend.text = "Enviar copia por WhatsApp"
                        btnSend.setOnClickListener {
                            SupplierContactManager.promptSaveContactIfNeeded(activity, so) {
                                val sanitizedPhone = SupplierContactManager.cleanSupplierPhone(so.supplierPhone)
                                val waUrl = if (!sanitizedPhone.isNullOrBlank()) {
                                    val waText = so.whatsappText ?: "Pedido F&B SmartOrder"
                                    "https://api.whatsapp.com/send?phone=$sanitizedPhone&text=${Uri.encode(waText)}"
                                } else {
                                    so.whatsappUrl
                                }
                                if (!waUrl.isNullOrEmpty()) {
                                    try {
                                        activity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(waUrl)))
                                    } catch (e: Exception) {
                                        val shareIntent = Intent(Intent.ACTION_SEND).apply {
                                            type = "text/plain"
                                            putExtra(Intent.EXTRA_TEXT, so.whatsappText ?: "Pedido F&B SmartOrder")
                                        }
                                        activity.startActivity(Intent.createChooser(shareIntent, "Compartir pedido con ${so.supplierName}"))
                                    }
                                }
                            }
                        }
                    } else {
                        btnSend.visibility = View.GONE
                    }
                } else {
                    btnSend.text = "Enviar Email (Brevo SMTP)"
                    btnSend.visibility = View.VISIBLE
                    layoutSent.visibility = View.GONE
                    btnSend.setOnClickListener {
                        if (orderId != null && viewModel != null) {
                            btnSend.isEnabled = false
                            btnSend.text = "Enviando vía SMTP..."
                            viewModel.dispatchOrderEmail(orderId, so.supplierId) { result ->
                                activity.runOnUiThread {
                                    result.fold(
                                        onSuccess = { msg ->
                                            Toast.makeText(activity, "¡Email enviado a ${so.supplierName}!", Toast.LENGTH_SHORT).show()
                                            dispatchedSet.add(sKey)
                                            btnSend.visibility = View.GONE
                                            layoutSent.visibility = View.VISIBLE
                                            tvSentText.text = "ENVIADO (EMAIL · BREVO)"
                                            updateProgress()
                                        },
                                        onFailure = { err ->
                                            btnSend.isEnabled = true
                                            btnSend.text = "Reintentar Email (SMTP)"
                                            AlertDialog.Builder(activity)
                                                .setTitle("Aviso de Entrega de Correo")
                                                .setMessage("No se pudo conectar directamente con Brevo SMTP (${err.message}). ¿Deseas abrir tu cliente de correo (Gmail/Outlook) como respaldo?")
                                                .setPositiveButton("Abrir correo") { _, _ ->
                                                    val emailIntent = Intent(Intent.ACTION_SENDTO).apply {
                                                        data = Uri.parse("mailto:${so.supplierEmail ?: ""}")
                                                        putExtra(Intent.EXTRA_SUBJECT, "Pedido F&B SmartOrder - ${so.supplierName}")
                                                        putExtra(Intent.EXTRA_TEXT, so.whatsappText ?: "Pedido de cocina")
                                                    }
                                                    try {
                                                        activity.startActivity(emailIntent)
                                                        dispatchedSet.add(sKey)
                                                        btnSend.visibility = View.GONE
                                                        layoutSent.visibility = View.VISIBLE
                                                        tvSentText.text = "ENVIADO (EMAIL EXTERNO)"
                                                        updateProgress()
                                                    } catch (e: Exception) {
                                                        Toast.makeText(activity, "No se encontró aplicación de correo", Toast.LENGTH_SHORT).show()
                                                    }
                                                }
                                                .setNegativeButton("Cancelar", null)
                                                .show()
                                        }
                                    )
                                }
                            }
                        } else {
                            // En caso de que no haya referencia a la API, fallback a Intent
                            val emailIntent = Intent(Intent.ACTION_SENDTO).apply {
                                data = Uri.parse("mailto:${so.supplierEmail ?: ""}")
                                putExtra(Intent.EXTRA_SUBJECT, "Pedido F&B SmartOrder - ${so.supplierName}")
                                putExtra(Intent.EXTRA_TEXT, so.whatsappText ?: "Pedido de cocina")
                            }
                            try {
                                activity.startActivity(emailIntent)
                            } catch (e: Exception) {
                                Toast.makeText(activity, "No se encontró aplicación de correo", Toast.LENGTH_SHORT).show()
                            }
                            dispatchedSet.add(sKey)
                            btnSend.visibility = View.GONE
                            layoutSent.visibility = View.VISIBLE
                            tvSentText.text = "ENVIADO (EMAIL)"
                            updateProgress()
                        }
                    }
                }
            } else {
                ivBadge.setImageResource(R.drawable.ic_logo_whatsapp)

                if (dispatchedSet.contains(sKey)) {
                    btnSend.visibility = View.GONE
                    layoutSent.visibility = View.VISIBLE
                    tvSentText.text = "ENVIADO (WHATSAPP)"
                } else {
                    btnSend.visibility = View.VISIBLE
                    layoutSent.visibility = View.GONE

                    btnSend.setOnClickListener {
                        SupplierContactManager.promptSaveContactIfNeeded(activity, so) {
                            val sanitizedPhone = SupplierContactManager.cleanSupplierPhone(so.supplierPhone)
                            val waUrl = if (!sanitizedPhone.isNullOrBlank()) {
                                val waText = so.whatsappText ?: "Pedido F&B SmartOrder"
                                "https://api.whatsapp.com/send?phone=$sanitizedPhone&text=${Uri.encode(waText)}"
                            } else {
                                so.whatsappUrl
                            }

                            if (!waUrl.isNullOrEmpty()) {
                                val intent = Intent(Intent.ACTION_VIEW, Uri.parse(waUrl))
                                try {
                                    activity.startActivity(intent)
                                } catch (e: Exception) {
                                    val shareIntent = Intent(Intent.ACTION_SEND).apply {
                                        type = "text/plain"
                                        putExtra(Intent.EXTRA_TEXT, so.whatsappText ?: "Pedido F&B SmartOrder")
                                    }
                                    activity.startActivity(Intent.createChooser(shareIntent, "Compartir pedido con ${so.supplierName}"))
                                }
                            } else {
                                val intent = Intent(Intent.ACTION_SEND).apply {
                                    type = "text/plain"
                                    putExtra(Intent.EXTRA_TEXT, so.whatsappText ?: "Pedido F&B SmartOrder")
                                    `package` = "com.whatsapp"
                                }
                                try {
                                    activity.startActivity(intent)
                                } catch (e: Exception) {
                                    activity.startActivity(Intent.createChooser(intent, "Compartir pedido con ${so.supplierName}"))
                                }
                            }
                            dispatchedSet.add(sKey)
                            btnSend.visibility = View.GONE
                            layoutSent.visibility = View.VISIBLE
                            tvSentText.text = "ENVIADO (WHATSAPP)"
                            updateProgress()
                        }
                    }
                }
            }

            container.addView(itemView)
        }

        updateProgress()

        btnFinish.setOnClickListener {
            val total = suborders.size
            val done = dispatchedSet.size
            if (done < total) {
                AlertDialog.Builder(activity)
                    .setTitle("Pedidos pendientes")
                    .setMessage("Aún te quedan ${total - done} pedidos de WhatsApp sin enviar. ¿Deseas limpiar la comanda de todas formas?")
                    .setPositiveButton("Sí, finalizar") { _, _ ->
                        onClearComanda()
                        dialog.dismiss()
                    }
                    .setNegativeButton("Continuar enviando", null)
                    .show()
            } else {
                onClearComanda()
                dialog.dismiss()
                Toast.makeText(activity, "¡Comanda finalizada y pedidos despachados!", Toast.LENGTH_LONG).show()
            }
        }

        btnDismiss.setOnClickListener {
            dialog.dismiss()
        }

        dialog.show()
    }
}
