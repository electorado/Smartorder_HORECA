package com.fb.smartorder.data.repository

import com.fb.smartorder.data.network.ApiService
import com.fb.smartorder.data.network.RetrofitClient
import com.fb.smartorder.model.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File

class ProductRepository(
    private val api: ApiService = RetrofitClient.apiService
) {

    suspend fun getProducts(
        query: String? = null,
        supplierId: String? = null,
        filterType: String? = null
    ): Result<List<Product>> {
        return try {
            val response = api.getProducts(query = query, supplierId = supplierId, filterType = filterType)
            if (response.isSuccessful) {
                val list = response.body()?.products ?: emptyList()
                Result.success(list)
            } else {
                Result.failure(Exception("HTTP ${response.code()}: ${response.message()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun updateProductOverride(productId: String, req: ProductOverrideRequest): Result<Unit> {
        return try {
            val response = api.updateProductOverride(productId, req)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("HTTP ${response.code()}: ${response.message()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun toggleFavorite(productId: String): Result<Unit> {
        return try {
            val response = api.toggleFavorite(productId)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("HTTP ${response.code()}: ${response.message()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun toggleHide(productId: String): Result<Unit> {
        return try {
            val response = api.toggleHide(productId)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("HTTP ${response.code()}: ${response.message()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun submitOrder(order: OrderRequest): Result<OrderResponse> {
        return try {
            val response = api.createOrder(order)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                val errBody = response.errorBody()?.string() ?: response.message()
                Result.failure(Exception("Error ${response.code()}: $errBody"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun dispatchOrderEmail(orderId: String, supplierId: String? = null): Result<String> {
        return try {
            val response = api.dispatchOrderEmail(orderId, supplierId)
            if (response.isSuccessful && response.body() != null) {
                val msg = response.body()?.get("message") as? String ?: "Pedido enviado por email vía Brevo SMTP"
                Result.success(msg)
            } else {
                val errBody = response.errorBody()?.string() ?: response.message()
                Result.failure(Exception("Error ${response.code()}: $errBody"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getSuppliers(): Result<List<Supplier>> {
        return try {
            val response = api.getSuppliers()
            if (response.isSuccessful) {
                val list = response.body()?.suppliers ?: emptyList()
                Result.success(list)
            } else {
                Result.failure(Exception("HTTP ${response.code()}: ${response.message()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun saveSupplier(supplier: Supplier): Result<Unit> {
        return try {
            val response = api.saveSupplier(supplier)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("Error guardando proveedor HTTP ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun deleteSupplier(supplierId: String): Result<Unit> {
        return try {
            val response = api.deleteSupplier(supplierId)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                val err = response.errorBody()?.string() ?: response.message()
                Result.failure(Exception("Error eliminando proveedor: $err"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun uploadCatalog(supplierId: String, file: File, isAnnex: Boolean = false): Result<CatalogUploadResponse> {
        return try {
            val suppBody = supplierId.toRequestBody("text/plain".toMediaTypeOrNull())
            val annexBody = (if (isAnnex) "true" else "false").toRequestBody("text/plain".toMediaTypeOrNull())
            val fileReq = file.asRequestBody("application/pdf".toMediaTypeOrNull())
            val filePart = MultipartBody.Part.createFormData("file", file.name, fileReq)

            val response = api.uploadCatalog(suppBody, annexBody, filePart)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                val errBody = response.errorBody()?.string() ?: response.message()
                Result.failure(Exception("Error subiendo catálogo: $errBody"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getOrdersHistory(): Result<List<OrderDetailResponse>> {
        return try {
            val response = api.getOrdersHistory()
            if (response.isSuccessful) {
                Result.success(response.body()?.orders ?: emptyList())
            } else {
                Result.failure(Exception("HTTP ${response.code()}: ${response.message()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun scanKitchenNotes(file: File): Result<ScanResponse> {
        return try {
            val reqFile = file.asRequestBody("image/jpeg".toMediaTypeOrNull())
            val body = MultipartBody.Part.createFormData("file", file.name, reqFile)
            val response = api.scanKitchenNotes(body)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                val errBody = response.errorBody()?.string() ?: response.message()
                Result.failure(Exception("Error procesando foto: $errBody"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
