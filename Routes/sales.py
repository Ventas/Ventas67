from fastapi import APIRouter, Request, Form, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from Database import get_db
from modules import models
from fastapi.responses import RedirectResponse,StreamingResponse
from datetime import date
from sqlalchemy import func
from typing import List
import os
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime
from fastapi.responses import HTMLResponse
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import mm, inch
import tempfile
from io import BytesIO
import serial
import serial.tools.list_ports
from fastapi import HTTPException


router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/sales")
def sales_page(request: Request, db: Session = Depends(get_db)):
    productos = db.query(models.Product).all()
    ventas = db.query(models.Sale).all()

    hoy = date.today()
    ventas_hoy = db.query(models.Sale).filter(func.date(models.Sale.timestamp) == hoy).all()

    resumen = {
        "total_vendido": sum(v.total for v in ventas_hoy),
        "productos_vendidos": sum(v.quantity for v in ventas_hoy),
        "numero_ventas": len(ventas_hoy)
    }

    # Devuelve solo los datos iniciales sin result (que es para POST)
    return templates.TemplateResponse("sales.html", {
        "request": request,
        "productos": productos,
        "ventas": ventas,
        "resumen": resumen
        
    })


@router.post("/process-sale")
def process_sale(
    request: Request,
    product: List[str] = Form(...),
    quantity: List[float] = Form(...),
    payment_method: str = Form(...),
    money_received: float = Form(...),
    db: Session = Depends(get_db)
):
    hoy = date.today()
    ventas_hoy = db.query(models.Sale).filter(func.date(models.Sale.timestamp) == hoy).all()

    resumen = {
        "total_vendido": sum(v.total for v in ventas_hoy),
        "productos_vendidos": sum(v.quantity for v in ventas_hoy),
        "numero_ventas": len(ventas_hoy)
    }

    total_general = 0
    subtotal = 0
    iva_total = 0
    sales_to_save = []
    
    max_group_id = db.query(func.max(models.Sale.sale_group_id)).scalar()
    sale_group_id = 1 if max_group_id is None else max_group_id + 1

    for p, q in zip(product, quantity):
        selected_product = db.query(models.Product).filter(models.Product.nombre == p).first()

        if not selected_product:
            return templates.TemplateResponse("sales.html", {
                "request": request,
                "result": {"status": "error", "message": f"Producto '{p}' no encontrado"},
                "productos": db.query(models.Product).all(),
                "ventas": db.query(models.Sale).all(),
                "resumen": resumen
            })

        if selected_product.stock < q:
            return templates.TemplateResponse("sales.html", {
                "request": request,
                "result": {"status": "error", "message": f"Stock insuficiente para '{p}' (disponible: {selected_product.stock})"},
                "productos": db.query(models.Product).all(),
                "ventas": db.query(models.Sale).all(),
                "resumen": resumen
            })

        # Calcular subtotal e IVA
        precio_sin_iva = selected_product.precio
        subtotal_producto = precio_sin_iva * q
        iva_producto = subtotal_producto * (selected_product.iva / 100)
        total_producto = subtotal_producto + iva_producto

        subtotal += subtotal_producto
        iva_total += iva_producto
        total_general += total_producto

        # Actualizar stock
        selected_product.stock -= q

        new_sale = models.Sale(
            sale_group_id=sale_group_id,
            product_id=selected_product.id,
            quantity=q,
            subtotal=subtotal_producto,
            iva=iva_producto,
            total=total_producto,
            payment_method=payment_method,
            product_iva_percentage=selected_product.iva
        )
        sales_to_save.append(new_sale)
        db.add(new_sale)

    # Aplicar redondeo a múltiplos de 50 (1735 → 1750, 1785 → 1800)
    redondeo = 50
    total_general = ((total_general + redondeo - 1) // redondeo) * redondeo

    # Recalcular cambio con el total redondeado
    change = money_received - total_general

    if change < 0:
        return templates.TemplateResponse("sales.html", {
            "request": request,
            "result": {"status": "error", "message": "El dinero recibido no es suficiente"},
            "productos": db.query(models.Product).all(),
            "ventas": db.query(models.Sale).all(),
            "resumen": resumen
        })

    db.commit()

    # Actualizar resumen
    ventas_hoy = db.query(models.Sale).filter(func.date(models.Sale.timestamp) == hoy).all()
    resumen = {
        "total_vendido": sum(v.total for v in ventas_hoy),
        "productos_vendidos": sum(v.quantity for v in ventas_hoy),
        "numero_ventas": len(ventas_hoy)
    }

    return templates.TemplateResponse("sales.html", {
        "request": request,
        "result": {
            "status": "ok", 
            "subtotal": subtotal,
            "iva": iva_total,
            "total": total_general,  # Total redondeado
            "change": change,       # Cambio con total redondeado
            "sale_id": sale_group_id,
            "total_sin_redondeo": subtotal + iva_total  # Opcional: para referencia
        },
        "productos": db.query(models.Product).all(),
        "ventas": db.query(models.Sale).all(),
        "resumen": resumen
    })
@router.post("/delete-sale")
def delete_sale(sale_id: int = Form(...), db: Session = Depends(get_db)):
    venta = db.query(models.Sale).filter(models.Sale.id == sale_id).first()

    if not venta:
        return {"error": "Venta no encontrada"}

    producto = db.query(models.Product).filter(models.Product.id == venta.product_id).first()
    if producto:
        producto.stock += venta.quantity
        db.commit()

    db.delete(venta)
    db.commit()

    return RedirectResponse(url="/sales", status_code=303)

@router.post("/get-product-by-barcode")
def get_product_by_barcode(barcode: str = Form(...), db: Session = Depends(get_db)):
    producto = db.query(models.Product).filter(models.Product.codigo_barras == barcode).first()
    
    if producto:
        return {
            "status": "ok",
            "product": {
                "nombre": producto.nombre,
                "precio": producto.precio,
                "stock": producto.stock
            }
        }
    return {"status": "error", "message": "Producto no encontrado"}

@router.get("/export-sales-excel")
def export_sales_excel(db: Session = Depends(get_db)):
    hoy = date.today()
    ventas = db.query(models.Sale).filter(func.date(models.Sale.timestamp) == hoy).all()

    total_vendido = sum(v.total for v in ventas)
    productos_vendidos = sum(v.quantity for v in ventas)
    numero_ventas = len(ventas)

    file_path = "ventas_dia.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Ventas del Día"

    # Cabeceras
    ws.append(["ID", "Producto", "Cantidad", "Total", "Método de Pago", "Fecha"])

    for venta in ventas:
        producto = db.query(models.Product).filter(models.Product.id == venta.product_id).first()
        ws.append([
            venta.id,
            producto.nombre if producto else "Desconocido",
            venta.quantity,
            venta.total,
            venta.payment_method,
            venta.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        ])

    # Espacio + resumen al final
    ws.append([])
    ws.append(["Resumen del Día"])
    ws.append(["Total Vendido", total_vendido])
    ws.append(["Productos Vendidos", productos_vendidos])
    ws.append(["Número de Ventas", numero_ventas])

    wb.save(file_path)

    return FileResponse(path=file_path, filename="ventas_dia.xlsx", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@router.get("/export-sales-by-date")
async def export_sales_by_date(selected_date: str, db: Session = Depends(get_db)):
    date_obj = datetime.strptime(selected_date, "%Y-%m-%d").date()
    filepath = generar_excel_para_fecha(date_obj, db)
    return FileResponse(
        path=filepath,
        filename=f"ventas_{selected_date}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
@router.get("/export-sales-pdf")
def export_sales_pdf(db: Session = Depends(get_db)):
    hoy = date.today()
    ventas = db.query(models.Sale).filter(func.date(models.Sale.timestamp) == hoy).all()

    total_vendido = sum(v.total for v in ventas)
    productos_vendidos = sum(v.quantity for v in ventas)
    numero_ventas = len(ventas)

    # Crear archivo PDF
    file_path = "ventas_dia.pdf"
    doc = SimpleDocTemplate(file_path, pagesize=letter)
    elements = []

    # Estilos
    styles = getSampleStyleSheet()
    elements.append(Paragraph("Reporte de Ventas del Día", styles['Title']))
    elements.append(Paragraph(f"Fecha: {hoy.strftime('%Y-%m-%d')}", styles['Normal']))

    # Datos de las ventas
    data = [["ID", "Producto", "Cantidad", "Total", "Método de Pago", "Fecha"]]
    
    for venta in ventas:
        producto = db.query(models.Product).filter(models.Product.id == venta.product_id).first()
        data.append([
            str(venta.id),
            producto.nombre if producto else "Desconocido",
            str(venta.quantity),
            f"${venta.total:.2f}",
            venta.payment_method,
            venta.timestamp.strftime("%Y-%m-%d %H:%M")
        ])

    # Crear tabla
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(table)

    # Resumen
    elements.append(Paragraph("Resumen del Día", styles['Heading2']))
    summary_data = [
        ["Total Vendido:", f"${total_vendido:.2f}"],
        ["Productos Vendidos:", str(productos_vendidos)],
        ["Número de Ventas:", str(numero_ventas)]
    ]
    summary_table = Table(summary_data)
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT')
    ]))
    elements.append(summary_table)

    # Generar PDF
    doc.build(elements)

    return FileResponse(
        path=file_path,
        filename="ventas_dia.pdf",
        media_type="application/pdf"
    )
