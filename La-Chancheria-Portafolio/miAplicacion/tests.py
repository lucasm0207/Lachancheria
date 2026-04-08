from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import Categoria, Producto, Cliente, Venta, Detalle_venta
from .services import VentaService


# =============================================================================
# TESTS DEL SERVICIO DE VENTAS (VentaService)
# =============================================================================


class VentaServiceTestBase(TestCase):
    """Clase base con datos compartidos para todos los tests de VentaService."""

    def setUp(self):
        # Categorías
        self.cat_unidad = Categoria.objects.create(Categoria="Abarrotes")
        self.cat_carnes = Categoria.objects.create(Categoria="BROSA")

        # Producto por unidad
        self.prod_unidad = Producto.objects.create(
            Id_categoria=self.cat_unidad,
            Nombre="Galletas",
            Corte="",
            Precio_kilo=Decimal("10.00"),
            precio_mayor_x_kg=Decimal("9.00"),
            unidad_medida="UNIDAD",
            stock_kg=Decimal("20.00"),
        )

        # Producto por peso / corte
        self.prod_corte = Producto.objects.create(
            Id_categoria=self.cat_carnes,
            Nombre="Carne Genérica",
            Corte="Asado",
            Precio_kilo=Decimal("500.00"),
            precio_mayor_x_kg=Decimal("480.00"),
            unidad_medida="KG",
            stock_kg=Decimal("100.00"),
        )

        # Cliente
        self.cliente = Cliente.objects.create(Nombre="Cliente Test")


class VentaServiceValidacionStockTest(VentaServiceTestBase):
    """Tests para validación de stock."""

    def test_stock_suficiente(self):
        es_valido, msg = VentaService.validar_stock_disponible(
            self.prod_unidad, Decimal("5.00")
        )
        self.assertTrue(es_valido)

    def test_stock_insuficiente(self):
        es_valido, msg = VentaService.validar_stock_disponible(
            self.prod_unidad, Decimal("25.00")
        )
        self.assertFalse(es_valido)
        self.assertIn("insuficiente", msg.lower())

    def test_cantidad_cero_invalida(self):
        es_valido, msg = VentaService.validar_stock_disponible(
            self.prod_unidad, Decimal("0")
        )
        self.assertFalse(es_valido)

    def test_cantidad_negativa_invalida(self):
        es_valido, msg = VentaService.validar_stock_disponible(
            self.prod_unidad, Decimal("-1")
        )
        self.assertFalse(es_valido)

    def test_producto_nulo(self):
        es_valido, msg = VentaService.validar_stock_disponible(None, Decimal("1"))
        self.assertFalse(es_valido)


class VentaServiceCalculoPrecioTest(VentaServiceTestBase):
    """Tests para cálculo de precios."""

    def test_precio_menor(self):
        precio = VentaService.calcular_precio_detalle(
            self.prod_corte, Decimal("2.00"), "menor"
        )
        # 2 kg * $500/kg = $1000
        self.assertEqual(precio, Decimal("1000.00"))

    def test_precio_mayor(self):
        precio = VentaService.calcular_precio_detalle(
            self.prod_corte, Decimal("2.00"), "mayor"
        )
        # 2 * ($500 * 0.85) = 2 * $425 = $850
        self.assertEqual(precio, Decimal("850.00"))

    def test_precio_unidades(self):
        precio = VentaService.calcular_precio_detalle(
            self.prod_unidad, Decimal("3.00"), "menor"
        )
        # 3 unid * $10 = $30
        self.assertEqual(precio, Decimal("30.00"))


class VentaServiceCrearTest(VentaServiceTestBase):
    """Tests para creación de ventas."""

    def test_crear_venta_exitosa(self):
        detalles = [{"producto": self.prod_unidad, "cantidad": Decimal("5.00")}]

        venta, msg = VentaService.crear_venta(
            self.cliente, "menor", "efectivo", "completada", detalles
        )

        self.assertIsNotNone(venta)
        self.assertEqual(venta.Precio, Decimal("50.00"))  # 5 * $10
        self.assertEqual(Detalle_venta.objects.filter(Id_venta=venta).count(), 1)

        # Verificar descuento de stock
        self.prod_unidad.refresh_from_db()
        self.assertEqual(self.prod_unidad.stock_kg, Decimal("15.00"))  # 20 - 5

    def test_crear_venta_sin_detalles_falla(self):
        venta, msg = VentaService.crear_venta(
            self.cliente, "menor", "efectivo", "completada", []
        )

        self.assertIsNone(venta)
        self.assertIn("al menos un producto", msg.lower())

    def test_crear_venta_stock_insuficiente_falla(self):
        detalles = [{"producto": self.prod_unidad, "cantidad": Decimal("50.00")}]

        venta, msg = VentaService.crear_venta(
            self.cliente, "menor", "efectivo", "completada", detalles
        )

        self.assertIsNone(venta)
        self.assertIn("insuficiente", msg.lower())

        # Verificar que el stock NO cambió (rollback)
        self.prod_unidad.refresh_from_db()
        self.assertEqual(self.prod_unidad.stock_kg, Decimal("20.00"))

    def test_crear_venta_multiple_productos(self):
        detalles = [
            {"producto": self.prod_unidad, "cantidad": Decimal("2.00")},
            {"producto": self.prod_corte, "cantidad": Decimal("1.00")},
        ]

        venta, msg = VentaService.crear_venta(
            self.cliente, "menor", "efectivo", "completada", detalles
        )

        self.assertIsNotNone(venta)
        # 2*$10 + 1*$500 = $520
        self.assertEqual(venta.Precio, Decimal("520.00"))
        self.assertEqual(Detalle_venta.objects.filter(Id_venta=venta).count(), 2)


