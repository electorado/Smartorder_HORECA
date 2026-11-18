package com.fb.smartorder.model

import com.google.gson.annotations.SerializedName

data class Product(
    @SerializedName("id")
    val id: String,

    @SerializedName("supplier_product_code")
    val supplierProductCode: String? = null,

    @SerializedName("name")
    var name: String,

    @SerializedName("original_name")
    val originalName: String? = null,

    @SerializedName("category")
    val category: String = "General",

    @SerializedName("standard_unit")
    var standardUnit: String = "kg",

    @SerializedName("best_price")
    var bestPrice: Double? = null,

    @SerializedName("best_supplier_id")
    val bestSupplierId: String? = null,

    @SerializedName("best_supplier_name")
    val bestSupplierName: String? = null,

    @SerializedName("available_offers")
    val availableOffers: Int = 0,

    @SerializedName("is_favorite")
    var isFavorite: Boolean = false,

    @SerializedName("is_hidden")
    var isHidden: Boolean = false,

    @SerializedName("custom_name")
    var customName: String? = null,

    @SerializedName("custom_price")
    var customPrice: Double? = null,

    @SerializedName("custom_unit")
    var customUnit: String? = null
)

data class ProductOverrideRequest(
    @SerializedName("custom_name") val customName: String? = null,
    @SerializedName("custom_price") val customPrice: Double? = null,
    @SerializedName("custom_unit") val customUnit: String? = null,
    @SerializedName("is_favorite") val isFavorite: Boolean? = null,
    @SerializedName("is_hidden") val isHidden: Boolean? = null
)

data class ProductsResponse(
    @SerializedName("products")
    val products: List<Product> = emptyList()
)
