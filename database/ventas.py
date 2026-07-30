import sqlite3
from pydantic import BaseModel
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_BASE = RAIZ / "datos_facturacion"
CARPETA_DATOS = CARPETA_BASE / "datos"
CARPETA_DATOS.mkdir(parents=True, exist_ok=True)

# Apuntamos a la carpeta de usuarios para localizar el users.db del Login
CARPETA_USUARIOS = CARPETA_BASE / "usuarios"
CARPETA_USUARIOS.mkdir(parents=True, exist_ok=True)


def redondear_monto(valor: float) -> float:
    return float(Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

class DetalleVenta(BaseModel):
    producto_id: int
    cantidad: int
    precio_unitario: float
    iva: float  # IVA aplicado al producto en el momento de la venta

class Venta(BaseModel):
    cliente_id: int
    empleado_id: int      # ID del usuario que realiza la venta
    total: float
    metodo_pago: str = "Efectivo"
    detalles: List[DetalleVenta] = []

class VentaDB:
    def __init__(self, db_name="facturacion.db"):
        self.db_path = CARPETA_DATOS / db_name
        self.users_db_path = CARPETA_USUARIOS / "users.db"
        self._crear_tablas()
        
    def obtener_conexion(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Permite mapear diccionarios automáticamente
        
        # ATTACH: Vincula temporalmente la BD de usuarios en esta conexión
        if self.users_db_path.exists():
            cursor = conn.cursor()
            cursor.execute(f"ATTACH DATABASE '{str(self.users_db_path)}' AS db_usuarios")
            
        return conn
    
    def _crear_tablas(self):
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            
            # Tabla Principal de Ventas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ventas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente_id INTEGER,
                    empleado_id INTEGER,
                    total NUMERIC(10,2) NOT NULL,
                    metodo_pago TEXT DEFAULT 'Efectivo',
                    estado TEXT DEFAULT 'Completada',
                    fecha_venta TEXT,
                    fecha_completa TEXT,
                    FOREIGN KEY(cliente_id) REFERENCES clientes(id)
                )
            """)
            
            # Tabla de Detalles de Ventas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS detalles_ventas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    venta_id INTEGER,
                    producto_id INTEGER,
                    cantidad INTEGER,
                    precio_unitario NUMERIC(10,2),
                    iva NUMERIC(5,2),
                    subtotal NUMERIC(10,2),
                    FOREIGN KEY(venta_id) REFERENCES ventas(id)
                )
            """)
            conn.commit()

    # ==========================================
    #          MÓDULO DE TRANSACCIONES
    # ==========================================
    def registrar_venta(self, venta: Venta, f_dia: str = None, f_completa: str = None) -> Dict[str, Any]:
        try:
            # Captura de tiempo local exacto desde Python si no es proveído
            if not f_dia or not f_completa:
                ahora = datetime.now()
                f_dia = ahora.strftime("%Y-%m-%d")
                f_completa = ahora.strftime("%Y-%m-%d %H:%M:%S")

            with self.obtener_conexion() as conn:
                cursor = conn.cursor()
                
                # Insertar cabecera de la venta con fechas explícitas locales
                cursor.execute("""
                    INSERT INTO ventas (cliente_id, empleado_id, total, metodo_pago, fecha_venta, fecha_completa)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (venta.cliente_id, venta.empleado_id, redondear_monto(venta.total), venta.metodo_pago, f_dia, f_completa))
                
                venta_id = cursor.lastrowid
                
                # Insertar cada artículo comprado en el detalle
                for d in venta.detalles:
                    precio_unitario = redondear_monto(d.precio_unitario)
                    iva = redondear_monto(d.iva)
                    precio_con_iva = redondear_monto(precio_unitario * (1 + iva / 100))
                    subtotal = redondear_monto(d.cantidad * precio_con_iva)
                    
                    cursor.execute("""
                        INSERT INTO detalles_ventas (venta_id, producto_id, cantidad, precio_unitario, iva, subtotal)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (venta_id, d.producto_id, d.cantidad, precio_unitario, iva, subtotal))
                    
                    # Reducir el stock del producto vendido
                    cursor.execute("""
                        UPDATE productos SET stock = stock - ? WHERE id = ?
                    """, (d.cantidad, d.producto_id))

                conn.commit()
                return {"success": True, "venta_id": venta_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def listar_ultimas_ventas(self, limite: int = 20) -> List[Dict[str, Any]]:
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT v.id, v.total, v.metodo_pago, v.estado, v.fecha_completa, v.fecha_venta,
                       c.nombre AS nombre_cliente,
                       u.username AS nombre_empleado
                FROM ventas v
                LEFT JOIN clientes c ON v.cliente_id = c.id
                LEFT JOIN db_usuarios.users u ON v.empleado_id = u.id
                ORDER BY v.id DESC
                LIMIT ?
            """, (limite,))
            
            ventas_rows = cursor.fetchall()
            ventas = [dict(row) for row in ventas_rows]
            
            for venta in ventas:
                venta_id = venta["id"]
                cursor.execute("""
                    SELECT dv.id, dv.cantidad, dv.precio_unitario, dv.iva, dv.subtotal, p.nombre AS nombre_producto
                    FROM detalles_ventas dv
                    JOIN productos p ON dv.producto_id = p.id
                    WHERE dv.venta_id = ?
                """, (venta_id,))
                venta["productos"] = [dict(p_row) for p_row in cursor.fetchall()]
                
            return ventas

    def obtener_ventas_totales_por_dia(self) -> List[Dict[str, Any]]:
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fecha_venta AS dia,
                       COUNT(id) AS cantidad_ventas,
                       SUM(total) AS total_recaudado
                FROM ventas
                WHERE estado = 'Completada'
                GROUP BY fecha_venta
                ORDER BY fecha_venta DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def obtener_total_ventas(self) -> float:
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT SUM(total) AS total_historico
                FROM ventas
                WHERE estado = 'Completada'
            """)
            row = cursor.fetchone()
            return row["total_historico"] if row and row["total_historico"] is not None else 0.0

    def obtener_total_ventas_hoy(self) -> float:
        # Se calcula usando la fecha del sistema local en vez de CURRENT_DATE de SQLite
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT SUM(total) AS total_hoy
                FROM ventas
                WHERE estado = 'Completada' AND fecha_venta = ?
            """, (fecha_hoy,))
            row = cursor.fetchone()
            return row["total_hoy"] if row and row["total_hoy"] is not None else 0.0

    def obtener_venta_con_productos(self, venta_id: int) -> Dict[str, Any]:
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT v.id, v.total, v.metodo_pago, v.estado, v.fecha_completa, v.fecha_venta,
                       c.nombre AS nombre_cliente,
                       u.username AS nombre_empleado
                FROM ventas v
                LEFT JOIN clientes c ON v.cliente_id = c.id
                LEFT JOIN db_usuarios.users u ON v.empleado_id = u.id
                WHERE v.id = ?
            """, (venta_id,))
            venta_row = cursor.fetchone()
            if not venta_row:
                return {}
            
            venta = dict(venta_row)
            
            cursor.execute("""
                SELECT dv.id, dv.cantidad, dv.precio_unitario, dv.iva, dv.subtotal, p.nombre AS nombre_producto
                FROM detalles_ventas dv
                JOIN productos p ON dv.producto_id = p.id
                WHERE dv.venta_id = ?
            """, (venta_id,))
            venta["productos"] = [dict(p_row) for p_row in cursor.fetchall()]
            
            return venta
    def obtener_metodos_pago(self) -> List[Dict[str, Any]]:
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT metodo_pago, COUNT(id) AS cantidad, SUM(total) AS total
                FROM ventas
                WHERE estado = 'Completada'
                GROUP BY metodo_pago
                ORDER BY cantidad DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def obtener_top_productos(self, limite: int = 5) -> List[Dict[str, Any]]:
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.nombre AS nombre_producto, 
                    SUM(dv.cantidad) AS cantidad_vendida,
                    SUM(dv.subtotal) AS total_generado
                FROM detalles_ventas dv
                JOIN productos p ON dv.producto_id = p.id
                JOIN ventas v ON dv.venta_id = v.id
                WHERE v.estado = 'Completada'
                GROUP BY dv.producto_id
                ORDER BY cantidad_vendida DESC
                LIMIT ?
            """, (limite,))
            return [dict(row) for row in cursor.fetchall()]

    def obtener_top_clientes(self, limite: int = 5) -> List[Dict[str, Any]]:
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.nombre AS nombre_cliente, 
                    COUNT(v.id) AS cantidad_compras,
                    SUM(v.total) AS total_gastado
                FROM ventas v
                JOIN clientes c ON v.cliente_id = c.id
                WHERE v.estado = 'Completada'
                GROUP BY v.cliente_id
                ORDER BY total_gastado DESC
                LIMIT ?
            """, (limite,))
            return [dict(row) for row in cursor.fetchall()]

    def obtener_rendimiento_empleados(self) -> List[Dict[str, Any]]:
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.username AS nombre_empleado,
                    COUNT(v.id) AS cantidad_ventas,
                    SUM(v.total) AS total_facturado,
                    AVG(v.total) AS ticket_promedio
                FROM ventas v
                JOIN db_usuarios.users u ON v.empleado_id = u.id
                WHERE v.estado = 'Completada'
                GROUP BY v.empleado_id
                ORDER BY total_facturado DESC
            """)
            resultados = [dict(row) for row in cursor.fetchall()]
            
            # Calcular porcentaje de rendimiento
            if resultados:
                max_total = resultados[0]['total_facturado'] if resultados else 1
                for r in resultados:
                    r['porcentaje'] = (r['total_facturado'] / max_total * 100) if max_total > 0 else 0
            return resultados

    def obtener_total_ventas_periodo(self, dias: int = 30) -> float:
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT SUM(total) AS total
                FROM ventas
                WHERE estado = 'Completada' 
                AND fecha_venta >= date('now', ?)
            """, (f'-{dias} days',))
            row = cursor.fetchone()
            return row['total'] if row and row['total'] else 0.0

    def obtener_cantidad_ventas_periodo(self, dias: int = 30) -> int:
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(id) AS cantidad
                FROM ventas
                WHERE estado = 'Completada' 
                AND fecha_venta >= date('now', ?)
            """, (f'-{dias} days',))
            row = cursor.fetchone()
            return row['cantidad'] if row else 0

    def obtener_ticket_promedio_periodo(self, dias: int = 30) -> float:
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT AVG(total) AS promedio
                FROM ventas
                WHERE estado = 'Completada' 
                AND fecha_venta >= date('now', ?)
            """, (f'-{dias} days',))
            row = cursor.fetchone()
            return row['promedio'] if row and row['promedio'] else 0.0

    def obtener_productos_vendidos_periodo(self, dias: int = 30) -> int:
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT SUM(dv.cantidad) AS total
                FROM detalles_ventas dv
                JOIN ventas v ON dv.venta_id = v.id
                WHERE v.estado = 'Completada' 
                AND v.fecha_venta >= date('now', ?)
            """, (f'-{dias} days',))
            row = cursor.fetchone()
            return row['total'] if row and row['total'] else 0