@router.get("/export-sales-by-date")
async def export_sales_by_date(selected_date: str):
    # Convertir la fecha
    date_obj = datetime.strptime(selected_date, "%Y-%m-%d").date()

    # Aquí deberías generar el archivo (Excel o PDF) según la fecha
    filepath = generar_excel_para_fecha(date_obj)  # <-- tu función personalizada

    return FileResponse(path=filepath, filename=f"ventas_{selected_date}.xlsx", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

def generar_excel_para_fecha(fecha: date, db: Session) -> str:
    ventas = db.query(models.Sale).filter(func.date(models.Sale.timestamp) == fecha).all()

    total_vendido = sum(v.total for v in ventas)
    productos_vendidos = sum(v.quantity for v in ventas)
    numero_ventas = len(ventas)

    wb = Workbook()
    ws = wb.active
    ws.title = f"Ventas {fecha}"

    # Cabeceras
    ws.append(["ID", "Producto", "Cantidad", "Total", "Método de Pago", "Fecha"])

    for venta in ventas:
        producto = db.query(models.Product).filter(models.Product.id == venta.product_id).first()
        ws.append([
            venta.id,
            producto.nombre if producto else "Desconocido",
            venta.quantity,
            venta.total,
            venta.payment_method,
            venta.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        ])

    # Espacio + resumen
    ws.append([])
    ws.append(["Resumen del Día"])
    ws.append(["Total Vendido", total_vendido])
    ws.append(["Productos Vendidos", productos_vendidos])
    ws.append(["Número de Ventas", numero_ventas])

    filename = f"ventas_{fecha}.xlsx"
    filepath = os.path.join(".", filename)
    wb.save(filepath)

    return filepath
@router.get("/ticket/{sale_group_id}")
async def generate_ticket(sale_group_id: int, db: Session = Depends(get_db)):
    # Obtener todos los items de venta con el mismo sale_group_id
    ventas = db.query(models.Sale).filter(models.Sale.sale_group_id == sale_group_id).order_by(models.Sale.id).all()
    if not ventas:
        return {"error": "Venta no encontrada"}
    
    main_sale = ventas[0]
    total_general = sum(v.total for v in ventas)
    
    # Crear un PDF con tamaño estándar para tickets (80mm de ancho)
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    doc = SimpleDocTemplate(temp_pdf.name, pagesize=(80*mm, 297*mm),
                          rightMargin=5*mm, leftMargin=5*mm, topMargin=5*mm, bottomMargin=5*mm)
    
    styles = getSampleStyleSheet()
    styles["Title"].fontSize = 12
    styles["Title"].leading = 14
    styles["Title"].alignment = 1
    
    # Definir estilos personalizados
    custom_styles = {
        "TicketSmall": ParagraphStyle(name="TicketSmall", fontSize=9, leading=11),
        "TicketFooter": ParagraphStyle(name="TicketFooter", fontSize=8, leading=10, alignment=1),
        "TicketTotal": ParagraphStyle(name="TicketTotal", fontSize=10, leading=12, alignment=2),
        "TicketPayment": ParagraphStyle(name="TicketPayment", fontSize=10, leading=12),
        "TicketThanks": ParagraphStyle(name="TicketThanks", fontSize=10, leading=12, alignment=1),
        "TicketProduct": ParagraphStyle(name="TicketProduct", fontSize=8, leading=10, wordWrap='CJK')
    }
    
    for style_name, style in custom_styles.items():
        styles.add(style)
    
    elements = []
    
    # Encabezado
    elements.append(Paragraph("Panaderia y minimercado La herradura", styles["Title"]))
    elements.append(Spacer(1, 5*mm))
    
    # Información de la tienda
    elements.append(Paragraph("Dirección: Calle 15 no 8-09", styles["TicketSmall"]))
    elements.append(Paragraph("Tel: 555-1234", styles["TicketSmall"]))
    elements.append(Paragraph("RFC: XXXX000000XX", styles["TicketSmall"]))
    elements.append(Spacer(1, 5*mm))
    
    # Detalles de la venta
    elements.append(Paragraph(f"Fecha: {main_sale.timestamp.strftime('%d/%m/%Y %H:%M')}", styles["TicketSmall"]))
    elements.append(Paragraph(f"Ticket: {main_sale.sale_group_id}", styles["TicketSmall"]))
    elements.append(Spacer(1, 5*mm))
    
    # Tabla de productos
    data = [["Producto", "Cant", "Precio", "Total"]]
    
    for venta in ventas:
        producto = db.query(models.Product).filter(models.Product.id == venta.product_id).first()
        nombre_producto = producto.nombre if producto else "Desconocido"
        precio_producto = producto.precio if producto else 0.00  # Usamos el precio del producto
        
        if len(nombre_producto) > 25:
            nombre_producto = nombre_producto[:22] + "..."
        
        data.append([
            Paragraph(nombre_producto, styles["TicketProduct"]),
            str(venta.quantity),
            f"${precio_producto:.2f}",  # Mostramos el precio unitario del producto
            f"${venta.total:.2f}"  # Mostramos el total de la línea
        ])
    
    # Anchos de columna en mm
    col_widths = [40*mm, 10*mm, 15*mm, 15*mm]
    
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('FONT', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.black),
        ('BOX', (0,0), (-1,-1), 0.25, colors.black),
        ('LEADING', (0,0), (-1,-1), 9),
        ('PADDING', (0,0), (-1,-1), (1,1,1,1)),
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 5*mm))
    
    # Totales
    elements.append(Paragraph(f"Total: ${total_general:.2f}", styles["TicketTotal"]))
    elements.append(Spacer(1, 5*mm))
    
    # Método de pago
    elements.append(Paragraph(f"Pago: {main_sale.payment_method.upper()}", styles["TicketPayment"]))
    elements.append(Spacer(1, 5*mm))
    
    # Pie de página
    elements.append(Paragraph("¡Gracias por su compra!", styles["TicketThanks"]))
    elements.append(Spacer(1, 3*mm))
    elements.append(Paragraph("Sistema de Ventas Wellmade v1.0", styles["TicketFooter"]))
    
    doc.build(elements)
    temp_pdf.close()
    
    return FileResponse(temp_pdf.name, filename=f"ticket_{sale_group_id}.pdf")

