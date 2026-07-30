import sqlite3
from pathlib import Path
from datetime import datetime

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_BASE = RAIZ / "datos_facturacion"
CARPETA_DATOS = CARPETA_BASE / "datos"
CARPETA_DATOS.mkdir(parents=True, exist_ok=True)

class AuditoriaDB:
    def __init__(self, db_name="facturacion.db"):
        self.db_name = db_name
        self.db_path = CARPETA_DATOS / db_name
        self.conexion = sqlite3.connect(str(self.db_path))
        self.cursor = self.conexion.cursor()
        self._crear_tabla()
    
    def _crear_tabla(self):
        # Eliminamos DEFAULT CURRENT_TIMESTAMP para controlar el tiempo real de manera manual y exacta
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS auditoria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER,
                usuario TEXT,
                accion TEXT NOT NULL,
                tabla TEXT NOT NULL,
                registro_id INTEGER,
                detalles TEXT,
                fecha_hora TEXT,
                FOREIGN KEY (usuario_id) REFERENCES users(id)
            )
        """)
        self.conexion.commit()
    
    def registrar(self, usuario: str, usuario_id: int, accion: str, tabla: str, registro_id: int = None, detalles: str = None, fecha_hora: str = None):
        try:
            # Si no se proporciona una fecha, se captura la hora local del sistema con milisegundos
            if not fecha_hora:
                fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            self.cursor.execute("""
                INSERT INTO auditoria (usuario_id, usuario, accion, tabla, registro_id, detalles, fecha_hora) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (usuario_id, usuario, accion, tabla, registro_id, detalles, fecha_hora))
            self.conexion.commit()
            return True
        except Exception as e:
            print(f"Error registrando auditoría: {e}")
            return False
    
    def obtener_logs(self, limite: int = 100, offset: int = 0):
        self.cursor.execute("""
            SELECT * FROM auditoria
            ORDER BY fecha_hora DESC
            LIMIT ? OFFSET ?
        """, (limite, offset))
        
        resultados = self.cursor.fetchall()
        logs = []
        for row in resultados:
            logs.append({
                "id": row[0],
                "usuario_id": row[1],
                "usuario": row[2],
                "accion": row[3],
                "tabla": row[4],
                "registro_id": row[5],
                "detalles": row[6],
                "fecha_hora": row[7]
            })
        return logs
    
    def obtener_logs_usuario(self, usuario: str, limite: int = 100):
        self.cursor.execute("""
            SELECT * FROM auditoria
            WHERE usuario = ?
            ORDER BY fecha_hora DESC
            LIMIT ?
        """, (usuario, limite))
        
        resultados = self.cursor.fetchall()
        logs = []
        for row in resultados:
            logs.append({
                "id": row[0],
                "usuario_id": row[1],
                "usuario": row[2],
                "accion": row[3],
                "tabla": row[4],
                "registro_id": row[5],
                "detalles": row[6],
                "fecha_hora": row[7]
            })
        return logs
    
    def obtener_logs_tabla(self, tabla: str, limite: int = 100):
        self.cursor.execute("""
            SELECT * FROM auditoria
            WHERE tabla = ?
            ORDER BY fecha_hora DESC
            LIMIT ?
        """, (tabla, limite))
        
        resultados = self.cursor.fetchall()
        logs = []
        for row in resultados:
            logs.append({
                "id": row[0],
                "usuario_id": row[1],
                "usuario": row[2],
                "accion": row[3],
                "tabla": row[4],
                "registro_id": row[5],
                "detalles": row[6],
                "fecha_hora": row[7]
            })
        return logs