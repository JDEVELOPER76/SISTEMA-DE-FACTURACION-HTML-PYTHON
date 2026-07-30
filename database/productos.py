import sqlite3
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_BASE = RAIZ / "datos_facturacion"
CARPETA_DATOS = CARPETA_BASE / "datos"
CARPETA_DATOS.mkdir(parents=True, exist_ok=True)

# 1. Modelo Pydantic actualizado con tus nuevos requerimientos
class Producto(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    precio: float
    iva: float = 12.0                # Porcentaje de IVA (ej. 12.0 o 15.0)
    codigo_barras: str               # Código de barras único del artículo
    proveedor: str                   # Nombre o ID del proveedor
    stock: int = 0                   # Cantidad disponible en inventario
    categoria: str
    imagen_url: Optional[str] = None # Ruta local o URL de la imagen (Opcional)

class ProductoDB:
    def __init__(self, db_name="facturacion.db"):
        self.db_path = CARPETA_DATOS / db_name
        self._crear_tabla()
    
    def obtener_conexion(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Permite acceder a las columnas por nombre
        return conn
    
    def _crear_tabla(self):
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS productos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    descripcion TEXT,
                    precio REAL NOT NULL,
                    iva REAL DEFAULT 12.0,
                    codigo_barras TEXT UNIQUE NOT NULL,
                    proveedor TEXT NOT NULL,
                    stock INTEGER DEFAULT 0,
                    categoria TEXT NOT NULL,
                    imagen_url TEXT,
                    activo INTEGER DEFAULT 1,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    def agregar_producto(self, producto: Producto) -> Dict[str, Any]:
        try:
            with self.obtener_conexion() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO productos (nombre, descripcion, precio, iva, codigo_barras, proveedor, stock, categoria, imagen_url) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    producto.nombre, producto.descripcion, producto.precio, producto.iva,
                    producto.codigo_barras, producto.proveedor, producto.stock, 
                    producto.categoria, producto.imagen_url
                ))
                conn.commit()
                return {"success": True, "id": cursor.lastrowid}
        except sqlite3.IntegrityError as e:
            return {"success": False, "error": f"El código de barras ya existe: {str(e)}"}
    
    def obtener_producto(self, producto_id: int) -> Optional[Dict[str, Any]]:
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM productos WHERE id = ? AND activo = 1", (producto_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def obtener_producto_por_codigo(self, codigo_barras: str) -> Optional[Dict[str, Any]]:
        """Busca un producto por su código de barras"""
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM productos WHERE codigo_barras = ? AND activo = 1", (codigo_barras,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def listar_productos(self, limite: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM productos 
                WHERE activo = 1
                ORDER BY fecha_creacion DESC 
                LIMIT ? OFFSET ?
            """, (limite, offset))
            return [dict(row) for row in cursor.fetchall()]
    
    def actualizar_producto(self, producto_id: int, producto: Producto) -> Dict[str, Any]:
        try:
            with self.obtener_conexion() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE productos 
                    SET nombre = ?, descripcion = ?, precio = ?, iva = ?, codigo_barras = ?, 
                        proveedor = ?, stock = ?, categoria = ?, imagen_url = ?, 
                        fecha_actualizacion = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    producto.nombre, producto.descripcion, producto.precio, producto.iva,
                    producto.codigo_barras, producto.proveedor, producto.stock, 
                    producto.categoria, producto.imagen_url, producto_id
                ))
                conn.commit()
                return {"success": True}
        except sqlite3.IntegrityError as e:
            return {"success": False, "error": str(e)}
    
    def eliminar_producto(self, producto_id: int) -> Dict[str, Any]:
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE productos SET activo = 0 WHERE id = ?", (producto_id,))
            conn.commit()
            return {"success": True}