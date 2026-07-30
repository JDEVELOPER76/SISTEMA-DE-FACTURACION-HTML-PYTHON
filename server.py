from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
import asyncio
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi import Form, HTTPException , File , UploadFile
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path
from typing import Dict, Set
import secrets
from decimal import Decimal, ROUND_HALF_UP
from herramientas.secret_key import LLAVE_SECRETA
from datetime import datetime , timedelta
from database.login import UserDB
from database.ventas import VentaDB
from database.productos import ProductoDB, Producto
from database.clientes import ClienteDB
from database.ventas import Venta
from database.auditoria import AuditoriaDB
from database.empleados import EmpleadoDB, Empleado
from user.ventas import DataVenta
from herramientas.mi_ip import obtener_ip_local
from py2exe_helper import resource_path
@asynccontextmanager
async def lifespan(app: FastAPI):

    async def periodic_cleanup():
        while True:
            await asyncio.sleep(3600)  # Cada hora
            limpiar_sesiones_antiguas()

    task = asyncio.create_task(periodic_cleanup())

    # Startup terminado
    yield

    # Shutdown
    task.cancel()

app = FastAPI(
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)


# Middleware de sesión
app.add_middleware(SessionMiddleware, secret_key=LLAVE_SECRETA)
static_dir = resource_path("static")
templates_dir = resource_path("templates")
app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)
CARPETA_IMAGENES = Path(static_dir) / "productos_img"
CARPETA_IMAGENES.mkdir(parents=True, exist_ok=True)
CARPETA_PERFIL_IMG = Path(static_dir) / "perfil_img"
CARPETA_PERFIL_IMG.mkdir(parents=True, exist_ok=True)


