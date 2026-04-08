"""
Migración de datos:
1. Convierte stock_kg de kilogramos → gramos (×1000) para productos con unidad_medida = 'KG'.
2. Mapea valores antiguos de Categoria.unidades_permitidas a los nuevos (UNIDAD_KG / UNIDAD_PAQUETE).
3. Mapea valores antiguos de Producto.unidad_medida a los nuevos (KG / UNIDAD / PAQUETE).
"""

from decimal import Decimal
from django.db import migrations


def convertir_datos_forward(apps, schema_editor):
    Categoria = apps.get_model('miAplicacion', 'Categoria')
    Producto = apps.get_model('miAplicacion', 'Producto')

    # ── 1. Mapear unidades_permitidas antiguas → nuevas ──
    mapeo_categoria = {
        'UNIDAD': 'UNIDAD_KG',
        'BOLSA': 'UNIDAD_PAQUETE',
        'LTS': 'UNIDAD_KG',
        'UNIDAD_LTS': 'UNIDAD_KG',
        'VOLUMEN': 'UNIDAD_KG',
        'EMPAQUETADO': 'UNIDAD_PAQUETE',
    }

    for cat in Categoria.objects.all():
        nuevo_valor = mapeo_categoria.get(cat.unidades_permitidas, cat.unidades_permitidas)
        if nuevo_valor != cat.unidades_permitidas:
            cat.unidades_permitidas = nuevo_valor
            cat.save(update_fields=['unidades_permitidas'])

    # ── 2. Mapear unidad_medida antigua de Producto → nueva ──
    mapeo_unidad = {
        'BOLSA': 'PAQUETE',
        'LTS': 'KG',
        'GR': 'KG',
        'DOCENA': 'PAQUETE',
        'MEDIA_RES': 'KG',
    }

    for prod in Producto.objects.all():
        unidad_vieja = prod.unidad_medida
        nueva_unidad = mapeo_unidad.get(unidad_vieja, unidad_vieja)

        if nueva_unidad != unidad_vieja:
            prod.unidad_medida = nueva_unidad

        # ── 3. Convertir stock de KG a gramos (×1000) ──
        # Solo si la unidad final es KG, multiplicamos el stock por 1000
        if prod.unidad_medida == 'KG':
            prod.stock_kg = (Decimal(str(prod.stock_kg or 0)) * Decimal('1000')).quantize(Decimal('0.01'))

        prod.save(update_fields=['unidad_medida', 'stock_kg'])


def convertir_datos_reverse(apps, schema_editor):
    """
    Reversa: convierte gramos → kg (÷1000) para productos KG.
    No intenta restaurar los mapeos originales de categoría/unidad
    ya que esa info se pierde.
    """
    Producto = apps.get_model('miAplicacion', 'Producto')

    for prod in Producto.objects.filter(unidad_medida='KG'):
        prod.stock_kg = (Decimal(str(prod.stock_kg or 0)) / Decimal('1000')).quantize(Decimal('0.01'))
        prod.save(update_fields=['stock_kg'])


class Migration(migrations.Migration):

    dependencies = [
        ('miAplicacion', '0022_unificar_unidades_kg_gramos'),
    ]

    operations = [
        migrations.RunPython(convertir_datos_forward, convertir_datos_reverse),
    ]
