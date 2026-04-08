from django.contrib import admin
from .models import Categoria, Producto, Cliente, Proveedores, Venta, Detalle_venta, Compra, Insumo, Detalle_compra, Promociones, Desposte

import csv
from django import forms
from django.shortcuts import render
from django.contrib import messages
import csv
from io import TextIOWrapper
from datetime import datetime
admin.site.site_header = 'La Chancheria'
admin.site.site_title = 'La Chancheria'
admin.site.index_title = 'Archivos'

class detalle_venta_Inline(admin.TabularInline):
    model = Detalle_venta

class ventaAdmin(admin.ModelAdmin):
    list_display = ('Id_venta', 'Id_cliente')
    inlines = [detalle_venta_Inline]

class detalle_compra_Inline(admin.TabularInline):
    model = Detalle_compra

class compraAdmin(admin.ModelAdmin):
    list_display = ('Id_compra', 'Id_proveedor')
    inlines = [detalle_compra_Inline]



class CsvImportForm(forms.Form):
    csv_file = forms.FileField()

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('Id_producto', 'Id_categoria', 'Corte', 'stock_kg', 'Precio_kilo')

   

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('import-csv/', self.import_csv)
        ]
        return custom_urls + urls

    def import_csv(self, request):
        if request.method == "POST":
            form = CsvImportForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = TextIOWrapper(request.FILES["csv_file"].file, encoding='utf-8')
                reader = csv.DictReader(csv_file)

                for row in reader:
                    try:
                        categoria_nombre = row["Id_Categoria"].strip()
                        categoria = Categoria.objects.get(nombre=categoria_nombre)

                        producto = Producto.objects.create(
                            Id_categoria=categoria,
                            Corte=row["Corte"],
                            Precio_kilo=float(row["Precio_Kilo"].replace("$", "").replace(".", "").replace(",", ".")),
                            precio_mayor_x_kg=float(row["recio_Mayor_X5Kg"].replace("$", "").replace(".", "").replace(",", ".")),
                            en_promocion=row["En_Promocion"].strip().upper() in ["VERDADERO", "TRUE", "1"],
                            cantidad=int(row["stock_kg"]),
                            fecha_ingreso_elaboracion=datetime.strptime(row["a_Ingreso/Elaborac"], "%Y-%m-%d %H:%M:%S"),
                            fecha_vencimiento=datetime.strptime(row["Fecha_Vencimiento"], "%Y-%m-%d").date(),
                            detalle=row["Detalle"],
                        )
                    except Exception as e:
                        self.message_user(request, f"Error en fila: {row} - {str(e)}", messages.ERROR)

                self.message_user(request, "Archivo CSV importado correctamente")
                return render(request, "admin/csv_upload_success.html")

        form = CsvImportForm()
        payload = {"form": form}
        return render(request, "admin/csv_form.html", payload)
admin.site.register(Venta, ventaAdmin)
admin.site.register(Compra, compraAdmin)
admin.site.register(Categoria)

admin.site.register(Cliente)
admin.site.register(Proveedores)
admin.site.register(Detalle_venta)
admin.site.register(Insumo)
admin.site.register(Detalle_compra)
admin.site.register(Promociones)
admin.site.register(Desposte)

