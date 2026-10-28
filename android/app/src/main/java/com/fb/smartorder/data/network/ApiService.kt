package com.fb.smartorder.data.network

import com.fb.smartorder.model.ProductsResponse
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Query

/**
 * Definición de endpoints REST de FastAPI consumidos por Retrofit.
 */
interface ApiService {

    /**
     * Obtiene el listado de productos/ingredientes maestros con su mejor oferta.
     */
    @GET("api/v1/products")
    suspend fun getProducts(
        @Query("query") query: String? = null,
        @Query("supplier_id") supplierId: String? = null
    ): Response<ProductsResponse>
}

