# =============================================================================
# SERVICIOS DE VENTAS - services.py
# Lógica centralizada para operaciones con ventas
# =============================================================================

from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Venta, Detalle_venta, Producto, Promociones
from django.utils import timezone


def _cantidad_interna(producto, cantidad):
    """
    Convierte la cantidad de venta (en unidad de display) a la unidad interna.
    - KG → la cantidad del usuario está en kg, internamente se guarda en gramos (×1000).
    - UNIDAD / PAQUETE → sin conversión.
    """
    cantidad = Decimal(str(cantidad))
    if producto.unidad_medida == 'KG':
        return Producto.kg_a_gramos(cantidad)
    return cantidad


class VentaService:
    """
    Servicio centralizado para todas las operaciones de ventas.
    Maneja validaciones, cálculos y actualización de stock.
    """

    # =========================================================================
    # VALIDACIONES
    # =========================================================================

    @staticmethod
    def validar_stock_disponible(producto: Producto, cantidad: Decimal) -> tuple[bool, str]:
        """
        Valida si hay suficiente stock para la cantidad solicitada.
        La cantidad viene en unidades de display (kg para KG), se convierte internamente.

        Args:
            producto: Instancia del producto a validar
            cantidad: Cantidad solicitada (en unidad de display)

        Returns:
            (es_valido: bool, mensaje: str)
        """
        if not producto:
            return False, "El producto no existe"

        # Refrescar desde BD para tener stock actualizado
        producto.refresh_from_db()

        cantidad = Decimal(str(cantidad))
        cantidad_interna = _cantidad_interna(producto, cantidad)
        stock_interno = Decimal(str(producto.stock_kg or 0))

        if cantidad <= 0:
            return False, "La cantidad debe ser mayor a 0"

        if stock_interno < cantidad_interna:
            # Mostrar stock en unidad de display
            stock_display = producto.stock_display
            return (
                False,
                f"Stock insuficiente. Disponible: {stock_display} {producto.get_unidad_medida_display()}",
            )

        return True, "Stock disponible"

    @staticmethod
    def validar_detalles_venta(detalles_data: list) -> tuple[bool, list[str]]:
        """
        Valida todos los detalles de una venta.

        Args:
            detalles_data: Lista de dicts con datos del detalle

        Returns:
            (es_valido: bool, errores: list[str])
        """
        errores = []

        if not detalles_data:
            return False, ["Debe agregar al menos un producto a la venta"]

        for idx, detalle in enumerate(detalles_data, 1):
            producto = detalle.get("producto")
            cantidad = detalle.get("cantidad")

            if not producto:
                errores.append(f"Detalle {idx}: Producto requerido")
                continue

            if not cantidad:
                errores.append(f"Detalle {idx}: Cantidad requerida")
                continue

            # Validar que UNIDAD/PAQUETE no acepte decimales
            if producto.unidad_medida in ('UNIDAD', 'PAQUETE'):
                if cantidad != cantidad.to_integral_value():
                    errores.append(
                        f"Detalle {idx} ({producto}): La cantidad debe ser entera para productos por {producto.get_unidad_medida_display()}"
                    )
                    continue

            es_valido, msg = VentaService.validar_stock_disponible(producto, cantidad)
            if not es_valido:
                errores.append(f"Detalle {idx} ({producto}): {msg}")

        return len(errores) == 0, errores

    # =========================================================================
    # CÁLCULOS DE PRECIO
    # =========================================================================

    # Porcentaje de descuento para ventas por mayor (15%)
    DESCUENTO_MAYOR = Decimal("0.15")

    @staticmethod
    def calcular_precio_detalle(
        producto: Producto, cantidad: Decimal, tipo_venta: str = "menor"
    ) -> Decimal:
        """
        Calcula el precio total para un detalle de venta.

        - Venta menor: usa Precio_kilo (precio unitario normal).
        - Venta mayor: aplica 15 % de descuento sobre el precio unitario normal.
        - Promoción: si existe una promoción activa, reemplaza el precio base.

        Args:
            producto: Instancia del producto
            cantidad: Cantidad a vender
            tipo_venta: 'mayor', 'menor' o 'promocion'

        Returns:
            Precio total (Decimal)
        """
        cantidad = Decimal(str(cantidad))
        precio_unitario = Decimal(str(producto.Precio_kilo))

        # Venta mayor → usar precio mayorista si existe, sino precio normal sin descuento
        if tipo_venta == "mayor" and producto.precio_mayor_x_kg is not None:
            precio_unitario = Decimal(str(producto.precio_mayor_x_kg))

        # Aplicar promoción si existe (reemplaza cualquier precio anterior)
        promocion = VentaService.obtener_promocion_aplicable(producto, cantidad)
        if promocion:
            precio_unitario = Decimal(str(promocion.Precio_oferta))

        return (cantidad * precio_unitario).quantize(Decimal("0.01"))

    @staticmethod
    def obtener_promocion_aplicable(
        producto: Producto, cantidad: Decimal
    ) -> Promociones | None:
        """
        Obtiene la promoción activa que aplica al producto.

        Args:
            producto: Instancia del producto
            cantidad: Cantidad a vender

        Returns:
            Instancia de Promociones o None
        """
        try:
            now = timezone.now()
            # Filtrar promociones activas para el producto
            promocion = Promociones.objects.filter(
                Id_producto=producto,
                estado="activa",
                Fecha_inicio__lte=now,
                Fecha_fin__gte=now,
            ).order_by('-Fecha_inicio').first()  # Tomar la promoción más reciente

            # Validar cantidad mínima si existe
            if promocion:
                if promocion.cantidad_minima and Decimal(str(cantidad)) < Decimal(str(promocion.cantidad_minima)):
                    return None

            return promocion
        except Exception as e:
            # Registrar el error para depuración
            print(f"Error al obtener promoción: {e}")
            return None

    @staticmethod
    def calcular_precio_total_venta(detalles: list) -> Decimal:
        """
        Calcula el precio total de una venta.

        Args:
            detalles: Lista de instancias Detalle_venta

        Returns:
            Total (Decimal)
        """
        total = Decimal("0.00")
        for detalle in detalles:
            total += Decimal(str(detalle.Precio_total or 0))
        return total

    # =========================================================================
    # OPERACIONES CON STOCK
    # =========================================================================

    @staticmethod
    def descontar_stock(producto: Producto, cantidad: Decimal) -> None:
        """
        Descuenta la cantidad del stock del producto.
        La cantidad viene en unidad de display (kg para KG).

        Args:
            producto: Instancia del producto
            cantidad: Cantidad a descontar (en unidad de display)
        """
        if not producto:
            return

        cantidad_interna = _cantidad_interna(producto, cantidad)
        producto.stock_kg = Decimal(str(producto.stock_kg or 0)) - cantidad_interna
        producto.save(update_fields=["stock_kg"])

    @staticmethod
    def devolver_stock(producto: Producto, cantidad: Decimal) -> None:
        """
        Devuelve la cantidad al stock del producto.
        La cantidad viene en unidad de display (kg para KG).

        Args:
            producto: Instancia del producto
            cantidad: Cantidad a devolver (en unidad de display)
        """
        if not producto:
            return

        cantidad_interna = _cantidad_interna(producto, cantidad)
        producto.stock_kg = Decimal(str(producto.stock_kg or 0)) + cantidad_interna
        producto.save(update_fields=["stock_kg"])

    # =========================================================================
    # OPERACIONES TRANSACCIONALES
    # =========================================================================

    @staticmethod
    @transaction.atomic
    def crear_venta(cliente, tipo_venta: str, forma_pago: str, estado: str, detalles_data: list) -> tuple[Venta | None, str]:
        """
        Crea una venta completa con sus detalles en una transacción atómica.

        Args:
            cliente: Instancia de Cliente
            tipo_venta: 'mayor', 'menor', 'promocion'
            forma_pago: 'efectivo', 'tarjeta', 'transferencia'
            estado: 'pendiente', 'completada', 'cancelada'
            detalles_data: List de dicts con {producto, cantidad, precio_total}

        Returns:
            (venta: Venta | None, mensaje: str)
        """
        # Validar detalles
        es_valido, errores = VentaService.validar_detalles_venta(detalles_data)
        if not es_valido:
            return None, " | ".join(errores)

        try:
            # Crear venta
            venta = Venta(
                Id_cliente=cliente,
                Tipo_venta=tipo_venta,
                Forma_pago=forma_pago,
                Estado=estado,
                Precio=Decimal("0.00"),
            )
            venta.save()

            # Crear detalles y descontar stock
            precio_total = Decimal("0.00")
            for detalle_data in detalles_data:
                producto = detalle_data["producto"]
                cantidad = Decimal(str(detalle_data["cantidad"]))

                # Calcular precio
                precio_detalle = VentaService.calcular_precio_detalle(
                    producto, cantidad, tipo_venta
                )

                # Crear detalle
                Detalle_venta.objects.create(
                    Id_venta=venta,
                    Id_producto=producto,
                    Cantidad=cantidad,
                    Precio_total=precio_detalle,
                )

                # Descontar stock
                VentaService.descontar_stock(producto, cantidad)
                precio_total += precio_detalle

            # Actualizar precio total de la venta
            venta.Precio = precio_total
            venta.save(update_fields=["Precio"])

            return venta, "Venta creada exitosamente"

        except Exception as e:
            # La transacción se revierte automáticamente
            return None, f"Error al crear la venta: {str(e)}"

    @staticmethod
    @transaction.atomic
    def actualizar_venta(
        venta: Venta, tipo_venta: str, forma_pago: str, estado: str, detalles_data: list
    ) -> tuple[bool, str]:
        """
        Actualiza una venta existente con nuevos detalles.

        Args:
            venta: Instancia de Venta a actualizar
            tipo_venta: Nuevo tipo de venta
            forma_pago: Nueva forma de pago
            estado: Nuevo estado
            detalles_data: List de dicts con {producto, cantidad, precio_total}

        Returns:
            (es_exitoso: bool, mensaje: str)
        """
        try:
            # PRIMERO devolver stock de detalles anteriores
            detalles_anteriores = Detalle_venta.objects.filter(Id_venta=venta).select_related(
                "Id_producto"
            )
            for detalle in detalles_anteriores:
                VentaService.devolver_stock(detalle.Id_producto, detalle.Cantidad)

            # DESPUÉS validar stock (ahora el stock refleja la devolución)
            es_valido, errores = VentaService.validar_detalles_venta(detalles_data)
            if not es_valido:
                # Rollback automático por @transaction.atomic
                raise Exception(" | ".join(errores))

            # Eliminar detalles anteriores
            detalles_anteriores.delete()

            # Crear nuevos detalles y descontar stock
            precio_total = Decimal("0.00")
            for detalle_data in detalles_data:
                producto = detalle_data["producto"]
                cantidad = Decimal(str(detalle_data["cantidad"]))

                # Calcular precio
                precio_detalle = VentaService.calcular_precio_detalle(
                    producto, cantidad, tipo_venta
                )

                # Crear detalle
                Detalle_venta.objects.create(
                    Id_venta=venta,
                    Id_producto=producto,
                    Cantidad=cantidad,
                    Precio_total=precio_detalle,
                )

                # Descontar stock
                VentaService.descontar_stock(producto, cantidad)
                precio_total += precio_detalle

            # Actualizar venta
            venta.Tipo_venta = tipo_venta
            venta.Forma_pago = forma_pago
            venta.Estado = estado
            venta.Precio = precio_total
            venta.save()

            return True, "Venta actualizada exitosamente"

        except Exception as e:
            # La transacción se revierte automáticamente
            return False, f"Error al actualizar la venta: {str(e)}"

    @staticmethod
    @transaction.atomic
    def eliminar_venta(venta: Venta) -> tuple[bool, str]:
        """
        Elimina una venta y devuelve el stock a los productos.

        Args:
            venta: Instancia de Venta a eliminar

        Returns:
            (es_exitoso: bool, mensaje: str)
        """
        try:
            detalles = Detalle_venta.objects.filter(Id_venta=venta).select_related(
                "Id_producto"
            )

            # Devolver stock
            for detalle in detalles:
                VentaService.devolver_stock(detalle.Id_producto, detalle.Cantidad)

            # Eliminar venta (también elimina detalles por cascade)
            venta.delete()

            return True, "Venta eliminada exitosamente"

        except Exception as e:
            return False, f"Error al eliminar la venta: {str(e)}"

    @staticmethod
    def cambiar_estado_venta(venta: Venta, nuevo_estado: str) -> tuple[bool, str]:
        """
        Cambia el estado de una venta.

        Args:
            venta: Instancia de Venta
            nuevo_estado: Nuevo estado ('pendiente', 'completada', 'cancelada')

        Returns:
            (es_exitoso: bool, mensaje: str)
        """
        estados_validos = ["pendiente", "completada", "cancelada"]

        if nuevo_estado not in estados_validos:
            return False, f"Estado inválido. Debe ser uno de: {', '.join(estados_validos)}"

        try:
            # Si cambiar a cancelada, devolver stock
            if nuevo_estado == "cancelada" and venta.Estado != "cancelada":
                detalles = Detalle_venta.objects.filter(Id_venta=venta).select_related(
                    "Id_producto"
                )
                for detalle in detalles:
                    VentaService.devolver_stock(detalle.Id_producto, detalle.Cantidad)

            venta.Estado = nuevo_estado
            venta.save(update_fields=["Estado"])

            return True, f"Venta cambiada a {nuevo_estado}"

        except Exception as e:
            return False, f"Error al cambiar estado: {str(e)}"
