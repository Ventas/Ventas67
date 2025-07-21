from sqlalchemy.orm import Session
from modules import models, schemas

def crear_producto(db: Session, producto: schemas.ProductoCreate, usuario_id: int):
    db_producto = models.Producto(**producto.dict(), usuario_id=usuario_id)
    db.add(db_producto)
    db.commit()
    db.refresh(db_producto)
    return db_producto