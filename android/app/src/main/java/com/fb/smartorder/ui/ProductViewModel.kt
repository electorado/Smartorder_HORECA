package com.fb.smartorder.ui

import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fb.smartorder.data.repository.ProductRepository
import com.fb.smartorder.model.*
import kotlinx.coroutines.launch
import java.io.File

sealed class ProductsUiState {
    object Loading : ProductsUiState()
    data class Success(val products: List<Product>) : ProductsUiState()
    data class Error(val message: String) : ProductsUiState()
}

class ProductViewModel(
    private val repository: ProductRepository = ProductRepository()
) : ViewModel() {

    private val _uiState = MutableLiveData<ProductsUiState>()
    val uiState: LiveData<ProductsUiState> = _uiState

    // Notas de cocina y líneas fuera de catálogo
    var chefNotes: String = ""
    val offCatalogItems = mutableListOf<OrderItem>()

    init {
        loadProducts()
    }

    fun loadProducts(
        query: String? = null,
        supplierId: String? = null,
        filterType: String? = null
    ) {
        _uiState.value = ProductsUiState.Loading
        viewModelScope.launch {
            val result = repository.getProducts(query = query, supplierId = supplierId, filterType = filterType)
            result.onSuccess { list ->
                _uiState.value = ProductsUiState.Success(list)
            }.onFailure { error ->
                _uiState.value = ProductsUiState.Error(error.message ?: "Network error")
            }
        }
    }

    fun toggleFavorite(product: Product, onComplete: ((Boolean) -> Unit)? = null) {
        viewModelScope.launch {
            val result = repository.toggleFavorite(product.id)
            if (result.isSuccess) {
                product.isFavorite = !product.isFavorite
                onComplete?.invoke(true)
            } else {
                onComplete?.invoke(false)
            }
        }
    }

    fun toggleHide(product: Product, onComplete: ((Boolean) -> Unit)? = null) {
        viewModelScope.launch {
            val result = repository.toggleHide(product.id)
            if (result.isSuccess) {
                product.isHidden = !product.isHidden
                onComplete?.invoke(true)
            } else {
                onComplete?.invoke(false)
            }
        }
    }

    fun updateProductOverride(
        productId: String,
        req: ProductOverrideRequest,
        onComplete: ((Boolean) -> Unit)? = null
    ) {
        viewModelScope.launch {
            val result = repository.updateProductOverride(productId, req)
            if (result.isSuccess) {
                loadProducts()
                onComplete?.invoke(true)
            } else {
                onComplete?.invoke(false)
            }
        }
    }

    fun submitOrder(
        items: List<OrderItem>,
        totalAmount: Double,
        onResult: (Result<OrderResponse>) -> Unit
    ) {
        viewModelScope.launch {
            val request = OrderRequest(
                items = items,
                totalAmount = totalAmount,
                chefNotes = if (chefNotes.isNotBlank()) chefNotes else null
            )
            val result = repository.submitOrder(request)
            onResult(result)
        }
    }

    fun uploadCatalog(
        supplierId: String,
        file: File,
        isAnnex: Boolean = false,
        onResult: (Result<CatalogUploadResponse>) -> Unit
    ) {
        viewModelScope.launch {
            val result = repository.uploadCatalog(supplierId, file, isAnnex)
            if (result.isSuccess) {
                loadProducts()
            }
            onResult(result)
        }
    }

    fun saveSupplier(
        supplier: Supplier,
        onResult: (Result<Unit>) -> Unit
    ) {
        viewModelScope.launch {
            val result = repository.saveSupplier(supplier)
            onResult(result)
        }
    }

    fun deleteSupplier(
        supplierId: String,
        onResult: (Result<Unit>) -> Unit
    ) {
        viewModelScope.launch {
            val result = repository.deleteSupplier(supplierId)
            if (result.isSuccess) {
                loadProducts()
            }
            onResult(result)
        }
    }

    fun getSuppliers(onResult: (List<Supplier>) -> Unit) {
        viewModelScope.launch {
            val result = repository.getSuppliers()
            onResult(result.getOrDefault(emptyList()))
        }
    }

    fun getOrdersHistory(onResult: (List<OrderDetailResponse>) -> Unit) {
        viewModelScope.launch {
            val result = repository.getOrdersHistory()
            onResult(result.getOrDefault(emptyList()))
        }
    }

    fun scanKitchenNotes(
        file: File,
        onResult: (Result<ScanResponse>) -> Unit
    ) {
        viewModelScope.launch {
            val result = repository.scanKitchenNotes(file)
            onResult(result)
        }
    }
}
