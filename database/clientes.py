# clientes.py (versión mejorada)
import sqlite3
from pydantic import BaseModel
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_BASE = RAIZ / "datos_facturacion"
CARPETA_DATOS = CARPETA_BASE / "datos"
CARPETA_DATOS.mkdir(parents=True, exist_ok=True)

class Cliente(BaseModel):
    nombre: str
    tipo_identificacion: str = "cedula"  # cedula, ruc, pasaporte, etc.
    identificacion: str
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    fecha_registro: Optional[str] = None

class ClienteDB:
    def __init__(self, db_name="facturacion.db"):
        self.db_name = db_name
        self.db_path = CARPETA_DATOS / db_name
        self.conexion = sqlite3.connect(str(self.db_path))
        self.cursor = self.conexion.cursor()
        self.conexion.row_factory = sqlite3.Row
        self._crear_tabla()
    
    def _crear_tabla(self):
        # Verificar si la tabla existe y tiene la estructura correcta
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                tipo_identificacion TEXT DEFAULT 'cedula',
                identificacion TEXT UNIQUE,
                direccion TEXT,
                telefono TEXT,
                email TEXT,
                fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Verificar si la columna identificacion existe, si no, agregarla
        self.cursor.execute("PRAGMA table_info(clientes)")
        columnas = [col[1] for col in self.cursor.fetchall()]
        
        if 'tipo_identificacion' not in columnas:
            self.cursor.execute("ALTER TABLE clientes ADD COLUMN tipo_identificacion TEXT DEFAULT 'cedula'")
        if 'identificacion' not in columnas:
            self.cursor.execute("ALTER TABLE clientes ADD COLUMN identificacion TEXT UNIQUE")
        if 'direccion' not in columnas:
            self.cursor.execute("ALTER TABLE clientes ADD COLUMN direccion TEXT")
        if 'telefono' not in columnas:
            self.cursor.execute("ALTER TABLE clientes ADD COLUMN telefono TEXT")
        if 'email' not in columnas:
            self.cursor.execute("ALTER TABLE clientes ADD COLUMN email TEXT")
        
        self.conexion.commit()
    
    def obtener_todos_los_clientes(self) -> List[Dict[str, Any]]:
        cursor = self.conexion.cursor()
        cursor.execute("""
            SELECT id, nombre, tipo_identificacion, identificacion, 
                   direccion, telefono, email, fecha_registro 
            FROM clientes 
            ORDER BY id DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    
    def obtener_cliente_por_id(self, cliente_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.conexion.cursor()
        cursor.execute("""
            SELECT id, nombre, tipo_identificacion, identificacion, 
                   direccion, telefono, email, fecha_registro 
            FROM clientes 
            WHERE id = ?
        """, (cliente_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def obtener_cliente_por_identificacion(self, identificacion: str) -> Optional[Dict[str, Any]]:
        cursor = self.conexion.cursor()
        cursor.execute("""
            SELECT id, nombre, tipo_identificacion, identificacion, 
                   direccion, telefono, email, fecha_registro 
            FROM clientes 
            WHERE identificacion = ?
        """, (identificacion,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def agregar_cliente(self, nombre: str, tipo_identificacion: str = "cedula", 
                        identificacion: str = None, direccion: str = None,
                        telefono: str = None, email: str = None) -> Dict[str, Any]:
        try:
            cursor = self.conexion.cursor()
            
            # Validar que la identificación no exista (si se proporcionó)
            if identificacion:
                cursor.execute("SELECT id FROM clientes WHERE identificacion = ?", (identificacion,))
                if cursor.fetchone():
                    return {"success": False, "error": "Ya existe un cliente con esta identificación"}
            
            cursor.execute("""
                INSERT INTO clientes (nombre, tipo_identificacion, identificacion, direccion, telefono, email)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (nombre, tipo_identificacion, identificacion, direccion, telefono, email))
            self.conexion.commit()
            return {"success": True, "id": cursor.lastrowid}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def actualizar_cliente(self, cliente_id: int, nombre: str = None, 
                          tipo_identificacion: str = None, identificacion: str = None,
                          direccion: str = None, telefono: str = None,
                          email: str = None) -> Dict[str, Any]:
        try:
            cursor = self.conexion.cursor()
            
            # Construir la consulta dinámicamente
            campos = []
            valores = []
            
            if nombre is not None:
                campos.append("nombre = ?")
                valores.append(nombre)
            if tipo_identificacion is not None:
                campos.append("tipo_identificacion = ?")
                valores.append(tipo_identificacion)
            if identificacion is not None:
                campos.append("identificacion = ?")
                valores.append(identificacion)
            if direccion is not None:
                campos.append("direccion = ?")
                valores.append(direccion)
            if telefono is not None:
                campos.append("telefono = ?")
                valores.append(telefono)
            if email is not None:
                campos.append("email = ?")
                valores.append(email)
            
            if not campos:
                return {"success": False, "error": "No se proporcionaron campos para actualizar"}
            
            valores.append(cliente_id)
            query = f"UPDATE clientes SET {', '.join(campos)} WHERE id = ?"
            cursor.execute(query, valores)
            self.conexion.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def eliminar_cliente(self, cliente_id: int) -> Dict[str, Any]:
        try:
            cursor = self.conexion.cursor()
            cursor.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))
            self.conexion.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def buscar_clientes(self, termino: str) -> List[Dict[str, Any]]:
        """Buscar clientes por nombre o identificación"""
        cursor = self.conexion.cursor()
        cursor.execute("""
            SELECT id, nombre, tipo_identificacion, identificacion, 
                   direccion, telefono, email, fecha_registro 
            FROM clientes 
            WHERE nombre LIKE ? OR identificacion LIKE ?
            ORDER BY nombre ASC
            LIMIT 20
        """, (f"%{termino}%", f"%{termino}%"))
        return [dict(row) for row in cursor.fetchall()]