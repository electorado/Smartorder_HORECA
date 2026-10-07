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

    def can_deliver(self, day: str) -> bool:
        """Comprueba si el proveedor realiza entregas el día indicado."""
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
    stock_available: bool = True
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    master_ingredient_id: Optional[str] = None
    similarity_score: float = 0.0

    def is_mapped(self) -> bool:
        """Indica si el producto bruto está homologado a un ingrediente maestro."""
        return bool(self.master_ingredient_id)

class MasterIngredient(BaseModel):
    id: str = Field(..., description="ID maestro (ej. ing_tomate_rama)")
    name: str = Field(..., description="Nombre estandarizado en cocina")
    category: str = Field(..., description="Categoría (ej. Frutas y Verduras, Lácteos, Carnes)")
    standard_unit: str = Field("kg", description="Unidad estándar de medida (kg, L, ud)")
    description: Optional[str] = None

    def get_summary(self) -> str:
        """Devuelve un resumen identificativo del ingrediente."""
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
        """Calcula y devuelve el importe total de la línea de pedido."""
        self.total_price = round(self.quantity * self.unit_price, 2)
        return self.total_price

class SupplierSubOrder(BaseModel):
    supplier_id: str
    supplier_name: str
    supplier_email: str
    items: List[OrderItem]
    subtotal: float

    def recalculate_subtotal(self) -> float:
        """Recalcula la suma de subtotales de las líneas del subpedido."""
        self.subtotal = round(sum(item.total_price for item in self.items), 2)
        return self.subtotal

    def meets_minimum(self, min_eur: float) -> bool:
        """Evalúa si el subpedido alcanza el pedido mínimo exigido."""
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
        """Agrupa las líneas de pedido en subpedidos desglosados por proveedor."""
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
        """Exporta el pedido a un diccionario serializable."""
        return self.model_dump()
