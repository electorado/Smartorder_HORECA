package com.fb.smartorder.util

import android.content.Context
import android.content.Intent
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import androidx.core.content.FileProvider
import com.fb.smartorder.model.OrderDetailResponse
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Generador nativo de Albaranes de Comanda en formato PDF (CU04 / R04F03).
 *
 * Utiliza android.graphics.pdf.PdfDocument (sin dependencias externas pesadas)
 * para renderizar un albarán formal de control de muelle con membrete del restaurante,
 * desglose agrupado por proveedor, precios y casillas de cotejo para recepción de mercancía.
 */
object PdfOrderGenerator {

    fun generateOrderPdf(
        context: Context,
        order: OrderDetailResponse,
        restaurantName: String = "F&B SMARTORDER RESTAURANT",
        chefName: String = "Chef de Turno"
    ): File {
        val pdfDocument = PdfDocument()

        // Dimensiones estándar A4 a 72 dpi: 595 x 842 puntos
        val pageWidth = 595
        val pageHeight = 842
        val pageInfo = PdfDocument.PageInfo.Builder(pageWidth, pageHeight, 1).create()
        val page = pdfDocument.startPage(pageInfo)
        val canvas: Canvas = page.canvas

        // Configuración de pinturas tipográficas
        val titlePaint = Paint().apply {
            color = Color.rgb(26, 26, 26)
            textSize = 18f
            typeface = Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD)
            isAntiAlias = true
        }

