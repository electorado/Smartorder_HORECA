package com.fb.smartorder.model

import com.google.gson.annotations.SerializedName

data class ScannedOffer(
    @SerializedName("supplier_id") val supplierId: String?,
    @SerializedName("supplier_name") val supplierName: String?,
    @SerializedName("price") val price: Double?,
    @SerializedName("canonical_price") val canonicalPrice: Double?,
    @SerializedName("canonical_unit") val canonicalUnit: String?
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

