from django.db import models, transaction
from django.core.exceptions import ValidationError
from decimal import Decimal, ROUND_HALF_UP
from django.db.models.signals import post_save
from django.dispatch import receiver

class Proveedores(models.Model):
    Id_proveedor = models.AutoField(primary_key=True)
    Nombre = models.CharField(max_length=100)
    Telefono = models.CharField(max_length=15, blank=True, null=True)
    Direccion = models.CharField(max_length=255, blank=True, null=True)
    Email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return self.Nombre
class Compra(models.Model):
    TIPO_CHOICES = [
        ('CARNE', 'Carne'),
        ('INSUMO', 'Insumo'),
    ]
    ESTADO_CHOICES = [
        ('completado', 'Completado'),
        ('pendiente', 'Pendiente'),
    ]
    FORMA_PAGO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia'),
        ('tarjeta', 'Tarjeta'),
        ('nota_credito', 'Nota de Crédito'),
    ]
    Id_compra = models.AutoField(primary_key=True)
    Id_proveedor = models.ForeignKey(Proveedores, on_delete=models.CASCADE)
    Tipo_compra = models.CharField(max_length=10, choices=TIPO_CHOICES, default='CARNE')
    Estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    Forma_pago = models.CharField(max_length=20, choices=FORMA_PAGO_CHOICES, default='efectivo')
    Precio_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    monto_pagado = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Monto ya pagado al proveedor por esta compra'
    )
    Fecha_compra = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.Id_compra} - {self.Tipo_compra}"

    @property
    def saldo_pendiente(self):
        """Monto que aún se debe al proveedor por esta compra"""
        return max(Decimal('0'), Decimal(str(self.Precio_total)) - Decimal(str(self.monto_pagado)))

    @property
    def esta_pagada(self):
        """Indica si la compra está totalmente pagada"""
        return self.monto_pagado >= self.Precio_total


class Categoria(models.Model):
    UNIDADES_PERMITIDAS_CHOICES = [
        ('UNIDAD_KG', 'Unidades y Kilogramos'),
        ('UNIDAD_PAQUETE', 'Unidades y Paquetes'),
    ]
    
    Id_categoria = models.AutoField(primary_key=True)
    Categoria = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    Cantidad = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unidades_permitidas = models.CharField(
        max_length=20,
        choices=UNIDADES_PERMITIDAS_CHOICES,
        default='UNIDAD_KG',
        help_text='Define qué unidades de medida se pueden usar para productos de esta categoría'
    )

    def __str__(self):
        return self.Categoria
    
    def validar_unidad_medida(self, unidad_medida):
        """Valida si una unidad de medida es permitida para esta categoría"""
        mapeo = {
            'UNIDAD_KG': ['UNIDAD', 'KG'],
            'UNIDAD_PAQUETE': ['UNIDAD', 'PAQUETE'],
        }
        
        unidades_validas = mapeo.get(self.unidades_permitidas, [])
        return unidad_medida in unidades_validas
    
    def get_unidades_disponibles(self):
        """Retorna las unidades de medida disponibles para esta categoría"""
        from .models import Producto  # import aquí para evitar circular import
        
        mapeo = {
            'UNIDAD_KG': ['UNIDAD', 'KG'],
            'UNIDAD_PAQUETE': ['UNIDAD', 'PAQUETE'],
        }
        
        codigos_permitidos = mapeo.get(self.unidades_permitidas, [])
        # Filtrar las opciones del modelo Producto
        return [(codigo, display) for codigo, display in Producto.UNIDAD_MEDIDA_CHOICES if codigo in codigos_permitidos]