        val subtitlePaint = Paint().apply {
            color = Color.rgb(184, 42, 42) // Stamp Red
            textSize = 12f
            typeface = Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD)
            isAntiAlias = true
        }

        val headerPaint = Paint().apply {
            color = Color.rgb(80, 80, 80)
            textSize = 10f
            typeface = Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD)
            isAntiAlias = true
        }

        val bodyPaint = Paint().apply {
            color = Color.rgb(40, 40, 40)
            textSize = 10f
            typeface = Typeface.create(Typeface.SANS_SERIF, Typeface.NORMAL)
            isAntiAlias = true
        }

        val smallPaint = Paint().apply {
            color = Color.rgb(120, 120, 120)
            textSize = 8.5f
            typeface = Typeface.create(Typeface.SANS_SERIF, Typeface.ITALIC)
            isAntiAlias = true
        }

        val linePaint = Paint().apply {
            color = Color.rgb(210, 200, 185)
            strokeWidth = 1f
            style = Paint.Style.STROKE
        }

        val boxPaint = Paint().apply {
            color = Color.rgb(245, 239, 230) // Bg Paper
            style = Paint.Style.FILL
        }

        var yPos = 40f
        val leftMargin = 40f
        val rightMargin = pageWidth - 40f

        // 1. Membrete superior
        canvas.drawRect(leftMargin, yPos, rightMargin, yPos + 65f, boxPaint)
        canvas.drawText(restaurantName.uppercase(), leftMargin + 15f, yPos + 24f, titlePaint)
        canvas.drawText("ALBARÁN DE COMANDA Y CONTROL DE RECEPCIÓN", leftMargin + 15f, yPos + 42f, subtitlePaint)
        canvas.drawText("Muelle de Carga · Central de Compras Hostelería", leftMargin + 15f, yPos + 56f, smallPaint)

        val orderShortId = if (!order.id.isNullOrEmpty() && order.id.length > 6) {
            order.id.takeLast(6).uppercase()
        } else {
            order.id ?: "001"
        }

        // Ref y Fecha en la esquina derecha del encabezado
        val dateStr = order.createdAt?.take(16)?.replace("T", " ")
            ?: SimpleDateFormat("dd/MM/yyyy HH:mm", Locale.getDefault()).format(Date())

        val idPaint = Paint().apply {
            color = Color.rgb(184, 42, 42)
            textSize = 14f
            typeface = Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD)
            textAlign = Paint.Align.RIGHT
        }
        val datePaint = Paint().apply {
            color = Color.rgb(80, 80, 80)
            textSize = 9.5f
            textAlign = Paint.Align.RIGHT
        }

        canvas.drawText("PEDIDO #$orderShortId", rightMargin - 15f, yPos + 28f, idPaint)
        canvas.drawText("Fecha: $dateStr", rightMargin - 15f, yPos + 44f, datePaint)
        canvas.drawText("Emitido por: $chefName", rightMargin - 15f, yPos + 58f, datePaint)

        yPos += 85f

        // 2. Tabla de productos agrupados por subpedidos
        val suborders = order.supplierSuborders ?: emptyList()
        val allItems = order.items ?: emptyList()

        if (suborders.isNotEmpty()) {
            for (so in suborders) {
                if (yPos > pageHeight - 120f) break

                // Cabecera del proveedor
                val suppPaint = Paint().apply {
                    color = Color.rgb(26, 26, 26)
                    textSize = 11f
                    typeface = Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD)
                }
                val suppHeaderBg = Paint().apply {
                    color = Color.rgb(235, 230, 220)
                    style = Paint.Style.FILL
                }
                canvas.drawRect(leftMargin, yPos, rightMargin, yPos + 20f, suppHeaderBg)
                canvas.drawText("PROVEEDOR: ${so.supplierName.uppercase()} (Subtotal: ${String.format("%.2f €", so.subtotal)})", leftMargin + 8f, yPos + 14f, suppPaint)

                val phoneStr = so.supplierPhone ?: "N/D"
                val contactPaint = Paint().apply {
                    color = Color.rgb(100, 100, 100)
                    textSize = 9f
                    textAlign = Paint.Align.RIGHT
                }
                canvas.drawText("Contacto: $phoneStr", rightMargin - 8f, yPos + 14f, contactPaint)
                yPos += 26f

                // Cabeceras de columnas
                canvas.drawText("CANT.", leftMargin + 8f, yPos, headerPaint)
                canvas.drawText("PRODUCTO / DESCRIPCIÓN", leftMargin + 65f, yPos, headerPaint)
                canvas.drawText("P.UNIT.", rightMargin - 120f, yPos, headerPaint)
                canvas.drawText("TOTAL", rightMargin - 55f, yPos, headerPaint)
                canvas.drawText("OK", rightMargin - 18f, yPos, headerPaint)
                yPos += 5f
                canvas.drawLine(leftMargin, yPos, rightMargin, yPos, linePaint)
                yPos += 14f

                // Filtrar ítems de este proveedor
                val itemsOfSupplier = allItems.filter { it.supplierId == so.supplierId || it.supplierName == so.supplierName }

                if (itemsOfSupplier.isNotEmpty()) {
                    for (item in itemsOfSupplier) {
                        if (yPos > pageHeight - 90f) break

                        val qtyStr = "${String.format("%.1f", item.quantity)} ${item.unit}"
                        canvas.drawText(qtyStr, leftMargin + 8f, yPos, bodyPaint)

                        val desc = if (item.isOffCatalog) "${item.ingredientName} (Adicional)" else item.ingredientName
                        val truncDesc = if (desc.length > 36) desc.take(33) + "..." else desc
                        canvas.drawText(truncDesc, leftMargin + 65f, yPos, bodyPaint)

                        val priceUnitStr = String.format("%.2f €", item.unitPrice)
                        canvas.drawText(priceUnitStr, rightMargin - 120f, yPos, bodyPaint)

                        val totalStr = String.format("%.2f €", item.totalPrice)
                        canvas.drawText(totalStr, rightMargin - 55f, yPos, bodyPaint)

                        // Casilla de verificación para el muelle [ ]
                        val checkPaint = Paint().apply {
                            color = Color.rgb(140, 140, 140)
                            style = Paint.Style.STROKE
                            strokeWidth = 1f
                        }
                        canvas.drawRect(rightMargin - 20f, yPos - 9f, rightMargin - 8f, yPos + 3f, checkPaint)

                        // Si hay notas del ingrediente
                        if (!item.notes.isNullOrEmpty()) {
                            yPos += 11f
                            canvas.drawText("   ↳ Nota: ${item.notes}", leftMargin + 65f, yPos, smallPaint)
                        }

                        yPos += 16f
                    }
                } else if (!so.whatsappText.isNullOrEmpty()) {
                    // Fallback a las líneas de texto si los items individuales no estuvieran poblados
                    val lines = so.whatsappText.lines().filter { it.trim().startsWith("•") }
                    for (line in lines) {
                        if (yPos > pageHeight - 90f) break
                        val cleanLine = line.replace("•", "").trim()
                        val truncLine = if (cleanLine.length > 55) cleanLine.take(52) + "..." else cleanLine
                        canvas.drawText(truncLine, leftMargin + 15f, yPos, bodyPaint)
                        // Casilla
                        val checkPaint = Paint().apply {
                            color = Color.rgb(140, 140, 140)
                            style = Paint.Style.STROKE
                            strokeWidth = 1f
                        }
                        canvas.drawRect(rightMargin - 20f, yPos - 9f, rightMargin - 8f, yPos + 3f, checkPaint)
                        yPos += 16f
                    }
                }

                yPos += 10f
            }
        } else {
            // Si no viniera desglosado por subpedidos, imprimir items generales
            for (item in allItems) {
                if (yPos > pageHeight - 90f) break
                val qtyStr = "${String.format("%.1f", item.quantity)} ${item.unit}"
                canvas.drawText(qtyStr, leftMargin + 8f, yPos, bodyPaint)
                canvas.drawText(item.ingredientName, leftMargin + 65f, yPos, bodyPaint)
                canvas.drawText(String.format("%.2f €", item.totalPrice), rightMargin - 55f, yPos, bodyPaint)
                yPos += 16f
            }
        }

        // 3. Bloque Total y Notas del Cocinero al pie
        yPos = maxOf(yPos + 10f, pageHeight - 110f)
        canvas.drawLine(leftMargin, yPos, rightMargin, yPos, linePaint)
        yPos += 18f

        // Notas del Cocinero si existen
        if (!order.chefNotes.isNullOrEmpty()) {
            val notePaint = Paint().apply {
                color = Color.rgb(211, 84, 0)
                textSize = 9.5f
                typeface = Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD)
            }
            canvas.drawText("INDICACIONES GENERALES DEL CHEF:", leftMargin + 8f, yPos, notePaint)
            yPos += 12f
            canvas.drawText(order.chefNotes, leftMargin + 8f, yPos, bodyPaint)
            yPos += 18f
        }

        // Gran Total
        val grandTotalPaint = Paint().apply {
            color = Color.rgb(184, 42, 42)
            textSize = 14f
            typeface = Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD)
            textAlign = Paint.Align.RIGHT
        }
        canvas.drawText("TOTAL ESTIMADO DEL PEDIDO: ${String.format("%.2f €", order.totalAmount)}", rightMargin - 8f, yPos, grandTotalPaint)

        yPos += 20f
        val footerPaint = Paint().apply {
            color = Color.rgb(150, 150, 150)
            textSize = 8f
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("Documento generado automáticamente por F&B SmartOrder · Control de Calidad y Trazabilidad HORECA", pageWidth / 2f, yPos, footerPaint)

        pdfDocument.finishPage(page)

        // Guardar archivo en almacenamiento interno compartido de la app
        val pdfDir = File(context.cacheDir, "albaranes")
        if (!pdfDir.exists()) pdfDir.mkdirs()

        val pdfFile = File(pdfDir, "Albaran_Pedido_${orderShortId}.pdf")
        FileOutputStream(pdfFile).use { out ->
            pdfDocument.writeTo(out)
        }
        pdfDocument.close()

        return pdfFile
    }

    /**
     * Lanza un Intent para abrir y visualizar el albarán PDF con cualquier visor del sistema.
     */
    fun openPdfViewer(context: Context, pdfFile: File) {
        val uri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            pdfFile
        )

        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/pdf")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }

        val chooser = Intent.createChooser(intent, "Abrir Albarán con...")
        chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(chooser)
    }
}