@router.get("/thermal-ticket/{sale_group_id}", response_class=HTMLResponse)
async def thermal_ticket(sale_group_id: int, db: Session = Depends(get_db)):
    # Obtener todos los items de venta con el mismo sale_group_id
    ventas = db.query(models.Sale).filter(models.Sale.sale_group_id == sale_group_id).order_by(models.Sale.id).all()
    
    if not ventas:
        return "<h1>Venta no encontrada</h1>"
    
    # La venta principal (usamos la primera para datos generales)
    main_sale = ventas[0]
    
    # Calcular totales
    subtotal = sum(v.subtotal for v in ventas)
    iva_total = sum(v.iva for v in ventas)
    total_general = sum(v.total for v in ventas)
    
    # Generar filas de productos para la tabla (versión para 80mm)
    productos_html = ""
    for venta in ventas:
        producto = db.query(models.Product).filter(models.Product.id == venta.product_id).first()
        nombre_producto = producto.nombre if producto else 'Desconocido'
        # Permitir nombres más largos para 80mm
        if len(nombre_producto) > 30:
            nombre_producto = nombre_producto[:27] + "..."
        
        # Calcular precio unitario (subtotal / cantidad)
        precio_unitario = venta.subtotal / venta.quantity if venta.quantity > 0 else 0
            
        productos_html += f"""
        <tr>
            <td style="width: 45%; word-wrap: break-word;">{nombre_producto}</td>
            <td style="width: 10%; text-align: center;">{venta.quantity}</td>
            <td style="width: 10%; text-align: right;">${precio_unitario:.2f}</td>
            <td style="width: 10%; text-align: right;">${venta.total:.2f}</td>
        </tr>
        """
    
    # Sección de domicilios mejorada
    domicilio_html = ""
    if hasattr(main_sale, 'delivery') and main_sale.delivery:
        domicilio_html = f"""
        <div class="delivery-section">
            <div class="section-title">🚚 PEDIDO PARA DOMICILIO</div>
            <div class="info-line"><span>Cliente:</span> <span class="bold">{getattr(main_sale, 'customer_name', 'No especificado')}</span></div>
            <div class="info-line"><span>Dirección:</span> <span>{getattr(main_sale, 'delivery_address', 'No especificado')}</span></div>
            <div class="info-line"><span>Teléfono:</span> <span class="bold">{getattr(main_sale, 'customer_phone', 'No especificado')}</span></div>
            <div class="info-line"><span>Notas:</span> <span>{getattr(main_sale, 'delivery_notes', 'Ninguna')}</span></div>
        </div>
        """
    else:
        domicilio_html = """
        <div class="delivery-info">
            <div class="section-title">📞 ¿NECESITAS DOMICILIO?</div>
            <div class="info-line center">¡Llámanos al 312-333-9424!</div>
            <div class="info-line center">Horario: 9am - 8pm</div>
        </div>
        """
    
    # Generar HTML completo optimizado para impresora térmica de 80mm
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Ticket de Venta</title>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: 'Arial Narrow', Arial, sans-serif;
                font-size: 14px;
                width: 80mm;
                margin: 0;
                padding: 2mm;
            }}
            .header {{
                text-align: center;
                font-weight: bold;
                font-size: 16px;
                margin-bottom: 3mm;
                border-bottom: 1px dashed #000;
                padding-bottom: 2mm;
            }}
            .info {{
                margin-bottom: 2mm;
                line-height: 1.2;
            }}
            .info-line {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 1mm;
            }}
            .center {{
                text-align: center;
                justify-content: center;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 3mm 0;
                table-layout: fixed;
            }}
            th {{
                text-align: left;
                border-bottom: 2px solid #000;
                padding: 1mm 0;
                font-weight: bold;
            }}
            td {{
                padding: 1mm 0;
                vertical-align: top;
                border-bottom: 1px dotted #ccc;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .right {{
                text-align: right;
            }}
            .total {{
                font-weight: bold;
                margin-top: 3mm;
            }}
            .footer {{
                text-align: center;
                margin-top: 4mm;
                font-size: 12px;
                border-top: 1px dashed #000;
                padding-top: 2mm;
            }}
            .summary {{
                margin-top: 3mm;
                border-top: 2px solid #000;
                padding-top: 2mm;
            }}
            .nowrap {{
                white-space: nowrap;
            }}
            .section-title {{
                font-weight: bold;
                margin: 3mm 0 2mm 0;
                text-align: center;
                background-color: #f0f0f0;
                padding: 1mm;
            }}
            .delivery-section {{
                margin: 3mm 0;
                padding: 2mm;
                border: 2px solid #000;
                border-radius: 2mm;
                background-color: #fff8e1;
            }}
            .delivery-info {{
                margin: 3mm 0;
                padding: 2mm;
                border: 1px dashed #000;
                border-radius: 2mm;
            }}
            .bold {{
                font-weight: bold;
            }}
            .qr-code {{
                text-align: center;
                margin: 3mm 0;
            }}
        </style>
    </head>
    <body>
        <div class="header">LA CAVA DE LOS QUESOS</div>
        <div class="info center">Cra 11 No 66-23 - Tel: 3123339424</div>
        <div class="info center">RFC: 51771188-9</div>
        
        <div class="info-line">
            <span class="bold">Fecha:</span>
            <span>{main_sale.timestamp.strftime('%d/%m/%Y %H:%M')}</span>
        </div>
        <div class="info-line">
            <span class="bold">Ticket #:</span>
            <span>{main_sale.sale_group_id}</span>
        </div>
        
        {domicilio_html}
        
        <table>
            <thead>
                <tr>
                    <th style="width: 45%;">Producto</th>
                    <th style="width: 15%; text-align: center;">Cant</th>
                    <th style="width: 20%; text-align: right;">P.Unit</th>
                    <th style="width: 20%; text-align: right;">Total</th>
                </tr>
            </thead>
            <tbody>
                {productos_html}
            </tbody>
        </table>
        
        <div class="summary">
            <div class="info-line">
                <span>Subtotal:</span>
                <span>${subtotal:.2f}</span>
            </div>
            <div class="info-line">
                <span>IVA:</span>
                <span>${iva_total:.2f}</span>
            </div>
            <div class="info-line total">
                <span>TOTAL:</span>
                <span>${total_general:.2f}</span>
            </div>
        </div>
        
        <div class="info-line">
            <span class="bold">Método de pago:</span>
            <span>{main_sale.payment_method.upper()}</span>
        </div>
        <div class="info-line">
            <span class="bold">Atendió:</span>
            <span>{getattr(main_sale, 'employee_name', 'Sistema')}</span>
        </div>
        
        <div class="qr-code">
            <!-- Espacio para código QR si es necesario -->
            <!-- <img src="qr_code.png" width="80" height="80"> -->
        </div>
        
        <div class="footer">
            <div class="bold">¡Gracias por su compra!</div>
            <div>Para domicilios llama al:</div>
            <div class="bold">312-333-9424</div>
            <div>Sistema Wellmade</div>
        </div>
        
        <script>
            // Imprimir automáticamente al cargar
            window.onload = function() {{
                setTimeout(function() {{
                    window.print();
                    setTimeout(function() {{
                        window.close();
                    }}, 100);
                }}, 100);
            }};
        </script>
    </body>
    </html>
    """
    
    return html_content

@router.get("/serial-ports")
def list_serial_ports():
    """Lista los puertos seriales disponibles con más información"""
    ports = serial.tools.list_ports.comports()
    port_info = []
    
    if not ports:
        # Intenta forzar la detección en sistemas Windows
        try:
            from serial.tools.list_ports_windows import comports
            ports = comports()
        except:
            pass
    
    for port in ports:
        try:
            port_info.append({
                "device": port.device,
                "description": port.description,
                "hwid": port.hwid,
                "manufacturer": port.manufacturer if port.manufacturer else "Desconocido",
                "serial_number": getattr(port, 'serial_number', 'N/A')
            })
        except Exception as e:
            print(f"Error procesando puerto {port}: {str(e)}")
    
    # Si no hay puertos, intenta listar manualmente (especialmente en Windows)
    if not port_info:
        import sys
        if sys.platform == 'win32':
            # Intenta listar puertos COM1-COM20 en Windows
            for i in range(1, 21):
                port_name = f"COM{i}"
                port_info.append({
                    "device": port_name,
                    "description": "Puerto serie (detección manual)",
                    "hwid": "N/A",
                    "manufacturer": "Desconocido",
                    "serial_number": "N/A"
                })
    
    return {"ports": port_info}

@router.post("/connect-scale")
def connect_to_scale(port: str, baudrate: int = 9600):
    """Conecta a la balanza"""
    try:
        # Cierra la conexión si ya existe
        if hasattr(connect_to_scale, 'ser') and connect_to_scale.ser:
            connect_to_scale.ser.close()
        
        # Abre nueva conexión
        connect_to_scale.ser = serial.Serial(port, baudrate, timeout=1)
        return {"status": "connected", "port": port}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/read-scale")
def read_scale():
    """Lee el peso actual de la balanza"""
    if not hasattr(connect_to_scale, 'ser') or not connect_to_scale.ser:
        raise HTTPException(status_code=400, detail="Balanza no conectada")
    
    try:
        # Lee datos de la balanza (ajusta según el protocolo de tu balanza)
        line = connect_to_scale.ser.readline().decode('utf-8').strip()
        weight = float(line)  # Ajusta el parsing según el formato de tu balanza
        return {"weight": weight}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/disconnect-scale")
def disconnect_scale():
    """Desconecta la balanza"""
    try:
        if hasattr(connect_to_scale, 'ser') and connect_to_scale.ser:
            connect_to_scale.ser.close()
            del connect_to_scale.ser
        return {"status": "disconnected"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))