class Insumo(models.Model):
    UNIDAD_MEDIDA_CHOICES = [
        ('KG', 'Kilogramo'),
        ('GR', 'Gramos'),
        ('MT', 'Metros'),
        ('ML', 'Mililitros'),
        ('LTS', 'Litros'),
        ('UNIDAD', 'Unidad'),
        ('BOLSA', 'Bolsa'),
        ('PAQUETE', 'Paquete'),
        ('DOCENA', 'Docena'),
    ]
    
    Id_insumo = models.AutoField(primary_key=True)
    # nombre del insumo/producto
    nombre = models.CharField(max_length=100)   # Removido unique=True para permitir edición
    # stock general (entero o unidades). Si querés kilos, luego cambiamos a DecimalField.
    Cantidad = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    Precio = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    Id_proveedor = models.ForeignKey(Proveedores, on_delete=models.CASCADE, null=True, blank=True)
    fecha_ingreso = models.DateTimeField(auto_now_add=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)

    # relacion opcional a Categoria (para carnes: vaca, cerdo...)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True)

    # tipo: carne vs insumo general
    TIPO_CHOICES = [
        ('insumo', 'Insumo'),
        ('carne', 'Carne'),
    ]
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='insumo')
    
    # Unidad de medida (tripas en metros, condimentos en gramos, etc)
    unidad_medida = models.CharField(
        max_length=20,
        choices=UNIDAD_MEDIDA_CHOICES,
        default='KG',
        help_text='Unidad de medida para este insumo'
    )

    def __str__(self):
        return self.nombre

    @property
    def stock_bajo(self):
        """Retorna True si el stock es menor a 100 kg"""
        return (self.Cantidad or 0) < 100


class LoteCarne(models.Model):
    """
    Modelo para manejar lotes de carne (medias res, desposte, merma).
    Cada lote referencia un Insumo de tipo 'carne'.
    """
    Id_lote = models.AutoField(primary_key=True)
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE, related_name='lotes')
    cantidad_medias_res = models.IntegerField(default=0)   # cuántas medias res llegaron (unidades)
    despostadas = models.IntegerField(default=0)           # cuántas medias res ya se despostaron
    merma_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # kg o porcentaje según convengas
    fecha_llegada = models.DateTimeField(auto_now_add=True)
    observaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Lote {self.Id_lote} - {self.insumo.nombre} ({self.cantidad_medias_res})"

