from django.contrib import admin
from django.urls import path
from miAplicacion import views
from django.contrib.auth import views as auth_views
from miAplicacion.views import generar_comprobante_venta
from django.contrib.auth.views import LogoutView
from django.contrib.auth import views as auth_views


urlpatterns = [
    # -------------------------
    # ADMIN
    # -------------------------
    path('admin/', admin.site.urls),

    # -------------------------
    # PÁGINA DE INICIO / BASE
    # -------------------------
    # root -> login page
    path('', views.CustomLoginView.as_view(template_name='login.html'), name='login'),
    # use custom logout view so GET redirects to login (prevents 405)
    path('logout/', views.logout_view, name='logout'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    # Dashboard (index) moved behind /dashboard/
    path('dashboard/', views.index, name='index'),   # Página principal en "/dashboard/"
    path('profile/', views.profile, name='profile'),
    path('base/', views.base, name='base'),
    path('password_change/', auth_views.PasswordChangeView.as_view(
    template_name='registration/password_change.html'
), name='password_change'),

path('password_change_done/', auth_views.PasswordChangeDoneView.as_view(
    template_name='registration/password_change_done.html'
), name='password_change_done'),


    #historial clientes
   
    path('historial-cliente/<int:cliente_id>/', views.historial_cliente_detalle, name='historial_cliente_detalle'),

    
    # -------------------------
    # CLIENTES
    # -------------------------
    path('clientes/', views.cliente_list, name='cliente_list'),
    path('clientes/nuevo/', views.cliente_create, name='cliente_create'),
    path('clientes/editar/<int:pk>/', views.cliente_update, name='cliente_update'),
    path('clientes/eliminar/<int:pk>/', views.cliente_delete, name='cliente_delete'),
    path("importar-clientes/", views.importar_clientes, name="importar_clientes"),



    
    # -------------------------
    # COMPRAS
    # -------------------------
    
    path('compras/', views.compra_list, name='compra_list'),
    path('compras/carne/', views.compra_carne_create, name='compra_carne_create'),
    path('compras/insumo/', views.compra_insumo_create, name='compra_insumo_create'),
    path('compras/editar/<int:pk>/', views.compra_update, name='compra_update'),
    path('compras/eliminar/<int:pk>/', views.compra_delete, name='compra_delete'),
    
    # -------------------------
    # PROVEEDORES
    # -------------------------
    path('proveedor/', views.proveedor_list, name='proveedor_list'),
    path('proveedor/nuevo/', views.proveedor_create, name='proveedor_create'),
    path('proveedor/<int:pk>/detalle/', views.proveedor_detail, name='proveedor_detail'),
    path('proveedor/editar/<int:pk>/', views.proveedor_update, name='proveedor_update'),
    path('proveedor/eliminar/<int:pk>/', views.proveedor_delete, name='proveedor_delete'),

    # -------------------------
    # VENTAS
    # -------------------------
    path('ventas/', views.venta_list, name='venta_list'),
    path('ventas/nuevo/', views.venta_create, name='venta_create'),
    path('ventas/detalle/<int:pk>/', views.venta_detalle, name='venta_detalle'),
    path('ventas/editar/<int:Id_venta>/', views.venta_update, name='venta_update'),
    path('ventas/eliminar/<int:pk>/', views.venta_delete, name='venta_delete'),
    path('ventas/estado/<int:pk>/<str:nuevo_estado>/', views.venta_cambiar_estado, name='venta_cambiar_estado'),
    path("ventas/importar-ventas/", views.importar_ventas, name="importar_ventas"),

    # -------------------------
    # PRODUCTOS
    # -------------------------
    path('productos/', views.producto_list, name='producto_list'),
    path('productos/nuevo/', views.producto_create, name='producto_create'),
    path('productos/editar/<int:pk>/', views.producto_update, name='producto_update'),
    path('productos/eliminar/<int:pk>/', views.producto_delete, name='producto_delete'),
    path('productos/detalle/<int:id_producto>/', views.producto_detalle, name='producto_detalle'),
    path("importar-productos/", views.importar_productos, name="importar_productos"),
    
    # API para unidades de medida
    path('api/unidades-categoria/<int:categoria_id>/', views.get_unidades_por_categoria, name='api_unidades_categoria'),
  
    
    path('categorias/', views.categoria_list, name='categoria_list'),
    path('categoria/nuevo/', views.categoria_create, name='categoria_create'),
    path('categoria/editar/<int:pk>/', views.categoria_update, name='categoria_update'),
    path('categoria/eliminar/<int:pk>/', views.categoria_delete, name='categoria_delete'),



# Lista de despostes
    path('despostes/', views.desposte_list, name='desposte_list'),

    # Crear desposte
    path('despostes/nuevo/', views.desposte_create, name='desposte_create'),

    # Agregar cortes a un desposte
    path('despostes/<int:desposte_id>/cortes/', views.desposte_add_cortes, name='desposte_add_cortes'),
    path('despostes/<int:desposte_id>/editar/', views.desposte_update, name='desposte_update'),
    path('despostes/<int:desposte_id>/eliminar/', views.desposte_delete, name='desposte_delete'),

    # URLs para gestión de insumos
path('insumos/', views.insumo_list_view, name='insumo_list'),
path('insumos/create/', views.insumo_create_view, name='insumo_create'),
path('insumos/<int:pk>/', views.insumo_detail_view, name='insumo_detail'),
path('insumos/<int:pk>/edit/', views.insumo_update_view, name='insumo_update'),
path('insumos/<int:pk>/delete/', views.insumo_delete_view, name='insumo_delete'),

# URLs para compras de insumos
path('compras/insumos/create/', views.insumo_purchase_create_view, name='insumo_purchase_create'),

    # -------------------------
    # PROMOCIONES
    # -------------------------
    path('promociones/', views.promocion_list, name='promocion_list'),
    path('promociones/nuevo/', views.promocion_create, name='promocion_create'),
    path('promociones/editar/<int:pk>/', views.promocion_update, name='promocion_update'),
    path('promociones/eliminar/<int:pk>/', views.promocion_delete, name='promocion_delete'),
    path('promociones/detalle/<int:pk>/', views.promocion_detalle, name='promocion_detalle'),


    # -------------------------
    # RECETAS (CRUD)
    # -------------------------
    path('produccion/recetas/', views.receta_list, name='receta_list'),
    path('produccion/recetas/nuevo/', views.receta_create, name='receta_create'),
    path('produccion/recetas/editar/<int:pk>/', views.receta_update, name='receta_update'),
    path('produccion/recetas/eliminar/<int:pk>/', views.receta_delete, name='receta_delete'),
    path('produccion/recetas/<int:pk>/', views.receta_detail, name='receta_detail'),

    # -------------------------
    # PRODUCCIONES
    # -------------------------
    path('produccion/', views.produccion_list, name='produccion_list'),
    path('produccion/nuevo/', views.produccion_create, name='produccion_create'),
    path('produccion/<int:pk>/resumen/', views.produccion_summary, name='produccion_summary'),
    path('produccion/<int:pk>/', views.produccion_detail, name='produccion_detail'),
    path('produccion/<int:pk>/eliminar/', views.produccion_delete, name='produccion_delete'),
    path('produccion/<int:pk>/anular/', views.produccion_anular, name='produccion_anular'),
    path('produccion/editar/<int:pk>/', views.produccion_update, name='produccion_update'),

    # -------------------------
    # COMPROBANTE DE VENTA
    # -------------------------
    path('ventas/<int:venta_id>/comprobante/', generar_comprobante_venta, name='comprobante_venta'),

    # -------------------------
    # PASARELA DE PAGO
    # -------------------------
    path('ventas/<int:venta_id>/pagar/', views.crear_pago_mercadopago, name='crear_pago'),
    path('ventas/<int:venta_id>/pago-exitoso/', views.pago_exitoso, name='pago_exitoso'),
    path('ventas/<int:venta_id>/pago-fallido/', views.pago_fallido, name='pago_fallido'),
    path('ventas/<int:venta_id>/pago-pendiente/', views.pago_pendiente, name='pago_pendiente'),

    # -------------------------
    # GESTIÓN DE USUARIOS
    # -------------------------
    path('usuarios/', views.gestion_usuarios, name='gestion_usuarios'),
    path('usuarios/crear/', views.usuario_crear, name='usuario_crear'),
    path('usuarios/<int:user_id>/asignar-grupo/', views.usuario_asignar_grupo, name='usuario_asignar_grupo'),
    path('usuarios/<int:user_id>/eliminar/', views.usuario_eliminar, name='usuario_eliminar'),
    path('usuarios/inicializar-grupos/', views.inicializar_grupos, name='inicializar_grupos'),
    path('configuracion/', views.configuracion, name='configuracion'),
    path('exportar/', views.exportar_csv, name='exportar_csv'),
    
    path('exportar/productos/', views.exportar_productos_csv, name='exportar_productos_csv'),

    path('exportar/clientes/', views.exportar_clientes_csv, name='exportar_clientes_csv'),
    ]