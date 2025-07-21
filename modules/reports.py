import io
import pandas as pd
from reportlab.pdfgen import canvas
from fastapi.responses import StreamingResponse
from modules.billing import get_sales
import openpyxl  # asegúrate de que esté instalado

def export_sales_excel():
    sales = get_sales()
    df = pd.DataFrame(sales)
    output = io.BytesIO()

    writer = pd.ExcelWriter(output, engine='openpyxl')
    df.to_excel(writer, index=False, sheet_name="Ventas")
    writer.close()

    output.seek(0)
    return StreamingResponse(
        output,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={"Content-Disposition": "attachment; filename=ventas.xlsx"}
    )

def export_sales_pdf():
    sales = get_sales()
    output = io.BytesIO()
    p = canvas.Canvas(output)
    p.setFont("Helvetica", 12)
    p.drawString(100, 800, "Historial de Ventas")

    y = 770
    for sale in sales:
        line = f"Producto: {sale['product']} | Cantidad: {sale['quantity']} | Total: ${sale['total']}"
        p.drawString(100, y, line)
        y -= 20
        if y < 50:
            p.showPage()
            y = 800

    p.save()
    output.seek(0)
    return StreamingResponse(output, media_type="application/pdf",
                             headers={"Content-Disposition": "attachment; filename=ventas.pdf"})