class Detalle_compra(models.Model):
    Id_detalle = models.AutoField(primary_key=True)
    Id_compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name='detalles')
    Id_insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE, null=True, blank=True)
    Id_categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, null=True, blank=True)
    Cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    Precio_total = models.DecimalField(max_digits=12, decimal_places=2)
    lote = models.ForeignKey(LoteCarne, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        if self.Id_categoria:
            return f"{self.Id_compra} - {self.Id_categoria}"
        return f"{self.Id_compra} - {self.Id_insumo}"
class Producto(models.Model):
    UNIDAD_MEDIDA_CHOICES = [
        ('KG', 'Kilogramo'),
        ('UNIDAD', 'Unidad'),
        ('PAQUETE', 'Paquete'),
    ]
    
    # Categorías que requieren el campo "Corte"
    CATEGORIAS_CON_CORTES = ['BROSA', 'TERNERA', 'POLLO', 'PESCADO', 'CHACINADOS']
    
    Id_producto = models.AutoField(primary_key=True)
    Id_categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)
    
    # Nombre general del producto (siempre visible)
    Nombre = models.CharField(max_length=100, blank=True, null=True, help_text='Nombre general del producto')
    
    # Corte específico (solo para carnes y chacinados)
    Corte = models.CharField(max_length=100, blank=True, null=True, help_text='Corte específico (para carnes/chacinados)')
    
    Precio_kilo = models.DecimalField(max_digits=10, decimal_places=2)
    precio_mayor_x_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text='Opcional: precio para ventas mayoristas. Si no se define, no se aplica descuento.')
    en_promocion = models.BooleanField(default=False)
    
    # Unidad de medida principal para ventas e inventario
    unidad_medida = models.CharField(
        max_length=20,
        choices=UNIDAD_MEDIDA_CHOICES,
        default='KG',
        help_text='Unidad de medida para ventas e inventario'
    )

    # Stock interno en GRAMOS para productos con unidad KG.
    # Para UNIDAD y PAQUETE se almacena la cantidad directamente.
    stock_kg = models.DecimalField(
        max_digits=12, 
        decimal_places=3, 
        default=Decimal('0.000'),
        help_text='Stock interno: en gramos si la unidad es KG, cantidad directa para UNIDAD/PAQUETE'
    )

    fecha_ingreso_elaboracion = models.DateTimeField(blank=True, null=True)
    fecha_vencimiento = models.DateField(blank=True, null=True, help_text='Opcional: solo para productos perecederos')
    detalle = models.TextField(blank=True, null=True)

    def __str__(self):
        # Mostrar Corte si existe, sino Nombre
        nombre_display = self.Corte if self.Corte else self.Nombre
        return f"{nombre_display} ({self.get_unidad_medida_display()})"
    
    def requiere_corte(self):
        """Verifica si la categoría requiere especificar corte"""
        if self.Id_categoria:
            return self.Id_categoria.Categoria.upper() in self.CATEGORIAS_CON_CORTES
        return False
    
    def clean(self):
        """Validación personalizada del modelo"""
        from django.core.exceptions import ValidationError
        
        # Validar que las categorías de carne tengan corte especificado
        if self.requiere_corte() and not self.Corte:
            raise ValidationError({
                'Corte': f'Los productos de la categoría "{self.Id_categoria.Categoria}" deben especificar un corte.'
            })
        
        # Validar que la unidad de medida sea compatible con la categoría
        if self.Id_categoria and self.unidad_medida:
            if not self.Id_categoria.validar_unidad_medida(self.unidad_medida):
                unidades_permitidas = self.Id_categoria.get_unidades_disponibles()
                nombres_unidades = [display for _, display in unidades_permitidas]
                raise ValidationError({
                    'unidad_medida': f'La categoría "{self.Id_categoria.Categoria}" solo permite las siguientes unidades: {", ".join(nombres_unidades)}. No se puede usar "{self.get_unidad_medida_display()}".'
                })
    
    def save(self, *args, **kwargs):
        """Override del save para ejecutar validaciones.
        
        Si se pasa update_fields (ej. solo actualizar stock), se salta
        full_clean() para evitar disparar validaciones no relacionadas.
        """
        if not kwargs.get('update_fields'):
            self.full_clean()  # Ejecuta clean() solo en guardados completos
        super().save(*args, **kwargs)
    
    def stock_formateado(self):
        """Retorna el stock con su unidad de medida (convierte gramos a kg para display)"""
        return f"{self.stock_display} {self.get_unidad_medida_display()}"
    
    def precio_formateado(self):
        """Retorna el precio con su unidad de medida"""
        return f"${self.Precio_kilo} / {self.get_unidad_medida_display()}"

    # ─── Conversión interna gramos ↔ kilogramos ───────────────────

    @property
    def stock_display(self):
        """
        Stock para mostrar al usuario:
        - KG: convierte gramos internos → kilogramos (divide entre 1000), 3 decimales
        - UNIDAD / PAQUETE: retorna entero (sin decimales)
        """
        stock = Decimal(str(self.stock_kg or 0))
        if self.unidad_medida == 'KG':
            return (stock / Decimal('1000')).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        return stock.quantize(Decimal('1'))

    @staticmethod
    def kg_a_gramos(valor_kg):
        """Convierte un valor en kilogramos a gramos (×1000)"""
        return (Decimal(str(valor_kg)) * Decimal('1000')).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)

    @staticmethod
    def gramos_a_kg(valor_gr):
        """Convierte un valor en gramos a kilogramos (÷1000)"""
        return (Decimal(str(valor_gr)) / Decimal('1000')).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)

class Cliente(models.Model):
    Id_cliente = models.AutoField(primary_key=True)
    Nombre = models.CharField(max_length=100)
    Telefono = models.CharField(max_length=15, blank=True, null=True)
    Direccion = models.CharField(max_length=255, blank=True, null=True)
    Email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return self.Nombre


class Venta(models.Model):
    Id_venta = models.AutoField(primary_key=True)
    Id_cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    Tipo_venta = models.CharField(max_length=50, choices=[('mayor', 'Mayor'), ('menor', 'Menor'), ('promocion', 'Promocion')])
    Precio = models.DecimalField(max_digits=10, decimal_places=2)
    Forma_pago = models.CharField(max_length=50, choices=[('efectivo', 'Efectivo'), ('tarjeta', 'Tarjeta'), ('transferencia', 'Transferencia')])
    Estado = models.CharField(max_length=50, choices=[('pendiente', 'Pendiente'), ('completada', 'Completada'), ('cancelada', 'Cancelada')])
    Fecha_venta = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.Tipo_venta + " - " + str(self.Fecha_venta)

