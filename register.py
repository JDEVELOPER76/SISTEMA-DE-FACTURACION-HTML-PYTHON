from fastapi import FastAPI, HTTPException, Depends ,Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from database.login import UserDB , User
from fastapi.responses import RedirectResponse , HTMLResponse
from py2exe_helper import resource_path

registro = FastAPI()
templates = Jinja2Templates(directory=resource_path("templates"))
user_db = UserDB()


@registro.exception_handler(404)
async def not_found(request: Request, response: HTMLResponse):
    return templates.TemplateResponse("404.html", {"request": request})

@registro.exception_handler(500)
async def server_error(request: Request, response: HTMLResponse):
    return templates.TemplateResponse("500.html", {"request": request})

@registro.exception_handler(405)
async def http_exception_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("405.html", {"request": request, "detail": exc.detail}, status_code=405)

@registro.get("/")
async def index_registro(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@registro.get("/cuenta%registrada%con%exito")
async def cuenta_registrada_con_exito(request: Request):
    return templates.TemplateResponse("registro_exitoso.html", {"request": request})

@registro.post("/registro")
async def register_user(form_data: OAuth2PasswordRequestForm = Depends()):
    username = form_data.username
    password = form_data.password
    if user_db.verificar_usuario(username, password):
        raise HTTPException(status_code=400, detail="Ya existe un usuario registrado.")
    user_db.agregar_usuario(User(username=username, password=password, tipo="admin"))
    return RedirectResponse(url="/cuenta%registrada%con%exito", status_code=303)
