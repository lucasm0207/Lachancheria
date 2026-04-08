from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation

# Importar todos los modelos necesarios de una sola vez
from .models import (
    Cliente,
    Venta,
    Detalle_venta,
    Producto,
    Compra,
    Detalle_compra,
    Proveedores,
    Categoria,
    Insumo,
    Desposte,
    CorteDesposte,
    Promociones,
    Receta,
    RecetaItem,
    Produccion,
    ProduccionDetalle,
)

class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['Categoria', 'descripcion', 'Cantidad', 'unidades_permitidas']
        widgets = {
            'Categoria': forms.TextInput(attrs={'class':'form-control'}),
            'descripcion': forms.Textarea(attrs={'class':'form-control', 'rows':2}),
            'Cantidad': forms.NumberInput(attrs={'class':'form-control', 'step':'0.01'}),
            'unidades_permitidas': forms.Select(attrs={'class':'form-select'}),
        }
        labels = {
            'Categoria': 'Nombre de la Categoría',
            'descripcion': 'Descripción',
            'Cantidad': 'Cantidad Comprada',
            'unidades_permitidas': 'Unidades de Medida Permitidas',
        }
        help_texts = {
            'unidades_permitidas': 'Define qué unidades de medida pueden usar los productos de esta categoría',
        }


# =============================================================================
# FORMULARIOS DE COMPRAS
# =============================================================================

class CompraForm(forms.ModelForm):
    class Meta:
        model = Compra
        fields = ['Id_proveedor', 'Tipo_compra', 'Forma_pago', 'Estado', 'monto_pagado']
        widgets = {
            'Id_proveedor': forms.Select(attrs={'class': 'form-select'}),
            'Tipo_compra': forms.Select(attrs={'class': 'form-select'}),
            'Forma_pago': forms.Select(attrs={'class': 'form-select'}),
            'Estado': forms.Select(attrs={'class': 'form-select'}),
            'monto_pagado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
        }
        labels = {
            'Id_proveedor': 'Proveedor',
            'Tipo_compra': 'Tipo compra',
            'Forma_pago': 'Forma pago',
            'Estado': 'Estado',
            'monto_pagado': 'Monto Pagado',
        }
        help_texts = {
            'monto_pagado': 'Cuánto se pagó al proveedor. Si es menor al total, queda como deuda.',
        }
        error_messages = {
            'Id_proveedor': {
                'required': '⚠️ Debes seleccionar un proveedor antes de continuar.',
            },
        }

class DetalleCompraCarneForm(forms.ModelForm):
    """Detalle de compra de carne: selecciona un Insumo de tipo 'carne'."""
    Id_insumo = forms.ModelChoiceField(
        queryset=Insumo.objects.filter(tipo='carne'),
        widget=forms.Select(attrs={'class':'form-select'}),
        label="Insumo (Carne)",
        error_messages={'required': '⚠️ Seleccioná un insumo de carne.'},
        required=False
    )

    class Meta:
        model = Detalle_compra
        fields = ['Id_insumo', 'Cantidad', 'Precio_total']
        widgets = {
            'Cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
            'Precio_total': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
        }
        error_messages = {
            'Cantidad': {'required': '⚠️ Ingresá la cantidad comprada.'},
            'Precio_total': {'required': '⚠️ Ingresá el precio total.'},
        }

    def clean_Cantidad(self):
        cantidad = self.cleaned_data.get('Cantidad')
        if cantidad is not None and cantidad <= 0:
            raise forms.ValidationError('⚠️ La cantidad debe ser mayor a 0.')
        return cantidad

    def clean_Precio_total(self):
        precio = self.cleaned_data.get('Precio_total')
        if precio is not None and precio <= 0:
            raise forms.ValidationError('⚠️ El precio debe ser mayor a 0.')
        return precio

