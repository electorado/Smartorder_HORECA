package com.fb.smartorder.model

import com.google.gson.annotations.SerializedName

/**
 * Modelo de datos representativo de un ingrediente o producto unificado
 * devuelto por el endpoint GET /api/v1/products de FastAPI.
 */
data class Product(
    @SerializedName("id")
    val id: String,

    @SerializedName("name")
    val name: String,

    @SerializedName("category")
    val category: String = "General",

    @SerializedName("standard_unit")
    val standardUnit: String = "kg",

    @SerializedName("best_price")
    val bestPrice: Double? = null,

    @SerializedName("best_supplier_id")
    val bestSupplierId: String? = null,

    @SerializedName("best_supplier_name")
    val bestSupplierName: String? = null,

    @SerializedName("available_offers")
    val availableOffers: Int = 0
)

/**
 * Envoltorio para la respuesta JSON de la API: { "products": [ ... ] }
 */
data class ProductsResponse(
    @SerializedName("products")
    val products: List<Product> = emptyList()
)