class VentaServiceActualizarTest(VentaServiceTestBase):
    """Tests para actualización de ventas."""

    def test_actualizar_venta_devuelve_stock(self):
        # Crear venta inicial
        detalles_init = [{"producto": self.prod_unidad, "cantidad": Decimal("5.00")}]
        venta, _ = VentaService.crear_venta(
            self.cliente, "menor", "efectivo", "completada", detalles_init
        )

        # Stock bajó a 15
        self.prod_unidad.refresh_from_db()
        self.assertEqual(self.prod_unidad.stock_kg, Decimal("15.00"))

        # Actualizar con cantidad diferente
        detalles_new = [{"producto": self.prod_unidad, "cantidad": Decimal("3.00")}]
        ok, msg = VentaService.actualizar_venta(
            venta, "menor", "efectivo", "completada", detalles_new
        )

        self.assertTrue(ok)
        venta.refresh_from_db()
        self.assertEqual(venta.Precio, Decimal("30.00"))  # 3 * $10

        # Stock: 20 (original) - 3 (nuevo) = 17
        self.prod_unidad.refresh_from_db()
        self.assertEqual(self.prod_unidad.stock_kg, Decimal("17.00"))


class VentaServiceEliminarTest(VentaServiceTestBase):
    """Tests para eliminación de ventas."""

    def test_eliminar_venta_devuelve_stock(self):
        detalles = [{"producto": self.prod_unidad, "cantidad": Decimal("5.00")}]
        venta, _ = VentaService.crear_venta(
            self.cliente, "menor", "efectivo", "completada", detalles
        )

        # Stock bajó a 15
        self.prod_unidad.refresh_from_db()
        self.assertEqual(self.prod_unidad.stock_kg, Decimal("15.00"))

        # Eliminar
        ok, msg = VentaService.eliminar_venta(venta)
        self.assertTrue(ok)

        # Stock debe volver a 20
        self.prod_unidad.refresh_from_db()
        self.assertEqual(self.prod_unidad.stock_kg, Decimal("20.00"))

        # La venta ya no debe existir
        self.assertFalse(Venta.objects.filter(pk=venta.pk).exists())


class VentaServiceCambiarEstadoTest(VentaServiceTestBase):
    """Tests para cambio de estado de ventas."""

    def test_cambiar_estado_a_cancelada_devuelve_stock(self):
        detalles = [{"producto": self.prod_unidad, "cantidad": Decimal("5.00")}]
        venta, _ = VentaService.crear_venta(
            self.cliente, "menor", "efectivo", "completada", detalles
        )

        ok, msg = VentaService.cambiar_estado_venta(venta, "cancelada")
        self.assertTrue(ok)

        # Stock devuelto
        self.prod_unidad.refresh_from_db()
        self.assertEqual(self.prod_unidad.stock_kg, Decimal("20.00"))

    def test_estado_invalido(self):
        detalles = [{"producto": self.prod_unidad, "cantidad": Decimal("1.00")}]
        venta, _ = VentaService.crear_venta(
            self.cliente, "menor", "efectivo", "completada", detalles
        )

        ok, msg = VentaService.cambiar_estado_venta(venta, "inventado")
        self.assertFalse(ok)


# =============================================================================
# TESTS DE TEMPLATES Y VISTAS
# =============================================================================


class VentaFormTemplateTest(VentaServiceTestBase):
    """Tests para que los templates rendericen correctamente."""

    def setUp(self):
        super().setUp()
        # Crear usuario autenticado con grupo admin para acceder a las vistas
        from django.contrib.auth.models import User, Group
        admin_group, _ = Group.objects.get_or_create(name="admin")
        self.user = User.objects.create_user(username="testadmin", password="testpass123")
        self.user.groups.add(admin_group)
        self.client.login(username="testadmin", password="testpass123")

    def test_venta_form_shows_nombre_and_corte_in_select(self):
        url = reverse("venta_create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")

        # El producto por unidad debe mostrarse con su Nombre
        self.assertIn("Galletas", content)

        # El producto por corte debe mostrarse con su Corte
        self.assertIn("Asado", content)

    def test_venta_update_shows_producto_info(self):
        # Crear una venta con detalle
        venta = Venta.objects.create(
            Id_cliente=self.cliente,
            Tipo_venta="menor",
            Precio=Decimal("0.00"),
            Forma_pago="efectivo",
            Estado="pendiente",
        )
        Detalle_venta.objects.create(
            Id_venta=venta,
            Id_producto=self.prod_unidad,
            Cantidad=Decimal("2.00"),
            Precio_total=Decimal("20.00"),
        )

        url = reverse("venta_update", args=[venta.Id_venta])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")

        # Al editar, el select debe contener el nombre del producto por unidad
        self.assertIn("Galletas", content)
        # Y debe incluir el atributo data-precio con el valor correcto
        self.assertIn('data-precio="10.00"', content)
