# =============================================================================
# IMPORTACIONES ORGANIZADAS - views.py
# =============================================================================

# Importaciones de Python estándar
from urllib import request

from django.db.models import Q, Prefetch
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import TextIOWrapper
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.db.models import F
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout as auth_logout
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import views as auth_views
from django.http import HttpResponse
import mercadopago
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from io import BytesIO
# import mercadopago  # Comentado temporalmente - descomentar cuando se instale el módulo
import os
from django.conf import settings
# Importaciones de modelos locales
from .models import (
    Cliente,
    Insumo, 
    Producto, 
    Venta, 
    Categoria, 
    Detalle_venta,
    Compra, 
    Detalle_compra,
    Proveedores, 
    Desposte,
    
)

# Importaciones de formularios locales
from .forms import (
    ClienteForm, 
    ProductoForm, 
    VentaForm, 
    DetalleVentaFormSet, 
    UploadCSVForm, 
    CompraForm, 
    ProvedorForm, 
    CategoriaForm,
    DetalleCompraCarneFormSet, 
    DetalleCompraInsumoFormSet,
    DesposteForm, 
    CorteDesposteFormSet,
    InsumoPurchaseDetailFormSet,
    InsumoForm
)  # 

# =============================================================================
# SISTEMA DE PERMISOS POR GRUPO
# =============================================================================
from django.contrib.auth.models import User, Group
from functools import wraps
from django.core.exceptions import PermissionDenied

# Definición de permisos por grupo
PERMISOS_POR_GRUPO = {
    'admin': ['*'],  # Acceso total
    'cajero': ['ventas', 'clientes', 'promociones'],
    'despostador': ['despostes', 'productos', 'categorias', 'insumos'],
    'inventario': ['productos', 'categorias', 'compras', 'proveedores', 'insumos'],
}