class DetalleCompraInsumoForm(forms.ModelForm):
    """Detalle de compra de insumo: selecciona un Insumo de tipo 'insumo' (excluye carne)."""
    Id_insumo = forms.ModelChoiceField(
        queryset=Insumo.objects.exclude(tipo='carne'),
        widget=forms.Select(attrs={'class':'form-select'}),
        label="Insumo",
        error_messages={'required': '⚠️ Seleccioná un insumo.'},
        required=False
    )
    producto_asociado = forms.ModelChoiceField( queryset=Producto.objects.all(), widget=forms.Select(attrs={'class': 'form-select'}), label="Sumar stock al Producto (Opcional)", required=False, help_text="Ej: Elegí 'Leña' para que se sume a la tienda. Dejalo vacío si es un insumo interno (Tripa, bolsas, etc)." )

    class Meta:
        model = Detalle_compra
        fields = ['Id_insumo', 'Cantidad', 'Precio_total']
        widgets = {
            'Cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
            'Precio_total': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
        }
        error_messages = {
            'Cantidad': {'required': '⚠️ Ingresá la cantidad comprada.'},
            'Precio_total': {'required': '⚠️ Ingresá el precio total.'},
        }

    def clean_Cantidad(self):
        cantidad = self.cleaned_data.get('Cantidad')
        if cantidad is not None and cantidad <= 0:
            raise forms.ValidationError('⚠️ La cantidad debe ser mayor a 0.')
        return cantidad

    def clean_Precio_total(self):
        precio = self.cleaned_data.get('Precio_total')
        if precio is not None and precio <= 0:
            raise forms.ValidationError('⚠️ El precio debe ser mayor a 0.')
        return precio


class BaseDetalleCompraFormSet(forms.BaseInlineFormSet):
    """FormSet base que hace opcional el campo Id_detalle para nuevas instancias."""
    def _construct_form(self, i, **kwargs):
        form = super()._construct_form(i, **kwargs)
        # El campo que Django genera para el PK (Id_detalle) debe ser opcional
        if 'Id_detalle' in form.fields:
            form.fields['Id_detalle'].required = False
        return form


DetalleCompraCarneFormSet = inlineformset_factory(
    Compra,
    Detalle_compra,
    form=DetalleCompraCarneForm,
    formset=BaseDetalleCompraFormSet,
    extra=1,
    can_delete=True
)

DetalleCompraInsumoFormSet = inlineformset_factory(
    Compra,
    Detalle_compra,
    form=DetalleCompraInsumoForm,
    formset=BaseDetalleCompraFormSet,
    extra=1,
    can_delete=True
)

class UploadCSVForm(forms.Form):
    archivo_csv = forms.FileField(label="Subir archivo CSV")

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['Nombre', 'Telefono', 'Direccion', 'Email']

class ProvedorForm(forms.ModelForm):
    class Meta:
        model = Proveedores
        fields = ['Nombre', 'Telefono', 'Direccion', 'Email']
        widgets = {
            'Nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese el nombre del proveedor'
            }),
            'Telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 1123456789',
                'pattern': '[0-9]+',
                'title': 'Solo se permiten números'
            }),
            'Direccion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Av. San Martín 1234, Ciudad'
            }),
            'Email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'ejemplo@correo.com'
            }),
        }
        labels = {
            'Nombre': 'Nombre del Proveedor',
            'Telefono': 'Teléfono',
            'Direccion': 'Dirección',
            'Email': 'Correo Electrónico',
        }
    
    def clean_Telefono(self):
        telefono = self.cleaned_data.get('Telefono')
        if not telefono:
            raise forms.ValidationError('El teléfono es obligatorio')
        # Eliminar espacios y guiones
        telefono_limpio = telefono.replace(' ', '').replace('-', '')
        if not telefono_limpio.isdigit():
            raise forms.ValidationError('El teléfono solo puede contener números')
        if len(telefono_limpio) < 8 or len(telefono_limpio) > 15:
            raise forms.ValidationError('El teléfono debe tener entre 8 y 15 dígitos')
        return telefono
    
    def clean_Direccion(self):
        direccion = self.cleaned_data.get('Direccion')
        if direccion and len(direccion) < 5:
            raise forms.ValidationError('La dirección debe tener al menos 5 caracteres')
        return direccion


# =============================================================================
# FORMULARIOS DE VENTAS - SECCIÓN LIMPIA Y CENTRALIZADA
# =============================================================================

