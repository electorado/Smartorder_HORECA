package com.fb.smartorder.model

import com.google.gson.annotations.SerializedName

data class ScannedOffer(
    @SerializedName("product_id") val productId: String? = null,
    @SerializedName("raw_name") val rawName: String? = null,
    @SerializedName("supplier_id") val supplierId: String? = null,
    @SerializedName("supplier_name") val supplierName: String? = null,
    @SerializedName("price") val price: Double? = null,
    @SerializedName("canonical_price") val canonicalPrice: Double? = null,
    @SerializedName("canonical_unit") val canonicalUnit: String? = null,
    @SerializedName("category") val category: String? = null,
    @SerializedName("unit") val unit: String? = null
)

data class ScannedItem(
    @SerializedName("raw_text") val rawText: String,
    @SerializedName("clean_name") val cleanName: String?,
    @SerializedName("quantity") val quantity: Double = 1.0,
    @SerializedName("unit") val unit: String = "kg",
    @SerializedName("master_ingredient_id") val masterIngredientId: String?,
    @SerializedName("similarity_score") val similarityScore: Double = 0.0,
    @SerializedName("best_offer") val bestOffer: ScannedOffer?
)

data class ScanResponse(
    @SerializedName("message") val message: String,
    @SerializedName("items_found_count") val itemsFoundCount: Int = 0,
    @SerializedName("items") val items: List<ScannedItem> = emptyList()
)

data class OrdersHistoryResponse(
    @SerializedName("orders") val orders: List<OrderDetailResponse> = emptyList()
)

