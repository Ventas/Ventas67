from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from Database import get_db
from modules import models
from datetime import datetime
from datetime import date

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/inventario", response_class=HTMLResponse)
def ver_inventario(request: Request, db: Session = Depends(get_db)):
    productos = db.query(models.Product).all()
    return templates.TemplateResponse("inventario.html", {
        "request": request,
        "productos": productos,
        "fecha_actual": date.today()  # Añade esta línea
    })

@router.post("/inventario", response_class=HTMLResponse)
def agregar_producto(
    request: Request,
    nombre: str = Form(...),
    descripcion: str = Form(""),
    precio: float = Form(...),
    stock: int = Form(...),
    unidad_stock: str = Form(...),
    codigo_barras: str = Form(None),
    iva: float = Form(...),
    precio_proveedor: float = Form(...),
    fecha_vencimiento: str = Form(None),
    db: Session = Depends(get_db)
):
    fecha = datetime.strptime(fecha_vencimiento, "%Y-%m-%d").date() if fecha_vencimiento else None
    nuevo_producto = models.Product(
        nombre=nombre,
        descripcion=descripcion,
        precio=precio,
        stock=stock,
        unidad_stock=unidad_stock,
        codigo_barras=codigo_barras if codigo_barras else None,
        iva=iva,
        precio_proveedor=precio_proveedor,
        fecha_vencimiento=fecha
    )
    db.add(nuevo_producto)
    db.commit()
    return RedirectResponse(url="/inventario", status_code=303)

@router.post("/inventario/eliminar/{producto_id}")
def eliminar_producto(producto_id: int, db: Session = Depends(get_db)):
    producto = db.query(models.Product).filter(models.Product.id == producto_id).first()
    if producto:
        db.delete(producto)
        db.commit()
    return RedirectResponse(url="/inventario", status_code=303)
@router.get("/inventario/editar/{producto_id}", response_class=HTMLResponse)
def mostrar_editar_producto(request: Request, producto_id: int, db: Session = Depends(get_db)):
    producto = db.query(models.Product).filter(models.Product.id == producto_id).first()
    if not producto:
        return RedirectResponse(url="/inventario", status_code=303)
    return templates.TemplateResponse("editar_producto.html", {"request": request, "producto": producto})

@router.post("/inventario/editar/{producto_id}")
def editar_producto(
    producto_id: int,
    nombre: str = Form(...),
    descripcion: str = Form(""),
    precio: float = Form(...),
    stock: int = Form(...),
    unidad_stock: str = Form(...),
    codigo_barras: str = Form(None),
    iva: float = Form(...),
    precio_proveedor: float = Form(...),
    fecha_vencimiento: str = Form(None),
    db: Session = Depends(get_db)
):
    producto = db.query(models.Product).filter(models.Product.id == producto_id).first()
    if producto:
        producto.nombre = nombre
        producto.descripcion = descripcion
        producto.precio = precio
        producto.stock = stock
        producto.unidad_stock = unidad_stock
        producto.iva = iva
        producto.precio_proveedor = precio_proveedor,
        producto.codigo_barras = codigo_barras if codigo_barras else None
        producto.fecha_vencimiento = datetime.strptime(fecha_vencimiento, "%Y-%m-%d").date() if fecha_vencimiento else None  # AÑADIDO
        db.commit()
    return RedirectResponse(url="/inventario", status_code=303)