class VentaForm(forms.ModelForm):
    """
    Formulario principal para crear/editar ventas.
    Valida datos básicos de la venta sin lógica de detalles.
    """

    class Meta:
        model = Venta
        fields = ["Id_cliente", "Tipo_venta", "Forma_pago", "Estado"]
        widgets = {
            "Id_cliente": forms.Select(
                attrs={"class": "form-select", "id": "id_cliente_select"}
            ),
            "Tipo_venta": forms.Select(
                attrs={"class": "form-select", "id": "id_tipo_venta_select"}
            ),
            "Forma_pago": forms.Select(
                attrs={"class": "form-select", "id": "id_forma_pago_select"}
            ),
            "Estado": forms.Select(
                attrs={"class": "form-select", "id": "id_estado_select"}
            ),
        }
        labels = {
            "Id_cliente": "Cliente",
            "Tipo_venta": "Tipo de Venta",
            "Forma_pago": "Forma de Pago",
            "Estado": "Estado",
        }

    def clean_Id_cliente(self):
        """Valida que se seleccione un cliente"""
        cliente = self.cleaned_data.get("Id_cliente")
        if not cliente:
            raise forms.ValidationError("Debe seleccionar un cliente")
        return cliente

    def clean_Tipo_venta(self):
        """Valida que se seleccione un tipo de venta válido"""
        tipo_venta = self.cleaned_data.get("Tipo_venta")
        if not tipo_venta:
            raise forms.ValidationError("Debe seleccionar un tipo de venta")
        return tipo_venta

    def clean_Forma_pago(self):
        """Valida que se seleccione una forma de pago válida"""
        forma_pago = self.cleaned_data.get("Forma_pago")
        if not forma_pago:
            raise forms.ValidationError("Debe seleccionar una forma de pago")
        return forma_pago


class DetalleVentaForm(forms.ModelForm):
    """
    Formulario para detalles individuales de una venta.
    Solo recibe datos del formulario; la validación de stock se hace en la vista.
    """

    class Meta:
        model = Detalle_venta
        fields = ["Id_producto", "Cantidad", "Precio_total"]
        widgets = {
            "Id_producto": forms.Select(attrs={"class": "form-select producto-select"}),
            "Cantidad": forms.NumberInput(
                attrs={
                    "class": "form-control cantidad-input",
                    "step": "0.001",
                    "min": "0.001",
                }
            ),
            "Precio_total": forms.NumberInput(
                attrs={
                    "class": "form-control subtotal-input",
                    "readonly": "readonly",
                    "step": "0.01",
                }
            ),
        }
        labels = {
            "Id_producto": "Producto",
            "Cantidad": "Cantidad",
            "Precio_total": "Subtotal",
        }

    def clean_Cantidad(self):
        """Valida que la cantidad sea positiva y entera para UNIDAD/PAQUETE"""
        cantidad = self.cleaned_data.get("Cantidad")
        if not cantidad or cantidad <= 0:
            raise forms.ValidationError("La cantidad debe ser mayor a 0")
        return cantidad

    def clean_Id_producto(self):
        """Valida que se seleccione un producto"""
        producto = self.cleaned_data.get("Id_producto")
        if not producto:
            raise forms.ValidationError("Debe seleccionar un producto")
        return producto

    def clean(self):
        """Validación cruzada: UNIDAD/PAQUETE no aceptan decimales"""
        cleaned_data = super().clean()
        producto = cleaned_data.get("Id_producto")
        cantidad = cleaned_data.get("Cantidad")

        if producto and cantidad:
            if producto.unidad_medida in ('UNIDAD', 'PAQUETE'):
                if cantidad != cantidad.to_integral_value():
                    raise forms.ValidationError(
                        f'⚠️ El producto "{producto}" se vende por {producto.get_unidad_medida_display()}. '
                        f'La cantidad debe ser un número entero (sin decimales).'
                    )
        return cleaned_data


# Formset para manejar múltiples detalles de venta
DetalleVentaFormSet = inlineformset_factory(
    Venta,
    Detalle_venta,
    form=DetalleVentaForm,
    extra=1,
    can_delete=True,
)