def redondear_monto(valor: float) -> float:
    return float(Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

# Registro en memoria de la última actividad de cada usuario (para el apartado "En línea")
usuarios_actividad: Dict[str, datetime] = {}
MINUTOS_PARA_CONSIDERAR_DESCONECTADO = 0


# ==========================================
#   PRESENCIA EN TIEMPO REAL (WebSocket)
# ==========================================
class ConnectionManager:
    """
    Mantiene:
    - Las conexiones WebSocket activas de cada usuario logueado (una persona
      puede tener varias pestañas abiertas, por eso es un set por username).
    - Las conexiones WebSocket de los admins que están viendo el panel
      "En línea", para poder empujarles la lista actualizada al instante.
    """
    def __init__(self):
        self.conexiones_usuarios: Dict[str, Set[WebSocket]] = {}
        self.conexiones_admin: Set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def conectar_usuario(self, username: str, ws: WebSocket):
        async with self.lock:
            self.conexiones_usuarios.setdefault(username, set()).add(ws)

    async def desconectar_usuario(self, username: str, ws: WebSocket):
        async with self.lock:
            conexiones = self.conexiones_usuarios.get(username)
            if conexiones:
                conexiones.discard(ws)
                if not conexiones:
                    del self.conexiones_usuarios[username]

    async def desconectar_usuario_completo(self, username: str):
        async with self.lock:
            conexiones = self.conexiones_usuarios.pop(username, set())
            return list(conexiones)

    async def conectar_admin(self, ws: WebSocket):
        async with self.lock:
            self.conexiones_admin.add(ws)

    async def desconectar_admin(self, ws: WebSocket):
        async with self.lock:
            self.conexiones_admin.discard(ws)

    def usuarios_conectados(self) -> Set[str]:
        return set(self.conexiones_usuarios.keys())

    async def notificar_admins(self):
        """Empuja la lista actualizada a todos los admins conectados al panel."""
        payload = construir_payload_en_linea()
        muertos = []
        for admin_ws in list(self.conexiones_admin):
            try:
                await admin_ws.send_json(payload)
            except Exception:
                muertos.append(admin_ws)
        for m in muertos:
            self.conexiones_admin.discard(m)


manager = ConnectionManager()


async def marcar_usuario_desconectado(username: str):
    if not username:
        return

    conexiones = await manager.desconectar_usuario_completo(username)
    usuarios_actividad.pop(username, None)
    await manager.notificar_admins()

    for ws in conexiones:
        try:
            await ws.close(code=1000)
        except Exception:
            pass


def usuarios_actualmente_conectados() -> Set[str]:
    """
    Une dos fuentes de verdad:
    1. Quienes tienen un WebSocket de presencia abierto ahora mismo (instantáneo).
    2. Quienes tuvieron actividad HTTP reciente pero aún no abrieron el socket
       (fallback para no perder a nadie mientras se actualiza el frontend).
    """
    ahora = datetime.now()
    limite = timedelta(minutes=MINUTOS_PARA_CONSIDERAR_DESCONECTADO)
    por_actividad = {
        username for username, ultima in usuarios_actividad.items()
        if ahora - ultima < limite
    }
    return por_actividad | manager.usuarios_conectados()


def construir_payload_en_linea() -> dict:
    """Arma el JSON que se manda tanto por GET como por WebSocket."""
    usernames_conectados = usuarios_actualmente_conectados()
    todos = {u["username"]: u for u in login_db.obtener_usuarios_basico()}

    conectados = []
    for username in usernames_conectados:
        u = todos.get(username, {})
        ultima = usuarios_actividad.get(username)
        conectados.append({
            "username": username,
            "nombre": u.get("nombre") or username,
            "puesto": u.get("puesto"),
            "tipo": u.get("tipo"),
            "foto": u.get("foto"),
            "en_vivo": username in manager.usuarios_conectados(),
            "ultima_actividad": ultima.strftime("%H:%M:%S") if ultima else None,
        })

    conectados.sort(key=lambda x: x["nombre"].lower())
    return {"conectados": conectados, "total": len(conectados)}

@app.middleware("http")
async def middleware_actividad(request: Request, call_next):
    response = await call_next(request)
    try:
        username = request.session.get("username")
        if username:
            usuarios_actividad[username] = datetime.now()
    except Exception:
        pass
    return response

@app.exception_handler(404)
async def not_found(request: Request, response: HTMLResponse):
    return templates.TemplateResponse("404.html", {"request": request})

@app.exception_handler(500)
async def server_error(request: Request, response: HTMLResponse):
    return templates.TemplateResponse("500.html", {"request": request})

@app.exception_handler(405)
async def http_exception_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("405.html", {"request": request, "detail": exc.detail}, status_code=405)


# Inicializamos la base de datos
ventas_db = VentaDB()
login_db = UserDB()
db_productos = ProductoDB()
cliente_db = ClienteDB()
auditoria_db = AuditoriaDB()
empleado_db = EmpleadoDB()

# Almacenamiento de sesiones activas del scanner (en memoria - para producción usa Redis)
scanner_sessions: Dict[str, dict] = {}

def obtener_foto_usuario(username: str):
    """Devuelve la ruta de la foto de perfil del usuario, o None si no tiene."""
    if not username:
        return None
    perfil = login_db.obtener_perfil(username)
    return perfil.get("foto") if perfil else None

@app.get("/", response_class=HTMLResponse)
async def vista_login(request: Request):
    error = request.query_params.get("error")
    return templates.TemplateResponse("index.html", {"request": request, "error": error})



# 1. Ruta GET para mostrar la página web de registro
@app.get("/nuevo_registro", response_class=HTMLResponse)
async def vista_nuevo_registro(request: Request):
    error = request.query_params.get("error")
    success = request.query_params.get("success")
    return templates.TemplateResponse("nuevo_registro.html", {
        "request": request, 
        "error": error,
        "success": success
    })

# 2. Ruta POST para procesar el formulario de registro de usuario
@app.post("/api/registrar_usuario")
async def registrar_usuario_web(
    request: Request,
    nombre: str = Form(...),
    puesto: str = Form(...),
    salario: float = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    tipo: str = Form(...)  # Por ejemplo: 'user' o 'admin'
):
    # Instanciamos la base de datos de empleados (asegúrate de tener empleado_db inicializado)
    # empleado_db = EmpleadoDB()
    
    nuevo_empleado = Empleado(
        nombre=nombre,
        puesto=puesto,
        salario=salario,
        username=username,
        password=password,
        tipo=tipo
    )
    
    resultado = empleado_db.agregar_usuario(nuevo_empleado)
    
    if not resultado:
        return RedirectResponse(url="/nuevo_registro?error=El%20nombre%20de%20usuario%20ya%20existe", status_code=303)
    
    # Opcional: Registrar el evento en la auditoría
    try:
        hora_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        auditoria_db.registrar(
            usuario=username,
            usuario_id=None,
            accion="REGISTRO_WEB",
            tabla="users",
            registro_id=None,
            detalles=f"Nuevo usuario registrado vía web: @{username}",
            fecha_hora=hora_local
        )
    except Exception:
        pass

    return RedirectResponse(url="/nuevo_registro?success=Usuario%20registrado%20exitosamente", status_code=303)

@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    username = request.session.get("username")
    rol = request.session.get("rol")
    
    # Control de acceso
    if not username or rol != "admin":
        return RedirectResponse(url="/?error=Acceso%20denegado", status_code=303)
    
    # 1. Obtener las últimas ventas con nombres de empleados y clientes
    ultimas_ventas = ventas_db.listar_ultimas_ventas(limite=10)
    
    # 2. Obtener el desglose de ventas totales por día
    ventas_por_dia = ventas_db.obtener_ventas_totales_por_dia()
    
    # 3. Calcular lo vendido el día de hoy para la tarjeta de arriba
    total_hoy = ventas_db.obtener_total_ventas_hoy()

    # Enviamos todo dentro del contexto a la plantilla admin.html
    return templates.TemplateResponse("admin.html", {
        "request": request, 
        "username": username,
        "foto": obtener_foto_usuario(username),
        "total_hoy": total_hoy,
        "total_historico": ventas_db.obtener_total_ventas(),
        "ultimas_ventas": ultimas_ventas,
        "ventas_por_dia": ventas_por_dia
    })

@app.get("/admin/ventas", response_class=HTMLResponse)
async def admin_ventas(request: Request):
    username = request.session.get("username")
    rol = request.session.get("rol")
    
    # Control de acceso
    if not username or rol != "admin":
        return RedirectResponse(url="/?error=Acceso%20denegado", status_code=303)
    
    # Obtener todas las ventas con su desglose de productos
    ultimas_ventas = ventas_db.listar_ultimas_ventas(limite=20)  # Puedes ajustar el límite
    ventas_con_productos = []
    for venta in ultimas_ventas:
        detalle = ventas_db.obtener_venta_con_productos(venta["id"])
        if detalle:
            # Convertir la cadena de fecha en un objeto datetime
            if isinstance(detalle.get("fecha_completa"), str):
                try:
                    detalle["fecha_completa"] = datetime.fromisoformat(detalle["fecha_completa"])
                except ValueError:
                    # Manejar el caso en que el formato no sea el esperado
                    pass  # O registrar un error si es necesario
            ventas_con_productos.append(detalle)

    return templates.TemplateResponse("admin_ventas.html", {
        "request": request, 
        "username": username,
        "foto": obtener_foto_usuario(username),
        "ventas_con_productos": ventas_con_productos
    })

@app.get("/admin/productos", response_class=HTMLResponse)
async def vista_productos(request: Request):
    # Trae todos los productos con IVA, stock, código de barras e imagen desde SQLite
    lista = db_productos.listar_productos()
    username = request.session.get("username")
    
    return templates.TemplateResponse("admin_productos.html", {
        "request": request,
        "username": username,
        "foto": obtener_foto_usuario(username),
        "productos": lista
    })



#post del login (validar usuarios)
@app.post("/login")
async def login(request: Request):
    form_data = await request.form()
    username = form_data.get("username")
    password = form_data.get("password")
    
    if login_db.verificar_usuario(username, password):
        request.session["username"] = username
        usuario_id = login_db.obtener_id_usuario(username)
        hora_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if login_db.es_admin(username):
            request.session["rol"] = "admin"
            auditoria_db.registrar(
                usuario=username,
                usuario_id=usuario_id,
                accion="LOGIN",
                tabla="users",
                registro_id=usuario_id,
                detalles="Inicio de sesión exitoso como Administrador.",
                fecha_hora=hora_local
            )
            return RedirectResponse(url="/admin", status_code=303)
        else:
            request.session["rol"] = "user"
            auditoria_db.registrar(
                usuario=username,
                usuario_id=usuario_id,
                accion="LOGIN",
                tabla="users",
                registro_id=usuario_id,
                detalles="Inicio de sesión exitoso como Operario/Empleado.",
                fecha_hora=hora_local
            )
            return RedirectResponse(url="/user/vender", status_code=303)
    else:
        return RedirectResponse(url="/?error=Credenciales%20inv%C3%A1lidas", status_code=303)
        
@app.get("/logout", response_class=HTMLResponse)
async def logout(request: Request):
    username = request.session.get("username")
    rol = request.session.get("rol")
    if username:
        usuario_id = login_db.obtener_id_usuario(username)
        hora_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        auditoria_db.registrar(
            usuario=username,
            usuario_id=usuario_id,
            accion="LOGOUT",
            tabla="users",
            registro_id=usuario_id,
            detalles=f"Cierre de sesión exitoso. Rol: {rol}.",
            fecha_hora=hora_local
        )
        await marcar_usuario_desconectado(username)
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)
        
