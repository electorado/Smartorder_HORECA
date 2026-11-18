package com.fb.smartorder.data.network

import com.fb.smartorder.model.*
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.*

interface ApiService {

    @POST("api/v1/auth/login")
    suspend fun login(
        @Body req: UserLoginRequest
    ): Response<AuthResponse>

    @POST("api/v1/auth/register")
    suspend fun register(
        @Body req: UserRegisterRequest
    ): Response<AuthResponse>

    @GET("api/v1/auth/profile")
    suspend fun getProfile(
        @Query("email") email: String
    ): Response<AuthResponse>

    @PUT("api/v1/auth/profile")
    suspend fun updateProfile(
        @Query("email") email: String,
        @Body req: UserUpdateRequest
    ): Response<AuthResponse>

    @GET("api/v1/products")
    suspend fun getProducts(
        @Query("query") query: String? = null,
        @Query("supplier_id") supplierId: String? = null,
        @Query("filter_type") filterType: String? = null
    ): Response<ProductsResponse>

    @PATCH("api/v1/products/{product_id}/override")
    suspend fun updateProductOverride(
        @Path("product_id") productId: String,
        @Body req: ProductOverrideRequest
    ): Response<Map<String, Any>>

    @POST("api/v1/products/{product_id}/favorite")
    suspend fun toggleFavorite(
        @Path("product_id") productId: String
    ): Response<Map<String, Any>>

    @POST("api/v1/products/{product_id}/hide")
    suspend fun toggleHide(
        @Path("product_id") productId: String
    ): Response<Map<String, Any>>

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

    @DELETE("api/v1/suppliers/{supplier_id}")
    suspend fun deleteSupplier(
        @Path("supplier_id") supplierId: String
    ): Response<Map<String, Any>>

    @Multipart
    @POST("api/v1/catalogs/upload")
    suspend fun uploadCatalog(
        @Part("supplier_id") supplierId: RequestBody,
        @Part("is_annex") isAnnex: RequestBody,
        @Part file: MultipartBody.Part
    ): Response<CatalogUploadResponse>

    @Multipart
    @POST("api/v1/scan-kitchen-notes")
    suspend fun scanKitchenNotes(
        @Part file: MultipartBody.Part
    ): Response<ScanResponse>
}
