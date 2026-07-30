import sqlite3 
from pydantic import BaseModel
from pathlib import Path 

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_BASE = RAIZ / "datos_facturacion"
CARPETA_USUARIOS = CARPETA_BASE / "usuarios"
CARPETA_USUARIOS.mkdir(parents=True, exist_ok=True)

class User(BaseModel):
    username: str
    password: str
    tipo: str

class UserDB:
    def __init__(self, db_name="users.db"):
        self.db_name = db_name
        self.db_path = CARPETA_USUARIOS / db_name
        self.conexion = sqlite3.connect(self.db_path)
        self.cursor = self.conexion.cursor()
        self._crear_tabla()
    
    def _crear_tabla(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                tipo TEXT NOT NULL,
                salario TEXT NOT NULL,
                puesto TEXT NOT NULL,
                nombre TEXT NOT NULL
            )
        """)
        self.conexion.commit()
        # Migración: agrega la columna 'foto' si la tabla ya existía sin ella
        try:
            self.cursor.execute("ALTER TABLE users ADD COLUMN foto TEXT")
            self.conexion.commit()
        except sqlite3.OperationalError:
            pass

    def obtener_perfil(self, username: str):
        """Devuelve los datos de perfil (para el apartado 'Perfil' y el topbar)."""
        self.cursor.execute(
            "SELECT username, nombre, puesto, tipo, foto FROM users WHERE username = ?",
            (username,)
        )
        row = self.cursor.fetchone()
        if not row:
            return None
        return {
            "username": row[0],
            "nombre": row[1],
            "puesto": row[2],
            "tipo": row[3],
            "foto": row[4]
        }

    def obtener_usuarios_basico(self):
        """Lista liviana de usuarios (para el apartado 'En línea')."""
        self.cursor.execute("SELECT username, nombre, puesto, tipo, foto FROM users")
        return [
            {"username": r[0], "nombre": r[1], "puesto": r[2], "tipo": r[3], "foto": r[4]}
            for r in self.cursor.fetchall()
        ]

    def actualizar_foto(self, username: str, foto_url: str):
        self.cursor.execute("UPDATE users SET foto = ? WHERE username = ?", (foto_url, username))
        self.conexion.commit()

    def actualizar_datos_basicos(self, username: str, nombre: str = None, puesto: str = None):
        """Edición sencilla del perfil: nombre y puesto."""
        if nombre is not None:
            self.cursor.execute("UPDATE users SET nombre = ? WHERE username = ?", (nombre, username))
        if puesto is not None:
            self.cursor.execute("UPDATE users SET puesto = ? WHERE username = ?", (puesto, username))
        self.conexion.commit()
        
    def es_admin(self, username: str):
        self.cursor.execute("SELECT tipo FROM users WHERE username = ?", (username,))
        result = self.cursor.fetchone()
        if result and result[0] == "admin":
            return True
        else:
            return False

    def verificar_usuario(self, username:str , password:str):
        self.cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
        result = self.cursor.fetchone()
        if result and result[0] == password:
            return True
        else:
            return False
    
    def obtener_id_usuario(self, username: str):
        self.cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def hay_usuarios(self):
        self.cursor.execute("SELECT COUNT(*) FROM users")
        result = self.cursor.fetchone()
        return result[0] > 0 if result else False

    def agregar_usuario(self, user: User):
        self.cursor.execute("INSERT INTO users (username, password, tipo, salario, puesto, nombre) VALUES (?, ?, ?, ?, ?, ?)",
                            (user.username, user.password, user.tipo, "", "", ""))
        self.conexion.commit()


#add = UserDB()
#add.agregar_usuario(User(username="admin", password="admin123", tipo="admin"))
#add.agregar_usuario(User(username="user", password="user123", tipo="user"))
#print(add.es_admin("admin"))
#print(add.es_admin("user"))
#print(add.verificar_usuario("adminx", "admin123"))
#print(add.verificar_usuario("user", "user123"))
#print(add.obtener_usuario_logueado("admin"))
#print(add.obtener_usuario_logueado("user"))