class Detalle_venta(models.Model):
    Id_detalle = models.AutoField(primary_key=True)
    Id_venta = models.ForeignKey(Venta, on_delete=models.CASCADE)
    Id_producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    Cantidad = models.DecimalField(max_digits=10, decimal_places=3)
    Precio_total = models.DecimalField(max_digits=10, decimal_places=2)


    def __str__(self):
        return str(self.Id_venta) + " - " + str(self.Id_producto)



class Promociones(models.Model):
    TIPO_PROMOCION_CHOICES = [
        ('rebaja_unidad', 'Rebaja por Unidad'),
        ('mayorista', 'Mayorista'),
        ('descuento_porcentaje', 'Descuento Porcentaje'),
        ('2x1', '2x1'),
        ('oferta_especial', 'Oferta Especial'),
    ]
    
    ESTADO_CHOICES = [
        ('activa', 'Activa'),
        ('inactiva', 'Inactiva'),
        ('programada', 'Programada'),
        ('vencida', 'Vencida'),
    ]
    
    Id_promocion = models.AutoField(primary_key=True)
    Id_producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='promociones')
    tipo_promocion = models.CharField(max_length=30, choices=TIPO_PROMOCION_CHOICES, default='rebaja_unidad')
    Precio_oferta = models.DecimalField(max_digits=10, decimal_places=2)
    descuento_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Porcentaje de descuento (0-100)")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='activa')
    Fecha_inicio = models.DateTimeField()
    Fecha_fin = models.DateTimeField()
    descripcion = models.TextField(blank=True, null=True, help_text="Descripción de la promoción")
    cantidad_minima = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Cantidad mínima para aplicar promoción (kg)")
    
    class Meta:
        verbose_name = 'Promoción'
        verbose_name_plural = 'Promociones'
        ordering = ['-Fecha_inicio']
    
    def __str__(self):
        return f"{self.Id_producto.Corte} - {self.get_tipo_promocion_display()} - ${self.Precio_oferta}"
    
    def esta_activa(self):
        """Verifica si la promoción está actualmente activa"""
        from django.utils import timezone
        now = timezone.now()
        return (
            self.estado == 'activa' and 
            self.Fecha_inicio <= now <= self.Fecha_fin
        )
    
    def dias_restantes(self):
        """Calcula los días restantes de la promoción"""
        from django.utils import timezone
        if self.Fecha_fin > timezone.now():
            delta = self.Fecha_fin - timezone.now()
            return delta.days
        return 0
    
    def porcentaje_descuento_calculado(self):
        """Calcula el porcentaje de descuento respecto al precio normal"""
        if self.Id_producto and self.Id_producto.Precio_kilo:
            precio_normal = self.Id_producto.Precio_kilo
            descuento = precio_normal - self.Precio_oferta
            return (descuento / precio_normal) * 100
        return 0

class Desposte(models.Model):
    Id_desposte = models.AutoField(primary_key=True)
    Id_insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE, null=True, blank=True, help_text='Insumo de carne a despostar')
    Fecha = models.DateTimeField(auto_now_add=True)
    Unidades = models.PositiveIntegerField(default=1)           # cuántas medias res / pollos despostás
    Peso_inicial = models.DecimalField(max_digits=10, decimal_places=2)  # Peso total en kg (de las unidades)
    Merma = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"Desposte {self.Id_desposte} - {self.Id_insumo}"
    
class CorteDesposte(models.Model):
    Id_corte = models.AutoField(primary_key=True)
    Id_desposte = models.ForeignKey(Desposte, on_delete=models.CASCADE, related_name='cortes')
    Id_producto = models.ForeignKey(Producto, on_delete=models.CASCADE)  # Ej: Costilla, Falda, etc.
    Peso = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.Id_producto} - {self.Peso} kg"
  

# ===========================
# MODELOS: Receta, RecetaItem,
# Produccion, ProduccionDetalle
# ===========================


