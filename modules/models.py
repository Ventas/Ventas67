from sqlalchemy import Column, Integer, String, Float, ForeignKey,DateTime
from sqlalchemy.orm import relationship
from Database import Base
from datetime import datetime
from sqlalchemy import Date

# class User(Base):
#     __tablename__ = "users"

#     id = Column(Integer, primary_key=True, index=True)
#     nombre = Column(String(100))
#     correo = Column(String(100), unique=True, index=True)
#     contraseña = Column(String(255))
#     rol = Column(String(50))

#     productos = relationship("products", back_populates="creado_por")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(String(255))
    stock = Column(Integer, nullable=False)
    unidad_stock = Column(String(100), nullable=False)
    precio = Column(Float, nullable=False)
    codigo_barras = Column(String, unique=True, nullable=True)
    iva = Column(Float, nullable=False, default=0.0)  # Porcentaje (ej: 19.0)
    precio_proveedor = Column(Float, nullable=False, default=0.0)
    fecha_vencimiento = Column(Date, nullable=True) 

    sales = relationship("Sale", back_populates="product")

class Sale(Base):
    __tablename__ = "sales"
    
    id = Column(Integer, primary_key=True, index=True)
    sale_group_id = Column(Integer)  # Mismo ID para todos los items de una misma venta
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer)
    subtotal = Column(Float)
    total = Column(Float)
    iva = Column(Float)
    payment_method = Column(String)
    product_iva_percentage = Column(Float)
    timestamp = Column(DateTime, default=datetime.now)

    # Relación hacia producto
    product = relationship("Product", back_populates="sales")

class Proveedor(Base):
    __tablename__ = "proveedores"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    razon_social = Column(String(100))
    nit_ruc = Column(String(50))
    direccion = Column(String(150))
    telefono = Column(String(20))
    correo = Column(String(100))
    contacto = Column(String(100))
    metodo_pago = Column(String(50))
    creado_en = Column(DateTime, default=datetime.utcnow)

    



    
    