#post de productos 
@app.post("/admin/productos/nuevo")
async def api_agregar_producto(
    request: Request,
    nombre: str = Form(...),
    descripcion: str = Form(None),
    precio: float = Form(...),
    iva: float = Form(...),
    codigo_barras: str = Form(...),
    proveedor: str = Form(...),
    stock: int = Form(...),
    categoria: str = Form(...),
    imagen_url: str = Form(None),              
    imagen_archivo: UploadFile = File(None)   
):
    username = request.session.get("username", "Desconocido")
    rol = request.session.get("rol")
    if not username or rol != "admin":
        raise HTTPException(status_code=403, detail="No autorizado")

    final_image_path = None
    if imagen_archivo and imagen_archivo.filename:
        try:
            extension = Path(imagen_archivo.filename).suffix 
            nombre_archivo = f"{codigo_barras}{extension}"
            ruta_guardado = CARPETA_IMAGENES / nombre_archivo
            # Leer completamente el archivo antes de guardarlo
            contenido_archivo = await imagen_archivo.read()
            # Escribir el contenido en el archivo
            with open(ruta_guardado, "wb") as f:
                f.write(contenido_archivo)
            final_image_path = f"/static/productos_img/{nombre_archivo}"
        except Exception as e:
            print(f"Error guardando imagen: {e}")
            raise HTTPException(status_code=400, detail=f"Error al guardar la imagen: {str(e)}")
    elif imagen_url and imagen_url.strip() != "":
        final_image_path = imagen_url

    nuevo_producto = Producto(
        nombre=nombre,
        descripcion=descripcion,
        precio=precio,
        iva=iva,
        codigo_barras=codigo_barras,
        proveedor=proveedor,
        stock=stock,
        categoria=categoria,
        imagen_url=final_image_path 
    )
    
    resultado = db_productos.agregar_producto(nuevo_producto)
    if not resultado["success"]:
        raise HTTPException(status_code=400, detail=resultado["error"])
        
    # Guardamos en auditoría la creación del producto
    usuario_id = login_db.obtener_id_usuario(username)
    hora_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    auditoria_db.registrar(
        usuario=username,
        usuario_id=usuario_id,
        accion="INSERT",
        tabla="productos",
        registro_id=None,
        detalles=f"Se agregó el producto '{nombre}' con stock inicial de {stock}.",
        fecha_hora=hora_local
    )
        
    return RedirectResponse(url="/admin/productos", status_code=303)