class Receta(models.Model):
    """
    Receta que produce un Producto final a partir de Insumos/Productos.
    - producto_final: FK a Producto (el producto que se obtiene al finalizar la receta).
    - rendimiento_por_lote: cantidad (kg o unidades) que produce 1 'lote base' de la receta.
    """
    Id_receta = models.AutoField(primary_key=True)
    producto_final = models.ForeignKey('Producto', on_delete=models.CASCADE, related_name='recetas')
    nombre = models.CharField(max_length=200)
    rendimiento_por_lote = models.DecimalField(max_digits=10, decimal_places=2,
                                              help_text="Cantidad (kg o unidades) que produce el lote base")
    notas = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} -> {self.producto_final.Corte}"

    def clean(self):
        if self.rendimiento_por_lote <= 0:
            raise ValidationError("El rendimiento por lote debe ser mayor a 0.")


class RecetaItem(models.Model):
    """
    Ingredientes de la receta. Puede referenciar un Insumo (ej: condimentos, grasa, tripa)
    o un Producto (ej: algún corte específico que ya figuraba en Producto).
    Se valida que al menos uno de los dos FK no sea nulo.
    cantidad_por_rendimiento: cantidad necesaria para 1 lote base (mismo unidad que rendimiento_por_lote).
    tipo_item: ayuda semántica (insumo / producto).
    """
    Id_receta_item = models.AutoField(primary_key=True)
    receta = models.ForeignKey(Receta, on_delete=models.CASCADE, related_name='items')
    insumo = models.ForeignKey('Insumo', on_delete=models.CASCADE, null=True, blank=True,
                               related_name='receta_items')
    producto = models.ForeignKey('Producto', on_delete=models.CASCADE, null=True, blank=True,
                                 related_name='receta_items_as_ingredient')
    cantidad_por_rendimiento = models.DecimalField(max_digits=10, decimal_places=3,
                                                   help_text="Cantidad para 1 lote base (mismo unidad que rendimiento).")
    TIPO_CHOICES = [
        ('insumo', 'Insumo'),
        ('producto', 'Producto'),
    ]
    tipo_item = models.CharField(max_length=10, choices=TIPO_CHOICES, default='insumo')
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden']

    def __str__(self):
        nombre = self.insumo.nombre if self.insumo else (self.producto.Corte if self.producto else "SIN ITEM")
        return f"{self.receta.nombre} - {nombre} : {self.cantidad_por_rendimiento}"

    def clean(self):
        if not (self.insumo or self.producto):
            raise ValidationError("RecetaItem debe referenciar un Insumo o un Producto.")
        if self.insumo and self.producto:
            raise ValidationError("RecetaItem no puede referenciar simultáneamente Insumo y Producto.")
        if self.cantidad_por_rendimiento <= 0:
            raise ValidationError("La cantidad por rendimiento debe ser mayor que 0.")

    @property
    def nombre_item(self):
        return self.insumo.nombre if self.insumo else self.producto.Corte

    def obtener_stock_actual(self):
        """Devuelve el stock actual del item referido en unidad de display (Decimal)."""
        if self.insumo:
            return self.insumo.Cantidad
        elif self.producto:
            return self.producto.stock_display
        return Decimal('0')


