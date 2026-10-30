# -*- coding: utf-8 -*-
"""
================================================================================
                         PRECIOS FARMACENTER v2.8.0
                   Sistema de Consulta de Precios - Droguerías
================================================================================
                                  DERECHOS RESERVADOS
                                        © 2026

DESARROLLADORES:
    • Santiago Rincón Chávez      - rinconchavezsantiago555@gmail.com
    • Juan David Chávez Garavito  - chavezgaravitoj@gmail.com

LICENCIA:
    Este software es propiedad intelectual de sus desarrolladores.
    Queda prohibida la reproducción, distribución, modificación o uso
    no autorizado sin el consentimiento expreso de los titulares.

INFORMACIÓN TÉCNICA:
    Versión: 2.8.0  |  Lanzamiento: 26/06/2026  |  Plataforma: Android

SOPORTE:
    Contacte a los desarrolladores para soporte o solicitud de licencias.
================================================================================
"""

import sqlite3
import os
import csv
import requests
import threading
import logging
import json
import hashlib
import time
import base64
import itertools
import sys
from datetime import datetime, timedelta

import licencia
import tema
from tema import (
    COL, ic, MButton, MIconButton, MTextIconButton, MCard, MTextInput, MSpinner,
    registrar_fuentes, ICON_FONT_NAME, fade_in,
)
from kivy.config import Config
Config.set('graphics', 'maxfps', '60')
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty, ObjectProperty
from kivy.clock import Clock
from kivy.utils import platform
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.image import Image
from kivy.graphics import Color, Rectangle
from kivy.core.clipboard import Clipboard
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.resources import resource_add_path
from kivy.metrics import dp, sp
from kivy.core.window import Window

# ============================================================
# FORZAR TAMAÑO DE VENTANA EN PC (simula un celular)
# ============================================================
if platform != 'android':
    Window.size = (360, 640)

# ============================================================
# IMPORTS PARA PDF Y PERMISOS
# ============================================================
try:
    from fpdf import FPDF
    PDF_DISPONIBLE = True
except ImportError:
    PDF_DISPONIBLE = False

if platform == 'android':
    from android.permissions import request_permissions, Permission
    try:
        from android.storage import primary_external_storage_path
    except ImportError:
        primary_external_storage_path = None

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FarmacenterApp")

# --- DESOFUSCACIÓN DE CADENAS ---
_CLAVE_OFUS = "fc26"

def _d(blob):
    if not blob:
        return ""
    try:
        crudo = base64.b64decode(blob.encode())
        return "".join(chr(b ^ ord(k)) for b, k in zip(crudo, itertools.cycle(_CLAVE_OFUS)))
    except Exception:
        return blob

# ============================================================
# FUNCIONES PARA MANEJO DE CSV (VENTAS Y VENDEDORES)
# ============================================================

def get_ruta_ventas():
    ruta = os.path.join(RUTA_BASE, 'datos_ventas')
    if not os.path.exists(ruta):
        os.makedirs(ruta)
    return ruta

def get_csv_vendedores():
    return os.path.join(get_ruta_ventas(), 'vendedores.csv')

def get_csv_ventas():
    return os.path.join(get_ruta_ventas(), 'ventas.csv')

# ============================================================
# VENDEDORES POR SUCURSAL
# ============================================================
VENDEDORES_POR_SUCURSAL = {
    "Maíz Amarillo": [
        ('01', '1 DROGUERIA'),
        ('02', 'HENRRY CAICEDO'),
        ('03', 'JOSE RINCON'),
        ('06', 'JOHN FREDDY RINCON CUITIVA'),
        ('07', 'JOSE GUILLERMO RINCON MARTINEZ'),
        ('08', 'MARIA OLIVA RODRIGUEZ LEON'),
        ('09', 'DROGUERIA 2'),
        ('17', 'JUAN RINCON'),
    ],
    "Villaceleste": [
        ('06', 'HENRY CAICEDO HERRERA'),
        ('02', 'JORGE ROBERTO GARAVITO'),
        ('05', 'JOSE JUNIOR MENDEZ'),
        ('03', 'JOSE RINCON'),
        ('09', 'MAGDA BETHSY PINILLA'),
        ('01', 'VENDEDOR GENERAL'),
    ],
}