@app.post("/admin/productos/editar/{producto_id}")
async def api_editar_producto(
    producto_id: int,
    nombre: str = Form(...),
    descripcion: str = Form(None),
    precio: float = Form(...),
    iva: float = Form(...),
    codigo_barras: str = Form(...),
    proveedor: str = Form(...),
    stock: int = Form(...),
    categoria: str = Form(...),
    imagen_url: str = Form(None),              # Nueva URL opcional
    imagen_archivo: UploadFile = File(None)   # Nuevo archivo opcional
):
    # 1. Buscar el producto actual en la base de datos para saber qué imagen tenía antes
    # (Esto evita que se borre la foto si el usuario solo quería cambiar el precio o el stock)
    producto_actual = db_productos.obtener_producto(producto_id)
    if not producto_actual:
        raise HTTPException(status_code=404, detail="Producto no encontrado en el sistema")
    
    # Por defecto, mantenemos la imagen que ya existía
    final_image_path = producto_actual.get("imagen_url")

    # Caso A: El usuario subió un NUEVO archivo físico para reemplazar la imagen vieja
    if imagen_archivo and imagen_archivo.filename:
        try:
            extension = Path(imagen_archivo.filename).suffix
            nombre_archivo = f"{codigo_barras}{extension}"
            ruta_guardado = CARPETA_IMAGENES / nombre_archivo
            # Leer completamente el archivo antes de guardarlo
            contenido_archivo = await imagen_archivo.read()
            # Escribir el contenido en el archivo
            with open(ruta_guardado, "wb") as f:
                f.write(contenido_archivo)
            final_image_path = f"/static/productos_img/{nombre_archivo}"
        except Exception as e:
            print(f"Error guardando imagen en edición: {e}")
            raise HTTPException(status_code=400, detail=f"Error al guardar la imagen: {str(e)}")
        
    # Caso B: No subió archivo, pero pegó un NUEVO link de internet
    elif imagen_url and imagen_url.strip() != "":
        final_image_path = imagen_url

    # 2. Armamos el objeto Producto actualizado con los nuevos datos recibidos del modal
    producto_actualizado = Producto(
        nombre=nombre,
        descripcion=descripcion,
        precio=precio,
        iva=iva,
        codigo_barras=codigo_barras,
        proveedor=proveedor,
        stock=stock,
        categoria=categoria,
        imagen_url=final_image_path  # Conserva la vieja o guarda la nueva ruta
    )
    
    # 3. Guardamos los cambios llamando a la función que ya tienes en productos.py
    resultado = db_productos.actualizar_producto(producto_id, producto_actualizado)
    if not resultado["success"]:
        raise HTTPException(status_code=400, detail=resultado["error"])
        
    # 4. Redireccionamos de vuelta al inventario refrescado
    return RedirectResponse(url="/admin/productos", status_code=303)
    
@app.get("/admin/clientes")
async def vista_clientes(request: Request):
    # cliente_db debe ser tu instancia de ClienteDB()
    lista_clientes = cliente_db.obtener_todos_los_clientes() 
    username = request.session.get("username")
    return templates.TemplateResponse("admin_clientes.html", {
        "request": request,
        "username": username,
        "foto": obtener_foto_usuario(username),
        "clientes": lista_clientes
    })

@app.post("/admin/clientes/nuevo")
async def api_agregar_cliente(
    nombre: str = Form(...),
    tipo_identificacion: str = Form("cedula"),
    identificacion: str = Form(None),
    direccion: str = Form(None),
    telefono: str = Form(None),
    email: str = Form(None)
):
    if not nombre or nombre.strip() == "":
        raise HTTPException(status_code=400, detail="El nombre del cliente es obligatorio")
    
    resultado = cliente_db.agregar_cliente(
        nombre=nombre.strip(),
        tipo_identificacion=tipo_identificacion,
        identificacion=identificacion.strip() if identificacion else None,
        direccion=direccion.strip() if direccion else None,
        telefono=telefono.strip() if telefono else None,
        email=email.strip() if email else None
    )
    
    if not resultado["success"]:
        raise HTTPException(status_code=400, detail=resultado["error"])
    
    return {"success": True, "id": resultado.get("id"), "message": "Cliente agregado exitosamente"}


@app.post("/admin/clientes/eliminar/{cliente_id}")
async def api_eliminar_cliente(cliente_id: int):
    # Usamos un método directo en la base de datos para borrarlo por ID
    resultado = cliente_db.eliminar_cliente(cliente_id)
    if not resultado["success"]:
        raise HTTPException(status_code=400, detail=resultado["error"])
        
    return RedirectResponse(url="/admin/clientes", status_code=303)

@app.get("/admin/auditoria",response_class=HTMLResponse)
async def admin_auditoria(request: Request):
    username = request.session.get("username")
    rol = request.session.get("rol")
    if not username or rol != "admin":
        return RedirectResponse(url="/?error=Acceso%20denegado", status_code=303)
    logs_auditoria = auditoria_db.obtener_logs()
    return templates.TemplateResponse("admin_auditoria.html", {
        "request": request, 
        "username": username,
        "foto": obtener_foto_usuario(username),
        "logs_auditoria": logs_auditoria
    })

