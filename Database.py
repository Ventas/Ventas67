from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv
from sqlalchemy.exc import ProgrammingError

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()




# with engine.connect() as conn:
#     conn.execute(text("DROP TABLE IF EXISTS sales"))
#     print("✅ Tabla 'sales' eliminada correctamente")

    
# with engine.connect() as conn:
#     conn.execute(text("DROP TABLE IF EXISTS products"))
#     print("✅ Tabla 'sales' eliminada correctamente")



# create_table_sql = """
# CREATE TABLE IF NOT EXISTS `products` (
#   `id`               INT NOT NULL AUTO_INCREMENT,
#   `nombre`           VARCHAR(100) NOT NULL,
#   `descripcion`      VARCHAR(255) DEFAULT NULL,
#   `stock`            INT NOT NULL,
#   `precio`           FLOAT NOT NULL,
#   `codigo_barras`    TEXT NOT NULL,
#   `unidad_stock`     TEXT,
#   `iva`              FLOAT NOT NULL DEFAULT 0,
#   `precio_proveedor` FLOAT NOT NULL DEFAULT 0,
#   `fecha_vencimiento` DATE DEFAULT NULL,
#   PRIMARY KEY (`id`),
#   KEY `ix_products_id` (`id`)
# ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
# """

# # 🚀 Ejecutamos en un bloque de transacción automática
# with engine.begin() as conn:
#     conn.execute(text(create_table_sql))

# print("✅ Tabla 'products' creada (o verificada) correctamente.")

# with engine.begin() as conn:      # begin() ⇒ autocommit al terminar
#     conn.execute(text(create_table_sql))

# print("✅ Tabla 'products' creada/actualizada correctamente.")

# create_proveedores_sql = """
# CREATE TABLE IF NOT EXISTS `proveedores` (
#   `id`             INT NOT NULL AUTO_INCREMENT,
#   `nombre`         VARCHAR(100) NOT NULL,
#   `razon_social`   VARCHAR(100) DEFAULT NULL,
#   `nit_ruc`        VARCHAR(50) DEFAULT NULL,
#   `direccion`      VARCHAR(150) DEFAULT NULL,
#   `telefono`       VARCHAR(20) DEFAULT NULL,
#   `correo`         VARCHAR(100) DEFAULT NULL,
#   `contacto`       VARCHAR(100) DEFAULT NULL,
#   `metodo_pago`    VARCHAR(50) DEFAULT NULL,
#   `creado_en`      DATETIME DEFAULT NULL,
#   PRIMARY KEY (`id`),
#   KEY `ix_proveedores_id` (`id`)
# ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
# """

# # 🚀 Ejecutar en un bloque de autocommit
# with engine.begin() as conn:
#     conn.execute(text(create_proveedores_sql))

# print("✅ Tabla 'proveedores' creada (o verificada) correctamente.")

# create_storeuser_sql = """
# CREATE TABLE IF NOT EXISTS `StoreUser` (
#   `id`        INT NOT NULL AUTO_INCREMENT,
#   `nombre`    VARCHAR(100) NOT NULL,
#   `username`  VARCHAR(50)  NOT NULL,
#   `password`  VARCHAR(255) NOT NULL,
#   `rol`       ENUM('admin','vendedor') NOT NULL DEFAULT 'vendedor',
#   `creado_en` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
#   PRIMARY KEY (`id`),
#   UNIQUE KEY `username` (`username`)
# ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
# """

# # 🚀 Crear o verificar la tabla
# with engine.begin() as conn:
#     conn.execute(text(create_storeuser_sql))

# print("✅ Tabla 'StoreUser' creada (o verificada) correctamente.")
    
# create_products_sql = """
# CREATE TABLE IF NOT EXISTS `products` (
#   `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
#   `nombre` VARCHAR(100) NOT NULL,
#   `descripcion` VARCHAR(255) DEFAULT NULL,
#   `stock` INT NOT NULL,
#   `precio` DECIMAL(10,2) NOT NULL,
#   `codigo_barras` TEXT NOT NULL,
#   `unidad_stock` TEXT,
#   `iva` DECIMAL(5,2) NOT NULL DEFAULT 0.00,
#   `precio_proveedor` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
#   `fecha_vencimiento` DATE DEFAULT NULL,
#   PRIMARY KEY (`id`),
#   KEY `ix_products_id` (`id`)
# ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
# """

# create_sales_sql = """
# CREATE TABLE IF NOT EXISTS `sales` (
#   `id`                     INT UNSIGNED NOT NULL AUTO_INCREMENT,
#   `product_id`             INT UNSIGNED NOT NULL,  -- 👈 mismo tipo que products.id
#   `quantity`               INT NOT NULL,
#   `total`                  DECIMAL(10,2) NOT NULL,
#   `payment_method`         VARCHAR(50) NOT NULL,
#   `timestamp`              DATETIME DEFAULT CURRENT_TIMESTAMP,
#   `sale_group_id`          INT DEFAULT NULL,
#   `iva`                    DECIMAL(10,2) NOT NULL DEFAULT 0.00,
#   `product_iva_percentage` DECIMAL(5,2)  NOT NULL DEFAULT 0.00,
#   `subtotal`               DECIMAL(10,2) NOT NULL DEFAULT 0.00,
#   PRIMARY KEY (`id`),
#   KEY `idx_product_id` (`product_id`),
#   CONSTRAINT `sales_ibfk_1`
#     FOREIGN KEY (`product_id`) REFERENCES `products` (`id`)
#     ON DELETE RESTRICT ON UPDATE CASCADE
# ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
# """

# # 🚀 Ejecutar todo en una única transacción
# with engine.begin() as conn:
#     conn.execute(text(create_products_sql))
#     conn.execute(text(create_sales_sql))

# print("✅ Tablas 'products' y 'sales' creadas correctamente con claves foráneas compatibles.")

# with engine.connect() as conn:
#     # Añadir columna iva a la tabla products
#     alter_table_sql = "ALTER TABLE products ADD COLUMN precio_proveedor FLOAT NOT NULL DEFAULT 0.0;"
#     conn.execute(text(alter_table_sql))
#     print("✅ Columna 'precio_proveedor' añadida a la tabla 'products' correctamente.")

# with engine.connect() as conn:
#     alter_table_sql = "ALTER TABLE products ADD COLUMN fecha_vencimiento FLOAT NOT NULL DEFAULT 0.0;"
#     conn.execute(text(alter_table_sql))
#     print("✅ Columna 'precio_proveedor' añadida a la tabla 'products' correctamente.")

# with engine.connect() as conn:
#     rename_sql = "ALTER TABLE sales RENAME COLUMN money_change TO `change`;"
#     conn.execute(text(rename_sql))
#     print("✅ Columna renombrada correctamente.")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

        