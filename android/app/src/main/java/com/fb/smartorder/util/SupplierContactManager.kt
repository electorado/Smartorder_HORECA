package com.fb.smartorder.util

import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.ContactsContract
import android.widget.Toast
import androidx.core.content.ContextCompat
import com.fb.smartorder.model.SupplierSubOrderResponse

/**
 * Utilidades para comprobar y registrar contactos de proveedores en la agenda del dispositivo.
 */
object SupplierContactManager {

    fun isSupplierInPhoneContacts(context: Context, phone: String?, email: String?): Boolean {
        if (phone.isNullOrBlank() && email.isNullOrBlank()) return true

        if (ContextCompat.checkSelfPermission(context, android.Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED) {
            try {
                if (!phone.isNullOrBlank()) {
                    val cleanDigits = phone.filter { it.isDigit() || it == '+' }
                    if (cleanDigits.length >= 6) {
                        val uri = Uri.withAppendedPath(ContactsContract.PhoneLookup.CONTENT_FILTER_URI, Uri.encode(cleanDigits))
                        context.contentResolver.query(uri, arrayOf(ContactsContract.PhoneLookup._ID), null, null, null)?.use { cursor ->
                            if (cursor.moveToFirst()) return true
                        }
                    }
                }
                if (!email.isNullOrBlank()) {
                    val uri = Uri.withAppendedPath(ContactsContract.CommonDataKinds.Email.CONTENT_LOOKUP_URI, Uri.encode(email))
                    context.contentResolver.query(uri, arrayOf(ContactsContract.CommonDataKinds.Email._ID), null, null, null)?.use { cursor ->
                        if (cursor.moveToFirst()) return true
                    }
                }
            } catch (e: Exception) {
                // Fallback a caché local si la consulta a la agenda falla
            }
        }

        val sp = context.getSharedPreferences("phone_contacts_cache", Context.MODE_PRIVATE)
        val cacheKey = "contact_" + (phone ?: email ?: "")
        return sp.getBoolean(cacheKey, false)
    }

    fun cleanSupplierPhone(phone: String?): String? {
        if (phone.isNullOrBlank()) return null
        val parts = phone.split(Regex("[/,;\\n|y\\-]"))
        val cands = mutableListOf<String>()
        for (p in parts) {
            var digits = p.filter { it.isDigit() }
            if (digits.startsWith("0034")) digits = digits.substring(4)
            else if (digits.startsWith("34") && digits.length == 11) digits = digits.substring(2)
            if (digits.length == 9 || (digits.length in 10..15)) {
                cands.add(digits)
            }
        }
        if (cands.isEmpty()) {
            val allDigits = phone.filter { it.isDigit() }
            if (allDigits.length in 9..15) cands.add(allDigits)
        }
        if (cands.isEmpty()) return null
        val mobile = cands.firstOrNull { it.startsWith("6") || it.startsWith("7") } ?: cands.first()
        return if (mobile.length == 9) "34$mobile" else mobile
    }

    fun markSupplierContactHandled(context: Context, phone: String?, email: String?) {
        val sp = context.getSharedPreferences("phone_contacts_cache", Context.MODE_PRIVATE)
        val cacheKey = "contact_" + (phone ?: email ?: "")
        if (cacheKey.isNotEmpty()) {
            sp.edit().putBoolean(cacheKey, true).apply()
        }
    }

    fun promptSaveContactIfNeeded(
        context: Context,
        so: SupplierSubOrderResponse,
        onProceed: () -> Unit
    ) {
        val phone = so.supplierPhone
        val email = so.supplierEmail

        if (isSupplierInPhoneContacts(context, phone, email)) {
            onProceed()
            return
        }

        val contactDetails = when {
            !phone.isNullOrBlank() && !email.isNullOrBlank() -> "Tel: $phone · Email: $email"
            !phone.isNullOrBlank() -> "Tel: $phone"
            !email.isNullOrBlank() -> "Email: $email"
            else -> ""
        }

        AlertDialog.Builder(context)
            .setTitle("Añadir a Contactos")
            .setMessage("El proveedor '${so.supplierName}' ($contactDetails) aún no está guardado en la agenda de tu teléfono.\n\n¿Deseas añadirlo a tus contactos?")
            .setPositiveButton("Guardar en Agenda") { _, _ ->
                markSupplierContactHandled(context, phone, email)
                val insertIntent = Intent(Intent.ACTION_INSERT).apply {
                    type = ContactsContract.RawContacts.CONTENT_TYPE
                    putExtra(ContactsContract.Intents.Insert.NAME, so.supplierName)
                    if (!phone.isNullOrBlank()) {
                        putExtra(ContactsContract.Intents.Insert.PHONE, phone)
                    }
                    if (!email.isNullOrBlank()) {
                        putExtra(ContactsContract.Intents.Insert.EMAIL, email)
                    }
                }
                try {
                    context.startActivity(insertIntent)
                } catch (e: Exception) {
                    Toast.makeText(context, "No se pudo abrir la agenda de contactos", Toast.LENGTH_SHORT).show()
                }
                onProceed()
            }
            .setNegativeButton("Solo Enviar Pedido") { _, _ ->
                markSupplierContactHandled(context, phone, email)
                onProceed()
            }
            .setCancelable(true)
            .show()
    }
}