@app.get("/admin/usuarios", response_class=HTMLResponse)
async def admin_usuarios(request: Request):
    username = request.session.get("username")
    rol = request.session.get("rol")
    if not username or rol != "admin":
        return RedirectResponse(url="/?error=Acceso%20denegado", status_code=303)
    usuarios = empleado_db.obtener_usuarios()
    return templates.TemplateResponse("admin_usuarios.html", {
        "request": request,
        "username": username,
        "foto": obtener_foto_usuario(username),
        "usuarios": usuarios
    })
@app.post("/admin/usuarios/nuevo")
async def api_agregar_usuario(
    request: Request,
    nombre: str = Form(...),
    puesto: str = Form(...),
    salario: float = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    tipo: str = Form(...)
):
    usuario_admin = request.session.get("username", "Desconocido")
    nuevo_empleado = Empleado(
        nombre=nombre,
        puesto=puesto,
        salario=salario,
        username=username,
        password=password,
        tipo=tipo  # Por defecto, el nuevo usuario es un empleado/operario
    )
    
    resultado = empleado_db.agregar_usuario(nuevo_empleado)
    if not resultado:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe. Elija otro.")
    usuario_id = login_db.obtener_id_usuario(usuario_admin)
    hora_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    auditoria_db.registrar(
        usuario=usuario_admin,
        usuario_id=usuario_id,
        accion="INSERT",
        tabla="users",
        registro_id=None,
        detalles=f"Se creó un nuevo usuario con rol '{tipo.upper()}': @{username} ({nombre}).",
        fecha_hora=hora_local
    )
        
    return RedirectResponse(url="/admin/usuarios", status_code=303)
        
@app.post("/admin/usuarios/cambiar_password/{username}")
async def api_cambiar_password(request: Request, username: str, nueva_clave: str = Form(...)):
    empleado_db.cambiar_password(username, nueva_clave)
    return RedirectResponse(url="/admin/usuarios", status_code=303)
@app.post("/admin/usuarios/eliminar/{username}")
async def api_eliminar_usuario(request: Request, username: str):
    empleado_db.eliminar_usuario(username)
    return RedirectResponse(url="/admin/usuarios", status_code=303)


#usuario empleado 
@app.get("/user/vender", response_class=HTMLResponse)
async def vista_panel_vender(request: Request):
    # Validar que el usuario esté logueado (puedes usar tu middleware o leer la sesión)
    usuario_actual = request.session.get("username")
    if not usuario_actual:
        return RedirectResponse(url="/", status_code=303)
        
    # Cargar datos necesarios para el punto de venta
    productos = db_productos.listar_productos(limite=200) # Carga el inventario activo
    clientes = cliente_db.obtener_todos_los_clientes()     # Carga tus clientes id y nombre
    
    return templates.TemplateResponse("empleado_vender.html", {
        "request": request,
        "productos": productos,
        "clientes": clientes,
        "usuario": usuario_actual
    })


@app.get("/user/sala", response_class=HTMLResponse)
async def vista_sala_empleado(request: Request):
    """Sala de Empleados: perfil propio, foto, compañeros en línea y estado del escáner."""
    ip = obtener_ip_local()
    port = request.url.port
    usuario_actual = request.session.get("username")
    if not usuario_actual:
        return RedirectResponse(url="/", status_code=303)

    perfil = login_db.obtener_perfil(usuario_actual)
    if not perfil:
        raise HTTPException(status_code=404, detail="No se encontró el perfil del usuario.")

    return templates.TemplateResponse("empleado_sala.html", {
        "request": request,
        "usuario": usuario_actual,
        "perfil": perfil,
        "server_ip":ip,
        "server_port":port
    })


@app.post("/api/vender")
async def api_procesar_venta(request: Request, data: DataVenta):
    # 1. Seguridad: Verificar qué usuario (user/empleado) está disparando la venta
    usuario_username = request.session.get("username")
    if not usuario_username:
        raise HTTPException(status_code=401, detail="Sesión expirada. Inicie sesión nuevamente.")
        
    if not data.detalles:
        raise HTTPException(status_code=400, detail="El carrito de compras está vacío.")
        
    # 2. Buscar el ID real de ese usuario usando tu login.py (db_usuarios es tu instancia de UserDB)
    empleado_id = login_db.obtener_id_usuario(usuario_username)
    if not empleado_id:
        raise HTTPException(status_code=400, detail="No se encontró el identificador del empleado.")
        
    # 3. Estructurar la información cruzada para ventas.py
    detalles_venta = []
    total_calculado = 0
    for item in data.detalles:
        # Aquí calculamos el precio final incluyendo el IVA para el total
        precio_con_iva = redondear_monto(item.precio_unitario * (1 + item.iva / 100))
        total_calculado += redondear_monto(item.cantidad * precio_con_iva)
        detalles_venta.append(item.model_dump())

    nueva_venta = {
        "cliente_id": data.cliente_id,
        "empleado_id": empleado_id,
        "total": redondear_monto(total_calculado), # Usamos el total calculado con IVA
        "metodo_pago": data.metodo_pago,
        "detalles": detalles_venta
    }
    
    resultado = ventas_db.registrar_venta(Venta(**nueva_venta))
    
    if not resultado["success"]:
        raise HTTPException(status_code=500, detail=resultado["error"])
    # Guardamos en auditoría el cierre de la venta exitosa
    venta_id = resultado.get("venta_id")
    hora_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    auditoria_db.registrar(
        usuario=usuario_username,
        usuario_id=empleado_id,
        accion="INSERT",
        tabla="ventas",
        registro_id=venta_id,
        detalles=f"Venta #{venta_id} registrada. Total cobrado con IVA: ${redondear_monto(total_calculado):.2f}. Método: {data.metodo_pago}.",
        fecha_hora=hora_local
    )
        
    return {"success": True, "venta_id": venta_id}

