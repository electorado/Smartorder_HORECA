package com.fb.smartorder.model

import com.google.gson.annotations.SerializedName

data class Supplier(
    @SerializedName("id")
    val id: String? = null,

    @SerializedName("name")
    val name: String,

    @SerializedName("email")
    val email: String? = null,

    @SerializedName("phone")
    val phone: String? = null,

    @SerializedName("preferred_channel")
    val preferredChannel: String? = "whatsapp"
)

data class SuppliersResponse(
    @SerializedName("suppliers")
    val suppliers: List<Supplier> = emptyList()
)

data class CatalogUploadResponse(
    @SerializedName("message")
    val message: String,

    @SerializedName("supplier_id")
    val supplierId: String?,

    @SerializedName("supplier_name")
    val supplierName: String?,

    @SerializedName("products_extracted")
    val productsExtracted: Int = 0,

    @SerializedName("products_loaded")
    val productsLoaded: Int = 0
)

