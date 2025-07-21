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
    
    # Generar filas de productos para la tabla (versión compacta)
    productos_html = ""
    for venta in ventas:
        producto = db.query(models.Product).filter(models.Product.id == venta.product_id).first()
        nombre_producto = producto.nombre if producto else 'Desconocido'
        # Acortar nombres de productos para 58mm
        if len(nombre_producto) > 20:
            nombre_producto = nombre_producto[:17] + "..."
            
        productos_html += f"""
        <tr>
            <td>{nombre_producto}</td>
            <td class="right">{venta.quantity}</td>
            <td class="right">${venta.total:.2f}</td>
        </tr>
        """
    
    # Generar HTML completo optimizado para 58mm
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Ticket de Venta</title>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: 'Arial Narrow', Arial, sans-serif;
                font-size: 10px;
                width: 58mm;
                margin: 0;
                padding: 2px;
            }}
            .header {{
                text-align: center;
                font-weight: bold;
                font-size: 11px;
                margin-bottom: 5px;
            }}
            .info {{
                margin-bottom: 3px;
                line-height: 1.2;
            }}
            .info-line {{
                display: flex;
                justify-content: space-between;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 5px 0;
            }}
            th {{
                text-align: left;
                border-bottom: 1px solid #000;
                padding: 1px 0;
                font-weight: bold;
            }}
            td {{
                padding: 1px 0;
                vertical-align: top;
            }}
            .right {{
                text-align: right;
            }}
            .total {{
                font-weight: bold;
                margin-top: 5px;
            }}
            .footer {{
                text-align: center;
                margin-top: 10px;
                font-size: 9px;
            }}
            .summary {{
                margin-top: 5px;
                border-top: 1px solid #000;
                padding-top: 3px;
            }}
            .nowrap {{
                white-space: nowrap;
            }}
        </style>
    </head>
    <body>
        <div class="header">Panaderia y minimercado La herradura</div>
        <div class="info">Calle 15 no 8-09</div>
        <div class="info-line">
            <span>Tel: XXXXX</span>
            <span>RFC: XXXX000000XX</span>
        </div>
        
        <div class="info-line">
            <span>Fecha: {main_sale.timestamp.strftime('%d/%m/%Y %H:%M')}</span>
            <span>Ticket: {main_sale.sale_group_id}</span>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>Producto</th>
                    <th class="right nowrap">Cant</th>
                    <th class="right nowrap">Total</th>
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
        
        <div class="info">Pago: {main_sale.payment_method.upper()}</div>
        
        <div class="footer">
            ¡Gracias por su compra!<br>
            Sistema Wellmade
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