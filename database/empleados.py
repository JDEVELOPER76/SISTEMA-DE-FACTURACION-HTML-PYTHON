import sqlite3
from .login import UserDB , User

class Empleado(User):
    nombre: str
    puesto: str
    salario: float

class EmpleadoDB(UserDB):
    def __init__(self, db_name="users.db"):
        super().__init__(db_name)

    def agregar_usuario(self, empleado: Empleado):
        try:
            self.cursor.execute("""
                INSERT INTO users (username, password, tipo, salario, puesto, nombre) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (empleado.username, empleado.password, empleado.tipo, empleado.salario, empleado.puesto, empleado.nombre))
            self.conexion.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        
    def cambiar_password(self, username: str, nueva_clave: str):
        self.cursor.execute("UPDATE users SET password = ? WHERE username = ?", (nueva_clave, username))
        self.conexion.commit()

    def eliminar_usuario(self, username: str):
        self.cursor.execute("DELETE FROM users WHERE username = ?", (username,))
        self.conexion.commit()
    
    def obtener_usuarios(self):
        self.cursor.execute("SELECT username, tipo, salario, puesto, nombre FROM users")
        return self.cursor.fetchall()