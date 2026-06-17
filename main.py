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
    Versión: 2.8.0  |  Lanzamiento: 2026  |  Plataforma: Android

SOPORTE:
    Contacte a los desarrolladores para soporte técnico o solicitud de licencias.
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
from datetime import datetime, timedelta

import licencia
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
    # "Terranova": [...],
    # "Covipro": [...],
}

def inicializar_vendedores():
    """
    Crea o actualiza el archivo vendedores.csv con todos los vendedores
    de todas las sucursales definidas en VENDEDORES_POR_SUCURSAL.
    Si el archivo ya existe, solo agrega los vendedores que falten.
    """
    ruta = get_csv_vendedores()
    
    # Leer vendedores existentes (si el archivo existe)
    existentes = set()
    if os.path.exists(ruta):
        with open(ruta, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existentes.add((row['codigo'], row['sucursal']))
    
    # Recorrer todas las sucursales y vendedores definidos
    nuevos = []
    for sucursal, vendedores in VENDEDORES_POR_SUCURSAL.items():
        for codigo, nombre in vendedores:
            if (codigo, sucursal) not in existentes:
                nuevos.append((codigo, nombre, sucursal))
    
    # Si hay nuevos vendedores, agregarlos al archivo
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
    
    # Si el archivo no existe (por alguna razón), crearlo con todos
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
                    except:
                        pass
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
        except:
            pass
    return total

# ============================================================
# FIN FUNCIONES CSV
# ============================================================

# --- SUCURSALES ---
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

# --- RUTAS ---
if platform == 'android':
    from android.storage import app_storage_path
    from jnius import autoclass
    RUTA_BASE = app_storage_path()
    android_id = None
    try:
        context = autoclass('android.content.Context')
        secure = autoclass('android.provider.Settings$Secure')
        python_activity = autoclass('org.kivy.android.PythonActivity')
        resolver = python_activity.mActivity.getContentResolver()
        android_id = secure.getString(resolver, secure.ANDROID_ID)
    except:
        android_id = "unknown_android"
    modelo = autoclass('android.os.Build').MODEL
    fabricante = autoclass('android.os.Build').MANUFACTURER
else:
    RUTA_BASE = os.path.dirname(os.path.abspath(__file__))
    android_id = None
    modelo = "PC"
    fabricante = "Desktop"

LOGO_PATH = RUTA_BASE.replace('\\', '/') + '/logo_farmacenter.png'
ICONO_PATH = RUTA_BASE.replace('\\', '/') + '/icono.png'
CONFIG_FILE = os.path.join(RUTA_BASE, 'config.json')

# --- FUNCIONES DE LICENCIA ---
def generar_device_id():
    if platform == 'android':
        base = f"{android_id}_{modelo}_{fabricante}"
    else:
        base = os.environ.get('COMPUTERNAME', 'dev')
    return licencia.generar_device_id(base)

def verificar_codigo(device_id, codigo_ingresado):
    return licencia.verificar_codigo(device_id, codigo_ingresado)

# --- CLASE PARA EL RECYCLEVIEW DE PRODUCTOS CON BOTÓN AGREGAR ---
class ProductoRow(BoxLayout):
    nombre = StringProperty("")
    laboratorio = StringProperty("")
    id_prod = StringProperty("")
    barras = StringProperty("")
    precio_caja = StringProperty("")
    precio_blister = StringProperty("")
    precio_unidad = StringProperty("")
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

# --- KV STRING COMPLETO ---
KV_STRING = f'''
<RootWidget>:
    # No se usa, solo para referencia

<ProductoRow>:
    orientation: 'horizontal'
    size_hint_y: None
    height: 135
    padding: [10, 5]
    canvas.before:
        Color:
            rgba: (1, 1, 1, 1)
        Rectangle:
            size: self.size
            pos: self.pos
        Color:
            rgba: (0.92, 0.92, 0.92, 1)
        Line:
            points: self.x, self.y, self.x + self.width, self.y
            width: 1

    BoxLayout:
        orientation: 'vertical'
        size_hint_x: 0.85
        padding: [10, 5]
        spacing: 2
        Label:
            text: root.nombre
            color: (0, 0, 0, 1)
            bold: True
            font_size: 16
            text_size: self.width, None
            halign: 'left'
            size_hint_y: None
            height: self.texture_size[1]

        Label:
            text: "Lab: " + root.laboratorio + "  |  Cod: " + root.id_prod + "  |  EAN: " + root.barras
            color: (0.5, 0.5, 0.5, 1)
            font_size: 11
            text_size: self.width, None
            halign: 'left'
            size_hint_y: None
            height: self.texture_size[1]

        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: 30
            spacing: 8
            Label:
                text: "Caja: " + root.precio_caja
                color: (0.1, 0.6, 0.1, 1)
                bold: True
                font_size: 13
                halign: 'left'
            Label:
                text: "Blister: " + root.precio_blister
                color: (0.1, 0.35, 0.65, 1)
                font_size: 13
                halign: 'center'
            Label:
                text: "Unidad: " + root.precio_unidad
                color: (0.8, 0.2, 0.1, 1)
                font_size: 13
                halign: 'right'

    Button:
        text: "+"
        size_hint_x: 0.15
        background_normal: ''
        background_color: (0.1, 0.6, 0.1, 1)
        color: (1, 1, 1, 1)
        bold: True
        font_size: 24
        on_press: root.agregar_al_carrito()

<ActivationScreen>:
    name: 'activation'
    canvas.before:
        Color:
            rgba: (1, 1, 1, 1)
        Rectangle:
            size: self.size
            pos: self.pos
    BoxLayout:
        orientation: 'vertical'
        padding: [24, 40, 24, 40]
        spacing: 20
        Image:
            source: "{LOGO_PATH}"
            allow_stretch: True
            keep_ratio: True
            size_hint: (0.5, 0.2)
            pos_hint: {{'center_x': 0.5}}
        Label:
            text: "Esta aplicación requiere activación"
            font_size: 18
            bold: True
            color: (0.1, 0.35, 0.65, 1)
            size_hint_y: 0.08
            halign: 'center'
        BoxLayout:
            orientation: 'vertical'
            size_hint_y: 0.15
            spacing: 8
            Label:
                text: "ID del dispositivo:"
                color: (0.2, 0.2, 0.2, 1)
                size_hint_y: None
                height: 24
            BoxLayout:
                orientation: 'horizontal'
                spacing: 10
                TextInput:
                    id: device_id_display
                    text: ""
                    readonly: True
                    multiline: False
                    font_size: 14
                    background_color: (0.95, 0.95, 0.95, 1)
                    foreground_color: (0.1, 0.35, 0.65, 1)
                Button:
                    text: "Copiar ID"
                    size_hint_x: 0.3
                    background_normal: ''
                    background_color: (0.1, 0.35, 0.65, 1)
                    color: (1,1,1,1)
                    on_press: root.copiar_id()
        TextInput:
            id: codigo_input
            hint_text: "Ingrese código de activación"
            multiline: False
            size_hint_y: 0.08
            padding: [12, 12]
            font_size: 16
            background_color: (1,1,1,1)
            foreground_color: (0, 0, 0, 1)
        Button:
            text: "ACTIVAR"
            size_hint_y: 0.08
            background_normal: ''
            background_color: (0.1, 0.35, 0.65, 1)
            color: (1,1,1,1)
            bold: True
            font_size: 16
            on_press: root.activar()
        Label:
            text: "Contacte al desarrollador para obtener su código de activacion"
            color: (0.5, 0.5, 0.5, 1)
            font_size: 11
            size_hint_y: 0.05
            halign: 'center'
        Label:
            text: "chavezgaravitoj@gmail.com   o   rinconchavezsantiago555@gmail.com"
            color: (0.1, 0.35, 0.65, 1)
            bold: True
            font_size: 12
            size_hint_y: 0.05
            halign: 'center'
        Label:
            id: error_label
            text: ""
            color: (0.8, 0.2, 0.1, 1)
            size_hint_y: 0.05

<CatalogScreen>:
    name: 'catalog'
    canvas.before:
        Color:
            rgba: (0.98, 0.98, 0.98, 1)
        Rectangle:
            size: self.size
            pos: self.pos

    BoxLayout:
        orientation: 'vertical'

        BoxLayout:
            size_hint_y: None
            height: 95
            padding: [12, 8, 12, 6]
            canvas.before:
                Color:
                    rgba: (0.1, 0.35, 0.65, 1)
                Rectangle:
                    size: self.size
                    pos: self.pos
            Image:
                source: "{LOGO_PATH}"
                size_hint_x: 0.25
                allow_stretch: True
                keep_ratio: True
            BoxLayout:
                orientation: 'vertical'
                padding: [8, 0, 0, 0]
                spacing: 2
                Label:
                    text: "PRECIOS FARMACENTER"
                    color: (1, 1, 1, 1)
                    bold: True
                    font_size: 16
                    halign: 'left'
                    text_size: self.width, None
                Label:
                    id: status_label
                    text: "Base de datos lista"
                    color: (0.9, 0.95, 1, 1)
                    font_size: 11
                    halign: 'left'
                    text_size: self.width, None
                ProgressBar:
                    id: sync_progress
                    max: 100
                    value: 0
                    size_hint_y: None
                    height: 4
                    opacity: 0

        BoxLayout:
            size_hint_y: None
            height: 64
            padding: [10, 8, 10, 4]
            spacing: 8

            Spinner:
                id: search_spinner
                text: 'NOMBRE'
                values: ('NOMBRE', 'CÓDIGO', 'BARRAS')
                size_hint_x: None
                width: 100
                background_normal: ''
                background_color: (0.1, 0.35, 0.65, 1)
                color: (1, 1, 1, 1)
                bold: True
                font_size: 14
                on_text: root.on_spinner_change(self.text)

            TextInput:
                id: search_input
                hint_text: "Buscar por nombre..."
                hint_text_color: (0.6, 0.6, 0.6, 1)
                multiline: False
                font_size: 18
                size_hint_x: 1
                padding: [12, 12]
                background_color: (1, 1, 1, 1)
                foreground_color: (0, 0, 0, 1)
                cursor_color: (0.1, 0.35, 0.65, 1)
                cursor_width: 2
                on_text: root.on_search_text(self.text)
                canvas.before:
                    Color:
                        rgba: (0.85, 0.85, 0.85, 1)
                    Line:
                        rounded_rectangle: (self.x, self.y, self.width, self.height, 6)
                        width: 1.2

            Button:
                text: "X"
                size_hint_x: None
                width: 48
                background_normal: ''
                background_color: (0.4, 0.4, 0.4, 1)
                color: (1, 1, 1, 1)
                bold: True
                font_size: 18
                on_press: 
                    root.ids.search_input.text = ""
                    root.on_search_text("")

            Button:
                id: vender_btn
                text: "VENDER"
                size_hint_x: None
                width: 80
                background_normal: ''
                background_color: (0.1, 0.6, 0.1, 1)
                color: (1, 1, 1, 1)
                bold: True
                font_size: 14
                disabled: True
                on_press: root.abrir_carrito()

        RecycleView:
            id: rv
            viewclass: 'ProductoRow'
            RecycleBoxLayout:
                default_size: None, 135
                default_size_hint: 1, None
                size_hint_y: None
                height: self.minimum_height
                orientation: 'vertical'
                spacing: 1

        BoxLayout:
            size_hint_y: None
            height: 58
            spacing: 8
            padding: [10, 6, 10, 8]
            Button:
                text: "SINCRONIZAR DATOS"
                background_normal: ''
                background_color: (0.1, 0.35, 0.65, 1)
                color: (1, 1, 1, 1)
                bold: True
                font_size: 14
                on_press: root.sincronizar()
            Button:
                text: "VER VENTAS"
                size_hint_x: 0.3
                background_normal: ''
                background_color: (0.8, 0.6, 0.1, 1)
                color: (1, 1, 1, 1)
                bold: True
                font_size: 11
                on_press: root.ir_historial_ventas()
            Button:
                text: "CAMBIAR SUCURSAL"
                size_hint_x: 0.35
                background_normal: ''
                background_color: (0.45, 0.45, 0.45, 1)
                color: (1, 1, 1, 1)
                bold: True
                font_size: 11
                on_press: app.cambiar_sucursal()

<HistorialVentasScreen>:
    name: 'historial_ventas'
    canvas.before:
        Color:
            rgba: (1, 1, 1, 1)
        Rectangle:
            size: self.size
            pos: self.pos
    BoxLayout:
        orientation: 'vertical'
        padding: [10, 10, 10, 10]
        spacing: 8
        
        BoxLayout:
            size_hint_y: None
            height: 60
            Label:
                text: "HISTORIAL DE VENTAS"
                color: (0.1, 0.35, 0.65, 1)
                bold: True
                font_size: 20
                halign: 'center'
                size_hint_y: None
                height: 50
                
        BoxLayout:
            size_hint_y: None
            height: 45
            spacing: 10
            Spinner:
                id: filtro_vendedor
                text: 'TODOS'
                values: ['TODOS']
                size_hint_x: 0.5
                background_normal: ''
                background_color: (0.1, 0.35, 0.65, 1)
                color: (1,1,1,1)
                font_size: 12
                on_text: root.aplicar_filtros()
            Spinner:
                id: filtro_periodo
                text: 'TODAS'
                values: ['TODAS', 'HOY', 'AYER', 'ÚLTIMA SEMANA', 'ÚLTIMO MES', 'ESTE MES']
                size_hint_x: 0.5
                background_normal: ''
                background_color: (0.1, 0.35, 0.65, 1)
                color: (1,1,1,1)
                font_size: 12
                on_text: root.aplicar_filtros()
                
        BoxLayout:
            size_hint_y: None
            height: 35
            spacing: 10
            Label:
                id: total_label
                text: "Total: $0"
                color: (0.1, 0.6, 0.1, 1)
                bold: True
                font_size: 14
            Button:
                text: "CERRAR"
                size_hint_x: 0.2
                background_normal: ''
                background_color: (0.45, 0.45, 0.45, 1)
                color: (1,1,1,1)
                bold: True
                font_size: 12
                on_press: root.cerrar_historial()
                
        ScrollView:
            id: scroll_ventas
            BoxLayout:
                id: ventas_container
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: 2

<PinScreen>:
    name: 'pin'
    canvas.before:
        Color:
            rgba: (1, 1, 1, 1)
        Rectangle:
            size: self.size
            pos: self.pos
    BoxLayout:
        orientation: 'vertical'
        padding: [24, 40, 24, 40]
        spacing: 20
        Image:
            source: "{LOGO_PATH}"
            allow_stretch: True
            keep_ratio: True
            size_hint: (0.5, 0.2)
            pos_hint: {{'center_x': 0.5}}
        Label:
            id: title_label
            text: "Ingrese su PIN"
            font_size: 20
            bold: True
            color: (0.1, 0.35, 0.65, 1)
            size_hint_y: 0.08
            halign: 'center'
        BoxLayout:
            id: circles_box
            size_hint_y: 0.1
            spacing: 20
            pos_hint: {{'center_x': 0.5}}
        Label:
            id: error_label
            text: ""
            color: (0.8, 0.2, 0.1, 1)
            font_size: 12
            size_hint_y: 0.05
            halign: 'center'
        GridLayout:
            cols: 3
            rows: 4
            spacing: 10
            size_hint_y: 0.45
            Button:
                text: "1"
                font_size: 28
                bold: True
                background_normal: ''
                background_color: (0.1, 0.35, 0.65, 1)
                color: (1, 1, 1, 1)
                on_press: root.agregar_digito("1")
            Button:
                text: "2"
                font_size: 28
                bold: True
                background_normal: ''
                background_color: (0.1, 0.35, 0.65, 1)
                color: (1, 1, 1, 1)
                on_press: root.agregar_digito("2")
            Button:
                text: "3"
                font_size: 28
                bold: True
                background_normal: ''
                background_color: (0.1, 0.35, 0.65, 1)
                color: (1, 1, 1, 1)
                on_press: root.agregar_digito("3")
            Button:
                text: "4"
                font_size: 28
                bold: True
                background_normal: ''
                background_color: (0.1, 0.35, 0.65, 1)
                color: (1, 1, 1, 1)
                on_press: root.agregar_digito("4")
            Button:
                text: "5"
                font_size: 28
                bold: True
                background_normal: ''
                background_color: (0.1, 0.35, 0.65, 1)
                color: (1, 1, 1, 1)
                on_press: root.agregar_digito("5")
            Button:
                text: "6"
                font_size: 28
                bold: True
                background_normal: ''
                background_color: (0.1, 0.35, 0.65, 1)
                color: (1, 1, 1, 1)
                on_press: root.agregar_digito("6")
            Button:
                text: "7"
                font_size: 28
                bold: True
                background_normal: ''
                background_color: (0.1, 0.35, 0.65, 1)
                color: (1, 1, 1, 1)
                on_press: root.agregar_digito("7")
            Button:
                text: "8"
                font_size: 28
                bold: True
                background_normal: ''
                background_color: (0.1, 0.35, 0.65, 1)
                color: (1, 1, 1, 1)
                on_press: root.agregar_digito("8")
            Button:
                text: "9"
                font_size: 28
                bold: True
                background_normal: ''
                background_color: (0.1, 0.35, 0.65, 1)
                color: (1, 1, 1, 1)
                on_press: root.agregar_digito("9")
            Button:
                text: ""
                disabled: True
                background_color: (0.9, 0.9, 0.9, 1)
            Button:
                text: "0"
                font_size: 28
                bold: True
                background_normal: ''
                background_color: (0.1, 0.35, 0.65, 1)
                color: (1, 1, 1, 1)
                on_press: root.agregar_digito("0")
            Button:
                text: "🗑"
                font_size: 28
                bold: True
                background_normal: ''
                background_color: (0.45, 0.45, 0.45, 1)
                color: (1, 1, 1, 1)
                on_press: root.borrar_digito()
        Label:
            id: countdown_label
            text: ""
            size_hint_y: 0.05
            color: (0.1, 0.35, 0.65, 1)
            font_size: 12

<SucursalSelectionScreen>:
    name: 'sucursal_selection'
    canvas.before:
        Color:
            rgba: (1, 1, 1, 1)
        Rectangle:
            size: self.size
            pos: self.pos
    BoxLayout:
        orientation: 'vertical'
        padding: [24, 40, 24, 40]
        spacing: 20
        BoxLayout:
            size_hint_y: 0.25
            orientation: 'vertical'
            Image:
                source: "{LOGO_PATH}"
                allow_stretch: True
                keep_ratio: True
                size_hint: (0.6, 0.8)
                pos_hint: {{'center_x': 0.5}}
        Label:
            text: 'Sistema de consulta de precios'
            color: (0.6, 0.6, 0.6, 1)
            font_size: 12
            size_hint_y: 0.05
            halign: 'center'
        Label:
            text: 'Seleccione su sucursal'
            font_size: 18
            bold: True
            color: (0.1, 0.35, 0.65, 1)
            size_hint_y: 0.08
        Label:
            size_hint_y: 0.02
        GridLayout:
            cols: 1
            spacing: 18
            size_hint_y: 0.45
            Button:
                text: "Maíz Amarillo"
                font_size: 16
                bold: True
                size_hint_y: None
                height: 55
                background_normal: ''
                background_color: (0.1, 0.35, 0.65, 1)
                color: (1, 1, 1, 1)
                on_press: app.seleccionar_sucursal('Maíz Amarillo')
            Button:
                text: "Terranova"
                font_size: 16
                bold: True
                size_hint_y: None
                height: 55
                background_normal: ''
                background_color: (0.1, 0.35, 0.65, 1)
                color: (1, 1, 1, 1)
                on_press: app.seleccionar_sucursal('Terranova')
            Button:
                text: "Villaceleste"
                font_size: 16
                bold: True
                size_hint_y: None
                height: 55
                background_normal: ''
                background_color: (0.1, 0.35, 0.65, 1)
                color: (1, 1, 1, 1)
                on_press: app.seleccionar_sucursal('Villaceleste')
            Button:
                text: "Covipro"
                font_size: 16
                bold: True
                size_hint_y: None
                height: 55
                background_normal: ''
                background_color: (0.1, 0.35, 0.65, 1)
                color: (1, 1, 1, 1)
                on_press: app.seleccionar_sucursal('Covipro')
        Label:
            size_hint_y: 0.1

<PreSplashScreen>:
    name: 'splash'
    canvas.before:
        Color:
            rgba: (1, 1, 1, 1)
        Rectangle:
            size: self.size
            pos: self.pos
    BoxLayout:
        orientation: 'vertical'
        padding: 30
        BoxLayout:
            size_hint_y: 0.7
            Image:
                source: "{LOGO_PATH}"
                allow_stretch: True
                keep_ratio: True
        Label:
            id: status_label
            text: "Iniciando Sistema..."
            color: (0.1, 0.35, 0.65, 1)
            bold: True
            font_size: 15
            size_hint_y: 0.1
        Label:
            id: sucursal_label
            text: ""
            color: (0.45, 0.45, 0.45, 1)
            font_size: 11
            size_hint_y: 0.1
        Widget:
            size_hint_y: 0.1
'''

Builder.load_string(KV_STRING)


# --- CLASES DE PANTALLAS ---
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
            app.activated = True
            app.guardar_configuracion_completa()
            app.root.current = 'pin'
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
            container.add_widget(Label(text="No hay ventas en este período", color=(0.5,0.5,0.5,1)))
            return
        
        for v in ventas:
            precio_total = float(v.get('precio_total', 0))
            cambio = float(v.get('cambio', 0))
            
            fila = BoxLayout(orientation='vertical', size_hint_y=None, height=90,
                            padding=[10, 5])
            with fila.canvas.before:
                Color(0.95, 0.95, 0.95, 1)
                Rectangle(pos=fila.pos, size=fila.size)
            
            lbl1 = Label(text=f"{v.get('producto_nombre', '')} - {v.get('formato', '')} x{v.get('cantidad', '1')}",
                        color=(0,0,0,1), bold=True, font_size=14, halign='left', size_hint_y=None, height=25)
            fila.add_widget(lbl1)
            
            lbl2 = Label(text=f"Vendedor: {v.get('vendedor_nombre', '')}  |  {v.get('fecha', '')} {v.get('hora', '')}",
                        color=(0.4,0.4,0.4,1), font_size=11, halign='left', size_hint_y=None, height=20)
            fila.add_widget(lbl2)
            
            lbl3 = Label(text=f"Total: ${precio_total:,.0f}  |  Recibido: ${float(v.get('dinero_recibido', 0)):,.0f}  |  Cambio: ${cambio:,.0f}",
                        color=(0.1,0.6,0.1,1), bold=True, font_size=12, halign='left', size_hint_y=None, height=25)
            fila.add_widget(lbl3)
            
            container.add_widget(fila)
    
    def cerrar_historial(self):
        app = App.get_running_app()
        app.root.current = 'catalog'


class PinScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pin_ingresado = ""
        self.modo_config = False
        self.pin_temporal = ""
        self.intentos = 0
        self.bloqueado_hasta = 0
        self.countdown_event = None

    def on_enter(self):
        self.resetear_estado()
        app = App.get_running_app()
        if app.pin_hash is None:
            self.modo_config = True
            self.ids.title_label.text = "Configure su PIN"
        else:
            self.modo_config = False
            self.ids.title_label.text = "Ingrese su PIN"
        self.actualizar_circulos()

    def resetear_estado(self):
        self.pin_ingresado = ""
        self.pin_temporal = ""
        self.intentos = 0
        self.bloqueado_hasta = 0
        if self.countdown_event:
            self.countdown_event.cancel()
        self.ids.error_label.text = ""
        self.ids.countdown_label.text = ""
        self.actualizar_circulos()

    def actualizar_circulos(self):
        circles_box = self.ids.circles_box
        circles_box.clear_widgets()
        for i in range(4):
            if i < len(self.pin_ingresado):
                circles_box.add_widget(Label(text="●", font_size=32, color=(0.1, 0.35, 0.65, 1)))
            else:
                circles_box.add_widget(Label(text="○", font_size=32, color=(0.6, 0.6, 0.6, 1)))

    def agregar_digito(self, digito):
        if self.bloqueado_hasta > time.time():
            return
        if len(self.pin_ingresado) < 4:
            self.pin_ingresado += digito
            self.actualizar_circulos()
            if len(self.pin_ingresado) == 4:
                self.validar_pin()

    def borrar_digito(self):
        if self.bloqueado_hasta > time.time():
            return
        self.pin_ingresado = self.pin_ingresado[:-1]
        self.actualizar_circulos()

    def validar_pin(self):
        app = App.get_running_app()
        if self.modo_config:
            if not self.pin_temporal:
                self.pin_temporal = self.pin_ingresado
                self.pin_ingresado = ""
                self.actualizar_circulos()
                self.ids.title_label.text = "Confirme su PIN"
                self.ids.error_label.text = ""
            else:
                if self.pin_ingresado == self.pin_temporal:
                    pin_hash = hashlib.sha256(self.pin_ingresado.encode()).hexdigest()
                    app.guardar_pin_hash(pin_hash)
                    app.pin_hash = pin_hash
                    self.ir_siguiente()
                else:
                    self.ids.error_label.text = "Los PIN no coinciden. Intente de nuevo."
                    self.pin_temporal = ""
                    self.pin_ingresado = ""
                    self.actualizar_circulos()
                    self.ids.title_label.text = "Configure su PIN"
        else:
            pin_hash_ingresado = hashlib.sha256(self.pin_ingresado.encode()).hexdigest()
            if pin_hash_ingresado == app.pin_hash:
                self.ir_siguiente()
            else:
                self.intentos += 1
                restantes = 3 - self.intentos
                if restantes <= 0:
                    self.bloquear()
                else:
                    self.ids.error_label.text = f"PIN incorrecto. Intentos restantes: {restantes}"
                    self.pin_ingresado = ""
                    self.actualizar_circulos()

    def bloquear(self):
        self.bloqueado_hasta = time.time() + 30
        self.ids.error_label.text = "Demasiados intentos. Espere 30 segundos."
        self.ids.countdown_label.text = "30"
        self.countdown_event = Clock.schedule_interval(self.actualizar_countdown, 1)

    def actualizar_countdown(self, dt):
        remaining = int(self.bloqueado_hasta - time.time())
        if remaining <= 0:
            self.countdown_event.cancel()
            self.countdown_event = None
            self.ids.countdown_label.text = ""
            self.ids.error_label.text = ""
            self.intentos = 0
            self.pin_ingresado = ""
            self.actualizar_circulos()
        else:
            self.ids.countdown_label.text = str(remaining)

    def ir_siguiente(self):
        app = App.get_running_app()
        if app.sucursal_actual and app.sucursal_actual in SUCURSALES:
            app.root.current = 'splash'
        else:
            app.root.current = 'sucursal_selection'


class SucursalSelectionScreen(Screen):
    pass


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
            content = BoxLayout(orientation='vertical', padding=10, spacing=10)
            content.add_widget(Label(
                text=f'No se pudieron cargar los datos.\n{error_msg}\n\nRevise su conexión a internet.',
                color=(0.1, 0.1, 0.1, 1), halign='center'))
            popup = Popup(title='Error de sincronización', content=content,
                         size_hint=(0.85, 0.45), title_color=(0.1, 0.35, 0.65, 1),
                         title_size=15, separator_color=(0.8, 0.8, 0.8, 1))
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
        except:
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
                item = {
                    'id_prod': str(r[0] or ""),
                    'barras': str(r[1] or ""),
                    'laboratorio': str(r[2] or "S/L"),
                    'nombre': str(r[3] or "Sin nombre"),
                    'precio_caja': self._fmt(self.safe_float(r[4])),
                    'precio_blister': self._fmt(self.safe_float(r[5])),
                    'precio_unidad': self._fmt(self.safe_float(r[6])),
                    'catalog_screen': self
                }
                data.append(item)
            self.ids.rv.data = data
        except Exception as e:
            logger.error(f"Error en búsqueda: {e}")

    # ============================================================
    # FUNCIONES DE VENDEDOR
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
        
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text="Seleccione un vendedor:", font_size=16, 
                                 color=(0.1,0.35,0.65,1), bold=True))
        
        for v in vendedores:
            btn = Button(text=f"{v['codigo']} - {v['nombre']}", 
                        size_hint_y=None, height=45,
                        background_normal='', background_color=(0.1,0.35,0.65,1),
                        color=(1,1,1,1), bold=True, font_size=14)
            btn.bind(on_press=lambda instance, v=v: self.seleccionar_vendedor(v))
            content.add_widget(btn)
        
        popup = Popup(title='Seleccionar Vendedor', content=content,
                     size_hint=(0.8, 0.6), auto_dismiss=False,
                     title_color=(0.1,0.35,0.65,1), title_size=16,
                     separator_color=(0.8,0.8,0.8,1))
        self._popup_vendedor = popup
        popup.open()

    def seleccionar_vendedor(self, vendedor):
        self.vendedor_actual = vendedor
        self.actualizar_boton_vender()
        self.actualizar_header_sucursal()
        if hasattr(self, '_popup_vendedor'):
            self._popup_vendedor.dismiss()

    # ============================================================
    # FUNCIONES DEL CARRITO
    # ============================================================
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
            popup = Popup(title='Atención', content=Label(text='Seleccione un vendedor primero'),
                          size_hint=(0.7, 0.3))
            popup.open()
            return
        
        if not self.carrito:
            popup = Popup(title='Carrito vacío', content=Label(text='Agregue productos con el botón "+"'),
                          size_hint=(0.7, 0.3))
            popup.open()
            return
        
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text="🛒 CARRITO DE COMPRAS", font_size=18, bold=True,
                                 color=(0.1,0.35,0.65,1), size_hint_y=None, height=35))
        
        scroll = ScrollView()
        lista_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=5)
        lista_box.bind(minimum_height=lista_box.setter('height'))
        
        total_venta = 0
        
        for idx, item in enumerate(self.carrito):
            producto = item['producto']
            formato = item['formato']
            cantidad = item['cantidad']
            precio_unitario = item['precio_unitario']
            subtotal = precio_unitario * cantidad
            total_venta += subtotal
            
            fila = BoxLayout(orientation='vertical', size_hint_y=None, height=110,
                            padding=[5,5], spacing=2)
            with fila.canvas.before:
                Color(0.95, 0.95, 0.95, 1)
                Rectangle(pos=fila.pos, size=fila.size)
            
            lbl_nombre = Label(text=f"{producto['nombre'][:30]}", bold=True, font_size=13,
                               color=(0,0,0,1), halign='left', size_hint_y=None, height=25)
            fila.add_widget(lbl_nombre)
            
            controles = BoxLayout(orientation='horizontal', size_hint_y=None, height=35, spacing=5)
            
            spinner_formato = Spinner(text=formato, values=('Unidad', 'Blister', 'Caja'),
                                      background_normal='', background_color=(0.1,0.35,0.65,1),
                                      color=(1,1,1,1), font_size=12, size_hint_x=0.3)
            spinner_formato.bind(text=lambda instance, val, i=idx: self.cambiar_formato_carrito(i, val))
            controles.add_widget(spinner_formato)
            
            caja_cantidad = BoxLayout(orientation='horizontal', size_hint_x=0.3, spacing=2)
            btn_menos = Button(text="-", size_hint_x=0.3, background_normal='',
                              background_color=(0.8,0.2,0.1,1), color=(1,1,1,1), font_size=16)
            btn_menos.bind(on_press=lambda instance, i=idx: self.cambiar_cantidad_carrito(i, -1))
            txt_cant = Label(text=str(cantidad), font_size=14, bold=True, color=(0,0,0,1), size_hint_x=0.4)
            btn_mas = Button(text="+", size_hint_x=0.3, background_normal='',
                             background_color=(0.1,0.6,0.1,1), color=(1,1,1,1), font_size=16)
            btn_mas.bind(on_press=lambda instance, i=idx: self.cambiar_cantidad_carrito(i, 1))
            caja_cantidad.add_widget(btn_menos)
            caja_cantidad.add_widget(txt_cant)
            caja_cantidad.add_widget(btn_mas)
            controles.add_widget(caja_cantidad)
            
            lbl_subtotal = Label(text=f"${subtotal:,.0f}", font_size=14, bold=True,
                                 color=(0.1,0.6,0.1,1), size_hint_x=0.3, halign='right')
            controles.add_widget(lbl_subtotal)
            
            btn_eliminar = Button(text="X", size_hint_x=0.1, background_normal='',
                                  background_color=(0.8,0.2,0.1,1), color=(1,1,1,1), font_size=14)
            btn_eliminar.bind(on_press=lambda instance, i=idx: self.eliminar_del_carrito(i))
            controles.add_widget(btn_eliminar)
            
            fila.add_widget(controles)
            lista_box.add_widget(fila)
        
        scroll.add_widget(lista_box)
        content.add_widget(scroll)
        
        total_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=45, spacing=10)
        total_box.add_widget(Label(text=f"TOTAL: ${total_venta:,.0f}", font_size=18, bold=True,
                                   color=(0.1,0.35,0.65,1), size_hint_x=0.6))
        
        btn_pagar = Button(text="PAGAR", background_normal='', background_color=(0.1,0.6,0.1,1),
                          color=(1,1,1,1), bold=True, font_size=16, size_hint_x=0.4)
        btn_pagar.bind(on_press=lambda instance: self.procesar_pago(total_venta))
        total_box.add_widget(btn_pagar)
        content.add_widget(total_box)
        
        btn_cerrar = Button(text="CERRAR CARRITO", size_hint_y=None, height=40,
                            background_normal='', background_color=(0.45,0.45,0.45,1),
                            color=(1,1,1,1), bold=True, font_size=14)
        btn_cerrar.bind(on_press=lambda instance: self.carrito_popup.dismiss())
        content.add_widget(btn_cerrar)
        
        self.carrito_popup = Popup(title='', content=content,
                                   size_hint=(0.9, 0.8), auto_dismiss=False,
                                   separator_color=(0.1,0.35,0.65,1))
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
        
        content = BoxLayout(orientation='vertical', padding=15, spacing=10)
        content.add_widget(Label(text=f"Total a pagar: ${total_venta:,.0f}", font_size=18,
                                 bold=True, color=(0.1,0.35,0.65,1), size_hint_y=None, height=40))
        
        dinero_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=50, spacing=10)
        dinero_box.add_widget(Label(text="Dinero recibido:", font_size=16, size_hint_x=0.5))
        txt_dinero = TextInput(text="0", font_size=18, multiline=False, input_filter='float',
                               size_hint_x=0.5, padding=[10,8],
                               background_color=(0.95,0.95,0.95,1), foreground_color=(0,0,0,1))
        dinero_box.add_widget(txt_dinero)
        content.add_widget(dinero_box)
        
        lbl_cambio = Label(text="Cambio: $0", font_size=16, bold=True,
                          color=(0.8,0.2,0.1,1), size_hint_y=None, height=40)
        content.add_widget(lbl_cambio)
        
        lbl_error = Label(text="", color=(0.8,0.2,0.1,1), font_size=12, size_hint_y=None, height=25)
        content.add_widget(lbl_error)
        
        btn_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=50, spacing=10)
        btn_confirmar = Button(text="CONFIRMAR VENTA", background_normal='',
                               background_color=(0.1,0.6,0.1,1), color=(1,1,1,1),
                               bold=True, font_size=16)
        btn_cancelar = Button(text="CANCELAR", background_normal='',
                              background_color=(0.6,0.2,0.1,1), color=(1,1,1,1),
                              bold=True, font_size=14)
        btn_box.add_widget(btn_confirmar)
        btn_box.add_widget(btn_cancelar)
        content.add_widget(btn_box)
        
        popup_pago = Popup(title='Confirmar Pago', content=content,
                           size_hint=(0.85, 0.45), title_color=(0.1,0.35,0.65,1),
                           title_size=16, separator_color=(0.8,0.8,0.8,1),
                           auto_dismiss=False)
        
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
            except:
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
            
            content_confirm = BoxLayout(orientation='vertical', padding=10, spacing=10)
            content_confirm.add_widget(Label(text="✅ Venta registrada exitosamente!", 
                                            font_size=16, color=(0.1,0.6,0.1,1), bold=True))
            content_confirm.add_widget(Label(text=f"Total: ${total_venta:,.0f}  |  Cambio: ${cambio:,.0f}",
                                            font_size=14, color=(0.1,0.35,0.65,1)))
            popup_confirm = Popup(title='Éxito', content=content_confirm,
                                 size_hint=(0.7, 0.3), auto_dismiss=True,
                                 title_color=(0.1,0.6,0.1,1), title_size=16)
            popup_confirm.open()
            Clock.schedule_once(lambda dt: popup_confirm.dismiss(), 2)
        
        btn_confirmar.bind(on_press=confirmar_venta)
        btn_cancelar.bind(on_press=popup_pago.dismiss)
        
        popup_pago.open()
        Clock.schedule_once(lambda dt: calcular_cambio(), 0.1)

    # ============================================================
    # FIN FUNCIONES DE CARRITO
    # ============================================================

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
                    except:
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
        sm.add_widget(PinScreen(name='pin'))
        sm.add_widget(SucursalSelectionScreen(name='sucursal_selection'))
        sm.add_widget(PreSplashScreen(name='splash'))
        sm.add_widget(CatalogScreen(name='catalog'))
        sm.add_widget(HistorialVentasScreen(name='historial_ventas'))
        
        self.cargar_configuracion_completa()
        
        if self.device_id is None:
            self.device_id = generar_device_id()
            self.guardar_configuracion_completa()
        
        if not self.activated:
            sm.current = 'activation'
        else:
            sm.current = 'pin'
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

    def guardar_pin_hash(self, pin_hash):
        self.pin_hash = pin_hash
        self.guardar_configuracion_completa()

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

    def seleccionar_sucursal(self, nombre_sucursal):
        self.set_sucursal(nombre_sucursal)
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
        except:
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
                    except:
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
        except:
            return 0.0

    def cambiar_sucursal(self):
        self.goto_sucursal_selection()

    def on_stop(self):
        try:
            if self.root and self.root.has_screen('catalog'):
                cat = self.root.get_screen('catalog')
                if hasattr(cat, 'conn') and cat.conn:
                    cat.conn.close()
        except:
            pass


if __name__ == '__main__':
    MiBaseDrogApp().run()