# Endpoint para buscar clientes (autocompletado)
@app.get("/api/clientes/buscar")
async def buscar_clientes(termino: str):
    if not termino or len(termino) < 2:
        return {"clientes": []}
    resultados = cliente_db.buscar_clientes(termino)
    return {"clientes": resultados}

# Endpoint para obtener cliente por identificación (para facturación)
@app.get("/api/clientes/identificacion/{identificacion}")
async def obtener_cliente_por_identificacion(identificacion: str):
    cliente = cliente_db.obtener_cliente_por_identificacion(identificacion)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente

# Endpoint para crear cliente rápido desde el punto de venta (API)
@app.post("/api/clientes/rapido")
async def api_crear_cliente_rapido(request: Request):
    data = await request.json()
    nombre = data.get("nombre")
    tipo_identificacion = data.get("tipo_identificacion", "cedula")
    identificacion = data.get("identificacion")
    direccion = data.get("direccion")
    telefono = data.get("telefono")
    email = data.get("email")
    
    if not nombre:
        raise HTTPException(status_code=400, detail="El nombre es obligatorio")
    
    resultado = cliente_db.agregar_cliente(
        nombre=nombre.strip(),
        tipo_identificacion=tipo_identificacion,
        identificacion=identificacion.strip() if identificacion else None,
        direccion=direccion.strip() if direccion else None,
        telefono=telefono.strip() if telefono else None,
        email=email.strip() if email else None
    )
    
    if not resultado["success"]:
        raise HTTPException(status_code=400, detail=resultado["error"])
    
    # Obtener el cliente creado
    cliente = cliente_db.obtener_cliente_por_id(resultado["id"])
    return {"success": True, "cliente": cliente}


@app.post("/api/scanner_login")
async def scanner_login(request: Request):
    data = await request.json()
    username = data.get("username")
    password = data.get("password")
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Usuario y contraseña requeridos")
    
    # Verificar credenciales
    if login_db.verificar_usuario(username, password):
        # Generar ID de sesión único
        session_id = secrets.token_urlsafe(32)
        
        # Guardar sesión (válida por 8 horas)
        scanner_sessions[session_id] = {
            "username": username,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "expires_at": datetime.now() + timedelta(hours=8)
        }
        
        # Registrar en auditoría
        usuario_id = login_db.obtener_id_usuario(username)
        hora_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        auditoria_db.registrar(
            usuario=username,
            usuario_id=usuario_id,
            accion="SCANNER_LOGIN",
            tabla="scanner_sessions",
            registro_id=None,
            detalles="Inicio de sesión en el escáner de barras.",
            fecha_hora=hora_local
        )
        
        return {
            "success": True,
            "session_id": session_id,
            "username": username
        }
    else:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

@app.post("/api/scanner_verify")
async def scanner_verify(request: Request):
    data = await request.json()
    username = data.get("username")
    session_id = data.get("session_id")
    
    if not username or not session_id:
        return {"valid": False}
    
    session = scanner_sessions.get(session_id)
    if session and session["username"] == username:
        # Actualizar última actividad
        session["last_activity"] = datetime.now()
        return {"valid": True}
    
    return {"valid": False}

# Almacén temporal en memoria para la comunicación entre el escáner y la terminal

lecturas_pendientes = {}  # Ejemplo de estructura: {"juan123": ["750123..."], "maria45": []}

@app.post("/api/transmitir_escaneo")
async def transmitir_escaneo(data: dict):
    """Recibe el código desde el scanner.html y lo guarda ESPECÍFICAMENTE para su usuario"""
    codigo = data.get("codigo_barras")
    username = data.get("username")  # El usuario que inició sesión en el celular
    
    if not codigo:
        raise HTTPException(status_code=400, detail="No se proporcionó un código de barras.")
    if not username:
        raise HTTPException(status_code=400, detail="No se proporcionó el usuario del escáner.")
    
    # Si el usuario no tiene una lista de lecturas creada en el diccionario, la creamos
    if username not in lecturas_pendientes:
        lecturas_pendientes[username] = []
        
    # Guardamos el código únicamente en la lista de este usuario
    lecturas_pendientes[username].append(codigo)
    
    return {"success": True, "message": f"Código transmitido exitosamente a la sesión de {username}"}

