package com.fb.smartorder.data.network

import com.fb.smartorder.model.*
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.*

interface ApiService {

    @GET("api/v1/products")
    suspend fun getProducts(
        @Query("query") query: String? = null,
        @Query("supplier_id") supplierId: String? = null
    ): Response<ProductsResponse>

    @POST("api/v1/orders")
    suspend fun createOrder(
        @Body order: OrderRequest
    ): Response<OrderResponse>

    @GET("api/v1/orders")
    suspend fun getOrdersHistory(): Response<OrdersHistoryResponse>

    @GET("api/v1/suppliers")
    suspend fun getSuppliers(): Response<SuppliersResponse>

    @POST("api/v1/suppliers")
    suspend fun saveSupplier(
        @Body supplier: Supplier
    ): Response<Map<String, Any>>

    @Multipart
    @POST("api/v1/catalogs/upload")
    suspend fun uploadCatalog(
        @Part("supplier_id") supplierId: RequestBody,
        @Part file: MultipartBody.Part
    ): Response<CatalogUploadResponse>

    @Multipart
    @POST("api/v1/scan-kitchen-notes")
    suspend fun scanKitchenNotes(
        @Part file: MultipartBody.Part
    ): Response<ScanResponse>
}