class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            'Id_categoria',
            'Nombre',
            'Corte',
            'unidad_medida',
            'Precio_kilo',
            'precio_mayor_x_kg',
            'en_promocion',
            'stock_kg',
            'fecha_ingreso_elaboracion',
            'fecha_vencimiento',
            'detalle',
        ]
        labels = {
            'Id_categoria': 'Categoría',
            'Nombre': 'Producto',
            'Corte': 'Corte (solo para carnes/chacinados)',
            'unidad_medida': 'Unidad de Medida',
            'Precio_kilo': 'Precio',
            'precio_mayor_x_kg': 'Precio Mayorista',
            'en_promocion': 'En Promoción',
            'stock_kg': 'Stock (en kilogramos)',
            'fecha_ingreso_elaboracion': 'Fecha de Ingreso/Elaboración (Opcional)',
            'fecha_vencimiento': 'Fecha de Vencimiento (Opcional)',
            'detalle': 'Detalles Adicionales',
        }
        widgets = {
            'Id_categoria': forms.Select(attrs={'class': 'form-select', 'id': 'id_categoria_select'}),
            'Nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Bolsa de Leña, Asado, Milanesas'}),
            'Corte': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_corte_input', 'placeholder': 'Ej: Asado, Costilla, Bife'}),
            'unidad_medida': forms.Select(attrs={'class': 'form-select', 'id': 'id_unidad_medida_select'}),
            'stock_kg': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'form-control', 'id': 'id_stock_input'}),
            'Precio_kilo': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'form-control', 'id': 'id_precio_input'}),
            'precio_mayor_x_kg': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'form-control', 'id': 'id_precio_mayor_input', 'placeholder': 'Opcional'}),
            'fecha_ingreso_elaboracion': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'fecha_vencimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'detalle': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'en_promocion': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'Nombre': 'Nombre general del producto (obligatorio)',
            'Corte': 'Especificar solo si es carne o chacinado (BROSA, TERNERA, POLLO, PESCADO, CHACINADOS)',
            'unidad_medida': 'Las unidades disponibles dependen de la categoría seleccionada',
            'stock_kg': 'Ingrese el stock en kilogramos (se almacena internamente en gramos)',
            'Precio_kilo': 'Precio de venta (se mostrará con la unidad de medida)',
            'precio_mayor_x_kg': 'Opcional: si no se define, en ventas mayoristas se usa el precio normal sin descuento',
            'fecha_vencimiento': 'Solo completar para productos perecederos (carnes, lácteos, etc.)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si estamos editando un producto existente con unidad KG,
        # convertir gramos internos → kg para mostrar en el formulario
        if self.instance and self.instance.pk and self.instance.unidad_medida == 'KG':
            gramos = Decimal(str(self.instance.stock_kg or 0))
            self.initial['stock_kg'] = (gramos / Decimal('1000')).quantize(Decimal('0.01'))
    
    def clean(self):
        cleaned_data = super().clean()
        categoria = cleaned_data.get('Id_categoria')
        unidad_medida = cleaned_data.get('unidad_medida')
        stock_input = cleaned_data.get('stock_kg')
        
        # Validar que la unidad de medida sea compatible con la categoría
        if categoria and unidad_medida:
            if not categoria.validar_unidad_medida(unidad_medida):
                unidades_permitidas = categoria.get_unidades_disponibles()
                nombres_unidades = [display for _, display in unidades_permitidas]
                raise forms.ValidationError(
                    f'❌ La categoría "{categoria.Categoria}" solo permite: {", ".join(nombres_unidades)}. '
                    f'No se puede usar "{dict(Producto.UNIDAD_MEDIDA_CHOICES).get(unidad_medida)}".'
                )
        
        # Convertir kg ingresados → gramos para almacenamiento interno
        if unidad_medida == 'KG' and stock_input is not None:
            cleaned_data['stock_kg'] = Producto.kg_a_gramos(stock_input)
        
        return cleaned_data


# =============================================================================
# FORMULARIOS DE DESPOSTES
# =============================================================================

