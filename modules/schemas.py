from pydantic import BaseModel
from typing import Optional

# -------- USUARIOS --------
class UsuarioBase(BaseModel):
    nombre: str
    correo: str
    rol: Optional[str] = "vendedor"

class UsuarioCreate(UsuarioBase):
    contraseña: str

class UsuarioOut(UsuarioBase):
    id: int

    class Config:
        orm_mode = True

# -------- PRODUCTOS --------
class ProductoBase(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    precio: float
    cantidad: int

class ProductoCreate(ProductoBase):
    pass

class ProductoOut(ProductoBase):
    id: int
    usuario_id: Optional[int]

    class Config:
        orm_mode = True