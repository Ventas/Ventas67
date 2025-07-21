from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from Database import get_db  # Tu función para obtener la sesión de DB
from fastapi.templating import Jinja2Templates
from modules import models  # Asegúrate de que esté importado correctamente

templates = Jinja2Templates(directory="templates")

router = APIRouter()

# 🔹 Ruta para listar proveedores
@router.get("/proveedores", response_class=HTMLResponse)
def listar_proveedores(request: Request, db: Session = Depends(get_db)):
    proveedores = db.query(models.Proveedor).all()
    return templates.TemplateResponse("proveedor.html", {
        "request": request,
        "proveedores": proveedores
    })

# 🔹 Ruta para crear nuevo proveedor
@router.post("/proveedores")
def crear_proveedor(
    nombre: str = Form(...),
    razon_social: str = Form(""),
    nit_ruc: str = Form(""),
    direccion: str = Form(""),
    telefono: str = Form(""),
    correo: str = Form(""),
    contacto: str = Form(""),
    metodo_pago: str = Form(""),
    db: Session = Depends(get_db)
):
    nuevo_proveedor = models.Proveedor(
        nombre=nombre,
        razon_social=razon_social,
        nit_ruc=nit_ruc,
        direccion=direccion,
        telefono=telefono,
        correo=correo,
        contacto=contacto,
        metodo_pago=metodo_pago
    )
    db.add(nuevo_proveedor)
    db.commit()
    return RedirectResponse(url="/proveedores", status_code=303)

# 🔹 Ruta para editar proveedor
@router.get("/proveedores/{proveedor_id}/editar", response_class=HTMLResponse)
def editar_proveedor_form(request: Request, proveedor_id: int, db: Session = Depends(get_db)):
    proveedor = db.query(models.Proveedor).filter(models.Proveedor.id == proveedor_id).first()
    return templates.TemplateResponse("editar_proveedor.html", {
        "request": request,
        "proveedor": proveedor
    })

@router.post("/proveedores/editar/{id}")
def editar_proveedor(
    id: int,
    nombre: str = Form(...),
    razon_social: str = Form(...),
    contacto: str = Form(...),
    telefono: str = Form(...),
    correo: str = Form(...),
    metodo_pago: str = Form(...),
    db: Session = Depends(get_db)
):
    proveedor = db.query(models.Proveedor).filter(models.Proveedor.id == id).first()

    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    proveedor.nombre = nombre
    proveedor.razon_social = razon_social
    proveedor.contacto = contacto
    proveedor.telefono = telefono
    proveedor.correo = correo
    proveedor.metodo_pago = metodo_pago

    db.commit()
    return RedirectResponse(url="/proveedores", status_code=303)

# 🔹 Ruta para eliminar proveedor
@router.post("/proveedores/eliminar/{id}")
def eliminar_proveedor(id: int, db: Session = Depends(get_db)):
    proveedor = db.query(models.Proveedor).filter(models.Proveedor.id == id).first()

    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    db.delete(proveedor)
    db.commit()
    return RedirectResponse(url="/proveedores", status_code=303)