@app.get("/api/verificar_lecturas")
async def verificar_lecturas(request: Request):
    """La terminal de ventas de la PC consulta este endpoint filtrando por su propia sesión"""
    # 1. Obtener el usuario logueado en la PC desde la sesión de Starlette/FastAPI
    usuario_pc = request.session.get("username") # Obtener el nombre del usuario de la sesión actual
    
    if not usuario_pc:
        return {"conectado": False, "usuario": None, "codigo": None}

    now = datetime.now()
    escaner_conectado = False
    
    # 2. Verificar si ESTE usuario específico tiene un escáner activo
    for session_id, session in scanner_sessions.items():
        if session["username"] == usuario_pc:
            expires_at = session.get("expires_at")
            if not expires_at and "created_at" in session:
                expires_at = session["created_at"] + timedelta(hours=8)
            
            if expires_at and now < expires_at:
                escaner_conectado = True
                break

    # 3. Extraer el código SOLO si le pertenece a este usuario
    codigo = None
    if usuario_pc in lecturas_pendientes and lecturas_pendientes[usuario_pc]:
        codigo = lecturas_pendientes[usuario_pc].pop(0)

    return {
        "conectado": escaner_conectado,
        "usuario": usuario_pc,
        "codigo": codigo
    }


@app.post("/api/scanner_logout")
async def scanner_logout(request: Request):
    data = await request.json()
    username = data.get("username")
    
    # Eliminar todas las sesiones del usuario
    sessions_to_remove = [
        session_id for session_id, session in scanner_sessions.items() 
        if session["username"] == username
    ]
    for session_id in sessions_to_remove:
        del scanner_sessions[session_id]
        
    return {"success": True}


# Modificar el endpoint existente para incluir validación de usuario
@app.post("/api/leer_codigo")
async def escanear_nativo(request: Request):
    """Lee un código de barras escaneado y devuelve la información del producto"""
    data = await request.json()
    codigo_barras = data.get("codigo_barras")
    usuario_escaner = data.get("usuario") # Usuario que está usando el scanner.html

    if not codigo_barras or not usuario_escaner:
        raise HTTPException(status_code=400, detail="Faltan datos: código de barras o usuario.")

    # Validar que el usuario del escáner tiene una sesión activa
    sesion_valida = False
    now = datetime.now()
    for session in scanner_sessions.values():
        # Si no tiene expires_at, calcular basándose en created_at (para compatibilidad con sesiones antiguas)
        expires_at = session.get("expires_at")
        if not expires_at and "created_at" in session:
            expires_at = session["created_at"] + timedelta(hours=8)
        
        if session["username"] == usuario_escaner and expires_at and now < expires_at:
            sesion_valida = True
            break
    
    if not sesion_valida:
        raise HTTPException(status_code=403, detail="Sesión de escáner no válida o expirada.")

    # Buscar el producto en la base de datos
    producto = db_productos.obtener_producto_por_codigo(codigo_barras)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado en el inventario.")
    
    # Devolver los datos del producto para que el frontend los use
    return producto


@app.get("/api/scanner_status")
async def scanner_status(request: Request):
    """Verifica si hay un scanner activo y quién lo está usando"""
    # Buscar sesiones de scanner activas (menos de 1 minuto sin actividad)
    now = datetime.now()
    active_sessions = []
    
    for session_id, session in scanner_sessions.items():
        if now - session["last_activity"] < timedelta(minutes=1):
            active_sessions.append(session["username"])
    
    if active_sessions:
        return {
            "active": True,
            "usuario": active_sessions[0]  # Retorna el primer scanner activo
        }
    else:
        return {"active": False, "usuario": None}

@app.get("/code", response_class=HTMLResponse)
async def vista_scanner(request: Request):
    return templates.TemplateResponse("scanner.html", {"request": request})


@app.get("/admin/estadistica", response_class=HTMLResponse)
async def vista_estadisticas(request: Request):
    username = request.session.get("username")
    rol = request.session.get("rol")
    
    if not username or rol != "admin":
        return RedirectResponse(url="/?error=Acceso%20denegado", status_code=303)
    
    # 1. Ventas por día (últimos 30 días)
    ventas_por_dia = ventas_db.obtener_ventas_totales_por_dia()
    ventas_por_dia = ventas_por_dia[:30]
    
    # 2. Métodos de pago
    metodos_pago = ventas_db.obtener_metodos_pago()
    
    # 3. Top 5 productos más vendidos
    top_productos = ventas_db.obtener_top_productos(limite=5)
    
    # 4. Top 5 clientes
    top_clientes = ventas_db.obtener_top_clientes(limite=5)
    
    # 5. Rendimiento por empleado
    empleados_ventas = ventas_db.obtener_rendimiento_empleados()
    
    # 6. Métricas del período (últimos 30 días)
    total_periodo = ventas_db.obtener_total_ventas_periodo(dias=30)
    total_ventas_periodo = ventas_db.obtener_cantidad_ventas_periodo(dias=30)
    ticket_promedio = ventas_db.obtener_ticket_promedio_periodo(dias=30)
    productos_vendidos = ventas_db.obtener_productos_vendidos_periodo(dias=30)
    
    return templates.TemplateResponse("admin_estadistica.html", {
        "request": request,
        "username": username,
        "foto": obtener_foto_usuario(username),
        "ventas_por_dia": ventas_por_dia,
        "metodos_pago": metodos_pago,
        "top_productos": top_productos,
        "top_clientes": top_clientes,
        "empleados_ventas": empleados_ventas,
        "total_periodo": total_periodo,
        "total_ventas_periodo": total_ventas_periodo,
        "ticket_promedio": ticket_promedio,
        "productos_vendidos": productos_vendidos
    })

