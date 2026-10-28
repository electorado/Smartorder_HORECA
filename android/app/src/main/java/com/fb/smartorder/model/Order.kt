package com.fb.smartorder.model

import com.google.gson.annotations.SerializedName

data class OrderItem(
    @SerializedName("master_ingredient_id")
    val masterIngredientId: String?,

    @SerializedName("ingredient_name")
    val ingredientName: String,

    @SerializedName("supplier_id")
    val supplierId: String,

    @SerializedName("supplier_name")
    val supplierName: String?,

    @SerializedName("quantity")
    val quantity: Double,

    @SerializedName("unit")
    val unit: String = "kg",

    @SerializedName("unit_price")
    val unitPrice: Double,

    @SerializedName("total_price")
    val totalPrice: Double,

    @SerializedName("notes")
    val notes: String? = null,

    @SerializedName("is_off_catalog")
    val isOffCatalog: Boolean = false
)

data class OrderRequest(
    @SerializedName("items")
    val items: List<OrderItem>,

    @SerializedName("total_amount")
    val totalAmount: Double,

    @SerializedName("chef_notes")
    val chefNotes: String? = null
)

data class SupplierSubOrderResponse(
    @SerializedName("supplier_id")
    val supplierId: String,

    @SerializedName("supplier_name")
    val supplierName: String,

    @SerializedName("supplier_phone")
    val supplierPhone: String?,

    @SerializedName("preferred_channel")
    val preferredChannel: String?,

    @SerializedName("subtotal")
    val subtotal: Double,

    @SerializedName("whatsapp_url")
    val whatsappUrl: String?,

    @SerializedName("whatsapp_text")
    val whatsappText: String?
)

data class OrderDetailResponse(
    @SerializedName("id")
    val id: String?,

    @SerializedName("supplier_suborders")
    val supplierSuborders: List<SupplierSubOrderResponse>? = emptyList(),

    @SerializedName("total_amount")
    val totalAmount: Double = 0.0,

    @SerializedName("chef_notes")
    val chefNotes: String? = null
)

data class OrderResponse(
    @SerializedName("message")
    val message: String,

    @SerializedName("order_id")
    val orderId: String,

    @SerializedName("order")
    val order: OrderDetailResponse? = null
)