def inicializar_vendedores():
    ruta = get_csv_vendedores()
    existentes = set()
    if os.path.exists(ruta):
        with open(ruta, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existentes.add((row['codigo'], row['sucursal']))
    
    nuevos = []
    for sucursal, vendedores in VENDEDORES_POR_SUCURSAL.items():
        for codigo, nombre in vendedores:
            if (codigo, sucursal) not in existentes:
                nuevos.append((codigo, nombre, sucursal))
    
    if nuevos:
        if not os.path.exists(ruta):
            with open(ruta, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['codigo', 'nombre', 'sucursal'])
        
        with open(ruta, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for codigo, nombre, sucursal in nuevos:
                writer.writerow([codigo, nombre, sucursal])
                logger.info(f"Vendedor agregado: {codigo} - {nombre} ({sucursal})")
    
    if not os.path.exists(ruta):
        with open(ruta, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['codigo', 'nombre', 'sucursal'])
            for sucursal, vendedores in VENDEDORES_POR_SUCURSAL.items():
                for codigo, nombre in vendedores:
                    writer.writerow([codigo, nombre, sucursal])
        logger.info(f"Archivo vendedores.csv creado con todas las sucursales.")

def obtener_vendedores(sucursal=None):
    ruta = get_csv_vendedores()
    vendedores = []
    if os.path.exists(ruta):
        with open(ruta, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if sucursal is None or row['sucursal'] == sucursal:
                    vendedores.append(row)
    return vendedores

def agregar_venta(vendedor_id, vendedor_nombre, producto_id, producto_nombre,
                  formato, cantidad, precio_unitario, precio_total,
                  dinero_recibido, cambio, sucursal, transaccion_id=None):
    ruta = get_csv_ventas()
    now = datetime.now()
    fecha = now.strftime("%d/%m/%Y")
    hora = now.strftime("%H:%M:%S")
    
    ultimo_id = 0
    if os.path.exists(ruta):
        with open(ruta, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if row:
                    try:
                        ultimo_id = int(row[0])
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Fila de ventas con id inválido ignorada: {e}")
        ultimo_id += 1
    else:
        ultimo_id = 1
    
    if transaccion_id is None:
        transaccion_id = ultimo_id
    
    with open(ruta, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if os.path.getsize(ruta) == 0:
            writer.writerow(['id', 'fecha', 'hora', 'vendedor_id', 'vendedor_nombre',
                            'producto_id', 'producto_nombre', 'formato', 'cantidad',
                            'precio_unitario', 'precio_total', 'dinero_recibido',
                            'cambio', 'sucursal', 'transaccion_id', 'sincronizado'])
        writer.writerow([ultimo_id, fecha, hora, vendedor_id, vendedor_nombre,
                        producto_id, producto_nombre, formato, cantidad,
                        precio_unitario, precio_total, dinero_recibido, cambio,
                        sucursal, transaccion_id, '0'])
    logger.info(f"Venta registrada: {producto_nombre} - {formato} x{cantidad} - ${precio_total}")
    return ultimo_id

def obtener_ventas(sucursal=None, vendedor_id=None, fecha_inicio=None, fecha_fin=None):
    ruta = get_csv_ventas()
    ventas = []
    if os.path.exists(ruta):
        with open(ruta, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if sucursal and row.get('sucursal', '') != sucursal:
                    continue
                if vendedor_id and row.get('vendedor_id', '') != vendedor_id:
                    continue
                if fecha_inicio and row.get('fecha', '') < fecha_inicio:
                    continue
                if fecha_fin and row.get('fecha', '') > fecha_fin:
                    continue
                ventas.append(row)
    return ventas

def obtener_ventas_dia(sucursal):
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
    return obtener_ventas(sucursal=sucursal, fecha_inicio=fecha_hoy, fecha_fin=fecha_hoy)

def calcular_total_ventas(ventas):
    total = 0
    for v in ventas:
        try:
            total += float(v.get('precio_total', 0))
        except (ValueError, TypeError) as e:
            logger.warning(f"Venta con precio_total inválido ignorada: {e}")
    return total

def eliminar_venta_por_id(id_venta):
    ruta = get_csv_ventas()
    if not os.path.exists(ruta):
        return False
    
    with open(ruta, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        filas = list(reader)
    
    id_str = str(id_venta)
    encontrado = False
    nuevas_filas = []
    for fila in filas:
        if fila and fila[0] == id_str:
            encontrado = True
            continue
        nuevas_filas.append(fila)
    
    if not encontrado:
        return False
    
    with open(ruta, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(nuevas_filas)
    
    logger.info(f"Venta ID {id_venta} eliminada.")
    return True

# ============================================================
# SUCURSALES
# ============================================================
SUCURSALES = {
    "Maíz Amarillo": {
        "url_ofuscada": "DhdGRhVZHRkFDF1GDwdAWQECQVkUBAEAU05fT0gQWlcUBkJZDw1GGAUMXxlcGwgZAUxCUxQQXVgHDx1SFAxVaRUGQEAfPEJeBxFfVzkAXVkWClZECQRTRTkMQFFJKmNyUzNRbDMJBFcpMnkECgZ6c1QBawUzImtzIltZGx8aV18nG2hcMSZjQRRTV2NZBg8GNQJ2DzVFVlkRDV5ZBwcPBw==",
        "db_name": "drogueria_maiz_amarillo.db",
        "csv_name": "datos_maiz_amarillo.csv"
    },
    "Terranova": {
        "url_ofuscada": "",
        "db_name": "drogueria_terranova.db",
        "csv_name": "datos_terranova.csv"
    },
    "Villaceleste": {
        "url_ofuscada": "DhdGRhVZHRkFDF1GDwdAWQECQVkUBAEAU05fT0gQWlcUBkJZDw1GGAUMXxlcGwgZAUxCUxQQXVgHDx1SFAxVaRAKXloHPFFTCgZBQgM8UVkJE1tSFAxVVxU8XUQBTHtnJQZVZjwgBFosF2YCLwFzZ1QlBHQMC3NnBzZkZwUQYFhUUR9SFCx3cTQJC0AVXFZZEQ1eWQcHDwc=",
        "db_name": "drogueria_villaceleste.db",
        "csv_name": "datos_villaceleste.csv"
    },
    "Covipro": {
        "url_ofuscada": "",
        "db_name": "drogueria_covipro.db",
        "csv_name": "datos_covipro.csv"
    }
}

# ============================================================
# CONTRASEÑAS POR SUCURSAL
# Se guardan como hash SHA-256, no en texto plano. Esto evita que
# la contraseña quede legible con un simple grep del código fuente
# o del APK descompilado; no protege contra un ataque de fuerza
# bruta offline sobre 5 dígitos, que sigue siendo trivial en un
# cliente sin backend. Para eso haría falta validar contra un
# servidor, que la app no tiene.
# ============================================================
def _hash_clave(clave):
    return hashlib.sha256(clave.encode()).hexdigest()

CONTRASENAS_SUCURSALES_HASH = {
    "Maíz Amarillo": _hash_clave("25531"),
    "Villaceleste": _hash_clave("29383"),
    "Terranova": _hash_clave("32420"),
    "Covipro": _hash_clave("25532"),
}

def verificar_contrasena_sucursal(sucursal, clave_ingresada):
    hash_esperado = CONTRASENAS_SUCURSALES_HASH.get(sucursal)
    return hash_esperado is not None and _hash_clave(clave_ingresada) == hash_esperado

# ============================================================
# RUTAS
# ============================================================
if platform == 'android':
    from jnius import autoclass
    RUTA_BASE = None
    # Intentar obtener la carpeta de archivos escribible de la app
    try:
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        actividad = PythonActivity.mActivity
        if actividad is not None:
            files_dir = actividad.getFilesDir().toString()
            RUTA_BASE = files_dir.replace('file://', '')
    except Exception as e:
        logger.error(f"No se pudo obtener getFilesDir: {e}")
    # Respaldo: usar app_storage_path si lo anterior falló
    if not RUTA_BASE:
        try:
            from android.storage import app_storage_path
            RUTA_BASE = app_storage_path()
        except Exception as e:
            logger.error(f"Respaldo app_storage_path falló: {e}")
    # Último respaldo: carpeta actual
    if not RUTA_BASE:
        RUTA_BASE = os.path.dirname(os.path.abspath(__file__))

    # device id de Android (también protegido)
    android_id = None
    try:
        secure = autoclass('android.provider.Settings$Secure')
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        resolver = PythonActivity.mActivity.getContentResolver()
        android_id = secure.getString(resolver, secure.ANDROID_ID)
    except Exception as e:
        logger.error(f"No se pudo leer ANDROID_ID: {e}")
        android_id = "unknown_android"
    try:
        modelo = autoclass('android.os.Build').MODEL
        fabricante = autoclass('android.os.Build').MANUFACTURER
    except Exception:
        modelo = "Android"
        fabricante = "Generic"
else:
    RUTA_BASE = os.path.dirname(os.path.abspath(__file__))
    android_id = None
    modelo = "PC"
    fabricante = "Desktop"

# ============================================================
# RUTAS DE IMÁGENES (funciona en PC y Android)
# ============================================================
if platform == 'android':
    if hasattr(sys, '_MEIPASS'):
        resource_add_path(os.path.join(sys._MEIPASS))
    LOGO_PATH = './logo_farmacenter.png'
    ICONO_PATH = './icono.png'
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    LOGO_PATH = os.path.join(BASE_DIR, 'logo_farmacenter.png').replace('\\', '/')
    ICONO_PATH = os.path.join(BASE_DIR, 'icono.png').replace('\\', '/')

CONFIG_FILE = os.path.join(RUTA_BASE, 'config.json')

# ============================================================
# LICENCIA: GUARDAR Y CARGAR
# ============================================================
ARCHIVO_LICENCIA = os.path.join(RUTA_BASE, 'licencia.json')

def guardar_licencia(device_id, codigo):
    try:
        datos = {
            'device_id': device_id,
            'codigo': codigo,
            'activada': True,
            'fecha': datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        with open(ARCHIVO_LICENCIA, 'w', encoding='utf-8') as f:
            json.dump(datos, f)
        logger.info("Licencia guardada correctamente.")
        return True
    except Exception as e:
        logger.error(f"Error guardando licencia: {e}")
        return False

def cargar_licencia():
    if os.path.exists(ARCHIVO_LICENCIA):
        try:
            with open(ARCHIVO_LICENCIA, 'r', encoding='utf-8') as f:
                datos = json.load(f)
                if datos.get('activada', False):
                    return datos.get('codigo')
        except Exception as e:
            logger.error(f"Error cargando licencia: {e}")
    return None

# ============================================================
# FUNCIONES DE LICENCIA (device_id)
# ============================================================
def generar_device_id():
    if platform == 'android':
        base = f"{android_id}_{modelo}_{fabricante}"
    else:
        base = os.environ.get('COMPUTERNAME', 'dev')
    return licencia.generar_device_id(base)

def verificar_codigo(device_id, codigo_ingresado):
    return licencia.verificar_codigo(device_id, codigo_ingresado)

# ============================================================
# CLASE ProductoRow (para el RecycleView) - CORREGIDA
# ============================================================
class ProductoRow(BoxLayout):
    nombre = StringProperty("")
    laboratorio = StringProperty("")
    id_prod = StringProperty("")
    barras = StringProperty("")
    precio_caja = StringProperty("")
    precio_blister = StringProperty("")
    precio_unidad = StringProperty("")
    estado = StringProperty("SI HAY")
    catalog_screen = ObjectProperty(None)

    def agregar_al_carrito(self):
        if self.catalog_screen and self.catalog_screen.vendedor_actual:
            producto = {
                'id_prod': self.id_prod,
                'nombre': self.nombre,
                'precio_caja': self.precio_caja,
                'precio_blister': self.precio_blister,
                'precio_unidad': self.precio_unidad,
            }
            self.catalog_screen.agregar_al_carrito(producto)
        else:
            if not self.catalog_screen or not self.catalog_screen.vendedor_actual:
                popup = Popup(title='Atención', 
                              content=Label(text='Debe seleccionar un vendedor primero'),
                              size_hint=(0.7,0.3))
                popup.open()

    def eliminar_producto(self):
        if self.catalog_screen:
            self.catalog_screen.eliminar_producto(self.id_prod)

# ============================================================
# KV STRING - CON CONTRASEÑAS EN SUCURSALES
# ============================================================
KV_STRING = f'''
#:import COL tema.COL
#:import ic tema.ic

# ============================================================
#  ESTILO GLOBAL DE POPUPS (afecta a todos los Popup de la app)
# ============================================================
<Popup>:
    title_color: COL['text']
    title_size: sp(15)
    title_align: 'center'
    separator_color: COL['accent']
    separator_height: dp(2)
    background: ''
    background_color: (0, 0, 0, 0)
    canvas.before:
        # tarjeta redondeada del popup
        Color:
            rgba: COL['card']
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(18)]

# ============================================================
#  FILA DE PRODUCTO (Tarjeta premium)
# ============================================================
<ProductoRow>:
    orientation: 'horizontal'
    size_hint_y: None
    height: dp(104)
    padding: [dp(12), dp(7)]
    spacing: dp(8)
    canvas.before:
        # sombra
        Color:
            rgba: (0, 0, 0, 0.07)
        RoundedRectangle:
            size: self.width - dp(10), self.height - dp(8)
            pos: self.x + dp(5), self.y + dp(1)
            radius: [dp(14)]
        # tarjeta
        Color:
            rgba: COL['card']
        RoundedRectangle:
            size: self.width - dp(10), self.height - dp(10)
            pos: self.x + dp(5), self.y + dp(5)
            radius: [dp(14)]

    BoxLayout:
        orientation: 'vertical'
        size_hint_x: 0.80
        padding: [dp(6), dp(2), 0, dp(2)]
        spacing: dp(2)
        Label:
            text: root.nombre
            color: COL['text']
            bold: True
            font_size: sp(13)
            text_size: self.width, None
            halign: 'left'
            valign: 'middle'
            shorten: True
            shorten_from: 'right'
            size_hint_y: None
            height: dp(18)
        Label:
            text: "Lab " + root.laboratorio + "   ·   Cod " + root.id_prod
            color: COL['text_mute']
            font_size: sp(9.5)
            text_size: self.width, None
            halign: 'left'
            shorten: True
            size_hint_y: None
            height: dp(14)
        Widget:
            size_hint_y: None
            height: dp(2)
        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: dp(20)
            spacing: dp(4)
            Label:
                text: "Caja [b]" + root.precio_caja + "[/b]"
                markup: True
                color: COL['success_dark']
                font_size: sp(9.5)
                halign: 'left'
                valign: 'middle'
                size_hint_x: 0.32
                text_size: self.size
            Label:
                text: "Blis [b]" + root.precio_blister + "[/b]"
                markup: True
                color: COL['primary']
                font_size: sp(9.5)
                halign: 'left'
                valign: 'middle'
                size_hint_x: 0.32
                text_size: self.size
            Label:
                text: "Und [b]" + root.precio_unidad + "[/b]"
                markup: True
                color: COL['accent_dark']
                font_size: sp(9.5)
                halign: 'left'
                valign: 'middle'
                size_hint_x: 0.30
                text_size: self.size
        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: dp(18)
            spacing: dp(5)
            Widget:
                size_hint_x: None
                width: dp(10)
                canvas:
                    Color:
                        rgba: COL['success'] if root.estado == "SI HAY" else COL['danger']
                    Ellipse:
                        pos: self.x, self.center_y - dp(4)
                        size: dp(8), dp(8)
            Label:
                text: root.estado
                font_size: sp(9.5)
                bold: True
                halign: 'left'
                valign: 'middle'
                text_size: self.size
                color: COL['success'] if root.estado == "SI HAY" else COL['danger']

    BoxLayout:
        orientation: 'vertical'
        size_hint_x: 0.20
        spacing: dp(6)
        padding: [dp(2), dp(20), dp(6), dp(20)]
        MIconButton:
            icon: 'cart_plus'
            bg: COL['success']
            bg_down: COL['success_dark']
            font_size: sp(15)
            radius: dp(9)
            size_hint_y: None
            height: dp(30)
            on_press: root.agregar_al_carrito()
        MIconButton:
            icon: 'trash'
            bg: COL['danger']
            bg_down: COL['danger_dark']
            font_size: sp(13)
            radius: dp(9)
            size_hint_y: None
            height: dp(30)
            on_press: root.eliminar_producto()

# ============================================================
#  PANTALLA DE ACTIVACIÓN
# ============================================================
<ActivationScreen>:
    name: 'activation'
    canvas.before:
        Color:
            rgba: COL['bg']
        Rectangle:
            size: self.size
            pos: self.pos
    BoxLayout:
        orientation: 'vertical'
        padding: [dp(24), dp(36), dp(24), dp(28)]
        spacing: dp(14)
        Widget:
            size_hint_y: None
            height: dp(8)
        Image:
            source: "{LOGO_PATH}"
            allow_stretch: True
            keep_ratio: True
            size_hint: (0.62, None)
            height: dp(78)
            pos_hint: {{'center_x': 0.5}}
        Label:
            text: "Activación requerida"
            font_size: sp(20)
            bold: True
            color: COL['text']
            size_hint_y: None
            height: dp(32)
            halign: 'center'
            text_size: self.width, None
        Label:
            text: "Activa la aplicación para comenzar a usarla"
            font_size: sp(12.5)
            color: COL['text_soft']
            size_hint_y: None
            height: dp(22)
            halign: 'center'
            text_size: self.width, None
        Widget:
            size_hint_y: None
            height: dp(6)
        MCard:
            orientation: 'vertical'
            size_hint_y: None
            height: dp(118)
            padding: [dp(16), dp(14)]
            spacing: dp(8)
            Label:
                text: "ID DEL DISPOSITIVO"
                color: COL['text_mute']
                bold: True
                size_hint_y: None
                height: dp(16)
                font_size: sp(10)
                halign: 'left'
                text_size: self.width, None
            BoxLayout:
                orientation: 'horizontal'
                spacing: dp(8)
                size_hint_y: None
                height: dp(46)
                MTextInput:
                    id: device_id_display
                    text: ""
                    readonly: True
                    font_size: sp(12)
                    foreground_color: COL['primary']
                MTextIconButton:
                    icon: 'copy'
                    label: 'Copiar'
                    icon_size: sp(15)
                    label_size: sp(12)
                    gap: dp(5)
                    size_hint_x: None
                    width: dp(98)
                    bg: COL['primary']
                    bg_down: COL['primary_dark']
                    on_press: root.copiar_id()
        Widget:
            size_hint_y: None
            height: dp(2)
        MTextInput:
            id: codigo_input
            hint_text: "Ingresa tu código de activación"
            size_hint_y: None
            height: dp(50)
            font_size: sp(14)
        MTextIconButton:
            icon: 'check'
            label: 'ACTIVAR'
            icon_size: sp(18)
            label_size: sp(15)
            size_hint_y: None
            height: dp(52)
            bg: COL['accent']
            bg_down: COL['accent_dark']
            on_press: root.activar()
        Label:
            id: error_label
            text: ""
            color: COL['danger']
            size_hint_y: None
            height: dp(22)
            font_size: sp(12)
            halign: 'center'
            text_size: self.width, None
        Widget:
        Label:
            text: "¿No tienes código? Contacta al desarrollador"
            color: COL['text_mute']
            font_size: sp(10.5)
            size_hint_y: None
            height: dp(20)
            halign: 'center'
            text_size: self.width, None
        Label:
            text: "chavezgaravitoj@gmail.com  ·  rinconchavezsantiago555@gmail.com"
            color: COL['primary']
            bold: True
            font_size: sp(10)
            size_hint_y: None
            height: dp(20)
            halign: 'center'
            text_size: self.width, None

# ============================================================
#  PANTALLA PRINCIPAL / CATÁLOGO
# ============================================================
<CatalogScreen>:
    name: 'catalog'
    canvas.before:
        Color:
            rgba: COL['bg']
        Rectangle:
            size: self.size
            pos: self.pos
    BoxLayout:
        orientation: 'vertical'
        spacing: dp(0)

        # ---- ENCABEZADO ----
        BoxLayout:
            size_hint_y: None
            height: dp(92)
            padding: [dp(14), dp(10), dp(14), dp(8)]
            spacing: dp(10)
            canvas.before:
                Color:
                    rgba: COL['primary_dark']
                Rectangle:
                    size: self.size
                    pos: self.pos
                Color:
                    rgba: COL['accent']
                Rectangle:
                    size: self.width, dp(3)
                    pos: self.x, self.y
            Image:
                source: "{LOGO_PATH}"
                size_hint_x: None
                width: dp(96)
                allow_stretch: True
                keep_ratio: True
            BoxLayout:
                orientation: 'vertical'
                spacing: dp(3)
                Label:
                    text: "PRECIOS FARMACENTER"
                    color: COL['white']
                    bold: True
                    font_size: sp(14)
                    halign: 'left'
                    valign: 'bottom'
                    text_size: self.width, None
                    size_hint_y: None
                    height: dp(20)
                Label:
                    id: status_label
                    text: "Base de datos lista"
                    color: (1, 1, 1, 0.75)
                    font_size: sp(9.5)
                    halign: 'left'
                    valign: 'top'
                    text_size: self.width, None
                    size_hint_y: None
                    height: dp(28)
                    shorten: True
                ProgressBar:
                    id: sync_progress
                    max: 100
                    value: 0
                    size_hint_y: None
                    height: dp(4)
                    opacity: 0

        # ---- BARRA DE BÚSQUEDA ----
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            padding: [dp(12), dp(10), dp(12), dp(6)]
            spacing: dp(7)
            MSpinner:
                id: search_spinner
                text: 'NOMBRE'
                values: ('NOMBRE', 'CÓDIGO', 'BARRAS')
                size_hint_x: None
                width: dp(86)
                font_size: sp(11)
                radius: dp(12)
                on_text: root.on_spinner_change(self.text)
            MTextInput:
                id: search_input
                hint_text: "Buscar producto..."
                font_size: sp(14)
                size_hint_x: 1
                on_text: root.on_search_text(self.text)
            MIconButton:
                icon: 'close'
                bg: COL['text_mute']
                bg_down: COL['text_soft']
                size_hint_x: None
                width: dp(44)
                font_size: sp(18)
                radius: dp(12)
                on_press:
                    root.ids.search_input.text = ""
                    root.on_search_text("")
            MButton:
                id: vender_btn
                text: 'VENDER'
                font_size: sp(12)
                size_hint_x: None
                width: dp(96)
                bg: COL['success']
                bg_down: COL['success_dark']
                radius: dp(12)
                disabled: True
                on_press: root.abrir_carrito()

        # ---- LISTA DE PRODUCTOS ----
        RecycleView:
            id: rv
            viewclass: 'ProductoRow'
            bar_width: dp(3)
            RecycleBoxLayout:
                default_size: None, dp(104)
                default_size_hint: 1, None
                size_hint_y: None
                height: self.minimum_height
                orientation: 'vertical'
                spacing: dp(2)
                padding: [0, dp(4), 0, dp(4)]

        # ---- BOTONES INFERIORES ----
        BoxLayout:
            size_hint_y: None
            height: dp(64)
            spacing: dp(8)
            padding: [dp(12), dp(8), dp(12), dp(10)]
            canvas.before:
                Color:
                    rgba: COL['card']
                Rectangle:
                    size: self.size
                    pos: self.pos
                Color:
                    rgba: COL['border']
                Rectangle:
                    size: self.width, dp(1)
                    pos: self.x, self.top - dp(1)
            MTextIconButton:
                icon: 'sync'
                label: 'SINCRONIZAR'
                icon_size: sp(16)
                label_size: sp(10.5)
                bg: COL['primary']
                bg_down: COL['primary_dark']
                on_press: root.sincronizar()
            MTextIconButton:
                icon: 'chart'
                label: 'VENTAS'
                icon_size: sp(16)
                label_size: sp(10.5)
                size_hint_x: 0.42
                bg: COL['accent']
                bg_down: COL['accent_dark']
                on_press: root.ir_historial_ventas()
            MTextIconButton:
                icon: 'store'
                label: 'SUCURSAL'
                icon_size: sp(16)
                label_size: sp(10.5)
                size_hint_x: 0.46
                bg: COL['text_soft']
                bg_down: COL['text']
                font_size: sp(11)
                on_press: app.ir_a_seleccion_sucursal()

# ============================================================
#  HISTORIAL DE VENTAS
# ============================================================
<HistorialVentasScreen>:
    name: 'historial_ventas'
    canvas.before:
        Color:
            rgba: COL['bg']
        Rectangle:
            size: self.size
            pos: self.pos
    BoxLayout:
        orientation: 'vertical'
        spacing: dp(0)
        # encabezado
        BoxLayout:
            size_hint_y: None
            height: dp(64)
            padding: [dp(16), 0]
            canvas.before:
                Color:
                    rgba: COL['primary_dark']
                Rectangle:
                    size: self.size
                    pos: self.pos
                Color:
                    rgba: COL['accent']
                Rectangle:
                    size: self.width, dp(3)
                    pos: self.x, self.y
            Label:
                text: "HISTORIAL DE VENTAS"
                color: COL['white']
                bold: True
                font_size: sp(16)
                halign: 'center'
                valign: 'middle'
                text_size: self.size

        BoxLayout:
            orientation: 'vertical'
            padding: [dp(12), dp(12), dp(12), dp(8)]
            spacing: dp(10)

            # filtros
            BoxLayout:
                size_hint_y: None
                height: dp(46)
                spacing: dp(8)
                MSpinner:
                    id: filtro_vendedor
                    text: 'TODOS'
                    values: ['TODOS']
                    size_hint_x: 0.5
                    font_size: sp(11)
                    on_text: root.aplicar_filtros()
                MSpinner:
                    id: filtro_periodo
                    text: 'TODAS'
                    values: ['TODAS', 'HOY', 'AYER', 'ÚLTIMA SEMANA', 'ÚLTIMO MES', 'ESTE MES']
                    size_hint_x: 0.5
                    font_size: sp(11)
                    on_text: root.aplicar_filtros()

            # tarjeta total
            MCard:
                size_hint_y: None
                height: dp(58)
                padding: [dp(16), dp(8)]
                spacing: dp(8)
                bg: COL['primary_light']
                Label:
                    text: "TOTAL"
                    color: COL['primary_dark']
                    bold: True
                    font_size: sp(11)
                    halign: 'left'
                    valign: 'middle'
                    text_size: self.size
                    size_hint_x: 0.3
                Label:
                    id: total_label
                    text: "Total: $0"
                    color: COL['success_dark']
                    bold: True
                    font_size: sp(18)
                    halign: 'right'
                    valign: 'middle'
                    text_size: self.size

            # lista
            ScrollView:
                id: scroll_ventas
                bar_width: dp(3)
                BoxLayout:
                    id: ventas_container
                    orientation: 'vertical'
                    size_hint_y: None
                    height: self.minimum_height
                    spacing: dp(8)
                    padding: [0, 0, 0, dp(8)]

            # acciones
            BoxLayout:
                size_hint_y: None
                height: dp(54)
                spacing: dp(8)
                MTextIconButton:
                    icon: 'pdf'
                    label: 'EXPORTAR PDF'
                    icon_size: sp(17)
                    label_size: sp(12)
                    bg: COL['danger']
                    bg_down: COL['danger_dark']
                    on_press: root.exportar_pdf()
                MTextIconButton:
                    icon: 'back'
                    label: 'CERRAR'
                    icon_size: sp(16)
                    label_size: sp(12)
                    size_hint_x: 0.42
                    bg: COL['text_soft']
                    bg_down: COL['text']
                    on_press: root.cerrar_historial()

# ============================================================
#  SELECCIÓN DE SUCURSAL
# ============================================================
<SucursalSelectionScreen>:
    name: 'sucursal_selection'
    canvas.before:
        Color:
            rgba: COL['bg']
        Rectangle:
            size: self.size
            pos: self.pos
    BoxLayout:
        orientation: 'vertical'
        padding: [dp(24), dp(36), dp(24), dp(30)]
        spacing: dp(14)
        BoxLayout:
            size_hint_y: None
            height: dp(96)
            Image:
                source: "{LOGO_PATH}"
                allow_stretch: True
                keep_ratio: True
                pos_hint: {{'center_x': 0.5}}
        Label:
            text: 'Sistema de consulta de precios'
            color: COL['text_soft']
            font_size: sp(12)
            size_hint_y: None
            height: dp(22)
            halign: 'center'
            text_size: self.width, None
        Label:
            text: 'Selecciona tu sucursal'
            font_size: sp(20)
            bold: True
            color: COL['text']
            size_hint_y: None
            height: dp(36)
            halign: 'center'
            text_size: self.width, None
        Widget:
            size_hint_y: None
            height: dp(4)
        GridLayout:
            cols: 1
            spacing: dp(12)
            MTextIconButton:
                icon: 'corn'
                label: 'Maíz Amarillo'
                icon_size: sp(20)
                label_size: sp(15)
                gap: dp(10)
                size_hint_y: None
                height: dp(58)
                bg: COL['primary']
                bg_down: COL['primary_dark']
                on_press: root.seleccionar_con_contraseña('Maíz Amarillo')
            MTextIconButton:
                icon: 'leaf'
                label: 'Terranova'
                icon_size: sp(20)
                label_size: sp(15)
                gap: dp(10)
                size_hint_y: None
                height: dp(58)
                bg: COL['primary']
                bg_down: COL['primary_dark']
                on_press: root.seleccionar_con_contraseña('Terranova')
            MTextIconButton:
                icon: 'city'
                label: 'Villaceleste'
                icon_size: sp(20)
                label_size: sp(15)
                gap: dp(10)
                size_hint_y: None
                height: dp(58)
                bg: COL['primary']
                bg_down: COL['primary_dark']
                on_press: root.seleccionar_con_contraseña('Villaceleste')
            MTextIconButton:
                icon: 'building'
                label: 'Covipro'
                icon_size: sp(20)
                label_size: sp(15)
                gap: dp(10)
                size_hint_y: None
                height: dp(58)
                bg: COL['primary']
                bg_down: COL['primary_dark']
                on_press: root.seleccionar_con_contraseña('Covipro')
        Widget:

# ============================================================
#  PANTALLA DE CARGA (SPLASH)
# ============================================================
<PreSplashScreen>:
    name: 'splash'
    canvas.before:
        Color:
            rgba: COL['primary_dark']
        Rectangle:
            size: self.size
            pos: self.pos
    BoxLayout:
        orientation: 'vertical'
        padding: dp(30)
        BoxLayout:
            size_hint_y: 0.62
            Image:
                source: "{LOGO_PATH}"
                allow_stretch: True
                keep_ratio: True
        Label:
            id: status_label
            text: "Iniciando Sistema..."
            color: COL['white']
            bold: True
            font_size: sp(15)
            size_hint_y: None
            height: dp(36)
            halign: 'center'
            text_size: self.width, None
        Label:
            id: sucursal_label
            text: ""
            color: (1, 1, 1, 0.7)
            font_size: sp(11.5)
            size_hint_y: None
            height: dp(24)
            halign: 'center'
            text_size: self.width, None
        Widget:
            size_hint_y: 0.12
'''

# Registrar la fuente de iconos vectoriales ANTES de cargar el KV
registrar_fuentes()

Builder.load_string(KV_STRING)


# ============================================================
# CLASES DE PANTALLAS
# ============================================================
class ActivationScreen(Screen):
    def on_enter(self):
        app = App.get_running_app()
        if app.device_id is None:
            app.device_id = generar_device_id()
            app.guardar_configuracion_completa()
        self.ids.device_id_display.text = str(app.device_id) if app.device_id else "Error generando ID"
        self.ids.error_label.text = ""

    def copiar_id(self):
        Clipboard.copy(self.ids.device_id_display.text)
        self.ids.error_label.text = "ID copiado al portapapeles"
        Clock.schedule_once(lambda dt: setattr(self.ids.error_label, 'text', ''), 2)

    def activar(self):
        app = App.get_running_app()
        codigo = self.ids.codigo_input.text.strip().upper()
        if verificar_codigo(app.device_id, codigo):
            guardar_licencia(app.device_id, codigo)
            app.activated = True
            app.guardar_configuracion_completa()
            self.manager.current = 'sucursal_selection'
        else:
            self.ids.error_label.text = "Código incorrecto. Verifique e intente nuevamente."


class HistorialVentasScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.catalog_screen = None
    
    def on_enter(self):
        app = App.get_running_app()
        if app.sucursal_actual:
            vendedores = obtener_vendedores(app.sucursal_actual)
            valores = ['TODOS'] + [v['nombre'] for v in vendedores]
            self.ids.filtro_vendedor.values = valores
        self.aplicar_filtros()
    
    def _calcular_fechas(self, periodo):
        hoy = datetime.now()
        fecha_hoy_str = hoy.strftime("%d/%m/%Y")
        
        if periodo == 'HOY':
            return fecha_hoy_str, fecha_hoy_str
        elif periodo == 'AYER':
            ayer = hoy - timedelta(days=1)
            fecha_str = ayer.strftime("%d/%m/%Y")
            return fecha_str, fecha_str
        elif periodo == 'ÚLTIMA SEMANA':
            inicio = hoy - timedelta(days=7)
            return inicio.strftime("%d/%m/%Y"), fecha_hoy_str
        elif periodo == 'ÚLTIMO MES':
            inicio = hoy - timedelta(days=30)
            return inicio.strftime("%d/%m/%Y"), fecha_hoy_str
        elif periodo == 'ESTE MES':
            inicio = hoy.replace(day=1)
            return inicio.strftime("%d/%m/%Y"), fecha_hoy_str
        else:
            return None, None
    
    def aplicar_filtros(self, *args):
        app = App.get_running_app()
        if not app.sucursal_actual:
            return
        
        filtro_vendedor = self.ids.filtro_vendedor.text
        filtro_periodo = self.ids.filtro_periodo.text
        
        fecha_inicio, fecha_fin = self._calcular_fechas(filtro_periodo)
        
        ventas = obtener_ventas(sucursal=app.sucursal_actual)
        
        if filtro_vendedor != 'TODOS':
            ventas = [v for v in ventas if v.get('vendedor_nombre', '') == filtro_vendedor]
        
        if fecha_inicio and fecha_fin:
            ventas_filtradas = []
            for v in ventas:
                fecha_venta = v.get('fecha', '')
                if fecha_inicio <= fecha_venta <= fecha_fin:
                    ventas_filtradas.append(v)
            ventas = ventas_filtradas
        
        total = calcular_total_ventas(ventas)
        self.ids.total_label.text = f"Total: ${total:,.0f}"
        self.mostrar_ventas(ventas)
    
    def mostrar_ventas(self, ventas):
        container = self.ids.ventas_container
        container.clear_widgets()
        
        if not ventas:
            container.add_widget(Label(text="No hay ventas en este período", color=COL['text_mute'], font_size=sp(12.5)))
            return
        
        for v in ventas:
            precio_total = float(v.get('precio_total', 0))
            cambio = float(v.get('cambio', 0))
            id_venta = v.get('id', '')
            
            fila = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(82),
                            padding=[dp(12), dp(8)], spacing=dp(6))
            def _draw_vrow(inst, *a):
                inst.canvas.before.clear()
                from kivy.graphics import Color as _C, RoundedRectangle as _RR
                with inst.canvas.before:
                    _C(0, 0, 0, 0.06)
                    _RR(pos=(inst.x, inst.y - dp(1)), size=inst.size, radius=[dp(12)])
                    _C(*COL['card'])
                    _RR(pos=inst.pos, size=inst.size, radius=[dp(12)])
            fila.bind(pos=_draw_vrow, size=_draw_vrow)
            _draw_vrow(fila)
            
            info_col = BoxLayout(orientation='vertical', size_hint_x=0.82, spacing=dp(2))
            
            lbl1 = Label(text=f"{v.get('producto_nombre', '')} - {v.get('formato', '')} x{v.get('cantidad', '1')}",
                        color=COL['text'], bold=True, font_size=sp(12.5), halign='left', valign='middle',
                        size_hint_y=None, height=dp(20), shorten=True)
            lbl1.bind(size=lambda i,*a: setattr(i,'text_size',i.size))
            info_col.add_widget(lbl1)
            
            lbl2 = Label(text=f"Vendedor: {v.get('vendedor_nombre', '')}  ·  {v.get('fecha', '')} {v.get('hora', '')}",
                        color=COL['text_mute'], font_size=sp(10), halign='left', valign='middle',
                        size_hint_y=None, height=dp(18), shorten=True)
            lbl2.bind(size=lambda i,*a: setattr(i,'text_size',i.size))
            info_col.add_widget(lbl2)
            
            lbl3 = Label(text=f"Total ${precio_total:,.0f}  ·  Recibido ${float(v.get('dinero_recibido', 0)):,.0f}  ·  Cambio ${cambio:,.0f}",
                        color=COL['success_dark'], bold=True, font_size=sp(10), halign='left', valign='middle',
                        size_hint_y=None, height=dp(20), shorten=True)
            lbl3.bind(size=lambda i,*a: setattr(i,'text_size',i.size))
            info_col.add_widget(lbl3)
            
            fila.add_widget(info_col)
            
            btn_eliminar = MIconButton(icon='trash', size_hint_x=0.18,
                                  bg=COL['danger'], bg_down=COL['danger_dark'], font_size=sp(16), radius=dp(10))
            btn_eliminar.bind(on_press=lambda instance, id_venta=id_venta: self.confirmar_eliminar_venta(id_venta))
            fila.add_widget(btn_eliminar)
            
            container.add_widget(fila)
    
    def confirmar_eliminar_venta(self, id_venta):
        content = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(12))
        content.add_widget(Label(text=f"¿Eliminar venta ID {id_venta}\npermanentemente?",
                                 font_size=sp(13), color=COL['text'], halign='center'))
        btn_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48), spacing=dp(8))
        btn_si = MButton(text="SÍ, ELIMINAR",
                         bg=COL['danger'], bg_down=COL['danger_dark'], font_size=sp(12))
        btn_no = MButton(text="CANCELAR", bg=COL['text_soft'], bg_down=COL['text'], font_size=sp(12))
        btn_box.add_widget(btn_si)
        btn_box.add_widget(btn_no)
        content.add_widget(btn_box)
        
        popup = Popup(title='Confirmar eliminación', content=content,
                      size_hint=(0.82, 0.4), auto_dismiss=False)
        
        def confirmar(instance):
            if eliminar_venta_por_id(id_venta):
                popup.dismiss()
                self.aplicar_filtros()
                content_ok = BoxLayout(orientation='vertical', padding=dp(8))
                content_ok.add_widget(Label(text=f"Venta ID {id_venta} eliminada", color=(0.1,0.6,0.1,1), font_size=sp(12)))
                popup_ok = Popup(title='Éxito', content=content_ok, size_hint=(0.6,0.3), auto_dismiss=True)
                popup_ok.open()
            else:
                popup.dismiss()
                content_err = BoxLayout(orientation='vertical', padding=dp(8))
                content_err.add_widget(Label(text="Error al eliminar venta", color=(0.8,0.2,0.1,1), font_size=sp(12)))
                popup_err = Popup(title='Error', content=content_err, size_hint=(0.6,0.3), auto_dismiss=True)
                popup_err.open()
        
        btn_si.bind(on_press=confirmar)
        btn_no.bind(on_press=popup.dismiss)
        popup.open()

    def exportar_pdf(self):
        if not PDF_DISPONIBLE:
            popup = Popup(title='Error', content=Label(text='FPDF no está instalado en este dispositivo', font_size=sp(12)),
                         size_hint=(0.7, 0.3))
            popup.open()
            return
        
        app = App.get_running_app()
        if not app.sucursal_actual:
            return
        
        filtro_vendedor = self.ids.filtro_vendedor.text
        filtro_periodo = self.ids.filtro_periodo.text
        fecha_inicio, fecha_fin = self._calcular_fechas(filtro_periodo)
        
        ventas = obtener_ventas(sucursal=app.sucursal_actual)
        
        if filtro_vendedor != 'TODOS':
            ventas = [v for v in ventas if v.get('vendedor_nombre', '') == filtro_vendedor]
        
        if fecha_inicio and fecha_fin:
            ventas_filtradas = []
            for v in ventas:
                fecha_venta = v.get('fecha', '')
                if fecha_inicio <= fecha_venta <= fecha_fin:
                    ventas_filtradas.append(v)
            ventas = ventas_filtradas
        
        if not ventas:
            popup = Popup(title='Sin datos', content=Label(text='No hay ventas para exportar', font_size=sp(12)),
                         size_hint=(0.7, 0.3))
            popup.open()
            return
        
        if platform == 'android':
            try:
                request_permissions([Permission.WRITE_EXTERNAL_STORAGE])
                if primary_external_storage_path:
                    ruta_guardado = os.path.join(primary_external_storage_path(), 'Download')
                else:
                    ruta_guardado = RUTA_BASE
            except Exception as e:
                logger.warning(f"Permiso de almacenamiento no disponible, usando ruta interna: {e}")
                ruta_guardado = RUTA_BASE
        else:
            ruta_guardado = RUTA_BASE
        
        os.makedirs(ruta_guardado, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"reporte_ventas_{timestamp}.pdf"
        ruta_completa = os.path.join(ruta_guardado, nombre_archivo)
        
        try:
            pdf = FPDF(orientation='P', unit='mm', format='A4')
            pdf.add_page()
            
            pdf.set_font('Arial', 'B', 16)
            pdf.cell(0, 10, 'REPORTE DE VENTAS', ln=True, align='C')
            pdf.ln(5)
            
            pdf.set_font('Arial', '', 10)
            pdf.cell(0, 8, f"Sucursal: {app.sucursal_actual} | Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')
            pdf.ln(5)
            
            pdf.set_font('Arial', 'B', 9)
            col_widths = [90, 20, 30, 30]
            pdf.cell(col_widths[0], 8, 'Producto', border=1)
            pdf.cell(col_widths[1], 8, 'Cant.', border=1, align='C')
            pdf.cell(col_widths[2], 8, 'Precio Unit.', border=1, align='C')
            pdf.cell(col_widths[3], 8, 'Total', border=1, align='C')
            pdf.ln()
            
            pdf.set_font('Arial', '', 8)
            total_general = 0
            
            for v in ventas:
                try:
                    producto = v.get('producto_nombre', 'Desconocido')[:30]
                    cantidad = str(v.get('cantidad', 0))
                    precio_unitario = f"${float(v.get('precio_unitario', 0)):,.0f}"
                    total = float(v.get('precio_total', 0))
                    total_general += total
                    
                    pdf.cell(col_widths[0], 7, producto, border=1)
                    pdf.cell(col_widths[1], 7, cantidad, border=1, align='C')
                    pdf.cell(col_widths[2], 7, precio_unitario, border=1, align='R')
                    pdf.cell(col_widths[3], 7, f"${total:,.0f}", border=1, align='R')
                    pdf.ln()
                except Exception as e:
                    logger.warning(f"Fila de venta omitida en PDF: {e}")
            
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(col_widths[0] + col_widths[1] + col_widths[2], 8, 'TOTAL GENERAL', border=1, align='R')
            pdf.cell(col_widths[3], 8, f"${total_general:,.0f}", border=1, align='R')
            
            pdf.output(ruta_completa)
            
            mensaje = f"PDF guardado en:\n{ruta_completa}"
            content = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(8))
            content.add_widget(Label(text=mensaje, halign='center', text_size=(dp(200), None), font_size=sp(11)))
            btn_ok = Button(text="OK", size_hint_y=None, height=dp(34), font_size=sp(12))
            popup_exito = Popup(title='✅ Reporte generado', content=content, size_hint=(0.8, 0.5))
            btn_ok.bind(on_press=popup_exito.dismiss)
            content.add_widget(btn_ok)
            popup_exito.open()
            
            if platform == 'android':
                try:
                    from android import intent
                    intent.action_view(ruta_completa)
                except Exception as e:
                    logger.warning(f"No se pudo abrir el PDF automáticamente: {e}")
                    
        except Exception as e:
            logger.error(f"Error generando PDF: {e}")
            popup = Popup(title='Error', content=Label(text=f'Error al generar PDF:\n{str(e)}', font_size=sp(11)),
                         size_hint=(0.8, 0.4))
            popup.open()
    
    def cerrar_historial(self):
        app = App.get_running_app()
        app.root.current = 'catalog'


class SucursalSelectionScreen(Screen):
    def seleccionar_con_contraseña(self, sucursal):
        """Muestra un popup para ingresar la contraseña antes de cambiar de sucursal"""
        app = App.get_running_app()
        
        # Si es la primera vez (no hay sucursal seleccionada) no pedir contraseña
        if app.sucursal_actual is None:
            app.seleccionar_sucursal(sucursal)
            return
        
        # Si ya está en esa sucursal, no hacer nada
        if app.sucursal_actual == sucursal:
            app.seleccionar_sucursal(sucursal)  # Simplemente recarga
            return
        
        # Crear popup para pedir contraseña
        content = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(12))
        
        # Mensaje
        content.add_widget(Label(
            text=f"Ingresa la contraseña para\n[b]{sucursal}[/b]",
            markup=True,
            font_size=sp(15),
            color=COL['text'],
            halign='center',
            size_hint_y=None,
            height=dp(50)
        ))
        
        # Campo de contraseña
        txt_password = MTextInput(
            hint_text="Contraseña",
            password=True,
            password_mask='●',
            font_size=sp(16),
            size_hint_y=None,
            height=dp(50)
        )
        content.add_widget(txt_password)
        
        # Mensaje de error
        lbl_error = Label(
            text="",
            color=(0.8, 0.2, 0.1, 1),
            font_size=sp(12),
            size_hint_y=None,
            height=dp(25)
        )
        content.add_widget(lbl_error)
        
        # Botones
        btn_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), spacing=dp(10))
        btn_aceptar = MButton(text="ACEPTAR", bg=COL['success'], bg_down=COL['success_dark'], font_size=sp(13))
        btn_cancelar = MButton(text="CANCELAR", bg=COL['text_soft'], bg_down=COL['text'], font_size=sp(13))
        btn_box.add_widget(btn_aceptar)
        btn_box.add_widget(btn_cancelar)
        content.add_widget(btn_box)
        
        popup = Popup(
            title='Cambiar sucursal',
            content=content,
            size_hint=(0.85, 0.5),
            auto_dismiss=False
        )
        
        def verificar(instance):
            password_ingresada = txt_password.text.strip()

            if verificar_contrasena_sucursal(sucursal, password_ingresada):
                popup.dismiss()
                app.seleccionar_sucursal(sucursal)
            else:
                lbl_error.text = "❌ Contraseña incorrecta"
                txt_password.text = ""
                txt_password.focus = True
        
        def cancelar(instance):
            popup.dismiss()
        
        def enfocar_input(dt):
            txt_password.focus = True
            
        btn_aceptar.bind(on_press=verificar)
        btn_cancelar.bind(on_press=cancelar)
        txt_password.bind(on_text_validate=verificar)  # Enter key
        
        popup.open()
        Clock.schedule_once(enfocar_input, 0.1)


class PreSplashScreen(Screen):
    def on_enter(self):
        app = App.get_running_app()
        if hasattr(self.ids, 'sucursal_label') and app.sucursal_actual:
            self.ids.sucursal_label.text = f"Sucursal: {app.sucursal_actual}"
        Clock.schedule_once(lambda dt: self.cargar_datos(), 0.5)

    def cargar_datos(self):
        app = App.get_running_app()
        if hasattr(self.ids, 'status_label'):
            self.ids.status_label.text = "Verificando base de datos..."
        if app.contar_productos() == 0:
            if hasattr(self.ids, 'status_label'):
                self.ids.status_label.text = "Descargando datos por primera vez..."
            app.descargar_y_sincronizar(self.on_sync_complete)
        else:
            self.on_sync_complete(True)

    def on_sync_complete(self, success, error_msg=""):
        if success:
            Clock.schedule_once(lambda dt: self.ir_al_catalogo(), 0.5)
        else:
            if hasattr(self.ids, 'status_label'):
                self.ids.status_label.text = "Error al cargar datos"
            if hasattr(self.ids, 'sucursal_label'):
                self.ids.sucursal_label.text = f"Error: {error_msg[:50]}"
            content = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(8))
            content.add_widget(Label(
                text=f'No se pudieron cargar los datos.\n{error_msg}\n\nRevise su conexión a internet.',
                color=(0.1, 0.1, 0.1, 1), halign='center', font_size=sp(11)))
            popup = Popup(title='Error de sincronización', content=content,
                         size_hint=(0.85, 0.45), title_color=(0.1, 0.35, 0.65, 1),
                         title_size=sp(14), separator_color=(0.8, 0.8, 0.8, 1))
            popup.open()
            Clock.schedule_once(lambda dt: self.ir_al_catalogo(), 3)

    def ir_al_catalogo(self):
        app = App.get_running_app()
        app.root.current = 'catalog'
        catalog = app.root.get_screen('catalog')
        catalog.limpiar_vendedor()
        Clock.schedule_once(lambda dt: catalog.mostrar_seleccion_vendedor(), 0.5)


class CatalogScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._search_event = None
        self.vendedor_actual = None
        self.carrito = []
        self.carrito_popup = None
        self.venta_popup = None

    def on_enter(self):
        self.conectar_db()
        Clock.schedule_once(lambda dt: self.buscar_productos(""), 0.1)
        self.actualizar_header_sucursal()
        inicializar_vendedores()
        self.actualizar_boton_vender()
        # ============================================================
        # NUEVO: Mostrar sucursal cargada
        # ============================================================
        app = App.get_running_app()
        if app.sucursal_actual:
            self.mostrar_mensaje_temporal(f"✅ Sucursal: {app.sucursal_actual}")

    def limpiar_vendedor(self):
        self.vendedor_actual = None
        self.carrito = []
        self.actualizar_boton_vender()
        self.actualizar_header_sucursal()

    def actualizar_header_sucursal(self):
        app = App.get_running_app()
        if app.sucursal_actual and hasattr(self.ids, 'status_label'):
            ultima_sync = app.obtener_ultima_sync(app.sucursal_actual)
            vendedor_text = f" | Vendedor: {self.vendedor_actual['nombre'] if self.vendedor_actual else 'No seleccionado'}"
            if ultima_sync:
                self.ids.status_label.text = f"Sucursal: {app.sucursal_actual} | Últ. sync: {ultima_sync}{vendedor_text}"
            else:
                self.ids.status_label.text = f"Sucursal: {app.sucursal_actual} | Sin sincronización{vendedor_text}"

    def conectar_db(self):
        app = App.get_running_app()
        try:
            self.conn = sqlite3.connect(app.db_path, check_same_thread=False)
            self.cursor = self.conn.cursor()
            self.cursor.execute("PRAGMA table_info(productos)")
            columnas = [row[1] for row in self.cursor.fetchall()]
            if columnas and 'p_caja' not in columnas:
                self.cursor.execute("DROP TABLE IF EXISTS productos")
            self.cursor.execute('''CREATE TABLE IF NOT EXISTS productos
                (id TEXT, barras TEXT, laboratorio TEXT, nombre TEXT,
                 p_caja REAL, p_blister REAL, p_unidad REAL)''')
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_nombre ON productos(nombre)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_id ON productos(id)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_barras ON productos(barras)")
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error conectando DB: {e}")

    def safe_float(self, valor):
        if not valor:
            return 0.0
        try:
            limpio = str(valor).strip().replace(",", "")
            return float(limpio)
        except (ValueError, TypeError):
            return 0.0

    def _fmt(self, valor):
        return f"$ {valor:,.0f}"

    def on_spinner_change(self, modo_texto):
        if modo_texto == 'NOMBRE':
            self.ids.search_input.hint_text = "Buscar por nombre..."
        elif modo_texto == 'CÓDIGO':
            self.ids.search_input.hint_text = "Buscar por código..."
        elif modo_texto == 'BARRAS':
            self.ids.search_input.hint_text = "Buscar por código de barras..."
        self.on_search_text(self.ids.search_input.text)

    def on_search_text(self, texto):
        if self._search_event:
            self._search_event.cancel()
        self._search_event = Clock.schedule_once(lambda dt: self.buscar_productos(texto), 0.3)

    def buscar_productos(self, texto=""):
        t = texto.strip().upper()
        modos = {'NOMBRE': 'nombre', 'CÓDIGO': 'id', 'BARRAS': 'barras'}
        spinner = self.ids.get('search_spinner')
        campo = modos.get(spinner.text, 'nombre') if spinner else 'nombre'
        try:
            if not t:
                query = "SELECT id, barras, laboratorio, nombre, p_caja, p_blister, p_unidad FROM productos ORDER BY nombre ASC LIMIT 100"
                params = []
            elif campo == 'nombre':
                palabras = t.split()
                condiciones = " AND ".join(["nombre LIKE ?" for _ in palabras])
                query = f"SELECT id, barras, laboratorio, nombre, p_caja, p_blister, p_unidad FROM productos WHERE {condiciones} ORDER BY nombre ASC LIMIT 100"
                params = [f"%{p}%" for p in palabras]
            else:
                query = f"SELECT id, barras, laboratorio, nombre, p_caja, p_blister, p_unidad FROM productos WHERE {campo} LIKE ? ORDER BY nombre ASC LIMIT 100"
                params = [f"%{t}%"]
            self.cursor.execute(query, params)
            filas = self.cursor.fetchall()
            data = []
            for r in filas:
                precio_caja = self.safe_float(r[4])
                precio_blister = self.safe_float(r[5])
                precio_unidad = self.safe_float(r[6])
                if precio_caja > 500 or precio_blister > 500 or precio_unidad > 500:
                    estado = "SI HAY"
                else:
                    estado = "NO HAY"
                item = {
                    'id_prod': str(r[0] or ""),
                    'barras': str(r[1] or ""),
                    'laboratorio': str(r[2] or "S/L"),
                    'nombre': str(r[3] or "Sin nombre"),
                    'precio_caja': self._fmt(precio_caja),
                    'precio_blister': self._fmt(precio_blister),
                    'precio_unidad': self._fmt(precio_unidad),
                    'estado': estado,
                    'catalog_screen': self
                }
                data.append(item)
            self.ids.rv.data = data
        except Exception as e:
            logger.error(f"Error en búsqueda: {e}")

    def eliminar_producto(self, id_prod):
        if not id_prod:
            return
        
        content = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(12))
        content.add_widget(Label(text=f"¿Eliminar producto\nID: {id_prod}?",
                                 font_size=sp(13), color=COL['text'], halign='center'))
        btn_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48), spacing=dp(8))
        btn_si = MButton(text="SÍ, ELIMINAR",
                         bg=COL['danger'], bg_down=COL['danger_dark'], font_size=sp(12))
        btn_no = MButton(text="CANCELAR", bg=COL['text_soft'], bg_down=COL['text'], font_size=sp(12))
        btn_box.add_widget(btn_si)
        btn_box.add_widget(btn_no)
        content.add_widget(btn_box)
        
        popup = Popup(title='Confirmar eliminación', content=content,
                      size_hint=(0.82, 0.4), auto_dismiss=False)
        
        def confirmar_eliminar(instance):
            try:
                self.cursor.execute("DELETE FROM productos WHERE id = ?", (id_prod,))
                self.conn.commit()
                popup.dismiss()
                self.mostrar_mensaje_temporal(f"🗑 Producto {id_prod} eliminado")
                self.buscar_productos(self.ids.search_input.text)
            except Exception as e:
                popup.dismiss()
                logger.error(f"Error eliminando producto: {e}")
                self.mostrar_mensaje_temporal("Error al eliminar")
        
        btn_si.bind(on_press=confirmar_eliminar)
        btn_no.bind(on_press=popup.dismiss)
        popup.open()

    # ============================================================
    # FUNCIONES DE VENDEDOR Y CARRITO
    # ============================================================
    def actualizar_boton_vender(self):
        btn = self.ids.vender_btn
        if self.vendedor_actual:
            btn.disabled = False
            btn.text = f"VENDER ({len(self.carrito)})" if self.carrito else "VENDER"
        else:
            btn.disabled = True
            btn.text = "VENDER"

    def mostrar_seleccion_vendedor(self):
        if self.vendedor_actual:
            return
        
        app = App.get_running_app()
        if not app.sucursal_actual:
            return
        
        vendedores = obtener_vendedores(app.sucursal_actual)
        if not vendedores:
            inicializar_vendedores()
            vendedores = obtener_vendedores(app.sucursal_actual)
        
        content = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(10))
        content.add_widget(Label(text="Selecciona un vendedor", font_size=sp(15),
                                 color=COL['text'], bold=True,
                                 size_hint_y=None, height=dp(28)))

        scroll_v = ScrollView(bar_width=dp(3))
        lista_v = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(8))
        lista_v.bind(minimum_height=lista_v.setter('height'))
        for v in vendedores:
            btn = MButton(text=f"{v['codigo']} - {v['nombre']}",
                          size_hint_y=None, height=dp(48),
                          bg=COL['primary'], bg_down=COL['primary_dark'],
                          font_size=sp(13))
            btn.bind(on_press=lambda instance, v=v: self.seleccionar_vendedor(v))
            lista_v.add_widget(btn)
        scroll_v.add_widget(lista_v)
        content.add_widget(scroll_v)

        popup = Popup(title='Seleccionar vendedor', content=content,
                     size_hint=(0.85, 0.6), auto_dismiss=False)
        self._popup_vendedor = popup
        popup.open()

    def seleccionar_vendedor(self, vendedor):
        self.vendedor_actual = vendedor
        self.actualizar_boton_vender()
        self.actualizar_header_sucursal()
        if hasattr(self, '_popup_vendedor'):
            self._popup_vendedor.dismiss()

    def agregar_al_carrito(self, producto):
        for item in self.carrito:
            if item['producto']['id_prod'] == producto['id_prod']:
                item['cantidad'] += 1
                self.actualizar_carrito_popup()
                self.actualizar_boton_vender()
                self.mostrar_mensaje_temporal(f"📦 {producto['nombre'][:20]} +1")
                return
        
        item = {
            'producto': producto,
            'formato': 'Unidad',
            'cantidad': 1,
            'precio_unitario': self.obtener_precio(producto, 'Unidad')
        }
        self.carrito.append(item)
        self.actualizar_boton_vender()
        self.mostrar_mensaje_temporal(f"➕ {producto['nombre'][:20]}")

    def obtener_precio(self, producto, formato):
        if formato == 'Caja':
            return float(producto['precio_caja'].replace('$ ', '').replace(',', '')) if producto['precio_caja'] else 0
        elif formato == 'Blister':
            return float(producto['precio_blister'].replace('$ ', '').replace(',', '')) if producto['precio_blister'] else 0
        else:
            return float(producto['precio_unidad'].replace('$ ', '').replace(',', '')) if producto['precio_unidad'] else 0

    def mostrar_mensaje_temporal(self, mensaje):
        original = self.ids.status_label.text
        self.ids.status_label.text = f"{mensaje}"
        Clock.schedule_once(lambda dt: setattr(self.ids.status_label, 'text', original), 2)

    def eliminar_del_carrito(self, index):
        if 0 <= index < len(self.carrito):
            del self.carrito[index]
            self.actualizar_carrito_popup()
            self.actualizar_boton_vender()

    def actualizar_carrito_popup(self):
        if self.carrito_popup and self.carrito_popup._window:
            self.carrito_popup.dismiss()
            self.abrir_carrito()

    def abrir_carrito(self):
        if not self.vendedor_actual:
            popup = Popup(title='Atención', content=Label(text='Seleccione un vendedor primero', font_size=sp(12)),
                          size_hint=(0.7, 0.3))
            popup.open()
            return
        
        if not self.carrito:
            popup = Popup(title='Carrito vacío', content=Label(text='Agregue productos con el botón "+"', font_size=sp(12)),
                          size_hint=(0.7, 0.3))
            popup.open()
            return
        
        content = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(8))
        
        scroll = ScrollView(bar_width=dp(3))
        lista_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(3))
        lista_box.bind(minimum_height=lista_box.setter('height'))
        
        total_venta = 0
        
        for idx, item in enumerate(self.carrito):
            producto = item['producto']
            formato = item['formato']
            cantidad = item['cantidad']
            precio_unitario = item['precio_unitario']
            subtotal = precio_unitario * cantidad
            total_venta += subtotal
            
            fila = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(90),
                            padding=[dp(10),dp(8)], spacing=dp(4))
            def _draw_fila(inst, *a):
                inst.canvas.before.clear()
                from kivy.graphics import Color as _C, RoundedRectangle as _RR
                with inst.canvas.before:
                    _C(*COL['primary_light'])
                    _RR(pos=inst.pos, size=inst.size, radius=[dp(12)])
            fila.bind(pos=_draw_fila, size=_draw_fila)
            _draw_fila(fila)
            
            lbl_nombre = Label(text=f"{producto['nombre'][:30]}", bold=True, font_size=sp(12.5),
                               color=COL['text'], halign='left', valign='middle',
                               size_hint_y=None, height=dp(20))
            lbl_nombre.bind(size=lambda i,*a: setattr(i,'text_size',i.size))
            fila.add_widget(lbl_nombre)
            
            controles = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(34), spacing=dp(5))
            
            spinner_formato = MSpinner(text=formato, values=('Unidad', 'Blister', 'Caja'),
                                      bg=COL['primary'], font_size=sp(10),
                                      size_hint_x=0.3, radius=dp(9))
            spinner_formato.bind(text=lambda instance, val, i=idx: self.cambiar_formato_carrito(i, val))
            controles.add_widget(spinner_formato)
            
            caja_cantidad = BoxLayout(orientation='horizontal', size_hint_x=0.3, spacing=dp(3))
            btn_menos = MButton(text="-", size_hint_x=0.32,
                              bg=COL['danger'], bg_down=COL['danger_dark'],
                              font_size=sp(18), radius=dp(9))
            btn_menos.bind(on_press=lambda instance, i=idx: self.cambiar_cantidad_carrito(i, -1))
            txt_cant = Label(text=str(cantidad), font_size=sp(13), bold=True, color=COL['text'], size_hint_x=0.36)
            btn_mas = MButton(text="+", size_hint_x=0.32,
                             bg=COL['success'], bg_down=COL['success_dark'],
                             font_size=sp(18), radius=dp(9))
            btn_mas.bind(on_press=lambda instance, i=idx: self.cambiar_cantidad_carrito(i, 1))
            caja_cantidad.add_widget(btn_menos)
            caja_cantidad.add_widget(txt_cant)
            caja_cantidad.add_widget(btn_mas)
            controles.add_widget(caja_cantidad)
            
            lbl_subtotal = Label(text=f"${subtotal:,.0f}", font_size=sp(12.5), bold=True,
                                 color=COL['success_dark'], size_hint_x=0.28, halign='right', valign='middle')
            lbl_subtotal.bind(size=lambda i,*a: setattr(i,'text_size',i.size))
            controles.add_widget(lbl_subtotal)
            
            btn_eliminar = MIconButton(icon='close', size_hint_x=0.12,
                                  bg=COL['text_mute'], bg_down=COL['text_soft'],
                                  font_size=sp(14), radius=dp(9))
            btn_eliminar.bind(on_press=lambda instance, i=idx: self.eliminar_del_carrito(i))
            controles.add_widget(btn_eliminar)
            
            fila.add_widget(controles)
            lista_box.add_widget(fila)
        
        scroll.add_widget(lista_box)
        content.add_widget(scroll)
        
        total_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(8))
        total_box.add_widget(Label(text=f"TOTAL: ${total_venta:,.0f}", font_size=sp(15), bold=True,
                                   color=COL['primary_dark'], size_hint_x=0.55))
        
        btn_pagar = MButton(text="PAGAR",
                          bg=COL['success'], bg_down=COL['success_dark'],
                          font_size=sp(13), size_hint_x=0.45)
        btn_pagar.bind(on_press=lambda instance: self.procesar_pago(total_venta))
        total_box.add_widget(btn_pagar)
        content.add_widget(total_box)
        
        btn_cerrar = MButton(text="CERRAR CARRITO", size_hint_y=None, height=dp(46),
                            bg=COL['text_soft'], bg_down=COL['text'],
                            font_size=sp(12))
        btn_cerrar.bind(on_press=lambda instance: self.carrito_popup.dismiss())
        content.add_widget(btn_cerrar)
        
        self.carrito_popup = Popup(title='Carrito de compras', content=content,
                                   size_hint=(0.92, 0.82), auto_dismiss=False)
        self.carrito_popup.open()

    def cambiar_formato_carrito(self, index, nuevo_formato):
        if 0 <= index < len(self.carrito):
            item = self.carrito[index]
            item['formato'] = nuevo_formato
            producto = item['producto']
            item['precio_unitario'] = self.obtener_precio(producto, nuevo_formato)
            if self.carrito_popup and self.carrito_popup._window:
                self.carrito_popup.dismiss()
                self.abrir_carrito()

    def cambiar_cantidad_carrito(self, index, delta):
        if 0 <= index < len(self.carrito):
            nueva = self.carrito[index]['cantidad'] + delta
            if nueva < 1:
                nueva = 1
            self.carrito[index]['cantidad'] = nueva
            if self.carrito_popup and self.carrito_popup._window:
                self.carrito_popup.dismiss()
                self.abrir_carrito()

    def procesar_pago(self, total_venta):
        if self.carrito_popup:
            self.carrito_popup.dismiss()
        
        content = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(10))
        content.add_widget(Label(text=f"Total a pagar: ${total_venta:,.0f}", font_size=sp(17),
                                 bold=True, color=COL['primary_dark'], size_hint_y=None, height=dp(38)))
        
        dinero_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48), spacing=dp(8))
        _lbl_dr = Label(text="Dinero recibido:", font_size=sp(12.5), color=COL['text_soft'],
                        size_hint_x=0.45, halign='left', valign='middle')
        _lbl_dr.bind(size=lambda i,*a: setattr(i,'text_size',i.size))
        dinero_box.add_widget(_lbl_dr)
        txt_dinero = MTextInput(text="0", font_size=sp(15), input_filter='float',
                               size_hint_x=0.55)
        dinero_box.add_widget(txt_dinero)
        content.add_widget(dinero_box)
        
        lbl_cambio = Label(text="Cambio: $0", font_size=sp(15), bold=True,
                          color=COL['danger'], size_hint_y=None, height=dp(32))
        content.add_widget(lbl_cambio)
        
        lbl_error = Label(text="", color=COL['danger'], font_size=sp(11), size_hint_y=None, height=dp(20))
        content.add_widget(lbl_error)
        
        btn_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), spacing=dp(8))
        btn_confirmar = MButton(text="CONFIRMAR VENTA",
                               bg=COL['success'], bg_down=COL['success_dark'],
                               font_size=sp(12.5))
        btn_cancelar = MButton(text="CANCELAR",
                              bg=COL['text_soft'], bg_down=COL['text'],
                              font_size=sp(12.5))
        btn_box.add_widget(btn_confirmar)
        btn_box.add_widget(btn_cancelar)
        content.add_widget(btn_box)
        
        popup_pago = Popup(title='Confirmar pago', content=content,
                           size_hint=(0.88, 0.5), auto_dismiss=False)
        
        def calcular_cambio(*args):
            try:
                dinero = float(txt_dinero.text) if txt_dinero.text else 0
                cambio = dinero - total_venta
                if cambio >= 0:
                    lbl_cambio.text = f"Cambio: ${cambio:,.0f}"
                    lbl_cambio.color = (0.1,0.6,0.1,1)
                else:
                    lbl_cambio.text = f"Faltan ${abs(cambio):,.0f}"
                    lbl_cambio.color = (0.8,0.2,0.1,1)
                return cambio >= 0
            except (ValueError, TypeError):
                return False
        
        txt_dinero.bind(text=calcular_cambio)
        
        def confirmar_venta(*args):
            if not calcular_cambio():
                lbl_error.text = "El dinero recibido es insuficiente"
                return
            
            dinero = float(txt_dinero.text) if txt_dinero.text else 0
            cambio = dinero - total_venta
            app = App.get_running_app()
            
            transaccion_id = int(time.time())
            for item in self.carrito:
                producto = item['producto']
                formato = item['formato'].lower()
                cantidad = item['cantidad']
                precio_unitario = item['precio_unitario']
                precio_total = precio_unitario * cantidad
                
                agregar_venta(
                    vendedor_id=self.vendedor_actual.get('codigo', ''),
                    vendedor_nombre=self.vendedor_actual.get('nombre', ''),
                    producto_id=producto.get('id_prod', ''),
                    producto_nombre=producto.get('nombre', ''),
                    formato=formato,
                    cantidad=cantidad,
                    precio_unitario=precio_unitario,
                    precio_total=precio_total,
                    dinero_recibido=dinero,
                    cambio=cambio,
                    sucursal=app.sucursal_actual,
                    transaccion_id=transaccion_id
                )
            
            self.carrito = []
            self.actualizar_boton_vender()
            popup_pago.dismiss()
            
            content_confirm = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(8))
            content_confirm.add_widget(Label(text="✅ Venta registrada exitosamente!", 
                                            font_size=sp(14), color=(0.1,0.6,0.1,1), bold=True))
            content_confirm.add_widget(Label(text=f"Total: ${total_venta:,.0f}  |  Cambio: ${cambio:,.0f}",
                                            font_size=sp(12), color=(0.1,0.35,0.65,1)))
            popup_confirm = Popup(title='Éxito', content=content_confirm,
                                 size_hint=(0.7, 0.3), auto_dismiss=True,
                                 title_color=(0.1,0.6,0.1,1), title_size=sp(14))
            popup_confirm.open()
            Clock.schedule_once(lambda dt: popup_confirm.dismiss(), 2)
        
        btn_confirmar.bind(on_press=confirmar_venta)
        btn_cancelar.bind(on_press=popup_pago.dismiss)
        
        popup_pago.open()
        Clock.schedule_once(lambda dt: calcular_cambio(), 0.1)

    def ir_historial_ventas(self):
        app = App.get_running_app()
        historial = app.root.get_screen('historial_ventas')
        if historial:
            historial.catalog_screen = self
            app.root.current = 'historial_ventas'

    def sincronizar(self):
        progress_bar = self.ids.sync_progress
        progress_bar.opacity = 1
        progress_bar.value = 0
        self._update_status("Descargando datos...")
        threading.Thread(target=self._proceso_sincro_con_progreso, daemon=True).start()

    def _proceso_sincro_con_progreso(self):
        app = App.get_running_app()
        try:
            if not app.current_url or app.current_url.startswith("URL_ONEDRIVE"):
                Clock.schedule_once(lambda dt: self._update_status("Error: URL no configurada"), 0)
                self._finalizar_sync_error()
                return
            self._update_progress(0, "Descargando CSV...")
            response = requests.get(app.current_url, stream=True, timeout=20)
            if response.status_code != 200:
                Clock.schedule_once(lambda dt: self._update_status(f"Error HTTP: {response.status_code}"), 0)
                self._finalizar_sync_error()
                return

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            with open(app.csv_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 60
                            self._update_progress(percent, f"Descargando... {int(percent)}%")
                        else:
                            self._update_progress(min(60, self.ids.sync_progress.value + 2), "Descargando...")
            self._update_progress(60, "Procesando CSV...")

            total_filas = 0
            with open(app.csv_path, 'r', encoding='latin-1') as f:
                total_filas = sum(1 for _ in f) - 1
            if total_filas <= 0:
                total_filas = 1

            conn_hilo = sqlite3.connect(app.db_path)
            cursor_hilo = conn_hilo.cursor()
            datos = []
            filas_procesadas = 0
            with open(app.csv_path, newline='', encoding='latin-1') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        datos.append((
                            row.get('CodProducto', ''),
                            row.get('CodigoBarras', ''),
                            row.get('Laboratorio', ''),
                            row.get('Nombre', 'S/N'),
                            self.safe_float(row.get('ValorCajaContado', 0)),
                            self.safe_float(row.get('ValorBlisterContado', 0)),
                            self.safe_float(row.get('ValorUnidadContado', 0)),
                        ))
                    except Exception as e:
                        logger.warning(f"Fila de CSV omitida en sincronización: {e}")
                        continue
                    filas_procesadas += 1
                    if filas_procesadas % 100 == 0:
                        percent = 60 + (filas_procesadas / total_filas) * 30
                        self._update_progress(percent, f"Procesando... {int((filas_procesadas/total_filas)*100)}%")
            if datos:
                cursor_hilo.execute("DELETE FROM productos")
                cursor_hilo.executemany("INSERT INTO productos VALUES (?,?,?,?,?,?,?)", datos)
                conn_hilo.commit()
                logger.info(f"{len(datos)} productos importados.")
            conn_hilo.close()

            self._update_progress(90, "Finalizando...")
            app.guardar_ultima_sync(app.sucursal_actual)
            Clock.schedule_once(lambda dt: self._update_status("Sincronización exitosa"), 0)
            self._update_progress(100, "Completado")
            Clock.schedule_once(lambda dt: self.buscar_productos(self.ids.search_input.text), 0)
            Clock.schedule_once(lambda dt: self._ocultar_barra_progreso(), 1.5)
        except Exception as e:
            logger.error(f"Error de sincronización: {e}")
            Clock.schedule_once(lambda dt: self._update_status("Error de conexión"), 0)
            self._finalizar_sync_error()

    def _update_progress(self, value, status_text):
        def update(dt):
            self.ids.sync_progress.value = value
            self._update_status(status_text)
        Clock.schedule_once(update, 0)

    def _update_status(self, msg):
        app = App.get_running_app()
        if app.sucursal_actual:
            self.ids.status_label.text = f"Sucursal: {app.sucursal_actual} | {msg}"
        else:
            self.ids.status_label.text = msg

    def _finalizar_sync_error(self):
        def hide(dt):
            self.ids.sync_progress.opacity = 0
            self.ids.sync_progress.value = 0
        Clock.schedule_once(hide, 2)

    def _ocultar_barra_progreso(self):
        self.ids.sync_progress.opacity = 0
        self.ids.sync_progress.value = 0
        self.actualizar_header_sucursal()


class MiBaseDrogApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sucursal_actual = None
        self.db_path = None
        self.csv_path = None
        self.current_url = None
        self.pin_hash = None
        self.ultimas_sync = {}
        self.device_id = None
        self.activated = False

    def build(self):
        self.title = "Precios Farmacenter"
        if os.path.exists(ICONO_PATH.replace('/', os.sep)):
            self.icon = ICONO_PATH
        sm = ScreenManager(transition=FadeTransition(duration=0.2))
        sm.add_widget(ActivationScreen(name='activation'))
        sm.add_widget(SucursalSelectionScreen(name='sucursal_selection'))
        sm.add_widget(PreSplashScreen(name='splash'))
        sm.add_widget(CatalogScreen(name='catalog'))
        sm.add_widget(HistorialVentasScreen(name='historial_ventas'))
        
        self.cargar_configuracion_completa()
        logger.info(f"Config cargada - sucursal: {self.sucursal_actual}")
        
        if self.device_id is None:
            self.device_id = generar_device_id()
            self.guardar_configuracion_completa()
        
        # En PC, asignar sucursal por defecto para desarrollo
        if platform != 'android' and self.sucursal_actual is None:
            self.sucursal_actual = "Maíz Amarillo"
            self.actualizar_rutas_sucursal()
            self.guardar_configuracion_completa()
            logger.info("PC: asignada sucursal por defecto")
        
        if self.activated or cargar_licencia():
            if self.sucursal_actual is not None:
                logger.info("Sucursal encontrada, yendo a splash")
                sm.current = 'splash'
            else:
                logger.info("No hay sucursal, yendo a selección")
                sm.current = 'sucursal_selection'
        else:
            logger.info("No activada, yendo a activación")
            sm.current = 'activation'
        
        return sm

    def cargar_configuracion_completa(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.sucursal_actual = config.get('sucursal')
                    if self.sucursal_actual and self.sucursal_actual in SUCURSALES:
                        self.actualizar_rutas_sucursal()
                    self.pin_hash = config.get('pin_hash')
                    self.ultimas_sync = config.get('ultimas_sync', {})
                    self.device_id = config.get('device_id')
                    self.activated = config.get('activated', False)
            except Exception as e:
                logger.error(f"Error cargando configuración: {e}")
                self.pin_hash = None
                self.ultimas_sync = {}
                self.device_id = None
                self.activated = False
        else:
            self.pin_hash = None
            self.ultimas_sync = {}
            self.device_id = None
            self.activated = False

    def guardar_configuracion_completa(self):
        config = {
            'sucursal': self.sucursal_actual,
            'pin_hash': self.pin_hash,
            'ultimas_sync': self.ultimas_sync,
            'device_id': self.device_id,
            'activated': self.activated
        }
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f)
        except Exception as e:
            logger.error(f"Error guardando configuración: {e}")

    def guardar_ultima_sync(self, sucursal):
        self.ultimas_sync[sucursal] = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.guardar_configuracion_completa()

    def obtener_ultima_sync(self, sucursal):
        return self.ultimas_sync.get(sucursal)

    def actualizar_rutas_sucursal(self):
        if self.sucursal_actual in SUCURSALES:
            info = SUCURSALES[self.sucursal_actual]
            self.db_path = os.path.join(RUTA_BASE, info['db_name'])
            self.csv_path = os.path.join(RUTA_BASE, info['csv_name'])
            self.current_url = _d(info.get('url_ofuscada', ''))
            logger.info(f"Sucursal seleccionada: {self.sucursal_actual}")

    def set_sucursal(self, nombre):
        self.sucursal_actual = nombre
        self.actualizar_rutas_sucursal()
        self.guardar_configuracion_completa()

    def clear_sucursal(self):
        self.sucursal_actual = None
        self.db_path = None
        self.csv_path = None
        self.current_url = None
        config = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        config['sucursal'] = None
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f)
        self.cargar_configuracion_completa()

    def goto_splash_screen(self):
        self.root.current = 'splash'
        splash = self.root.get_screen('splash')
        if hasattr(splash, 'ids') and hasattr(splash.ids, 'sucursal_label'):
            splash.ids.sucursal_label.text = f"Sucursal: {self.sucursal_actual}"

    def goto_sucursal_selection(self):
        self.clear_sucursal()
        self.root.current = 'sucursal_selection'

    def ir_a_seleccion_sucursal(self):
        self.root.current = 'sucursal_selection'

    def seleccionar_sucursal(self, nombre_sucursal):
        logger.info(f"Seleccionando sucursal: {nombre_sucursal}")
        self.set_sucursal(nombre_sucursal)
        self.guardar_configuracion_completa()
        self.cargar_configuracion_completa()
        logger.info(f"Sucursal guardada: {self.sucursal_actual}")
        
        # ============================================================
        # Popup de confirmación
        # ============================================================
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(
            text=f"Sucursal guardada:\n{nombre_sucursal}",
            font_size=sp(16),
            color=(0.1, 0.35, 0.65, 1),
            halign='center'
        ))
        popup = Popup(
            title='✅ Éxito',
            content=content,
            size_hint=(0.7, 0.3),
            auto_dismiss=True
        )
        popup.open()
        Clock.schedule_once(lambda dt: popup.dismiss(), 2)
        # ============================================================
        
        self.goto_splash_screen()

    def contar_productos(self):
        if not self.db_path or not os.path.exists(self.db_path):
            return 0
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM productos')
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except sqlite3.Error as e:
            logger.error(f"Error contando productos en {self.db_path}: {e}")
            return 0

    def descargar_y_sincronizar(self, callback=None):
        def sync_thread():
            success = False
            error_msg = ""
            try:
                if not self.current_url or self.current_url.startswith("URL_ONEDRIVE"):
                    error_msg = "URL de descarga no configurada."
                else:
                    r = requests.get(self.current_url, timeout=30)
                    if r.status_code == 200:
                        with open(self.csv_path, 'wb') as f:
                            f.write(r.content)
                        self._importar_csv_sincrono()
                        success = True
                        self.guardar_ultima_sync(self.sucursal_actual)
                    else:
                        error_msg = f"Error HTTP: {r.status_code}"
            except Exception as e:
                error_msg = str(e)
            if callback:
                Clock.schedule_once(lambda dt: callback(success, error_msg), 0)
        threading.Thread(target=sync_thread, daemon=True).start()

    def _importar_csv_sincrono(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            datos = []
            with open(self.csv_path, newline='', encoding='latin-1') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        datos.append((
                            row.get('CodProducto', ''),
                            row.get('CodigoBarras', ''),
                            row.get('Laboratorio', ''),
                            row.get('Nombre', 'S/N'),
                            self._safe_float(row.get('ValorCajaContado', 0)),
                            self._safe_float(row.get('ValorBlisterContado', 0)),
                            self._safe_float(row.get('ValorUnidadContado', 0)),
                        ))
                    except Exception as e:
                        logger.warning(f"Fila de CSV omitida en importación: {e}")
                        continue
            if datos:
                cursor.execute("DELETE FROM productos")
                cursor.executemany("INSERT INTO productos VALUES (?,?,?,?,?,?,?)", datos)
                conn.commit()
                logger.info(f"{len(datos)} productos importados.")
        except Exception as e:
            logger.error(f"Error importando CSV: {e}")
        finally:
            if conn:
                conn.close()

    def _safe_float(self, valor):
        if not valor:
            return 0.0
        try:
            return float(str(valor).strip().replace(",", ""))
        except (ValueError, TypeError):
            return 0.0

    def cambiar_sucursal(self):
        self.goto_sucursal_selection()

    def on_stop(self):
        try:
            if self.root and self.root.has_screen('catalog'):
                cat = self.root.get_screen('catalog')
                if hasattr(cat, 'conn') and cat.conn:
                    cat.conn.close()
        except Exception as e:
            logger.warning(f"Error cerrando conexión DB al salir: {e}")


if __name__ == '__main__':
    MiBaseDrogApp().run()
