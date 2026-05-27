import sqlite3 
from pydantic import BaseModel
from pathlib import Path 

RAIZ = Path(__file__).resolve().parent
CARPETA_USUARIOS = RAIZ / "usuarios"
CARPETA_USUARIOS.mkdir(exist_ok=True)

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

    


#add = UserDB()
#add.agregar_usuario(User(username="admin", password="admin123", tipo="admin"))
#add.agregar_usuario(User(username="user", password="user123", tipo="user"))
#print(add.es_admin("admin"))
#print(add.es_admin("user"))
#print(add.verificar_usuario("adminx", "admin123"))
#print(add.verificar_usuario("user", "user123"))
#print(add.obtener_usuario_logueado("admin"))
#print(add.obtener_usuario_logueado("user"))
