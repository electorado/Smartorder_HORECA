from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class Supplier(BaseModel):
    id: str = Field(..., description="ID único del proveedor (ej. prov_paco_01)")
    name: str = Field(..., description="Nombre comercial del proveedor")
    email: str = Field(..., description="Email para recepción de pedidos")
    phone: Optional[str] = Field(None, description="Teléfono de contacto")
    delivery_days: List[str] = Field(default_factory=list, description="Días de entrega habituales")
    minimum_order_euro: float = Field(0.0, description="Pedido mínimo en Euros")
    active: bool = Field(True, description="Estado del proveedor")

class RawProduct(BaseModel):
    id: Optional[str] = None
    supplier_id: str
    supplier_name: str
    supplier_product_code: Optional[str] = None
    raw_name: str
    clean_name: str
    price: float
    unit: str
    stock_available: bool = True
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    master_ingredient_id: Optional[str] = None
    similarity_score: float = 0.0

class MasterIngredient(BaseModel):
    id: str = Field(..., description="ID maestro (ej. ing_tomate_rama)")
    name: str = Field(..., description="Nombre estandarizado en cocina")
    category: str = Field(..., description="Categoría (ej. Frutas y Verduras, Lácteos, Carnes)")
    standard_unit: str = Field("kg", description="Unidad estándar de medida (kg, L, ud)")
    description: Optional[str] = None

class OrderItem(BaseModel):
    master_ingredient_id: Optional[str] = None
    ingredient_name: str
    quantity: float
    unit: str
    unit_price: float
    total_price: float
    supplier_id: str
    supplier_name: str
    supplier_product_code: Optional[str] = None
    notes: Optional[str] = None
    is_off_catalog: bool = False

class SupplierSubOrder(BaseModel):
    supplier_id: str
    supplier_name: str
    supplier_email: str
    items: List[OrderItem]
    subtotal: float

class Order(BaseModel):
    id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field("pending", description="draft | pending | sent | confirmed | cancelled")
    items: List[OrderItem]
    total_amount: float
    supplier_suborders: List[SupplierSubOrder] = Field(default_factory=list)
    chef_notes: Optional[str] = None
