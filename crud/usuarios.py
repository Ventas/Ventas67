from sqlalchemy.orm import Session
from modules import models, schemas
import hashlib

def crear_usuario(db: Session, usuario: schemas.UsuarioCreate):
    hashed_password = hashlib.sha256(usuario.contraseña.encode()).hexdigest()
    db_usuario = models.Usuario(
        nombre=usuario.nombre,
        correo=usuario.correo,
        contraseña=hashed_password,
        rol=usuario.rol
    )
    db.add(db_usuario)
    db.commit()
    db.refresh(db_usuario)
    return db_usuario