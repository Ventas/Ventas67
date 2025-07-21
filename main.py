from fastapi import FastAPI, Request, Form, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from Routes import auth, inventario,sales, Proveedor
from modules import models
from Database import engine
from fastapi.responses import HTMLResponse , RedirectResponse
from sqlalchemy import text
from starlette.status import HTTP_302_FOUND
import hashlib
from openpyxl import Workbook
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import datetime
from openpyxl import Workbook

SCALE_PORT = 'COM3'  # o '/dev/ttyUSB0' en Linux
SCALE_BAUDRATE = 9600


models.Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(inventario.router)
app.include_router(sales.router)
templates = Jinja2Templates(directory="templates")
app.include_router(Proveedor.router)




# ✅ Función para cifrar contraseñas con SHA-256
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

@app.get("/")
async def root():
    return RedirectResponse(url="/login")

# Ruta principal con menú
@app.get("/menu", response_class=HTMLResponse)
async def menu_principal(request: Request):
    return templates.TemplateResponse("menu.html", {"request": request})


# Mostrar el formulario de login
@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/logout")
async def logout(request: Request):
    # Ejemplo: Limpiar cookies de sesión
    response = RedirectResponse(url="/login", status_code=HTTP_302_FOUND)
    response.delete_cookie("session_token")  # Si usas cookies
    # Otra lógica de limpieza de sesión si es necesario
    return response

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    with engine.connect() as conn:
        # Ejecutar la consulta para obtener al usuario
        result = conn.execute(
            text("SELECT * FROM StoreUser WHERE username = :username"),
            {"username": username}
        ).fetchone()

        # Agregar print para depurar
        print("Resultado de la consulta:", result)

        if result:
            print(f"Contraseña almacenada: {result[3]}")  # Muestra la contraseña almacenada
            if password == result[3]:  # Comparación directa sin cifrado
                # Login exitoso
                print("Login exitoso")
                return RedirectResponse(url="/menu", status_code=HTTP_302_FOUND)
            else:
                print("Contraseña incorrecta")
        else:
            print("Usuario no encontrado")

    # Si no hay coincidencia
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": "Usuario o contraseña incorrectos"
    })

# Crear usuario (vista vacía, redirige a usuarios con form vacío)
@app.get("/crear-usuario", response_class=HTMLResponse)
async def crear_usuario_form(request: Request):
    return templates.TemplateResponse("usuarios.html", {"request": request, "usuario": None, "usuarios": []})

# Mostrar todos los usuarios
@app.get("/usuarios", response_class=HTMLResponse)
async def mostrar_usuarios(request: Request):
    with engine.connect() as conn:
        usuarios = conn.execute(text("SELECT * FROM StoreUser")).mappings().all()
    return templates.TemplateResponse("usuarios.html", {"request": request, "usuarios": usuarios, "usuario": None})

# Guardar o actualizar usuario
@app.post("/usuarios/guardar")
async def guardar_usuario(
    request: Request,
    id: str = Form(None),
    nombre: str = Form(...),
    username: str = Form(...),
    password: str = Form(None),
    rol: str = Form(...)
):
    try:
        with engine.connect() as conn:
            if id:  # Actualizar
                if password:
                    conn.execute(
                        text("""
                            UPDATE StoreUser
                            SET nombre=:nombre, username=:username, password=:password, rol=:rol
                            WHERE id=:id
                        """),
                        {
                            "id": id,
                            "nombre": nombre,
                            "username": username,
                            "password": hash_password(password),
                            "rol": rol
                        }
                    )
                else:
                    conn.execute(
                        text("""
                            UPDATE StoreUser
                            SET nombre=:nombre, username=:username, rol=:rol
                            WHERE id=:id
                        """),
                        {
                            "id": id,
                            "nombre": nombre,
                            "username": username,
                            "rol": rol
                        }
                    )
            else:  # Crear nuevo
                conn.execute(
                    text("""
                        INSERT INTO StoreUser (nombre, username, password, rol)
                        VALUES (:nombre, :username, :password, :rol)
                    """),
                    {
                        "nombre": nombre,
                        "username": username,
                        "password": hash_password(password),
                        "rol": rol
                    }
                )
            conn.commit()
        return RedirectResponse(url="/usuarios", status_code=HTTP_302_FOUND)

    except Exception as e:
        return templates.TemplateResponse("usuarios.html", {
            "request": request,
            "error": "Error al guardar usuario: " + str(e),
            "usuarios": [],
            "usuario": None
        })

# Editar usuario
@app.get("/usuarios/editar/{usuario_id}", response_class=HTMLResponse)
async def editar_usuario(request: Request, usuario_id: int):
    with engine.connect() as conn:
        usuario = conn.execute(
            text("SELECT * FROM StoreUser WHERE id = :id"), {"id": usuario_id}
        ).mappings().fetchone()

        usuarios = conn.execute(text("SELECT * FROM StoreUser")).mappings().all()

    if usuario:
        return templates.TemplateResponse("usuarios.html", {
            "request": request,
            "usuario": usuario,
            "usuarios": usuarios
        })
    else:
        return RedirectResponse(url="/usuarios", status_code=HTTP_302_FOUND)

# Eliminar usuario
@app.post("/usuarios/eliminar/{usuario_id}")
async def eliminar_usuario(usuario_id: int):
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM StoreUser WHERE id = :id"), {"id": usuario_id})
        conn.commit()
    return RedirectResponse(url="/usuarios", status_code=HTTP_302_FOUND)

# Mostrar formulario de cambio de contraseña
@app.get("/cambiar-password", response_class=HTMLResponse)
def cambiar_password_form(request: Request, username: str = ""):
    return templates.TemplateResponse("cambiar_password.html", {"request": request, "username": username})

# Procesar formulario de cambio de contraseña
@app.post("/cambiar-password", response_class=HTMLResponse)
async def cambiar_password(
    request: Request,
    username: str = Form(...),
    actual_password: str = Form(...),
    nueva_password: str = Form(...)
):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM StoreUser WHERE username = :username"),
            {"username": username}
        ).mappings().fetchone()

        if result:
            if result["password"] == (actual_password):
                # Actualizar la contraseña
                conn.execute(
                    text("UPDATE StoreUser SET password = :password WHERE username = :username"),
                    {
                        "password": (nueva_password),
                        "username": username
                    }
                )
                conn.commit()
                return templates.TemplateResponse("cambiar_password.html", {
                    "request": request,
                    "mensaje": "Contraseña actualizada correctamente"
                })
            else:
                return templates.TemplateResponse("cambiar_password.html", {
                    "request": request,
                    "error": "La contraseña actual es incorrecta"
                })
        else:
            return templates.TemplateResponse("cambiar_password.html", {
                "request": request,
                "error": "Usuario no encontrado"
            })

# Ejecutar en desarrollo
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)