@app.get("/admin/en_linea", response_class=HTMLResponse)
async def vista_usuarios_en_linea(request: Request):
    username = request.session.get("username")
    rol = request.session.get("rol")
    if not username or rol != "admin":
        return RedirectResponse(url="/?error=Acceso%20denegado", status_code=303)

    return templates.TemplateResponse("admin_en_linea.html", {
        "request": request,
        "username": username,
        "foto": obtener_foto_usuario(username)
    })


# ==========================================
#   APARTADO "EN LÍNEA"
# ==========================================
@app.get("/api/usuarios/en_linea")
async def usuarios_en_linea(request: Request):
    """
    Se mantiene como fallback (ej. para la carga inicial de la página antes
    de que el WebSocket termine de conectar). La fuente de verdad en tiempo
    real es el WebSocket /ws/en_linea.
    """
    username_actual = request.session.get("username")
    if not username_actual:
        raise HTTPException(status_code=401, detail="No autorizado")

    return construir_payload_en_linea()


@app.websocket("/ws/presencia")
async def ws_presencia(websocket: WebSocket):
    """
    Cada usuario logueado abre este socket mientras tiene la app abierta.
    Mientras el socket siga vivo, el usuario cuenta como "en línea" al
    instante; cuando se cierra (cierre de pestaña, refresh, pérdida de red),
    se marca como desconectado de inmediato y se avisa a los admins.
    """
    username = websocket.session.get("username")
    if not username:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    await manager.conectar_usuario(username, websocket)
    usuarios_actividad[username] = datetime.now()
    await manager.notificar_admins()

    try:
        while True:
            # El cliente debe mandar un ping periódico (ej. cada 20-30s) para
            # mantener la conexión viva y refrescar la última actividad.
            await websocket.receive_text()
            usuarios_actividad[username] = datetime.now()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.desconectar_usuario(username, websocket)
        await manager.notificar_admins()


@app.websocket("/ws/en_linea")
async def ws_en_linea(websocket: WebSocket):
    """Socket que consumen tanto el panel de admin como la sala de empleados
    para recibir la lista de usuarios en línea actualizada en tiempo real,
    sin hacer polling. Cualquier usuario logueado puede escuchar."""
    username = websocket.session.get("username")
    if not username:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    await manager.conectar_admin(websocket)
    # Estado inicial al conectarse
    await websocket.send_json(construir_payload_en_linea())

    try:
        while True:
            # No esperamos nada del admin, solo detectamos la desconexión.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.desconectar_admin(websocket)


# ==========================================
#   APARTADO "PERFIL"
# ==========================================
@app.get("/api/perfil")
async def obtener_mi_perfil(request: Request):
    username = request.session.get("username")
    if not username:
        raise HTTPException(status_code=401, detail="No autorizado")
    perfil = login_db.obtener_perfil(username)
    if not perfil:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return perfil

@app.post("/api/perfil/editar")
async def editar_mi_perfil(
    request: Request,
    nombre: str = Form(...),
    puesto: str = Form(None)
):
    username = request.session.get("username")
    if not username:
        raise HTTPException(status_code=401, detail="No autorizado")

    login_db.actualizar_datos_basicos(username, nombre=nombre.strip(), puesto=(puesto.strip() if puesto else None))

    usuario_id = login_db.obtener_id_usuario(username)
    hora_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    auditoria_db.registrar(
        usuario=username,
        usuario_id=usuario_id,
        accion="UPDATE",
        tabla="users",
        registro_id=usuario_id,
        detalles="El usuario actualizó los datos de su perfil.",
        fecha_hora=hora_local
    )

    return {"success": True}

@app.post("/api/perfil/foto")
async def subir_foto_perfil(request: Request, imagen_archivo: UploadFile = File(...)):
    username = request.session.get("username")
    if not username:
        raise HTTPException(status_code=401, detail="No autorizado")

    if not imagen_archivo or not imagen_archivo.filename:
        raise HTTPException(status_code=400, detail="No se proporcionó ninguna imagen")

    extension = Path(imagen_archivo.filename).suffix.lower()
    if extension not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        raise HTTPException(status_code=400, detail="Formato de imagen no permitido")

    try:
        nombre_archivo = f"{username}{extension}"
        ruta_guardado = CARPETA_PERFIL_IMG / nombre_archivo
        contenido = await imagen_archivo.read()
        with open(ruta_guardado, "wb") as f:
            f.write(contenido)
        ruta_final = f"/static/perfil_img/{nombre_archivo}"
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al guardar la imagen: {str(e)}")

    login_db.actualizar_foto(username, ruta_final)

    usuario_id = login_db.obtener_id_usuario(username)
    hora_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    auditoria_db.registrar(
        usuario=username,
        usuario_id=usuario_id,
        accion="UPDATE",
        tabla="users",
        registro_id=usuario_id,
        detalles="El usuario actualizó su foto de perfil.",
        fecha_hora=hora_local
    )

    return {"success": True, "foto": ruta_final}




# Limpiar sesiones antiguas cada hora
def limpiar_sesiones_antiguas():
    now = datetime.now()
    expired_sessions = []
    for session_id, session in scanner_sessions.items():
        if now - session["last_activity"] > timedelta(hours=8):
            expired_sessions.append(session_id)
    
    for session_id in expired_sessions:
        del scanner_sessions[session_id]