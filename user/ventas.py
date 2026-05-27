from pydantic import BaseModel
from typing import List


class ItemCarrito(BaseModel):
    producto_id: int
    cantidad: int
    precio_unitario: float
    iva: float

class DataVenta(BaseModel):
    cliente_id: int
    metodo_pago: str
    detalles: List[ItemCarrito]