class DesposteForm(forms.ModelForm):
    Id_insumo = forms.ModelChoiceField(
        queryset=Insumo.objects.filter(tipo='carne'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Insumo de Carne',
    )

    class Meta:
        model = Desposte
        fields = ['Id_insumo', 'Unidades', 'Peso_inicial']
        labels = {
            'Id_insumo': 'Insumo de Carne',
            'Unidades': 'Unidades (cantidad de animales)',
            'Peso_inicial': 'Peso inicial total (kg)',
        }
        widgets = {
            'Unidades': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'Peso_inicial': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def clean_Unidades(self):
        unidades = self.cleaned_data.get('Unidades')
        if unidades is None:
            raise ValidationError("Ingrese una cantidad de unidades válida.")
        try:
            unidades = int(unidades)
        except (TypeError, ValueError):
            raise ValidationError("Unidades debe ser un número entero.")
        if unidades < 1:
            raise ValidationError("La cantidad de unidades debe ser al menos 1.")
        return unidades

    def clean_Peso_inicial(self):
        peso = self.cleaned_data.get('Peso_inicial')
        if peso is None:
            raise ValidationError("Ingrese el peso inicial.")
        try:
            peso_dec = Decimal(str(peso))
        except (TypeError, InvalidOperation):
            raise ValidationError("Peso inicial inválido.")
        if peso_dec <= Decimal('0.00'):
            # Regla B: peso inicial inválido (<= 0)
            raise ValidationError("Peso inicial debe ser mayor a cero.")
        return peso_dec

    def clean(self):
        """
        Validación compuesta:
        - A) Verifica que el insumo de carne tenga suficiente stock (Cantidad) para las unidades solicitadas.
        """
        cleaned = super().clean()
        insumo = cleaned.get('Id_insumo')
        unidades = cleaned.get('Unidades')

        if insumo and unidades is not None:
            try:
                origen = Insumo.objects.get(pk=insumo.pk)
            except Insumo.DoesNotExist:
                raise ValidationError("El insumo seleccionado no existe.")
            if origen.Cantidad < unidades:
                raise ValidationError({
                    'Unidades': f"No hay suficiente stock del insumo {origen.nombre}. Disponible: {origen.Cantidad}. Ajustá la cantidad o elegí otro insumo."
                })
        return cleaned


class CorteDesposteForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        desposte = kwargs.pop('desposte', None)
        super().__init__(*args, **kwargs)

        if desposte:
            categoria = desposte.Id_insumo.categoria
            self.fields['Id_producto'].queryset = Producto.objects.filter(
                Id_categoria=categoria
            )

    class Meta:
        model = CorteDesposte
        fields = ['Id_producto', 'Peso']
        labels = {
            'Id_producto': 'Corte',
            'Peso': 'Peso del corte (kg)',
        }
        widgets = {
            'Id_producto': forms.Select(attrs={'class': 'form-control'}),
            'Peso': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
    def clean_Id_producto(self):
        producto = self.cleaned_data.get("Id_producto")
        desposte = self.initial.get("desposte")

        if producto and desposte:
         if producto.Id_categoria != desposte.Id_insumo.Id_categoria:
             raise ValidationError(
                "El producto no corresponde al tipo de animal del desposte."
            )
        return producto
    def clean_Peso(self):
        peso = self.cleaned_data.get('Peso')
        if peso is None or peso == '':
            # Si querés permitir 0 entonces quitar esta validación; aquí la forzamos a >= 0
            raise ValidationError("Ingrese el peso del corte (>= 0).")
        try:
            peso_dec = Decimal(str(peso))
        except (TypeError, InvalidOperation):
            raise ValidationError("Peso inválido.")
        if peso_dec < Decimal('0.00'):
            raise ValidationError("El peso no puede ser negativo.")
        return peso_dec


class BaseCorteDesposteFormSet(BaseInlineFormSet):
    """
    Validación global del formset para:
    - C: la suma de los pesos de los cortes NO debe exceder el Peso_inicial del desposte.
    - Se ejecuta antes de guardar y evita que se apliquen cambios al stock si falla.
    """
    def clean(self):
        super().clean()
        # Sumar pesos de formularios que NO estén marcados para eliminación
        total_peso = Decimal('0.00')
        for form in self.forms:
            # Skip forms vacíos sin datos
            if not hasattr(form, 'cleaned_data'):
                continue
            cd = form.cleaned_data
            # Si el formulario está marcado para borrado, no sumarlo
            if cd.get('DELETE', False):
                continue
            peso = cd.get('Peso')
            if peso is None:
                # Si falta el peso y el formulario tiene producto, lo marcamos como error
                if cd.get('Id_producto'):
                    form.add_error('Peso', 'Ingrese el peso del corte.')
                continue
            try:
                peso_dec = Decimal(str(peso))
            except (TypeError, InvalidOperation):
                form.add_error('Peso', 'Peso inválido.')
                continue
            total_peso += peso_dec

        # Obtener el peso inicial desde la instancia Desposte asociada al formset.
        # IMPORTANTE: self.instance debe existir (el desposte debe haberse guardado antes de usar el formset).
        peso_inicial = None
        try:
            peso_inicial = Decimal(str(self.instance.Peso_inicial or '0.00'))
        except (AttributeError, InvalidOperation):
            peso_inicial = Decimal('0.00')

        if total_peso > peso_inicial:
            # Regla C: la suma de cortes > peso inicial -> error global
            raise ValidationError(f"La suma de los pesos de los cortes ({total_peso} kg) excede el peso inicial ({peso_inicial} kg). Corregí los valores.")

# Instanciación del formset usando la clase base custom
CorteDesposteFormSet = inlineformset_factory(
    Desposte,
    CorteDesposte,
    form=CorteDesposteForm,
    formset=BaseCorteDesposteFormSet,
    extra=1,
    can_delete=True
)
# ============================================================================= 

# =============================================================================

# ============================================
# FORMULARIO DETALLE DE COMPRA DE INSUMOS
# ============================================

class InsumoPurchaseDetailForm(forms.ModelForm):
    """Formulario para detalle de compra de insumos"""

    Id_insumo = forms.ModelChoiceField(
        queryset=Insumo.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Insumo"
    )
    producto_asociado = forms.ModelChoiceField(
        queryset=Producto.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Sumar stock al Producto (Opcional)",
        required=False,
        help_text="Ej: Elegí 'Leña' para que se sume a la tienda. Dejalo vacío si es un insumo interno (Tripa, bolsas, etc)."
    )
    class Meta:
        model = Detalle_compra
        fields = ['Id_insumo', 'Cantidad', 'Precio_total']
        labels = {
            'Cantidad': 'Cantidad',
            'Precio_total': 'Precio Total',
        }
        widgets = {
            'Cantidad': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'Precio_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


# ============================================
# FORMSET PARA MÚLTIPLES INSUMOS EN UNA COMPRA
# ============================================

InsumoPurchaseDetailFormSet = inlineformset_factory(
    Compra,
    Detalle_compra,
    form=InsumoPurchaseDetailForm,
    extra=1,
    can_delete=True,
    fk_name='Id_compra'
)

# ==============================
# FORMULARIO PARA EL MODELO Insumo
# ==============================
class InsumoForm(forms.ModelForm):
    """Formulario simplificado: solo registra QUÉ es el insumo.
    El stock se gestiona a través de las compras."""
    class Meta:
        model = Insumo
        fields = [
            'nombre',
            'tipo',
            'unidad_medida',
            'categoria',
        ]
        labels = {
            'nombre': 'Nombre del Insumo',
            'tipo': 'Tipo',
            'unidad_medida': 'Unidad de Medida',
            'categoria': 'Categoría (opcional)',
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Media Res, Cerdo, Leña, Vino'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'unidad_medida': forms.Select(attrs={'class': 'form-select'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
        }
        help_texts = {
            'tipo': 'Carne = medias reses, cerdos, etc. Insumo = vino, leña, productos de almacén.',
            'unidad_medida': 'Unidad en la que se compra y almacena.',
            'categoria': 'Solo para carnes: seleccionar la categoría correspondiente.',
        }



# =============================================================================
# FORMULARIOS DE PROMOCIONES
# =============================================================================

class PromocionForm(forms.ModelForm):
    class Meta:
        model = Promociones
        fields = [
            'Id_producto',
            'tipo_promocion',
            'Precio_oferta',
            'descuento_porcentaje',
            'estado',
            'Fecha_inicio',
            'Fecha_fin',
            'descripcion',
            'cantidad_minima'
        ]
        widgets = {
            'Id_producto': forms.Select(attrs={'class': 'form-select'}),
            'tipo_promocion': forms.Select(attrs={'class': 'form-select'}),
            'Precio_oferta': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'descuento_porcentaje': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'Fecha_inicio': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'Fecha_fin': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'cantidad_minima': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
        labels = {
            'Id_producto': 'Producto',
            'tipo_promocion': 'Tipo de Promoción',
            'Precio_oferta': 'Precio en Oferta',
            'descuento_porcentaje': 'Descuento (%)',
            'estado': 'Estado',
            'Fecha_inicio': 'Fecha de Inicio',
            'Fecha_fin': 'Fecha de Fin',
            'descripcion': 'Descripción',
            'cantidad_minima': 'Cantidad Mínima (kg)'
        }
    
    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get('Fecha_inicio')
        fecha_fin = cleaned_data.get('Fecha_fin')
        precio_oferta = cleaned_data.get('Precio_oferta')
        producto = cleaned_data.get('Id_producto')
        
        # Validar que la fecha de fin sea posterior a la fecha de inicio
        if fecha_inicio and fecha_fin:
            if fecha_fin <= fecha_inicio:
                raise forms.ValidationError('La fecha de fin debe ser posterior a la fecha de inicio.')
        
        # Validar que el precio de oferta sea menor al precio normal
        if producto and precio_oferta:
            if precio_oferta >= producto.Precio_kilo:
                raise forms.ValidationError(
                    f'El precio de oferta (${precio_oferta}) debe ser menor al precio normal (${producto.Precio_kilo}).'
                )
        
        return cleaned_data


# ---------- Forms para Receta / RecetaItem / Produccion ----------


class RecetaForm(forms.ModelForm):
    class Meta:
        model = Receta
        fields = ['nombre', 'producto_final', 'rendimiento_por_lote', 'notas']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'producto_final': forms.Select(attrs={'class': 'form-select'}),
            'rendimiento_por_lote': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'nombre': 'Nombre de la receta',
            'producto_final': 'Producto final',
            'rendimiento_por_lote': 'Rendimiento por lote (kg o unidades)',
            'notas': 'Notas / Observaciones'
        }

    def clean_rendimiento_por_lote(self):
        val = self.cleaned_data.get('rendimiento_por_lote')
        if val is None:
            raise ValidationError("Ingrese rendimiento por lote.")
        try:
            dec = Decimal(str(val))
        except (TypeError, InvalidOperation):
            raise ValidationError("Valor inválido.")
        if dec <= Decimal('0'):
            raise ValidationError("El rendimiento por lote debe ser mayor que 0.")
        return dec


class RecetaItemForm(forms.ModelForm):
    """
    Form para cada ingrediente de la receta.
    Permite elegir Insumo o Producto (uno u otro) y la cantidad necesaria para 1 lote base.
    """
    class Meta:
        model = RecetaItem
        fields = ['insumo', 'producto', 'tipo_item', 'cantidad_por_rendimiento', 'orden']
        widgets = {
            'insumo': forms.Select(attrs={'class': 'form-select'}),
            'producto': forms.Select(attrs={'class': 'form-select'}),
            'tipo_item': forms.Select(attrs={'class': 'form-select'}),
            'cantidad_por_rendimiento': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min':'0.001'}),
            'orden': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }
        labels = {
            'insumo': 'Insumo (ej: condimento, grasa, tripa)',
            'producto': 'Producto (ej: corte de carne como ingrediente)',
            'tipo_item': 'Tipo de ítem',
            'cantidad_por_rendimiento': 'Cantidad por lote base',
            'orden': 'Orden',
        }

    def clean(self):
        cleaned = super().clean()
        # Si el formulario está marcado para eliminación, no validar
        if cleaned.get('DELETE'):
            return cleaned

        insumo = cleaned.get('insumo')
        producto = cleaned.get('producto')
        cantidad = cleaned.get('cantidad_por_rendimiento')

        # Si el formulario está vacío (sin insumo/producto/cantidad/orden), omitir validación
        empty_fields = all(
            v in (None, '', []) for v in [insumo, producto, cantidad, cleaned.get('orden')]
        )
        if empty_fields:
            return cleaned

        if not insumo and not producto:
            raise ValidationError("Debes seleccionar un Insumo o un Producto para este ingrediente.")
        if insumo and producto:
            raise ValidationError("No puedes seleccionar Insumo y Producto al mismo tiempo en un ingrediente.")
        try:
            cantidad_dec = Decimal(str(cantidad))
        except (TypeError, InvalidOperation):
            raise ValidationError({'cantidad_por_rendimiento': "Cantidad inválida."})
        if cantidad_dec <= Decimal('0'):
            raise ValidationError({'cantidad_por_rendimiento': "La cantidad debe ser mayor que 0."})
        return cleaned

# Inline formset para editar RecetaItem dentro de Receta
RecetaItemFormSet = inlineformset_factory(
    Receta,
    RecetaItem,
    form=RecetaItemForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False
)


class ProduccionForm(forms.ModelForm):
    """
    Form para crear/editar una Producción.
    No ejecuta la confirmación (aplicar stock) — eso lo hace el método modelo .confirmar()
    Ideal flujo: crear -> revisar resumen de cantidades necesarias -> confirmar con acción que llame a .confirmar()
    """
    class Meta:
        model = Produccion
        fields = ['receta', 'cantidad_producida', 'merma', 'observaciones']
        widgets = {
            'receta': forms.Select(attrs={'class': 'form-select'}),
            'cantidad_producida': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'merma': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.00'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'receta': 'Receta',
            'cantidad_producida': 'Cantidad a producir (kg o unidades)',
            'merma': 'Merma (kg o unidades)',
            'observaciones': 'Observaciones'
        }

    def clean_cantidad_producida(self):
        cantidad = self.cleaned_data.get('cantidad_producida')
        if cantidad is None:
            raise ValidationError("Ingrese la cantidad a producir.")
        try:
            dec = Decimal(str(cantidad))
        except (TypeError, InvalidOperation):
            raise ValidationError("Cantidad inválida.")
        if dec <= Decimal('0'):
            raise ValidationError("La cantidad producida debe ser mayor que 0.")
        return dec

    def clean_merma(self):
        merma = self.cleaned_data.get('merma') or Decimal('0')
        try:
            dec = Decimal(str(merma))
        except (TypeError, InvalidOperation):
            raise ValidationError("Merma inválida.")
        if dec < Decimal('0'):
            raise ValidationError("La merma no puede ser negativa.")
        return dec

    def clean(self):
        cleaned = super().clean()
        cantidad = cleaned.get('cantidad_producida')
        merma = cleaned.get('merma') or Decimal('0')
        receta = cleaned.get('receta')

        if cantidad is None or receta is None:
            return cleaned

        try:
            cantidad_dec = Decimal(str(cantidad))
            merma_dec = Decimal(str(merma))
        except (TypeError, InvalidOperation):
            return cleaned  # errores ya agregados en sus campos

        if merma_dec > cantidad_dec:
            raise ValidationError({'merma': "La merma no puede ser mayor que la cantidad producida."})

        # Validación opcional: pre-chequeo de stock (solo aviso, no bloquea)
        faltantes = []
        temp_prod = Produccion(receta=receta, cantidad_producida=cantidad_dec, merma=merma_dec)
        for ri, req in temp_prod.cantidades_necesarias():
            if ri.insumo:
                stock = ri.insumo.Cantidad
                nombre = ri.insumo.nombre
            else:
                stock = ri.producto.stock_display
                nombre = ri.producto.Corte
            if Decimal(stock) < Decimal(req):
                faltantes.append(f"{nombre}: disponible {stock} - requerido {req}")
        # Guardar lista de faltantes para que la vista/resumen pueda mostrarlos,
        # pero NO bloquear la creación de la producción aquí — permitimos guardar
        # como 'borrador' y que el usuario confirme desde la vista de resumen.
        if faltantes:
            self.faltantes = faltantes
            cleaned['faltantes'] = faltantes

        return cleaned


class ProduccionConfirmForm(forms.Form):
    """
    Form simple para confirmar una producción desde la vista.
    - action: hidden field o checkbox de confirmación
    El backend debe recibir la producción (id) y llamar a produccion.confirmar(usuario=request.user)
    """
    confirmar = forms.BooleanField(required=True, label="Confirmar producción y aplicar cambios en stock")

    def clean_confirmar(self):
        val = self.cleaned_data.get('confirmar')
        if not val:
            raise ValidationError("Debes confirmar la acción para aplicar la producción.")
        return val

class PromocionBusquedaForm(forms.Form):
    """Formulario para búsqueda y filtrado de promociones"""
    
    busqueda = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por producto...'
        }),
        label='Buscar'
    )
    
    producto = forms.ModelChoiceField(
        queryset=Producto.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Producto',
        empty_label='Todos los productos'
    )
    
    estado = forms.ChoiceField(
        choices=[('', 'Todos los estados')] + Promociones.ESTADO_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Estado'
    )
    
    tipo_promocion = forms.ChoiceField(
        choices=[('', 'Todos los tipos')] + Promociones.TIPO_PROMOCION_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Tipo de Promoción'
    )
    
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Desde'
    )
    
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Hasta'
    )