class Produccion(models.Model):
    """
    Registro de una producción. Inicialmente 'borrador' y luego 'confirmada' tras ejecutar confirmar().
    """
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('confirmada', 'Confirmada'),
        ('anulada', 'Anulada'),
    ]

    Id_produccion = models.AutoField(primary_key=True)
    receta = models.ForeignKey(Receta, on_delete=models.PROTECT, related_name='producciones')
    cantidad_producida = models.DecimalField(max_digits=10, decimal_places=2,
                                             help_text="Cantidad final producida (kg o unidades).")
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey('auth.User', on_delete=models.PROTECT, null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador')
    merma = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'),
                                help_text="Merma en las mismas unidades que cantidad_producida (kg o unidades).")
    observaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Producción {self.Id_produccion} - {self.receta.nombre} - {self.cantidad_producida} ({self.estado})"

    @property
    def detalles(self):
        """
        Devuelve un resumen de los detalles de la producción.
        """
        return f"Receta: {self.receta.nombre}, Cantidad: {self.cantidad_producida}, Estado: {self.estado}"

    def calcular_factor(self):
        """
        Factor = cuantos 'lotes base' se requieren para la cantidad_producida.
        factor = cantidad_producida / receta.rendimiento_por_lote
        """
        if not self.receta.rendimiento_por_lote or self.receta.rendimiento_por_lote == 0:
            return Decimal('0')
        return (Decimal(self.cantidad_producida) / Decimal(self.receta.rendimiento_por_lote)).quantize(Decimal('0.000'), rounding=ROUND_HALF_UP)

    def cantidades_necesarias(self):
        """
        Devuelve una lista de tuplas (RecetaItem, cantidad_necesaria) calculada
        para la cantidad_producida actual.
        """
        factor = self.calcular_factor()
        reqs = []
        for ri in self.receta.items.all():
            cantidad_req = (Decimal(ri.cantidad_por_rendimiento) * factor).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
            reqs.append((ri, cantidad_req))
        return reqs

    def confirmar(self, usuario=None):
        """
        Confirma la producción: verifica stock, descuenta insumos/productos usados y suma producto terminado.
        Registra ProduccionDetalle para auditoría.
        TODO: en caso de merma, se puede ajustar el neto a sumar.
        """
        if self.estado != 'borrador':
            raise ValidationError("Solo se pueden confirmar producciones en estado 'borrador'.")

        # cálculos previos
        factor = self.calcular_factor()
        if factor <= 0:
            raise ValidationError("Factor de producción inválido (rendimiento por lote = 0 o cantidad_producida inválida).")

        # Armamos la lista de items que vamos a bloquear/usar
        receta_items = list(self.receta.items.select_related('insumo', 'producto').all())

        # Empezamos la transacción atómica y bloqueamos filas relevantes
        with transaction.atomic():
            from django.apps import apps
            InsumoModel = apps.get_model(self._meta.app_label, 'Insumo')
            ProductoModel = apps.get_model(self._meta.app_label, 'Producto')

            insumo_ids = [ri.insumo_id for ri in receta_items if ri.insumo_id]
            producto_ids = [ri.producto_id for ri in receta_items if ri.producto_id]

            insumos_locked = {}
            productos_locked = {}

            if insumo_ids:
                for ins in InsumoModel.objects.select_for_update().filter(pk__in=insumo_ids):
                    insumos_locked[ins.pk] = ins
            if producto_ids:
                for prod in ProductoModel.objects.select_for_update().filter(pk__in=producto_ids):
                    productos_locked[prod.pk] = prod

            # Verificar stock disponible
            consumos = []  # lista de (tipo, instancia, cantidad_necesaria_interna)
            for ri, cantidad_req in self.cantidades_necesarias():
                if ri.insumo:
                    inst = insumos_locked.get(ri.insumo_id) or InsumoModel.objects.select_for_update().get(pk=ri.insumo_id)
                    if inst.Cantidad < cantidad_req:
                        raise ValidationError(f"Stock insuficiente de insumo '{inst.nombre}': disponible {inst.Cantidad}, requerido {cantidad_req}")
                    consumos.append(('insumo', inst, cantidad_req))
                elif ri.producto:
                    inst = productos_locked.get(ri.producto_id) or ProductoModel.objects.select_for_update().get(pk=ri.producto_id)
                    # Convertir cantidad de receta (kg) a gramos si el producto usa KG
                    cantidad_interna = ProductoModel.kg_a_gramos(cantidad_req) if inst.unidad_medida == 'KG' else cantidad_req
                    if inst.stock_kg < cantidad_interna:
                        stock_display = inst.stock_display
                        raise ValidationError(f"Stock insuficiente de producto (ingrediente) '{inst.Corte}': disponible {stock_display} kg, requerido {cantidad_req}")
                    consumos.append(('producto', inst, cantidad_interna))

            # Si todo ok: aplicar movimientos
            # 1) descontar consumos
            detalles = []
            for tipo, instancia, cantidad in consumos:
                if tipo == 'insumo':
                    instancia.Cantidad = (Decimal(instancia.Cantidad) - Decimal(cantidad)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    instancia.save()
                else:  # producto como ingrediente
                    instancia.stock_kg = (Decimal(instancia.stock_kg) - Decimal(cantidad)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    instancia.save()

                pd = ProduccionDetalle.objects.create(
                    produccion=self,
                    item_tipo= 'insumo' if tipo == 'insumo' else 'producto',
                    item_insumo = instancia.pk if tipo == 'insumo' else None,
                    item_producto = instancia.pk if tipo == 'producto' else None,
                    cantidad_usada = cantidad
                )
                detalles.append(pd)

            # 2) sumar producto final (considerar merma si corresponde)
            neto_a_sumar = Decimal(self.cantidad_producida) - Decimal(self.merma or 0)
            if neto_a_sumar < 0:
                raise ValidationError("La merma no puede ser mayor que la cantidad producida.")
            # bloquear y actualizar producto final
            producto_final = ProductoModel.objects.select_for_update().get(pk=self.receta.producto_final.pk)
            # Convertir a gramos si el producto final usa KG
            neto_interno = ProductoModel.kg_a_gramos(neto_a_sumar) if producto_final.unidad_medida == 'KG' else neto_a_sumar
            # Actualizar stock de forma atómica en DB para evitar problemas de concurrencia
            from django.db.models import F
            ProductoModel.objects.filter(pk=producto_final.pk).update(
                stock_kg=F('stock_kg') + Decimal(str(neto_interno))
            )
            # Refrescar la instancia desde BD para traer el nuevo stock_kg
            producto_final.refresh_from_db()

            # guardar detalle del producto final
            ProduccionDetalle.objects.create(
                produccion=self,
                item_tipo='producto_final',
                item_producto=producto_final.pk,
                cantidad_usada=neto_a_sumar
            )

            # 3) marcar produccion como confirmada
            if usuario:
                self.usuario = usuario
            self.estado = 'confirmada'
            self.save()

        return True  # todo ok


class ProduccionDetalle(models.Model):
    """
    Registro del detalle de lo que se consumió / produjo en una Produccion.
    item_tipo puede ser 'insumo', 'producto' (ingrediente) o 'producto_final' (lo que se sumó).
    """
    Id_produccion_detalle = models.AutoField(primary_key=True)
    produccion = models.ForeignKey(Produccion, on_delete=models.CASCADE, related_name='detalles')
    item_tipo = models.CharField(max_length=30, choices=[
        ('insumo', 'Insumo'),
        ('producto', 'Producto'),
        ('producto_final', 'Producto Final'),
    ])
    # referenciamos por PK manualmente para no forzar integridad doble; más adelante podés relacionar con FK opcional
    item_insumo = models.IntegerField(null=True, blank=True)
    item_producto = models.IntegerField(null=True, blank=True)
    cantidad_usada = models.DecimalField(max_digits=12, decimal_places=3)
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        nombre = ""
        if self.item_tipo == 'insumo' and self.item_insumo:
            ins = None
            from django.apps import apps
            InsumoModel = apps.get_model(self._meta.app_label, 'Insumo')
            try:
                ins = InsumoModel.objects.get(pk=self.item_insumo)
                nombre = ins.nombre
            except InsumoModel.DoesNotExist:
                nombre = f"Insumo {self.item_insumo}"
        elif (self.item_tipo in ('producto', 'producto_final')) and self.item_producto:
            from django.apps import apps
            ProductoModel = apps.get_model(self._meta.app_label, 'Producto')
            try:
                prod = ProductoModel.objects.get(pk=self.item_producto)
                nombre = prod.Corte
            except ProductoModel.DoesNotExist:
                nombre = f"Producto {self.item_producto}"
        return f"{self.produccion} -> {nombre} : {self.cantidad_usada}"

@receiver(post_save, sender=Detalle_compra)
def actualizar_stock_producto(sender, instance, **kwargs):
    """
    Actualiza el stock de Producto automáticamente si el insumo no requiere desposte.
    """
    if instance.Id_insumo and instance.Id_categoria:
        # Buscar o crear el producto asociado al insumo
        producto, creado = Producto.objects.get_or_create(
            Id_categoria=instance.Id_categoria,
            Nombre=instance.Id_insumo.Nombre,
            defaults={
                'Precio_kilo': instance.Precio_total / instance.Cantidad,
                'unidad_medida': 'KG',  # Suponiendo que la unidad es KG
            }
        )

        # Actualizar el stock del producto
        producto.stock_kg += instance.Cantidad * 1000  # Convertir a gramos si es necesario
        producto.save()
