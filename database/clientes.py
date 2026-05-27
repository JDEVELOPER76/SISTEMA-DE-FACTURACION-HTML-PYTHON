import sqlite3
from pydantic import BaseModel
from pathlib import Path
from typing import List, Dict, Any

RAIZ = Path(__file__).resolve().parent
CARPETA_DATOS = RAIZ / "datos"
CARPETA_DATOS.mkdir(exist_ok=True)

class Cliente(BaseModel):
    nombre: str
    email: str
    fecha: str

class ClienteDB:
    def __init__(self, db_name="facturacion.db"):
        self.db_name = db_name
        self.db_path = CARPETA_DATOS / db_name
        self.conexion = sqlite3.connect(str(self.db_path))
        self.cursor = self.conexion.cursor()
        self.conexion.row_factory = sqlite3.Row
        self._crear_tabla()
    
    def _crear_tabla(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                fecha_registro CURRENT_TIMESTAMP            
            )
        """)
        self.conexion.commit()
    
    def obtener_todos_los_clientes(self) -> List[Dict[str, Any]]:
            cursor = self.conexion.cursor()
            cursor.execute("SELECT id, nombre FROM clientes ORDER BY id DESC")
            return [dict(row) for row in cursor.fetchall()]
    
    def agregar_cliente(self, nombre: str) -> Dict[str, Any]:
        try:
                cursor = self.conexion.cursor()
                cursor.execute("INSERT INTO clientes (nombre) VALUES (?)", (nombre,))
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