def grupo_requerido(*grupos_permitidos):
    """
    Decorador que restringe el acceso a usuarios que pertenezcan a ciertos grupos.
    El grupo 'admin' siempre tiene acceso.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            user_groups = set(request.user.groups.values_list('name', flat=True))
            
            # Admin siempre tiene acceso
            if 'admin' in user_groups:
                return view_func(request, *args, **kwargs)
            
            # Verificar si el usuario tiene alguno de los grupos permitidos
            if user_groups.intersection(set(grupos_permitidos)):
                return view_func(request, *args, **kwargs)
            
            # Superusuarios siempre tienen acceso
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            raise PermissionDenied("No tienes acceso a esta función :(")
        return _wrapped_view
    return decorator


def tiene_acceso_a_seccion(user, seccion):
    """Verifica si un usuario tiene acceso a una sección específica."""
    if not user.is_authenticated:
        return False
    
    user_groups = list(user.groups.values_list('name', flat=True))
    
    for grupo in user_groups:
        permisos = PERMISOS_POR_GRUPO.get(grupo, [])
        if '*' in permisos or seccion in permisos:
            return True
    return False

# -------------------------
# PÁGINA DE INICIO Y BA
# -------------------------



def _to_decimal(v):
    try:
        return Decimal(v)
    except Exception:
        return Decimal('0.00')

def aumentar_stock(obj, cantidad):
    """Suma `cantidad` al atributo Cantidad del objeto si existe."""
    if obj is None:
        return
    if hasattr(obj, 'Cantidad'):
        current = obj.Cantidad or 0
        obj.Cantidad = _to_decimal(current) + _to_decimal(cantidad)
        obj.save()

def disminuir_stock(obj, cantidad):
    """Resta `cantidad` al atributo Cantidad del objeto si existe."""
    if obj is None:
        return
    if hasattr(obj, 'Cantidad'):
        current = obj.Cantidad or 0
        obj.Cantidad = _to_decimal(current) - _to_decimal(cantidad)
        obj.save()
# ---------------------


@login_required
def index(request):
    # Top compradores por total de ventas (los 5 principales)
    try:
        buyers_qs = (
            Venta.objects
            .values('Id_cliente__Nombre')
            .annotate(total=Sum('Precio'))
            .order_by('-total')[:5]
        )
        top_buyers = [{'nombre': b.get('Id_cliente__Nombre') or '—', 'total': b.get('total') or 0} for b in buyers_qs]
    except Exception:
        top_buyers = []

    # Promociones activas (mostrar productos en promoción)
    promociones = []
    try:
        from .models import Promociones
        promos = Promociones.objects.select_related('Id_producto').filter(estado='activa')[:5]
        for p in promos:
            prod = getattr(p, 'Id_producto', None)
            promociones.append({
                'nombre': getattr(prod, 'Corte', str(p)),
                'precio': getattr(prod, 'Precio_kilo', ''),
                'image_url': getattr(prod, 'imagen_url', '') if prod else ''
            })
    except Exception:
        promociones = []

    return render(request, 'index.html', {
        'top_buyers': top_buyers,
        'promociones': promociones,
    })
def base(request):
    return render(request, 'base.html')


@login_required
def profile(request):
    # Simple profile page — templates/user_profile.html
    return render(request, 'user_profile.html', {'user': request.user})


def logout_view(request):
    """Cerrar sesión y redirigir al login (acepta GET y POST)."""
    # Si el usuario no estaba autenticado simplemente redirigimos también
    try:
        auth_logout(request)
    except Exception:
        pass
    from django.contrib import messages
    messages.info(request, 'Sesión cerrada correctamente.')
    return redirect('login')


# Custom LoginView que descarta mensajes previos para evitar mostrar mensajes
# (p. ej. "Sesión cerrada correctamente") al volver a iniciar sesión.
class CustomLoginView(auth_views.LoginView):
    template_name = 'login.html'

    def _clear_messages(self, request):
        try:
            # Consumir y descartar cualquier mensaje pendiente
            list(messages.get_messages(request))
        except Exception:
            pass

    def get(self, request, *args, **kwargs):
        self._clear_messages(request)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self._clear_messages(request)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        # Actualizar last_login con la hora actual
        response = super().form_valid(form)
        self.request.user.last_login = timezone.now()
        self.request.user.save(update_fields=['last_login'])
        return response


def categoria_list(request):
    categorias = Categoria.objects.all()
    return render(request, 'categorias/categoria_list.html', {'categorias': categorias})

def categoria_create(request):
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            categoria = form.save()
            messages.success(request, f'✅ Categoría "{categoria.Categoria}" creada exitosamente.')
            return redirect('categoria_list')
        else:
            messages.error(request, '❌ Hubo errores en el formulario. Por favor, revisa los campos.')
    else:
        form = CategoriaForm()
    return render(request, 'categorias/categoria_form.html', {
        'form': form,
        'titulo': 'Agregar categoria'
    })

def categoria_update(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    if request.method == 'POST':
        form = CategoriaForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            messages.success(request, f'✅ Categoría "{categoria.Categoria}" actualizada exitosamente.')
            return redirect('categoria_list')
        else:
            messages.error(request, '❌ Hubo errores en el formulario. Por favor, revisa los campos.')
    else:
        form = CategoriaForm(instance=categoria)
    return render(request, 'categorias/categoria_form.html', {
        'form': form,
        'titulo': f'Editar categoría: {categoria.Categoria}'
    })

def categoria_delete(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    if request.method == 'POST':
        categoria.delete()
        return redirect('categoria_list')
    return render(request, 'categorias/categoria_delete.html', {'categoria': categoria})


#hitorial de ventas 

from django.db.models import Sum

def historial_cliente_detalle(request, cliente_id):
    cliente = get_object_or_404(Cliente, Id_cliente=cliente_id)
    
    # Obtenemos el historial del cliente
    historial = Detalle_venta.objects.filter(Id_venta__Id_cliente=cliente).order_by('-Id_venta__Fecha_venta')
    
    # Calculamos ranking de productos más comprados
    ranking = (
        Detalle_venta.objects
        .filter(Id_venta__Id_cliente=cliente)
        .values('Id_producto__Corte')
        .annotate(total_cantidad=Sum('Cantidad'))
        .order_by('-total_cantidad')
    )
    
    return render(request, 'clientes/historial_cliente.html', {
        'historial': historial,
        'cliente': cliente,
        'ranking': ranking
    })
# -------------------------
# CLIENTES
# -------------------------
@login_required
@grupo_requerido('admin', 'cajero')
def cliente_list(request):
    clientes = Cliente.objects.all()
    return render(request, 'clientes/cliente_list.html', {'clientes': clientes})

@login_required
@grupo_requerido('admin', 'cajero')
def cliente_create(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('cliente_list')
    else:
        form = ClienteForm()
    return render(request, 'clientes/cliente_form.html', {
        'form': form,
        'titulo': 'Agregar Cliente'
    })

@login_required
@grupo_requerido('admin', 'cajero')
def cliente_update(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            return redirect('cliente_list')
    else:
        form = ClienteForm(instance=cliente)
    return render(request, 'clientes/cliente_form.html', {
        'form': form,
        'titulo': 'Editar Cliente'
    })

def cliente_delete(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        cliente.delete()
        return redirect('cliente_list')
    return render(request, 'clientes/cliente_delete.html', {'cliente': cliente})

def importar_clientes(request):
    if request.method == "POST":
        form = UploadCSVForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = request.FILES["archivo_csv"]
            decoded_file = TextIOWrapper(archivo.file, encoding="utf-8")
            reader = csv.reader(decoded_file)
            next(reader, None)  # saltar encabezado

            for fila in reader:
                if len(fila) < 4:
                    continue
                Cliente.objects.create(
                    Nombre=fila[0],
                    Direccion=fila[1],
                    Telefono=fila[2],
                    Email=fila[3]
                )

            messages.success(request, "Clientes importados correctamente.")
            return redirect("cliente_list")
    else:
        form = UploadCSVForm()

    return render(request, "clientes/importar_clientes.html", {"form": form})


# =============================================================================
# VISTAS DE VENTAS - SECCIÓN LIMPIA Y CENTRALIZADA
# =============================================================================

from .services import VentaService


@login_required
@grupo_requerido("admin", "cajero")
def venta_list(request):
    """
    Lista todas las ventas con opciones de filtrado y paginación.
    """
    ventas = (
        Venta.objects.select_related("Id_cliente")
        .prefetch_related(
            Prefetch(
                "detalle_venta_set",
                queryset=Detalle_venta.objects.select_related("Id_producto"),
            )
        )
        .all()
        .order_by("-Fecha_venta")
    )

    # Filtro por ID
    venta_id = request.GET.get("id", "").strip()
    if venta_id:
        try:
            ventas = ventas.filter(Id_venta=int(venta_id))
        except ValueError:
            pass

    # Filtro por cliente
    cliente = request.GET.get("cliente", "").strip()
    if cliente:
        ventas = ventas.filter(Id_cliente__Nombre__icontains=cliente)

    # Filtro por tipo de venta
    tipo_venta = request.GET.get("tipo_venta", "").strip()
    if tipo_venta:
        ventas = ventas.filter(Tipo_venta=tipo_venta)

    # Filtro por estado
    estado = request.GET.get("estado", "").strip()
    if estado:
        ventas = ventas.filter(Estado=estado)

    # Filtro por rango de fechas
    fecha_desde = request.GET.get("fecha_desde", "").strip()
    if fecha_desde:
        try:
            ventas = ventas.filter(Fecha_venta__date__gte=fecha_desde)
        except Exception:
            pass

    fecha_hasta = request.GET.get("fecha_hasta", "").strip()
    if fecha_hasta:
        try:
            ventas = ventas.filter(Fecha_venta__date__lte=fecha_hasta)
        except Exception:
            pass

    # Filtro por producto
    producto = request.GET.get("producto", "").strip()
    if producto:
        ventas = ventas.filter(
            Q(detalle_venta__Id_producto__Nombre__icontains=producto)
            | Q(detalle_venta__Id_producto__Corte__icontains=producto)
        ).distinct()

    # Paginación
    paginator = Paginator(ventas, 15)
    page = request.GET.get("page", 1)
    try:
        ventas_paginadas = paginator.page(page)
    except PageNotAnInteger:
        ventas_paginadas = paginator.page(1)
    except EmptyPage:
        ventas_paginadas = paginator.page(paginator.num_pages)

    return render(
        request, "ventas/venta_list.html", {"ventas": ventas_paginadas, "total_ventas": paginator.count}
    )


@login_required
@grupo_requerido("admin", "cajero")
def venta_create(request):
    """
    Crea una nueva venta.
    Integra con VentaService para manejo transaccional y validación.
    """
    venta_form = VentaForm(request.POST or None)
    detalle_formset = DetalleVentaFormSet(request.POST or None)
    productos = Producto.objects.all()

    if request.method == "POST":
        if venta_form.is_valid() and detalle_formset.is_valid():
            cliente = venta_form.cleaned_data["Id_cliente"]
            tipo_venta = venta_form.cleaned_data["Tipo_venta"]
            forma_pago = venta_form.cleaned_data["Forma_pago"]
            estado = venta_form.cleaned_data["Estado"]

            # Preparar datos de detalles
            detalles_data = []
            for form in detalle_formset.forms:
                if not hasattr(form, "cleaned_data"):
                    continue
                if form.cleaned_data.get("DELETE", False):
                    continue

                producto = form.cleaned_data.get("Id_producto")
                cantidad = form.cleaned_data.get("Cantidad")

                if producto and cantidad:
                    detalles_data.append(
                        {
                            "producto": producto,
                            "cantidad": cantidad,
                        }
                    )

            # Usar servicio para crear venta
            venta, mensaje = VentaService.crear_venta(
                cliente, tipo_venta, forma_pago, estado, detalles_data
            )

            if venta:
                messages.success(request, "✅ Venta registrada exitosamente")
                return redirect("venta_list")
            else:
                messages.error(request, f"❌ Error al crear la venta: {mensaje}")

        else:
            # Mostrar errores del formulario
            if venta_form.errors:
                for field, errors in venta_form.errors.items():
                    messages.error(request, f"Error en {field}: {', '.join(errors)}")

            if detalle_formset.errors:
                for i, form_errors in enumerate(detalle_formset.errors):
                    if form_errors:
                        for field, errors in form_errors.items():
                            messages.error(
                                request,
                                f"Error en detalle {i + 1}, {field}: {', '.join(errors)}",
                            )

    return render(
        request,
        "ventas/venta_form.html",
        {
            "venta_form": venta_form,
            "detalle_formset": detalle_formset,
            "productos": productos,
            "modo": "Nueva",
        },
    )


@login_required
@grupo_requerido("admin", "cajero")
def venta_update(request, Id_venta):
    """
    Edita una venta existente.
    Integra con VentaService para manejo transaccional y validación.
    """
    venta = get_object_or_404(Venta, Id_venta=Id_venta)
    venta_form = VentaForm(request.POST or None, instance=venta)
    detalle_formset = DetalleVentaFormSet(request.POST or None, instance=venta)
    productos = Producto.objects.all()

    if request.method == "POST":
        if venta_form.is_valid() and detalle_formset.is_valid():
            tipo_venta = venta_form.cleaned_data["Tipo_venta"]
            forma_pago = venta_form.cleaned_data["Forma_pago"]
            estado = venta_form.cleaned_data["Estado"]

            # Preparar datos de detalles
            detalles_data = []
            for form in detalle_formset.forms:
                if not hasattr(form, "cleaned_data"):
                    continue
                if form.cleaned_data.get("DELETE", False):
                    continue

                producto = form.cleaned_data.get("Id_producto")
                cantidad = form.cleaned_data.get("Cantidad")

                if producto and cantidad:
                    detalles_data.append(
                        {
                            "producto": producto,
                            "cantidad": cantidad,
                        }
                    )

            # Usar servicio para actualizar venta
            es_exitoso, mensaje = VentaService.actualizar_venta(
                venta, tipo_venta, forma_pago, estado, detalles_data
            )

            if es_exitoso:
                messages.success(request, "✅ Venta actualizada exitosamente")
                return redirect("venta_list")
            else:
                messages.error(request, f"❌ Error al actualizar la venta: {mensaje}")

        else:
            # Mostrar errores del formulario
            if venta_form.errors:
                for field, errors in venta_form.errors.items():
                    messages.error(request, f"Error en {field}: {', '.join(errors)}")

            if detalle_formset.errors:
                for i, form_errors in enumerate(detalle_formset.errors):
                    if form_errors:
                        for field, errors in form_errors.items():
                            messages.error(
                                request,
                                f"Error en detalle {i + 1}, {field}: {', '.join(errors)}",
                            )

    return render(
        request,
        "ventas/venta_form.html",
        {
            "venta_form": venta_form,
            "detalle_formset": detalle_formset,
            "productos": productos,
            "modo": "Editar",
        },
    )


@login_required
@grupo_requerido("admin", "cajero")
def venta_delete(request, pk):
    """
    Elimina una venta y devuelve el stock a los productos.
    """
    venta = get_object_or_404(Venta, pk=pk)

    if request.method == "POST":
        es_exitoso, mensaje = VentaService.eliminar_venta(venta)

        if es_exitoso:
            messages.success(request, "✅ Venta eliminada exitosamente")
            return redirect("venta_list")
        else:
            messages.error(request, f"❌ {mensaje}")
            return redirect("venta_detalle", pk=pk)

    return render(request, "ventas/venta_delete.html", {"venta": venta})


@login_required
@grupo_requerido("admin", "cajero")
def venta_detalle(request, pk):
    """
    Muestra el detalle completo de una venta.
    """
    venta = get_object_or_404(
        Venta.objects.select_related("Id_cliente").prefetch_related(
            Prefetch(
                "detalle_venta_set",
                queryset=Detalle_venta.objects.select_related("Id_producto"),
            )
        ),
        pk=pk,
    )
    detalles = venta.detalle_venta_set.all()

    return render(
        request,
        "ventas/venta_detalle.html",
        {
            "venta": venta,
            "detalles": detalles,
        },
    )


@login_required
@grupo_requerido("admin", "cajero")
def venta_cambiar_estado(request, pk, nuevo_estado):
    """
    Cambia el estado de una venta.
    Usa VentaService para manejar la lógica de devolución de stock si es necesario.
    """
    venta = get_object_or_404(Venta, pk=pk)

    es_exitoso, mensaje = VentaService.cambiar_estado_venta(venta, nuevo_estado)

    if es_exitoso:
        messages.success(request, f"✅ {mensaje}")
    else:
        messages.error(request, f"❌ {mensaje}")

    # Redirigir a la misma página con los mismos filtros
    referer = request.META.get("HTTP_REFERER", "")
    if referer:
        return redirect(referer)

    return redirect("venta_list")


@login_required
@grupo_requerido("admin", "cajero")
def importar_ventas(request):
    """
    Importa ventas desde un archivo CSV.
    """
    form = UploadCSVForm()

    if request.method == "POST":
        form = UploadCSVForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = form.cleaned_data["archivo_csv"]
            archivo.seek(0)

            try:
                contenido = archivo.read().decode("utf-8")
            except UnicodeDecodeError:
                archivo.seek(0)
                contenido = archivo.read().decode("latin-1")

            reader = csv.reader(io.StringIO(contenido))
            next(reader, None)  # Saltar encabezado

            errores = []
            ventas_importadas = 0
            clientes_creados = 0

            mapa_forma_pago = {
                "efectivo": "efectivo",
                "tarjeta": "tarjeta",
                "transferencia": "transferencia",
                "true": "efectivo",
                "1": "efectivo",
                "false": "tarjeta",
                "0": "tarjeta",
                "si": "efectivo",
                "sí": "efectivo",
            }

            mapa_estado = {
                "0": "pendiente",
                "1": "completada",
                "2": "cancelada",
                "pendiente": "pendiente",
                "completada": "completada",
                "cancelada": "cancelada",
            }

            mapa_tipo = {
                "contado": "menor",
                "tarjeta": "mayor",
                "transferencia": "mayor",
                "promocion": "promocion",
                "mayor": "mayor",
                "menor": "menor",
            }

            for lineno, row in enumerate(reader, start=2):
                try:
                    if len(row) < 6:
                        continue

                    id_cliente_raw = row[0].strip()
                    tipo_raw = row[1].strip()
                    precio_raw = row[2].strip()
                    forma_raw = row[3].strip().lower()
                    estado_raw = row[4].strip().lower()
                    fecha_raw = row[5].strip()

                    # Precio
                    precio_norm = precio_raw.replace(",", ".")
                    try:
                        precio = Decimal(precio_norm)
                    except InvalidOperation:
                        continue

                    # Forma de pago
                    forma_pago = mapa_forma_pago.get(forma_raw, forma_raw)

                    # Estado
                    estado = mapa_estado.get(estado_raw, "pendiente")

                    # Fecha
                    fecha_venta = None
                    if fecha_raw:
                        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                            try:
                                dt = datetime.strptime(fecha_raw, fmt)
                                if fmt == "%Y-%m-%d":
                                    dt = datetime.combine(dt.date(), datetime.min.time())
                                fecha_venta = timezone.make_aware(dt)
                                break
                            except ValueError:
                                continue

                    # Tipo
                    tipo_venta = mapa_tipo.get(tipo_raw.lower(), tipo_raw.lower())

                    with transaction.atomic():
                        # Cliente
                        if id_cliente_raw.isdigit():
                            id_cliente = int(id_cliente_raw)
                            cliente, creado = Cliente.objects.get_or_create(
                                pk=id_cliente,
                                defaults={"Nombre": f"Cliente {id_cliente}"},
                            )
                        else:
                            cliente, creado = Cliente.objects.get_or_create(
                                Nombre=id_cliente_raw or f"Cliente fila{lineno}"
                            )

                        if creado:
                            clientes_creados += 1

                        # Venta
                        Venta.objects.create(
                            Id_cliente=cliente,
                            Tipo_venta=tipo_venta,
                            Precio=precio,
                            Forma_pago=forma_pago,
                            Estado=estado,
                            Fecha_venta=fecha_venta,
                        )
                        ventas_importadas += 1

                except Exception:
                    continue

            # Mensajes
            if ventas_importadas > 0:
                messages.success(request, f"✅ {ventas_importadas} ventas cargadas correctamente.")

            if clientes_creados > 0:
                messages.info(request, f"ℹ️ {clientes_creados} clientes creados automáticamente.")

            return redirect("importar_ventas")

    return render(request, "ventas/importar_ventas.html", {"form": form})


# -------------------------
# PRODUCTOS
# -------------------------
# -------------------------
@login_required
@grupo_requerido('admin', 'despostador', 'inventario')
def producto_list(request):
    productos = Producto.objects.all().order_by('Corte')
    return render(request, 'productos/producto_list.html', {'productos': productos})

@login_required
@grupo_requerido('admin', 'despostador', 'inventario')
def producto_detalle(request, id_producto):
    producto = get_object_or_404(Producto, pk=id_producto)
    # Aseguramos que stock_kg siempre sea Decimal para evitar problemas en templates
    stock_kg = producto.stock_kg if getattr(producto, 'stock_kg', None) is not None else Decimal('0.00')
    return render(request, 'productos/producto_detail.html', {
        'producto': producto,
        'stock_kg': stock_kg,
    })
# -------------------------
# CREAR PRODUCTO
# -------------------------
def producto_create(request):
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            producto = form.save(commit=False)
            # asegurarse stock_kg tiene valor decimal
            if getattr(producto, 'stock_kg', None) in (None, ''):
                producto.stock_kg = Decimal('0.00')
            producto.save()
            messages.success(request, f"Producto '{producto.Corte}' creado correctamente.")
            return redirect('producto_list')
        else:
            # Mostrar errores en consola y en mensajes para debug
            print("Errores en ProductoForm:", form.errors)   # revisalo en la consola del servidor
            messages.error(request, "Hay errores en el formulario. Revisá los campos.")
    else:
        form = ProductoForm()
    return render(request, 'productos/producto_form.html', {'form': form, 'titulo': 'Crear Producto'})

def producto_update(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            producto = form.save(commit=False)
            if getattr(producto, 'stock_kg', None) in (None, ''):
                producto.stock_kg = Decimal('0.00')
            producto.save()
            nombre_display = producto.Corte if producto.Corte else producto.Nombre
            messages.success(request, f"Producto '{nombre_display}' actualizado correctamente.")
            return redirect('producto_list')
        else:
            print("Errores en ProductoForm (update):", form.errors)
            messages.error(request, "Hay errores en el formulario. Revisá los campos.")
    else:
        form = ProductoForm(instance=producto)
    return render(request, 'productos/producto_form.html', {'form': form, 'titulo': 'Editar Producto', 'producto': producto})

# -------------------------
# ELIMINAR PRODUCTO
# -------------------------
def producto_delete(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        producto.delete()
        nombre_display = producto.Corte if producto.Corte else producto.Nombre
        messages.success(request, f"Producto '{nombre_display}' eliminado correctamente.")
        return redirect('producto_list')
    return render(request, 'productos/producto_delete.html', {'producto': producto})


def importar_productos(request):
    form = UploadCSVForm()


    if request.method == "POST":
        form = UploadCSVForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = form.cleaned_data['archivo_csv']


            # Intentar primero con UTF-8
            try:
                decoded_file = archivo.read().decode("utf-8").splitlines()
            except UnicodeDecodeError:
                archivo.seek(0)
                decoded_file = archivo.read().decode("latin-1").splitlines()


            reader = csv.reader(decoded_file)
            next(reader, None)  # saltar encabezado


            for row in reader:
                if len(row) < 6:  # ajustar al número de columnas que esperás
                    continue
                try:
                    categoria = Categoria.objects.get(pk=row[0])


                    fecha_ingreso = None
                    fecha_venc = None

                    precio_mayor = Decimal(row[3]) if row[3].strip() else None

                    if len(row) > 6 and row[6]:
                        fecha_naive = datetime.strptime(row[6], "%Y-%m-%d %H:%M:%S")
                        fecha_ingreso = timezone.make_aware(fecha_naive)


                    if len(row) > 7 and row[7]:
                        fecha_naive_venc = datetime.strptime(row[7], "%Y-%m-%d")
                        fecha_venc = timezone.make_aware(datetime.combine(fecha_naive_venc, datetime.min.time()))


                    Producto.objects.create(
                        Id_categoria=categoria,
                        Corte=row[1],
                        Precio_kilo=Decimal(row[2]),
                        precio_mayor_x_kg=precio_mayor,
                        en_promocion=row[4].strip().lower() in ["true", "1", "sí", "si"],
                        stock_kg=int(row[5]),
                        fecha_ingreso_elaboracion=fecha_ingreso,
                        fecha_vencimiento=fecha_venc,
                        detalle=row[8] if len(row) > 8 else "",
                    )
                except Exception as e:
                    print(f"Error en fila {row}: {e}")


            messages.success(request, "Productos importados correctamente.")
            return redirect("importar_productos")  # usar el name de la URL


    return render(request, "productos/importar_productos.html", {"form": form})







# -------------------------
# PROVEEDORES
# -------------------------

@login_required
@grupo_requerido('admin', 'inventario')
def proveedor_list(request):
    from django.db.models import Sum, F, Value, DecimalField
    from django.db.models.functions import Coalesce

    proveedores_qs = Proveedores.objects.all()
    
    # Filtro por nombre
    nombre = request.GET.get('nombre', '')
    if nombre:
        proveedores_qs = proveedores_qs.filter(Nombre__icontains=nombre)
    
    # Filtro por email
    email = request.GET.get('email', '')
    if email:
        proveedores_qs = proveedores_qs.filter(Email__icontains=email)
    
    # Filtro por teléfono
    telefono = request.GET.get('telefono', '')
    if telefono:
        proveedores_qs = proveedores_qs.filter(Telefono__icontains=telefono)

    # Anotar totales de compras, pagos y deuda
    proveedores_qs = proveedores_qs.annotate(
        total_comprado=Coalesce(Sum('compra__Precio_total'), Value(Decimal('0.00')), output_field=DecimalField()),
        total_pagado=Coalesce(Sum('compra__monto_pagado'), Value(Decimal('0.00')), output_field=DecimalField()),
    )
    # Calcular deuda en Python (total_comprado - total_pagado)
    proveedores_list = []
    for p in proveedores_qs:
        p.deuda = p.total_comprado - p.total_pagado
        proveedores_list.append(p)
    
    return render(request, 'proveedores/proveedor_list.html', {'proveedor': proveedores_list})


def proveedor_detail(request, pk):
    """Vista detalle del proveedor: historial de compras, deuda, pagos."""
    proveedor = get_object_or_404(Proveedores, pk=pk)
    compras = Compra.objects.filter(Id_proveedor=proveedor).order_by('-Fecha_compra')

    total_comprado = compras.aggregate(
        total=Sum('Precio_total')
    )['total'] or Decimal('0.00')

    total_pagado = compras.aggregate(
        total=Sum('monto_pagado')
    )['total'] or Decimal('0.00')

    deuda_total = total_comprado - total_pagado

    return render(request, 'proveedores/proveedor_detail.html', {
        'proveedor': proveedor,
        'compras': compras,
        'total_comprado': total_comprado,
        'total_pagado': total_pagado,
        'deuda_total': deuda_total,
    })

def proveedores_detalle(request, id_proveedor):
    proveedor = get_object_or_404(Proveedores, id_proveedor=id_proveedor)
    return render(request, 'proveedores/proveedor_list.html', {'proveedor': proveedor})
def proveedor_create(request):
    if request.method == 'POST':
        form = ProvedorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '🎉 ¡Proveedor cargado exitosamente! 😊')
            return redirect('proveedor_list')
    else:
        form = ProvedorForm()
    return render(request, 'proveedores/proveedor_form.html', {
        'form': form,
        'titulo': 'Agregar Proveedor'
    })

def proveedor_update(request, pk):
    proveedor = get_object_or_404(Proveedores, pk=pk)
    if request.method == 'POST':
        form = ProvedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ ¡Proveedor actualizado exitosamente!')
            return redirect('proveedor_list')
    else:
        form = ProvedorForm(instance=proveedor)
    return render(request, 'proveedores/proveedor_form.html', {
        'form': form,
        'titulo': 'Editar Proveedor'
    })

def proveedor_delete(request, pk):
    proveedor = get_object_or_404(Proveedores, pk=pk)
    if request.method == 'POST':
        proveedor.delete()
        return redirect('proveedor_list')
    return render(request, 'proveedores/proveedor_delete.html', {'proveedor': proveedor})

from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.db import transaction


# -------------------------
# LIST
# -------------------------
@login_required
@grupo_requerido('admin', 'inventario')
def compra_list(request):
    compras = Compra.objects.all().order_by('-Fecha_compra')
    return render(request, 'compras/compra_list.html', {'compras': compras})


# -------------------------
# DETAIL
# -------------------------
@login_required
@grupo_requerido('admin', 'inventario')
def compra_detalle(request, pk):
    compra = get_object_or_404(Compra, pk=pk)
    return render(request, 'compras/compra_detalle.html', {'compra': compra})


# -------------------------
# CREATE
# -------------------------
@login_required
@grupo_requerido('admin', 'inventario')
def compra_carne_create(request):
    compra_form = CompraForm(request.POST or None)
    detalle_formset = DetalleCompraCarneFormSet(request.POST or None)

    if request.method == "POST":
        if compra_form.is_valid() and detalle_formset.is_valid():
            with transaction.atomic():
                compra = compra_form.save(commit=False)
                compra.Tipo_compra = 'CARNE'
                compra.Precio_total = Decimal('0.00')
                compra.save()

                total_compra = Decimal('0.00')
                for form in detalle_formset:
                    data = form.cleaned_data
                    if not data or data.get('DELETE', False):
                        continue

                    insumo = data.get('Id_insumo')     # instancia Insumo (tipo=carne)
                    cantidad = _to_decimal(data.get('Cantidad') or 0)
                    precio_total = _to_decimal(data.get('Precio_total') or 0)

                    # crear detalle
                    Detalle_compra.objects.create(
                        Id_compra=compra,
                        Id_insumo=insumo,
                        Cantidad=cantidad,
                        Precio_total=precio_total,
                    )

                    # actualizar stock en el insumo
                    if insumo:
                        aumentar_stock(insumo, cantidad)

                    total_compra += precio_total

                compra.Precio_total = total_compra
                compra.save()

            messages.success(request, f'✅ Compra de carne #{compra.Id_compra} guardada exitosamente. Total: ${total_compra}')
            return redirect('compra_list')
        else:
            print("Errores en compra_form:", compra_form.errors)
            print("Errores en detalle_formset:", detalle_formset.errors)

    return render(request, 'compras/compra_carne_form.html', {
        'form': compra_form,
        'detalle_formset': detalle_formset,
        'titulo': 'Agregar Compra de Carne'
    })


@login_required
@grupo_requerido('admin', 'inventario')
def compra_insumo_create(request):
    compra_form = CompraForm(request.POST or None)
    detalle_formset = DetalleCompraInsumoFormSet(request.POST or None)
    
    if request.method == "POST" and compra_form.is_valid() and detalle_formset.is_valid():
        with transaction.atomic():
            compra = compra_form.save(commit=False)
            compra.Tipo_compra = 'INSUMO'
            compra.Precio_total = Decimal('0.00')
            compra.save()

            total_compra = Decimal('0.00')

            for form in detalle_formset:
                data = form.cleaned_data
                if not data or data.get('DELETE', False):
                    continue

                insumo = data.get('Id_insumo')
                cantidad = _to_decimal(data.get('Cantidad') or 0)
                precio_total = _to_decimal(data.get('Precio_total') or 0)
                producto_elegido = data.get('producto_asociado')

                # Crear detalle
                Detalle_compra.objects.create(
                    Id_compra=compra,
                    Id_insumo=insumo,
                    Cantidad=cantidad,
                    Precio_total=precio_total,
                )

                # Aumentar stock del insumo
                if insumo:
                    insumo.Cantidad = (insumo.Cantidad or 0) + cantidad
                    insumo.save()

                # 🔹 NUEVO: si eligieron producto asociado, aumentar su stock
                if producto_elegido:
                    cantidad = Decimal(cantidad or 0)

                    producto_elegido.stock_kg = (producto_elegido.stock_kg or Decimal("0")) + cantidad
                    producto_elegido.save()

            compra.Precio_total = total_compra
            compra.save()

        return redirect('compra_list')

    return render(request, 'compras/compra_insumo_form.html', {
        'form': compra_form,
        'detalle_formset': detalle_formset,
        'titulo': 'Agregar Compra de Insumo'
    })

   
@login_required
@grupo_requerido('admin', 'inventario')
def compra_update(request, pk):
    compra = get_object_or_404(Compra, pk=pk)
    compra_form = CompraForm(request.POST or None, instance=compra)

    # Elegir formset según tipo de compra
    if compra.Tipo_compra == 'CARNE':
        DetalleFormSetClass = DetalleCompraCarneFormSet
    else:
        DetalleFormSetClass = DetalleCompraInsumoFormSet

    detalle_formset = DetalleFormSetClass(request.POST or None, instance=compra)

    if request.method == "POST":
        if compra_form.is_valid() and detalle_formset.is_valid():
            with transaction.atomic():
                # 1) RESTAR del stock las cantidades actuales de los detalles persistidos
                for det_old in Detalle_compra.objects.filter(Id_compra=compra):
                    if getattr(det_old, 'Id_insumo', None):
                        disminuir_stock(det_old.Id_insumo, det_old.Cantidad)

                # 2) Guardar cambios en la compra
                compra = compra_form.save(commit=False)
                compra.save()

                # 3) Procesar TODOS los formularios del formset (nuevos y existentes)
                for form in detalle_formset.forms:
                    if form in detalle_formset.deleted_forms:
                        continue
                    if not form.has_changed() and not form.instance.pk:
                        continue
                    if form.is_valid():
                        det = form.save(commit=False)
                        det.Id_compra = compra
                        det.save()

                        # Aumentar stock en el insumo
                        if getattr(det, 'Id_insumo', None):
                            aumentar_stock(det.Id_insumo, det.Cantidad)

                # 4) Eliminar los marcados para borrar (stock ya se restó en paso 1)
                for form in detalle_formset.deleted_forms:
                    det = form.instance
                    if det.pk:
                        det.delete()

                # 5) Calcular total sumando TODOS los detalles de la compra
                total_compra = Decimal('0.00')
                for det in Detalle_compra.objects.filter(Id_compra=compra):
                    total_compra += _to_decimal(det.Precio_total)
                
                compra.Precio_total = total_compra
                compra.save()

            messages.success(request, f'✅ Compra #{compra.Id_compra} actualizada. Total: ${total_compra}')
            return redirect('compra_list')

    # GET o formulario inválido -> renderizar
    return render(request, 'compras/compra_carne_form.html' if compra.Tipo_compra == 'CARNE' else 'compras/compra_insumo_form.html', {
        'form': compra_form,
        'detalle_formset': detalle_formset,
        'titulo': f'Editar Compra ({compra.Tipo_compra})'
    })


# -------------------------
# DELETE
# -------------------------
@login_required
@grupo_requerido('admin', 'inventario')
def compra_delete(request, pk):
    compra = get_object_or_404(Compra, pk=pk)
    if request.method == 'POST':
        with transaction.atomic():
            # Restar stock según los detalles
            for det in Detalle_compra.objects.filter(Id_compra=compra):
                if getattr(det, 'Id_insumo', None):
                    disminuir_stock(det.Id_insumo, det.Cantidad)
            # Borrar compra (y por cascada los detalles)
            compra.delete()
        return redirect('compra_list')

    return render(request, 'compras/compra_delete.html', {'compra': compra})



# -----------------------------
# Lista de despostes
# -----------------------------
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Desposte, CorteDesposte, Producto, Categoria
from .forms import DesposteForm, CorteDesposteFormSet

# -----------------------------
# Lista de despostes
# -----------------------------

# LIST
# LIST
@login_required
@grupo_requerido('admin', 'despostador')
def desposte_list(request):
    despostes = Desposte.objects.all().order_by('-Fecha')
    
    # Filtro por ID
    desposte_id = request.GET.get('id', '')
    if desposte_id:
        despostes = despostes.filter(Id_desposte=desposte_id)
    
    # Filtro por insumo de carne
    insumo_nombre = request.GET.get('insumo', '')
    if insumo_nombre:
        despostes = despostes.filter(Id_insumo__nombre__icontains=insumo_nombre)
    
    # Filtro por rango de peso (Peso_inicial)
    rango_peso = request.GET.get('rango_peso', '')
    if rango_peso:
        if rango_peso == '0-10':
            despostes = despostes.filter(Peso_inicial__gte=0, Peso_inicial__lte=10)
        elif rango_peso == '10-50':
            despostes = despostes.filter(Peso_inicial__gt=10, Peso_inicial__lte=50)
        elif rango_peso == '50-100':
            despostes = despostes.filter(Peso_inicial__gt=50, Peso_inicial__lte=100)
        elif rango_peso == '100':
            despostes = despostes.filter(Peso_inicial__gt=100)
    
    # Filtro por fecha
    fecha = request.GET.get('fecha', '')
    if fecha:
        despostes = despostes.filter(Fecha__date=fecha)
    
    return render(request, 'despostes/desposte_list.html', {'despostes': despostes})


# CREATE
def desposte_create(request):
    if request.method == 'POST':
        desposte_form = DesposteForm(request.POST)
        if desposte_form.is_valid():
            # Los clean() del form ya validaron Unidades y Peso_inicial (A y B)
            desposte = desposte_form.save(commit=False)

            # Normalizar valores
            try:
                unidades = int(desposte.Unidades or 1)
            except (TypeError, ValueError):
                messages.error(request, "Unidades inválidas.")
                return render(request, 'despostes/desposte_form.html', {'form': desposte_form})

            try:
                peso_inicial = Decimal(str(desposte.Peso_inicial or '0.00'))
            except (TypeError, InvalidOperation):
                messages.error(request, "Peso inicial inválido.")
                return render(request, 'despostes/desposte_form.html', {'form': desposte_form})

            # Bloqueo y transacción para evitar race conditions al descontar unidades
            insumo = get_object_or_404(Insumo, pk=desposte.Id_insumo.pk)
            with transaction.atomic():
                insumo = Insumo.objects.select_for_update().get(pk=insumo.pk)
                if insumo.Cantidad < unidades:
                    messages.error(request, f"No hay suficiente stock del insumo {insumo.nombre}. Disponible: {insumo.Cantidad}")
                    return render(request, 'despostes/desposte_form.html', {'form': desposte_form})

                # Descontar unidades del insumo
                insumo.Cantidad = F('Cantidad') - unidades
                insumo.save()
                insumo.refresh_from_db()

                # Guardar el desposte (sin cortes todavía)
                desposte.Unidades = unidades
                desposte.Peso_inicial = peso_inicial
                desposte.save()

            return redirect('desposte_add_cortes', desposte_id=desposte.Id_desposte)
        else:
            # Los errores de validación aparecerán en el form
            messages.error(request, "Hay errores en el formulario. Revisalos.")
    else:
        desposte_form = DesposteForm()

    return render(request, 'despostes/desposte_form.html', {'form': desposte_form})


# ADD CORTES
def desposte_add_cortes(request, desposte_id):
    desposte = get_object_or_404(Desposte, pk=desposte_id)
    formset = CorteDesposteFormSet(
    request.POST or None,
    instance=desposte,
    form_kwargs={'desposte': desposte}
)
    if request.method == "POST":
        if formset.is_valid():
            # El formset (BaseCorteDesposteFormSet) ya validó la Regla C (suma cortes <= peso inicial).
            # Ahora aplicamos cambios al stock en una transacción controlada.
            # Preparamos los objetos a guardar
            cortes_objs = formset.save(commit=False)  # nuevos y editados
            # Productos involucrados (tanto de cortes nuevos/actualizados como de eliminados)
            producto_pks = set()
            for corte in cortes_objs:
                if corte.Id_producto:
                    producto_pks.add(corte.Id_producto.pk)
            for obj in formset.deleted_objects:
                if obj.Id_producto:
                    producto_pks.add(obj.Id_producto.pk)

            with transaction.atomic():
                # Bloqueamos los productos que vamos a modificar
                productos = {p.pk: p for p in Producto.objects.select_for_update().filter(pk__in=producto_pks)}

                # 1) Manejar eliminaciones: restar del stock los pesos de cortes eliminados
                for obj in formset.deleted_objects:
                    prod = productos.get(obj.Id_producto.pk) or Producto.objects.select_for_update().get(pk=obj.Id_producto.pk)
                    cantidad_rest = Decimal(str(obj.Peso or 0))
                    # Convertir kg → gramos si el producto usa KG
                    if prod.unidad_medida == 'KG':
                        cantidad_rest = Producto.kg_a_gramos(cantidad_rest)
                    prod.stock_kg = (prod.stock_kg or Decimal('0.00')) - cantidad_rest
                    if prod.stock_kg < 0:
                        prod.stock_kg = Decimal('0.00')
                    prod.save()
                    # el objeto en DB será eliminado por formset.save() si corresponde (aquí lo eliminamos manualmente)
                    # pero para seguridad lo eliminamos:
                    try:
                        obj.delete()
                    except Exception:
                        # si ya fue eliminado o no tiene pk, continue
                        pass

                # 2) Guardar cortes nuevos/actualizados y sumar sus pesos al stock
                total_peso_cortes = Decimal('0.00')
                for corte in cortes_objs:
                    # asegurar peso en Decimal
                    try:
                        peso = Decimal(str(corte.Peso or '0.00'))
                    except (TypeError, InvalidOperation):
                        peso = Decimal('0.00')
                    corte.Peso = peso

                    prod = productos.get(corte.Id_producto.pk) or Producto.objects.select_for_update().get(pk=corte.Id_producto.pk)
                    # Convertir kg → gramos si el producto usa KG
                    peso_interno = Producto.kg_a_gramos(peso) if prod.unidad_medida == 'KG' else peso
                    prod.stock_kg = (prod.stock_kg or Decimal('0.00')) + peso_interno
                    prod.save()

                    corte.Id_desposte = desposte
                    corte.save()

                    total_peso_cortes += peso

                # 3) Guardar merma y desposte
                peso_inicial = Decimal(str(desposte.Peso_inicial or '0.00'))
                # Nota: la validación de total_peso_cortes <= peso_inicial ya se hizo en el formset,
                # pero la comprobamos nuevamente por seguridad
                if total_peso_cortes > peso_inicial:
                    # Si esto ocurre, revertimos la transacción (se hace automáticamente al lanzar excepción)
                    messages.error(request, "La suma de los pesos de los cortes supera el peso inicial. No se guardó.")
                    raise ValueError("Suma pesos > peso_inicial (inconsistencia)")

                desposte.Merma = peso_inicial - total_peso_cortes
                desposte.save()

            messages.success(request, f"Desposte guardado. Merma: {desposte.Merma} kg")
            return redirect('desposte_list')
        else:
            # formset no válido: errores aparecerán en formset
            messages.error(request, "Hay errores en los cortes. Revisá los formularios.")

    return render(request, 'despostes/desposte_add_cortes.html', {
        'desposte': desposte,
        'formset': formset
    })


# UPDATE (edita desposte y cortes en la misma vista; aplica deltas al stock)
def desposte_update(request, desposte_id):
    desposte = get_object_or_404(Desposte, pk=desposte_id)
    form = DesposteForm(request.POST or None, instance=desposte)
    formset = CorteDesposteFormSet(request.POST or None, instance=desposte)

    if request.method == 'POST':
        if form.is_valid() and formset.is_valid():
            nuevo_desposte = form.save(commit=False)
            # validar peso inicial (ya hecho en form.clean_Peso_inicial) y suma cortes (formset)
            try:
                nuevo_peso_inicial = Decimal(str(nuevo_desposte.Peso_inicial or '0.00'))
            except (TypeError, InvalidOperation):
                messages.error(request, "Peso inicial inválido.")
                return redirect('desposte_update', desposte_id=desposte.Id_desposte)

            # Preparamos mapas previos y nuevos por producto para calcular deltas
            prev_cortes = list(desposte.cortes.select_related('Id_producto').all())
            prev_map = {}
            for c in prev_cortes:
                prev_map[c.Id_producto.pk] = prev_map.get(c.Id_producto.pk, Decimal('0.00')) + Decimal(str(c.Peso or 0))

            nuevos_map = {}
            # recorrer cleaned_data del formset para sumar pesos (excluye deletions)
            for f in formset:
                cd = getattr(f, 'cleaned_data', None)
                if not cd:
                    continue
                if cd.get('DELETE', False):
                    continue
                prod = cd.get('Id_producto')
                peso = Decimal(str(cd.get('Peso') or 0))
                nuevos_map[prod.pk] = nuevos_map.get(prod.pk, Decimal('0.00')) + peso

            all_product_pks = set(list(prev_map.keys()) + list(nuevos_map.keys()))
            with transaction.atomic():
                productos = {p.pk: p for p in Producto.objects.select_for_update().filter(pk__in=all_product_pks)}

                # Aplicar deltas por producto
                for pk in all_product_pks:
                    prod = productos.get(pk)
                    if not prod:
                        continue
                    prev_sum = prev_map.get(pk, Decimal('0.00'))
                    new_sum = nuevos_map.get(pk, Decimal('0.00'))
                    delta = new_sum - prev_sum
                    # Convertir kg → gramos si el producto usa KG
                    if prod.unidad_medida == 'KG':
                        delta = Producto.kg_a_gramos(delta) if delta >= 0 else -Producto.kg_a_gramos(abs(delta))
                    prod.stock_kg = (prod.stock_kg or Decimal('0.00')) + delta
                    if prod.stock_kg < 0:
                        prod.stock_kg = Decimal('0.00')
                    prod.save()

                # Guardar desposte y cortes
                nuevo_desposte.save()
                formset.save()

            messages.success(request, "Desposte actualizado correctamente")
            return redirect('desposte_list')
        else:
            messages.error(request, "Errores en formulario o cortes. Revisá los datos.")
    return render(request, 'despostes/desposte_form.html', {'form': form, 'formset': formset, 'update': True})


# DELETE
def desposte_delete(request, desposte_id):
    desposte = get_object_or_404(Desposte, pk=desposte_id)
    if request.method == 'POST':
        with transaction.atomic():
            # Restaurar unidades en el insumo de carne
            insumo = Insumo.objects.select_for_update().get(pk=desposte.Id_insumo.pk)
            insumo.Cantidad = F('Cantidad') + desposte.Unidades
            insumo.save()
            insumo.refresh_from_db()

            # Restar stock_kg de productos usados en los cortes
            productos_pks = [c.Id_producto.pk for c in desposte.cortes.all()]
            productos = {p.pk: p for p in Producto.objects.select_for_update().filter(pk__in=productos_pks)}

            for corte in desposte.cortes.all():
                prod = productos.get(corte.Id_producto.pk)
                if not prod:
                    continue
                cantidad_rest = Decimal(str(corte.Peso or 0))
                # Convertir kg → gramos si el producto usa KG
                if prod.unidad_medida == 'KG':
                    cantidad_rest = Producto.kg_a_gramos(cantidad_rest)
                prod.stock_kg = (prod.stock_kg or Decimal('0.00')) - cantidad_rest
                if prod.stock_kg < 0:
                    prod.stock_kg = Decimal('0.00')
                prod.save()

            desposte.delete()

        messages.success(request, "Desposte eliminado correctamente")
        return redirect('desposte_list')

    return render(request, 'despostes/desposte_confirm_delete.html', {'desposte': desposte})
# =============================================================================
# VISTAS PARA GESTIÓN DE INSUMOS
# =============================================================================

# -------------------------\n# VISTAS PARA GESTIÓN DE INSUMOS
# -------------------------

@login_required
@grupo_requerido('admin', 'despostador', 'inventario')
def insumo_list_view(request):
    """Lista todos los insumos con alerta de stock bajo"""
    insumos = Insumo.objects.all().order_by('nombre')
    
    # Filtro por nombre
    nombre = request.GET.get('nombre', '')
    if nombre:
        insumos = insumos.filter(nombre__icontains=nombre)
    
    # Filtro por tipo (campo: tipo)
    tipo = request.GET.get('tipo', '')
    if tipo:
        insumos = insumos.filter(tipo=tipo)
    
    # Filtro por stock
    stock_filtro = request.GET.get('stock', '')
    if stock_filtro == 'bajo':
        insumos = insumos.filter(Cantidad__gt=0, Cantidad__lt=100)
    elif stock_filtro == 'sin':
        insumos = insumos.filter(Cantidad__lte=0)
    
    # Insumos con stock bajo para la alerta superior
    insumos_stock_bajo = Insumo.objects.filter(Cantidad__lt=100, Cantidad__gt=0).order_by('Cantidad')
    
    return render(
        request,
        'insumos/insumo_list.html',
        {
            'insumos': insumos,
            'insumos_stock_bajo': insumos_stock_bajo,
        }
    )
def insumo_create_view(request):
    """Crear nuevo insumo"""
    if request.method == 'POST':
        form = InsumoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('insumo_list')
    else:
        form = InsumoForm()
    
    return render(request, 'insumos/insumo_form.html', {
        'form': form,
        'titulo': 'Agregar Nuevo Insumo'
    })

def insumo_update_view(request, pk):
    """Actualizar insumo existente"""
    insumo_item = get_object_or_404(Insumo, pk=pk)
    
    if request.method == 'POST':
        form = InsumoForm(request.POST, instance=insumo_item)
        if form.is_valid():
            form.save()
            return redirect('insumo_list')
    else:
        form = InsumoForm(instance=insumo_item)
    
    return render(request, 'insumos/insumo_form.html', {
        'form': form,
        'titulo': f'Editar Insumo: {insumo_item.nombre}'
    })

def insumo_delete_view(request, pk):
    """Eliminar insumo"""
    insumo_item = get_object_or_404(Insumo, pk=pk)
    
    if request.method == 'POST':
        insumo_item.delete()
        return redirect('insumo_list')
    
    return render(request, 'insumos/insumo_delete.html', {'insumo': insumo_item})

def insumo_detail_view(request, pk):
    """Ver detalle de insumo con historial de compras."""
    insumo_item = get_object_or_404(Insumo, pk=pk)

    # Historial de compras de este insumo
    detalles_compra = (
        Detalle_compra.objects
        .filter(Id_insumo=insumo_item)
        .select_related('Id_compra', 'Id_compra__Id_proveedor')
        .order_by('-Id_compra__Fecha_compra')
    )

    return render(request, 'insumos/insumo_detail.html', {
        'insumo': insumo_item,
        'detalles_compra': detalles_compra,
    })

# -------------------------
# VISTA PARA COMPRAS DE INSUMOS (Replica exacta de la lógica de carne)
# -------------------------
def insumo_purchase_create_view(request):
    """Crear compra de insumos"""

    compra_form = CompraForm(request.POST or None)
    detalle_formset = InsumoPurchaseDetailFormSet(request.POST or None)

    if request.method == "POST":
        if compra_form.is_valid() and detalle_formset.is_valid():
            with transaction.atomic():

                compra = compra_form.save(commit=False)
                compra.Tipo_compra = 'INSUMO'
                compra.Precio_total = Decimal('0.00')
                compra.save()

                total_compra = Decimal('0.00')

                for form in detalle_formset:
                    data = form.cleaned_data
                    if not data or data.get('DELETE', False):
                        continue

                    insumo_item = data.get('Id_insumo')  # instancia Insumo
                    cantidad = _to_decimal(data.get('Cantidad') or 0)
                    precio_total = data.get('Precio_total') or Decimal('0.00')

                    try:
                        precio_total = _to_decimal(precio_total)
                    except:
                        precio_total = Decimal('0.00')

                    # Crear detalle
                    Detalle_compra.objects.create(
                        Id_compra=compra,
                        Id_insumo=insumo_item,
                        Cantidad=cantidad,
                        Precio_total=precio_total
                    )

                    # Actualizar stock
                    aumentar_stock_insumo(insumo_item, cantidad)
                    total_compra += precio_total

                compra.Precio_total = total_compra
                compra.save()

            return redirect('compra_list')

    return render(request, 'insumos/insumo_purchase_form.html', {
        'form': compra_form,
        'detalle_formset': detalle_formset,
        'titulo': 'Agregar Compra de Insumos'
    })
def aumentar_stock_insumo(insumo_obj, cantidad):
    if insumo_obj is None:
        return

    current = insumo_obj.Cantidad or 0
    insumo_obj.Cantidad = _to_decimal(current) + _to_decimal(cantidad)
    insumo_obj.save()


def disminuir_stock_insumo(insumo_obj, cantidad):
    if insumo_obj is None:
        return

    current = insumo_obj.Cantidad or 0
    insumo_obj.Cantidad = _to_decimal(current) - _to_decimal(cantidad)
    insumo_obj.save()
# =============================================================================
# API HELPERS - Unidades de Medida por Categoría
# =============================================================================
from django.http import JsonResponse

def get_unidades_por_categoria(request, categoria_id):
    """API endpoint para obtener las unidades de medida permitidas por una categoría"""
    try:
        categoria = Categoria.objects.get(Id_categoria=categoria_id)
        unidades_disponibles = categoria.get_unidades_disponibles()
        return JsonResponse({
            'success': True,
            'unidades': [{'codigo': codigo, 'nombre': nombre} for codigo, nombre in unidades_disponibles],
            'categoria': categoria.Categoria
        })
    except Categoria.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Categoría no encontrada'
        }, status=404)

# =============================================================================
# VISTAS DE PROMOCIONES
# =============================================================================
from .models import Promociones
from .forms import PromocionForm, PromocionBusquedaForm
from django.db.models import Q

@login_required
@grupo_requerido('admin', 'cajero')
def promocion_list(request):
    """Lista de promociones con búsqueda y filtros"""
    promociones = Promociones.objects.select_related('Id_producto').all()
    form = PromocionBusquedaForm(request.GET or None)
    
    # Aplicar filtros si el formulario es válido
    if form.is_valid():
        busqueda = form.cleaned_data.get('busqueda')
        producto = form.cleaned_data.get('producto')
        estado = form.cleaned_data.get('estado')
        tipo_promocion = form.cleaned_data.get('tipo_promocion')
        fecha_desde = form.cleaned_data.get('fecha_desde')
        fecha_hasta = form.cleaned_data.get('fecha_hasta')
        
        # Filtro de búsqueda por nombre de producto
        if busqueda:
            promociones = promociones.filter(
                Q(Id_producto__Corte__icontains=busqueda) |
                Q(descripcion__icontains=busqueda)
            )
        
        # Filtro por producto específico
        if producto:
            promociones = promociones.filter(Id_producto=producto)
        
        # Filtro por estado
        if estado:
            promociones = promociones.filter(estado=estado)
        
        # Filtro por tipo de promoción
        if tipo_promocion:
            promociones = promociones.filter(tipo_promocion=tipo_promocion)
        
        # Filtro por rango de fechas
        if fecha_desde:
            promociones = promociones.filter(Fecha_inicio__gte=fecha_desde)
        
        if fecha_hasta:
            promociones = promociones.filter(Fecha_fin__lte=fecha_hasta)
    
    # Actualizar estados automáticamente basándose en fechas
    actualizar_estados_promociones()
    
    return render(request, 'promociones/promocion_list.html', {
        'promociones': promociones,
        'form': form,
    })

def actualizar_estados_promociones():
    """Actualiza automáticamente el estado de las promociones basándose en las fechas"""
    now = timezone.now()
    
    # Marcar como vencidas las promociones que terminaron
    Promociones.objects.filter(
        Fecha_fin__lt=now,
        estado__in=['activa', 'programada']
    ).update(estado='vencida')
    
    # Activar promociones programadas que ya iniciaron
    Promociones.objects.filter(
        Fecha_inicio__lte=now,
        Fecha_fin__gte=now,
        estado='programada'
    ).update(estado='activa')

def promocion_create(request):
    """Crear una nueva promoción"""
    if request.method == 'POST':
        form = PromocionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Promoción creada exitosamente.')
            return redirect('promocion_list')
    else:
        form = PromocionForm()
    
    return render(request, 'promociones/promocion_form.html', {
        'form': form,
        'titulo': 'Nueva Promoción',
        'modo': 'Crear'
    })

def promocion_update(request, pk):
    """Editar una promoción existente"""
    promocion = get_object_or_404(Promociones, pk=pk)
    
    if request.method == 'POST':
        form = PromocionForm(request.POST, instance=promocion)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Promoción actualizada exitosamente.')
            return redirect('promocion_list')
    else:
        form = PromocionForm(instance=promocion)
    
    return render(request, 'promociones/promocion_form.html', {
        'form': form,
        'titulo': 'Editar Promoción',
        'modo': 'Editar',
        'promocion': promocion
    })

def promocion_delete(request, pk):
    """Eliminar una promoción"""
    promocion = get_object_or_404(Promociones, pk=pk)
    
    if request.method == 'POST':
        promocion.delete()
        messages.success(request, '✅ Promoción eliminada exitosamente.')
        return redirect('promocion_list')
    
    return render(request, 'promociones/promocion_delete.html', {
        'promocion': promocion
    })

def promocion_detalle(request, pk):
    """Ver detalles de una promoción"""
    promocion = get_object_or_404(Promociones, pk=pk)
    
    return render(request, 'promociones/promocion_detalle.html', {
        'promocion': promocion
    })


# =========================
# VISTAS: Receta y Producción
# =========================
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, get_object_or_404, redirect
from django.db import transaction
from django.contrib import messages

# modelos y forms nuevos
from .models import Receta, RecetaItem, Produccion, ProduccionDetalle, Producto, Insumo
from .forms import RecetaForm, RecetaItemFormSet, ProduccionForm, ProduccionConfirmForm


def receta_list(request):
    recetas = Receta.objects.all().order_by('-fecha_creacion')
    return render(request, 'produccion/receta_list.html', {'recetas': recetas})


def receta_create(request):
    """
    Crear receta + sus items via inline formset (RecetaForm + RecetaItemFormSet)
    """
    if request.method == 'POST':
        form = RecetaForm(request.POST)
        formset = RecetaItemFormSet(request.POST)
        try:
            if form.is_valid() and formset.is_valid():
                with transaction.atomic():
                    receta = form.save()
                    # guardar items enlazados
                    items = formset.save(commit=False)
                    for it in items:
                        it.receta = receta
                        it.save()
                    # borrar items marcados para eliminar (si los hubiera en edit, aquí no aplica pero por si)
                    for obj in getattr(formset, 'deleted_objects', []):
                        obj.delete()
                messages.success(request, f"Receta '{receta.nombre}' creada correctamente.")
                return redirect('receta_list')
            else:
                messages.error(request, "Corrige los errores del formulario de receta.")
        except Exception as e:
            # capturar excepciones para debugging y mostrar mensaje amigable
            import traceback; traceback.print_exc()
            messages.error(request, f"Error al crear la receta: {e}")
    else:
        form = RecetaForm()
        formset = RecetaItemFormSet()

    return render(request, 'produccion/receta_form.html', {
        'form': form,
        'formset': formset,
        'titulo': 'Crear Receta'
    })


def receta_update(request, pk):
    receta = get_object_or_404(Receta, pk=pk)
    if request.method == 'POST':
        form = RecetaForm(request.POST, instance=receta)
        formset = RecetaItemFormSet(request.POST, instance=receta)
        try:
            if form.is_valid() and formset.is_valid():
                with transaction.atomic():
                    receta = form.save()
                    items = formset.save(commit=False)
                    for it in items:
                        it.receta = receta
                        it.save()
                    for obj in getattr(formset, 'deleted_objects', []):
                        obj.delete()
                messages.success(request, f"Receta '{receta.nombre}' actualizada.")
                return redirect('receta_list')
            else:
                # Debug: mostrar errores
                if form.errors:
                    for field, errors in form.errors.items():
                        for err in errors:
                            messages.error(request, f"Formulario {field}: {err}")
                if formset.errors:
                    for i, form_errors in enumerate(formset.errors):
                        for field, errors in form_errors.items():
                            for err in errors:
                                messages.error(request, f"Ingrediente {i+1} {field}: {err}")
                if formset.non_form_errors():
                    for err in formset.non_form_errors():
                        messages.error(request, f"Formset: {err}")
                messages.error(request, "Corrige los errores del formulario.")
        except Exception as e:
            import traceback; traceback.print_exc()
            messages.error(request, f"Error al actualizar la receta: {e}")
    else:
        form = RecetaForm(instance=receta)
        formset = RecetaItemFormSet(instance=receta)

    return render(request, 'produccion/receta_form.html', {
        'form': form,
        'formset': formset,
        'titulo': 'Editar Receta',
        'receta': receta
    })


def receta_delete(request, pk):
    receta = get_object_or_404(Receta, pk=pk)
    if request.method == 'POST':
        receta.delete()
        messages.success(request, "Receta eliminada.")
        return redirect('receta_list')
    return render(request, 'produccion/receta_confirm_delete.html', {'receta': receta})


def receta_detail(request, pk):
    receta = get_object_or_404(Receta, pk=pk)
    items = receta.items.select_related('insumo', 'producto').all()
    return render(request, 'produccion/receta_detail.html', {'receta': receta, 'items': items})


# =========================
# VISTAS PARA PRODUCCIÓN
# =========================


def produccion_list(request):
    producciones = Produccion.objects.all().order_by('-fecha')
    return render(request, 'produccion/produccion_list.html', {'producciones': producciones})


def produccion_create(request):
    """
    Crear una producción en estado 'borrador'. Luego el usuario revisa el resumen y confirma.
    """
    if request.method == 'POST':
        form = ProduccionForm(request.POST)
        if form.is_valid():
            # Validar que la receta tenga producto final vinculado
            receta = form.cleaned_data.get('receta')
            if not receta or not receta.producto_final:
                messages.error(request, "⚠️ La receta seleccionada no tiene un producto final vinculado. Por favor, edita la receta primero.")
                return redirect('receta_list')
            
            produccion = form.save(commit=False)
            produccion.estado = 'borrador'
            if request.user.is_authenticated:
                produccion.usuario = request.user
            produccion.save()
            messages.success(request, "Producción guardada como borrador. Revisá y confirmá.")
            return redirect('produccion_summary', pk=produccion.pk)
        else:
            messages.error(request, "Corrige los errores del formulario de producción.")
    else:
        form = ProduccionForm()

    return render(request, 'produccion/produccion_form.html', {
        'form': form,
        'titulo': 'Registrar Producción'
    })


def produccion_summary(request, pk):
    """
    Muestra el resumen de la producción (cantidades necesarias por ingrediente y stock disponible).
    Desde aquí se puede confirmar (POST con ProduccionConfirmForm) para ejecutar la transacción.
    """
    produccion = get_object_or_404(Produccion, pk=pk)
    
    # Validar que la receta tenga producto final
    if not produccion.receta or not produccion.receta.producto_final:
        messages.error(request, "⚠️ La receta no tiene un producto final vinculado. Edita la receta primero.")
        return redirect('produccion_list')
    
    resumen = produccion.cantidades_necesarias()  # lista de (RecetaItem, cantidad_req)
    faltantes = []
    detalles_muestra = []

    for ri, req in resumen:
        if ri.insumo:
            stock = getattr(ri.insumo, 'Cantidad', Decimal('0.00'))
            nombre = ri.insumo.nombre
            unidad = ri.insumo.get_unidad_medida_display()
        else:
            stock = getattr(ri.producto, 'stock_kg', Decimal('0.00'))
            nombre = ri.producto.Corte
            unidad = ri.producto.get_unidad_medida_display()
        diff = Decimal(stock) - Decimal(req)
        detalles_muestra.append({
            'nombre': nombre, 
            'requerido': req, 
            'stock': stock, 
            'sobrante': diff,
            'unidad': unidad
        })
        if diff < 0:
            faltantes.append(f"{nombre}: disponible {stock} {unidad.lower()} - requerido {req} {unidad.lower()}")

    # Form para confirmar
    if request.method == 'POST':
        confirm_form = ProduccionConfirmForm(request.POST)
        if confirm_form.is_valid() and confirm_form.cleaned_data.get('confirmar'):
            try:
                with transaction.atomic():
                    # llamar al método del modelo que aplica los cambios (ya maneja select_for_update)
                    produccion.confirmar(usuario=request.user if request.user.is_authenticated else None)
                messages.success(request, "✓ Producción confirmada y stock actualizado.")
                return redirect('produccion_list')
            except Exception as e:
                messages.error(request, f"❌ Error al confirmar: {str(e)}")
        else:
            if confirm_form.errors:
                messages.error(request, "⚠️ Por favor marca la casilla de confirmación.")
    else:
        confirm_form = ProduccionConfirmForm()

    return render(request, 'produccion/produccion_summary.html', {
        'produccion': produccion,
        'detalles': detalles_muestra,
        'faltantes': faltantes,
        'confirm_form': confirm_form
    })


def produccion_detail(request, pk):
    produccion = get_object_or_404(Produccion, pk=pk)
    detalles = produccion.detalles.select_related().all()
    return render(request, 'produccion/produccion_detail.html', {
        'produccion': produccion,
        'detalles': detalles
    })


def produccion_delete(request, pk):
    produccion = get_object_or_404(Produccion, pk=pk)
    # Solo permitir borrar si está en borrador (o si sos admin y querés manejar reversión manual)
    if request.method == 'POST':
        if produccion.estado == 'confirmada':
            messages.error(request, "No se puede borrar una producción ya confirmada desde aquí. Anulála manualmente si corresponde.")
            return redirect('produccion_detail', pk=pk)
        produccion.delete()
        messages.success(request, "Producción borrada.")
        return redirect('produccion_list')

    return render(request, 'produccion/produccion_confirm_delete.html', {'produccion': produccion})
def produccion_update(request, pk):
    """
    Permite editar una producción solo si está en estado 'borrador'.
    Luego de guardar vuelve al resumen para confirmar.
    """
    produccion = get_object_or_404(Produccion, pk=pk)

    # No permitir editar si ya fue confirmada o anulada
    if produccion.estado != 'borrador':
        messages.error(request, "⚠️ Solo se pueden editar producciones en estado borrador.")
        return redirect('produccion_detail', pk=pk)

    if request.method == 'POST':
        form = ProduccionForm(request.POST, instance=produccion)
        if form.is_valid():
            receta = form.cleaned_data.get('receta')

            # Validar que la receta tenga producto final
            if not receta or not receta.producto_final:
                messages.error(
                    request,
                    "⚠️ La receta seleccionada no tiene un producto final vinculado."
                )
                return redirect('receta_list')

            produccion = form.save(commit=False)

            if request.user.is_authenticated:
                produccion.usuario = request.user

            produccion.save()

            messages.success(request, "✏️ Producción actualizada. Revisá el resumen antes de confirmar.")
            return redirect('produccion_summary', pk=produccion.pk)

        else:
            messages.error(request, "Corrige los errores del formulario.")

    else:
        form = ProduccionForm(instance=produccion)

    return render(request, 'produccion/produccion_form.html', {
        'form': form,
        'titulo': 'Editar Producción'
    })

def produccion_anular(request, pk):
    """
    Anula una producción confirmada: esto debe devolver stock (opcional / peligroso).
    Aquí simplemente marco como 'anulada' y dejé un placeholder para que implementes la reversión
    adecuada (crear movimientos inversos). Recomiendo que pidas confirmación extra y registres auditoría.
    """
    produccion = get_object_or_404(Produccion, pk=pk)
    if request.method == 'POST':
        if produccion.estado != 'confirmada':
            messages.error(request, "Solo se pueden anular producciones confirmadas.")
            return redirect('produccion_detail', pk=pk)

        produccion.estado = 'anulada'
        produccion.save()
        messages.success(request, "Producción marcada como anulada. Implementá reversión si la querés automática.")
        return redirect('produccion_detail', pk=pk)

    return render(request, 'produccion/produccion_confirm_anular.html', {'produccion': produccion})

# =============================================================================
    #Genera y devuelve un PDF con el comprobante de venta que incluye: encabezado con fecha y 
    #número de venta, datos del cliente (si existe), tabla detallada de productos con cantidades 
    #y precios, total final y mensaje de agradecimiento.
# =============================================================================
def generar_comprobante_venta(request, venta_id):
    from .models import Venta, Detalle_venta
    
    venta = Venta.objects.get(Id_venta=venta_id)
    detalles = Detalle_venta.objects.filter(Id_venta=venta)
    
    # Crear el PDF
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # ========== LOGO ==========
    logo_path = os.path.join(settings.STATICFILES_DIRS[0], 'img', 'logo.png')
    if os.path.exists(logo_path):
        p.drawImage(logo_path, 2*cm, height - 4*cm, width=3*cm, height=3*cm, preserveAspectRatio=True)
    
    # ========== ENCABEZADO ==========
    p.setFont("Helvetica-Bold", 20)
    p.drawCentredString(width/2 + 1*cm, height - 2.5*cm, "LA CHANCHERÍA")
    
    p.setFont("Helvetica", 11)
    p.drawCentredString(width/2 + 1*cm, height - 3.2*cm, "Carnicería Artesanal - Calidad Premium")
    
    p.setFont("Helvetica-Bold", 12)
    p.drawCentredString(width/2 + 1*cm, height - 3.9*cm, "COMPROBANTE DE VENTA")
    
    # Línea separadora
    p.setStrokeColorRGB(0.8, 0.1, 0.1)  # Color rojo oscuro
    p.setLineWidth(2)
    p.line(2*cm, height - 4.5*cm, width - 2*cm, height - 4.5*cm)
    
    # ========== INFORMACIÓN DE LA VENTA ==========
    p.setStrokeColorRGB(0, 0, 0)  # Volver a negro
    p.setLineWidth(1)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(2*cm, height - 5.5*cm, "N° Comprobante:")
    p.drawString(12*cm, height - 5.5*cm, "Fecha:")
    
    p.setFont("Helvetica", 10)
    p.drawString(5*cm, height - 5.5*cm, str(venta.Id_venta))
    p.drawString(14*cm, height - 5.5*cm, venta.Fecha_venta.strftime('%d/%m/%Y %H:%M'))
    
    if venta.Id_cliente:
        p.setFont("Helvetica-Bold", 10)
        p.drawString(2*cm, height - 6.2*cm, "Cliente:")
        p.setFont("Helvetica", 10)
        p.drawString(4*cm, height - 6.2*cm, str(venta.Id_cliente.Nombre))
    
    p.setFont("Helvetica-Bold", 10)
    p.drawString(2*cm, height - 6.9*cm, "Tipo de Venta:")
    p.drawString(12*cm, height - 6.9*cm, "Forma de Pago:")
    
    p.setFont("Helvetica", 10)
    p.drawString(5.5*cm, height - 6.9*cm, str(venta.Tipo_venta))
    p.drawString(15.5*cm, height - 6.9*cm, str(venta.Forma_pago))
    
    # Línea separadora
    p.line(2*cm, height - 7.5*cm, width - 2*cm, height - 7.5*cm)
    
    # ========== TABLA DE PRODUCTOS ==========
    y = height - 8.5*cm
    
    # Fondo gris para encabezado de tabla
    p.setFillColorRGB(0.9, 0.9, 0.9)
    p.rect(2*cm, y - 0.2*cm, width - 4*cm, 0.7*cm, fill=True, stroke=False)
    
    p.setFillColorRGB(0, 0, 0)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(2.2*cm, y, "Producto")
    p.drawString(10*cm, y, "Cantidad")
    p.drawString(13*cm, y, "Precio Unit.")
    p.drawString(16*cm, y, "Subtotal")
    
    # Detalles de productos
    p.setFont("Helvetica", 10)
    y -= 0.9*cm
    
    for detalle in detalles:
        producto = detalle.Id_producto
        producto_nombre = (producto.Corte if producto.Corte else producto.Nombre) or "Sin nombre"
        producto_nombre = producto_nombre[:35]
        
        precio_unitario = detalle.Precio_total / detalle.Cantidad if detalle.Cantidad > 0 else 0
        
        p.drawString(2.2*cm, y, producto_nombre)
        p.drawString(10*cm, y, f"{detalle.Cantidad}")
        p.drawString(13*cm, y, f"${precio_unitario:.2f}")
        p.drawString(16*cm, y, f"${detalle.Precio_total:.2f}")
        y -= 0.6*cm
    
    # Línea antes del total
    p.line(2*cm, y - 0.2*cm, width - 2*cm, y - 0.2*cm)
    
    # ========== TOTAL ==========
    p.setFont("Helvetica-Bold", 14)
    p.setFillColorRGB(0.8, 0.1, 0.1)  # Rojo para el total
    p.drawString(13*cm, y - 1*cm, f"TOTAL: ${venta.Precio:.2f}")
    
    # Estado
    p.setFillColorRGB(0, 0, 0)
    p.setFont("Helvetica", 10)
    p.drawString(2*cm, y - 1*cm, f"Estado: {venta.Estado}")
    
    # ========== PIE DE PÁGINA PERSONALIZADO ==========
    p.setStrokeColorRGB(0.8, 0.1, 0.1)
    p.setLineWidth(2)
    p.line(2*cm, 4*cm, width - 2*cm, 4*cm)
    
    p.setFillColorRGB(0, 0, 0)
    p.setFont("Helvetica-Bold", 11)
    p.drawCentredString(width/2, 3.3*cm, "¡Gracias por elegirnos!")
    
    p.setFont("Helvetica", 9)
    p.drawCentredString(width/2, 2.7*cm, "La Chanchería - Carnicería de Calidad desde 2020")
    p.drawCentredString(width/2, 2.2*cm, "📍 Tu dirección aquí | 📞 Tu teléfono aquí")
    p.drawCentredString(width/2, 1.7*cm, "🌐 www.lachancheria.com | 📧 contacto@lachancheria.com")
    
    p.showPage()
    p.save()
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="comprobante_venta_{venta_id}.pdf"'
    return response
# -------------------------
# VISTA PARA CREAR PAGO CON MERCADO PAGO
# -------------------------
def crear_pago_mercadopago(request, venta_id):
    from .models import Venta
    
    venta = Venta.objects.get(Id_venta=venta_id)
    
    # Inicializar SDK
    sdk = mercadopago.SDK(settings.MERCADO_PAGO_ACCESS_TOKEN)
    
    # Crear preferencia de pago
    preference_data = {
        "items": [
            {
                "title": f"Venta #{venta.Id_venta} - La Chancheria",
                "quantity": 1,
                "unit_price": float(venta.Precio),
                "currency_id": "ARS"
            }
        ],
        "external_reference": str(venta.Id_venta),
    }
    
    preference_response = sdk.preference().create(preference_data)
    
    # Debug
    print("=" * 50)
    print("STATUS:", preference_response.get("status"))
    print("RESPONSE:", preference_response.get("response"))
    print("=" * 50)
    
    status = preference_response.get("status")
    if status != 201:
        error_msg = preference_response.get("response", "Error desconocido")
        messages.error(request, f'Error de Mercado Pago (status {status}): {error_msg}')
        return redirect('venta_list')
    
    preference = preference_response.get("response", {})
    init_point = preference.get("sandbox_init_point")  # Usar sandbox para pruebas
    
    if not init_point:
        init_point = preference.get("init_point")
    
    if not init_point:
        messages.error(request, f'No se pudo obtener el link de pago.')
        return redirect('venta_list')
    
    return redirect(init_point)

def pago_exitoso(request, venta_id):
    from .models import Venta
    
    try:
        venta = Venta.objects.get(Id_venta=venta_id)
        venta.Estado = 'completada'
        venta.save()
        messages.success(request, f'¡Pago realizado con éxito! Venta #{venta_id} completada.')
    except Venta.DoesNotExist:
        messages.error(request, f'No se encontró la venta #{venta_id}')
    
    return redirect('venta_list')


def pago_fallido(request, venta_id):
    messages.error(request, f'El pago de la venta #{venta_id} falló. Intenta nuevamente.')
    return redirect('venta_list')


def pago_pendiente(request, venta_id):
    messages.warning(request, f'El pago de la venta #{venta_id} está pendiente de confirmación.')
    return redirect('venta_list')


# =============================================================================
# GESTIÓN DE USUARIOS Y NIVELES DE ACCESO
# =============================================================================

@login_required
def gestion_usuarios(request):
    """Vista para listar y gestionar usuarios del sistema."""
    # Solo admin puede gestionar usuarios
    if not request.user.groups.filter(name='admin').exists() and not request.user.is_superuser:
        raise PermissionDenied("Solo administradores pueden gestionar usuarios.")
    
    usuarios = User.objects.all().prefetch_related('groups')
    grupos = Group.objects.all()
    
    return render(request, 'usuarios/gestion_usuarios.html', {
        'usuarios': usuarios,
        'grupos': grupos,
    })


@login_required
def usuario_asignar_grupo(request, user_id):
    """Asignar o cambiar el grupo de un usuario."""
    if not request.user.groups.filter(name='admin').exists() and not request.user.is_superuser:
        raise PermissionDenied("Solo administradores pueden asignar grupos.")
    
    usuario = get_object_or_404(User, pk=user_id)
    grupos = Group.objects.all()
    
    if request.method == 'POST':
        grupo_id = request.POST.get('grupo')
        
        # Limpiar grupos anteriores
        usuario.groups.clear()
        
        if grupo_id:
            grupo = get_object_or_404(Group, pk=grupo_id)
            usuario.groups.add(grupo)
            messages.success(request, f'✅ Usuario "{usuario.username}" asignado al grupo "{grupo.name}".')
        else:
            messages.info(request, f'Usuario "{usuario.username}" sin grupo asignado.')
        
        return redirect('gestion_usuarios')
    
    grupo_actual = usuario.groups.first()
    
    return render(request, 'usuarios/asignar_grupo.html', {
        'usuario': usuario,
        'grupos': grupos,
        'grupo_actual': grupo_actual,
    })


@login_required
def usuario_crear(request):
    """Crear un nuevo usuario."""
    if not request.user.groups.filter(name='admin').exists() and not request.user.is_superuser:
        raise PermissionDenied("Solo administradores pueden crear usuarios.")
    
    grupos = Group.objects.all()
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        grupo_id = request.POST.get('grupo')
        
        # Validaciones
        if not username:
            messages.error(request, 'El nombre de usuario es requerido.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, f'El usuario "{username}" ya existe.')
        elif password != password2:
            messages.error(request, 'Las contraseñas no coinciden.')
        elif len(password) < 4:
            messages.error(request, 'La contraseña debe tener al menos 4 caracteres.')
        else:
            usuario = User.objects.create_user(username=username, email=email, password=password)
            
            if grupo_id:
                grupo = get_object_or_404(Group, pk=grupo_id)
                usuario.groups.add(grupo)
            
            messages.success(request, f'✅ Usuario "{username}" creado exitosamente.')
            return redirect('gestion_usuarios')
    
    return render(request, 'usuarios/usuario_form.html', {
        'grupos': grupos,
        'titulo': 'Crear Usuario',
    })


@login_required
def usuario_eliminar(request, user_id):
    """Eliminar un usuario."""
    if not request.user.groups.filter(name='admin').exists() and not request.user.is_superuser:
        raise PermissionDenied("Solo administradores pueden eliminar usuarios.")
    
    usuario = get_object_or_404(User, pk=user_id)
    
    # No permitir eliminar el propio usuario
    if usuario == request.user:
        messages.error(request, 'No puedes eliminarte a ti mismo.')
        return redirect('gestion_usuarios')
    
    if request.method == 'POST':
        username = usuario.username
        usuario.delete()
        messages.success(request, f'✅ Usuario "{username}" eliminado.')
        return redirect('gestion_usuarios')
    
    return render(request, 'usuarios/usuario_confirm_delete.html', {
        'usuario': usuario,
    })


def crear_grupos_iniciales():
    """Función para crear los grupos iniciales del sistema."""
    grupos_a_crear = ['admin', 'cajero', 'despostador', 'inventario']
    for nombre in grupos_a_crear:
        Group.objects.get_or_create(name=nombre)


@login_required
def inicializar_grupos(request):
    """Vista para inicializar los grupos (solo admin/superuser)."""
    if not request.user.is_superuser:
        raise PermissionDenied("Solo superusuarios pueden inicializar grupos.")
    
    crear_grupos_iniciales()
    messages.success(request, '✅ Grupos inicializados correctamente.')
    return redirect('gestion_usuarios')
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def configuracion(request):
    return render(request, "configuracion/configuracion.html")
from django.shortcuts import render

def exportar_csv(request):
    return render(request, "exportar/exportar_csv.html")
import csv
from django.http import HttpResponse
from .models import Producto, Cliente


def exportar_productos_csv(request):

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="productos.csv"'

    response.write('\ufeff')  # para Excel

    writer = csv.writer(response, delimiter=';')

    writer.writerow([
        'ID',
        'Producto',
        'Corte',
        'Unidad de Medida',
        'Precio por Unidad',
        'Stock Disponible'
    ])

    productos = Producto.objects.all()

    for p in productos:

        writer.writerow([
            p.Id_producto,
            p.Corte,  # o p.nombre si tenés campo nombre
            p.Corte if p.Corte else "-",
            "Kilogramo" if "kg" in str(p.stock_kg).lower() else "Unidad",
            p.Precio_kilo,
            p.stock_kg
        ])

    return response


def exportar_clientes_csv(request):

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="clientes.csv"'

    writer = csv.writer(response)

    writer.writerow(['ID','Nombre','Telefono'])

    clientes = Cliente.objects.all()

    for c in clientes:
        writer.writerow([
            c.id,
            c.nombre,
            c.telefono
        ])

    return response