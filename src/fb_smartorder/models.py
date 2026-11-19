from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class Supplier(BaseModel):
    id: Optional[str] = Field(None, description="ID del proveedor (ej. prov_paco_01)")
    name: str = Field(..., description="Nombre del proveedor")
    email: Optional[str] = Field(None, description="Email para pedidos")
    phone: Optional[str] = Field(None, description="Teléfono de contacto o WhatsApp")
    preferred_channel: Optional[str] = Field("whatsapp", description="Canal preferido (whatsapp o email)")
    delivery_days: List[str] = Field(default_factory=list, description="Días de reparto")
    minimum_order_euro: float = Field(0.0, description="Pedido mínimo en euros")
    active: bool = Field(True, description="Estado activo")

    def can_deliver(self, day: str) -> bool:
        """Indica si el proveedor reparte el día indicado."""
        return any(day.lower() in d.lower() for d in self.delivery_days)

class RawProduct(BaseModel):
    id: Optional[str] = None
    supplier_id: str
    supplier_name: str
    supplier_product_code: Optional[str] = None
    raw_name: str
    clean_name: str
    price: float
    unit: str
    format: Optional[str] = None
    canonical_unit: Optional[str] = "ud"
    canonical_quantity: Optional[float] = 1.0
    canonical_price: Optional[float] = None
    stock_available: bool = True
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    master_ingredient_id: Optional[str] = None
    similarity_score: float = 0.0
    # Campos de personalización y favoritos
    is_favorite: bool = False
    is_hidden: bool = False
    custom_name: Optional[str] = None
    custom_price: Optional[float] = None
    custom_unit: Optional[str] = None

    def is_mapped(self) -> bool:
        """Indica si el producto está vinculado a un ingrediente maestro."""
        return bool(self.master_ingredient_id)

class ProductOverrideUpdate(BaseModel):
    custom_name: Optional[str] = Field(None, description="Nombre personalizado del producto")
    custom_price: Optional[float] = Field(None, description="Precio personalizado")
    custom_unit: Optional[str] = Field(None, description="Unidad personalizada (kg, ud, caja, etc.)")
    is_favorite: Optional[bool] = Field(None, description="Marcar como favorito/habitual")
    is_hidden: Optional[bool] = Field(None, description="Ocultar del catálogo activo")

class MasterIngredient(BaseModel):
    id: str = Field(..., description="ID maestro (ej. ing_tomate_rama)")
    name: str = Field(..., description="Nombre del ingrediente")
    category: str = Field(..., description="Categoría")
    standard_unit: str = Field("kg", description="Unidad estándar (kg, L, ud)")
    description: Optional[str] = None

    def get_summary(self) -> str:
        return f"{self.name} ({self.category}) [{self.standard_unit}]"

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

    def calculate_total(self) -> float:
        """Calcula el total de la línea."""
        self.total_price = round(self.quantity * self.unit_price, 2)
        return self.total_price

class SupplierSubOrder(BaseModel):
    supplier_id: str
    supplier_name: str
    supplier_email: Optional[str] = None
    supplier_phone: Optional[str] = None
    preferred_channel: Optional[str] = "whatsapp"
    items: List[OrderItem]
    subtotal: float
    whatsapp_url: Optional[str] = None
    whatsapp_text: Optional[str] = None
    email_dispatched: Optional[bool] = False
    email_status: Optional[str] = None

    def recalculate_subtotal(self) -> float:
        """Recalcula el subtotal sumando las líneas."""
        self.subtotal = round(sum(item.total_price for item in self.items), 2)
        return self.subtotal

    def meets_minimum(self, min_eur: float) -> bool:
        """Comprueba si alcanza el pedido mínimo."""
        return self.subtotal >= min_eur

class Order(BaseModel):
    id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field("pending", description="draft | pending | sent | confirmed | cancelled")
    items: List[OrderItem]
    total_amount: float
    supplier_suborders: List[SupplierSubOrder] = Field(default_factory=list)
    chef_notes: Optional[str] = None

    def consolidate_by_supplier(self) -> None:
        """Agrupa las líneas del pedido por proveedor."""
        grouped: dict = {}
        for item in self.items:
            grouped.setdefault(item.supplier_id, []).append(item)

        suborders = []
        for s_id, items in grouped.items():
            suborders.append(
                SupplierSubOrder(
                    supplier_id=s_id,
                    supplier_name=items[0].supplier_name,
                    supplier_email=f"pedidos@{s_id.lower().replace('_', '')}.com",
                    items=items,
                    subtotal=round(sum(it.total_price for it in items), 2)
                )
            )
        self.supplier_suborders = suborders
        self.total_amount = round(sum(so.subtotal for so in suborders), 2)

    def export_order_sheet(self) -> dict:
        return self.model_dump()


# --- Modelos de Autenticación y Usuario ---

class UserRegister(BaseModel):
    name: str = Field(..., description="Nombre del usuario o cocinero")
    email: str = Field(..., description="Email")
    password: str = Field(..., min_length=4, description="Contraseña")
    restaurant_name: str = Field(..., description="Nombre del restaurante")

class UserLogin(BaseModel):
    email: str = Field(..., description="Email")
    password: str = Field(..., description="Contraseña")

class UserProfile(BaseModel):
    id: Optional[str] = None
    name: str
    email: str
    restaurant_name: str
    created_at: Optional[datetime] = None

class UserUpdate(BaseModel):
    name: Optional[str] = None
    restaurant_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None

class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., description="Email de la cuenta")
    new_password: Optional[str] = Field(None, description="Nueva contraseña opcional (si no se indica, se genera una temporal enviada por Brevo)")


