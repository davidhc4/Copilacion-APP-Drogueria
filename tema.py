# -*- coding: utf-8 -*-
"""
================================================================================
                    TEMA PREMIUM - PRECIOS FARMACENTER
              Sistema de diseño moderno (estilo Uber / Apple Music)
================================================================================
Este módulo NO contiene lógica de negocio. Solo define:
  - La paleta de colores de marca Farmacenter.
  - El registro de la fuente de iconos vectoriales (Material Design Icons).
  - Componentes reutilizables: botones con sombra y bordes redondeados,
    tarjetas, campos de texto modernos, spinners y popups estilizados.
  - Helpers de animación (escala/opacidad al presionar, fade de pantallas).

Se importa desde main.py. No modifica ninguna función existente.
================================================================================
"""

import os
import sys

from kivy.metrics import dp, sp
from kivy.utils import platform, get_color_from_hex as H
from kivy.animation import Animation
from kivy.core.text import LabelBase
from kivy.properties import (
    ListProperty, NumericProperty, StringProperty, BooleanProperty, ObjectProperty
)
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner, SpinnerOption
from kivy.graphics import Color, RoundedRectangle, Line

# ============================================================
# PALETA DE MARCA FARMACENTER
# Derivada del logo: azul corporativo + naranja de acento.
# ============================================================
COL = {
    # Azules de marca
    "primary":        H("#1B5BA6"),   # azul Farmacenter
    "primary_dark":   H("#0E3D73"),   # azul profundo (encabezados)
    "primary_light":  H("#E8F1FB"),   # azul muy claro (fondos suaves)
    # Acento naranja del logo
    "accent":         H("#F39200"),   # naranja vibrante
    "accent_dark":    H("#D87E00"),
    # Semánticos
    "success":        H("#1FA85A"),   # verde "SI HAY" / confirmar
    "success_dark":   H("#16823F"),
    "danger":         H("#E04434"),   # rojo "NO HAY" / eliminar
    "danger_dark":    H("#B4291B"),
    "warning":        H("#F5A623"),
    # Neutros
    "bg":             H("#F4F6F9"),   # fondo general (gris muy claro)
    "card":           H("#FFFFFF"),   # tarjetas
    "surface":        H("#FFFFFF"),
    "border":         H("#E3E8EF"),   # bordes sutiles
    "text":           H("#1A2330"),   # texto principal
    "text_soft":      H("#5A6573"),   # texto secundario
    "text_mute":      H("#97A1AD"),   # texto terciario / hints
    "white":          H("#FFFFFF"),
    "shadow":         (0, 0, 0, 0.16), # sombra base
}

# ============================================================
# FUENTE DE ICONOS VECTORIALES (Material Design Icons)
# ============================================================
def _ruta_recurso(nombre):
    """Resuelve la ruta del recurso en PC y en Android empaquetado."""
    if hasattr(sys, "_MEIPASS"):
        cand = os.path.join(sys._MEIPASS, nombre)
        if os.path.exists(cand):
            return cand
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, nombre)


ICON_FONT_NAME = "Icons"
_FUENTE_OK = False

def registrar_fuentes():
    """Registra la fuente de iconos. Llamar una vez al iniciar la app."""
    global _FUENTE_OK
    if _FUENTE_OK:
        return
    ruta = _ruta_recurso("mdi.ttf")
    if os.path.exists(ruta):
        LabelBase.register(name=ICON_FONT_NAME, fn_regular=ruta)
        _FUENTE_OK = True
    else:
        # Si no está la fuente, los iconos caerán a texto vacío y no rompe nada.
        _FUENTE_OK = False


# Glifos Material Design Icons (unicode).
# Codepoints VERIFICADOS contra la fuente mdi.ttf incluida en el proyecto.
ICON = {
    "search":      "\U000F0349",  # magnify
    "barcode":     "\U000F0072",  # barcode-scan
    "tag":         "\U000F04FC",  # tag-outline
    "close":       "\U000F0156",  # close
    "cart":        "\U000F0110",  # cart
    "cart_plus":   "\U000F0112",  # cart-plus
    "plus":        "\U000F0415",  # plus
    "minus":       "\U000F0374",  # minus
    "trash":       "\U000F0A7A",  # trash-can-outline
    "sync":        "\U000F04E6",  # sync
    "chart":       "\U000F0128",  # chart-bar
    "building":    "\U000F0991",  # office-building
    "store":       "\U000F10C1",  # storefront-outline
    "copy":        "\U000F018F",  # content-copy
    "pdf":         "\U000F0226",  # file-pdf-box
    "check":       "\U000F012C",  # check
    "user":        "\U000F0004",  # account
    "corn":        "\U000F07B8",  # corn
    "city":        "\U000F0146",  # city
    "leaf":        "\U000F032A",  # leaf
    "home":        "\U000F02DC",  # home
    "lock":        "\U000F033E",  # lock
    "chevron":     "\U000F0140",  # chevron-down
    "back":        "\U000F004D",  # arrow-left
}

def ic(nombre):
    """Devuelve el glifo del icono o cadena vacía si no existe."""
    return ICON.get(nombre, "") if _FUENTE_OK else ""


# ============================================================
# HELPERS DE ANIMACIÓN
# ============================================================
def animar_press(widget):
    """Efecto de 'pulse' al presionar: encoge y vuelve."""
    Animation.cancel_all(widget, "scale_anim")
    a = (Animation(scale_anim=0.94, d=0.06, t="out_quad")
         + Animation(scale_anim=1.0, d=0.12, t="out_back"))
    a.start(widget)


def fade_in(widget, d=0.25):
    widget.opacity = 0
    Animation(opacity=1, d=d, t="out_quad").start(widget)


# ============================================================
# COMPONENTE: BOTÓN PREMIUM
# Bordes redondeados + sombra dibujada + animación al presionar.
# Reemplaza visualmente a Button sin cambiar su API (text, on_press...).
# ============================================================
class MButton(Button):
    radius = NumericProperty(dp(14))
    bg = ListProperty(COL["primary"])
    bg_down = ListProperty(COL["primary_dark"])
    shadow_on = BooleanProperty(True)
    scale_anim = NumericProperty(1.0)
    elev = NumericProperty(dp(4))   # desplazamiento de la sombra

    def __init__(self, **kwargs):
        # Neutraliza el fondo nativo de Kivy
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        kwargs.setdefault("color", COL["white"])
        kwargs.setdefault("bold", True)
        super().__init__(**kwargs)
        self._draw = {}
        with self.canvas.before:
            self._c_shadow = Color(*COL["shadow"])
            self._r_shadow = RoundedRectangle(radius=[self.radius])
            self._c_bg = Color(*self.bg)
            self._r_bg = RoundedRectangle(radius=[self.radius])
        self.bind(pos=self._sync, size=self._sync, scale_anim=self._sync,
                  bg=self._sync, state=self._sync, radius=self._sync,
                  disabled=self._sync, shadow_on=self._sync, elev=self._sync)
        self._sync()

    def _sync(self, *a):
        s = self.scale_anim
        w, h = self.width * s, self.height * s
        x = self.x + (self.width - w) / 2.0
        y = self.y + (self.height - h) / 2.0
        # Sombra
        sh_alpha = COL["shadow"][3] if (self.shadow_on and not self.disabled) else 0
        self._c_shadow.rgba = (0, 0, 0, sh_alpha)
        self._r_shadow.pos = (x, y - self.elev)
        self._r_shadow.size = (w, h)
        self._r_shadow.radius = [self.radius]
        # Fondo (oscurece al presionar, gris si disabled)
        if self.disabled:
            base = (COL["border"][0], COL["border"][1], COL["border"][2], 1)
        elif self.state == "down":
            base = self.bg_down
        else:
            base = self.bg
        self._c_bg.rgba = base
        self._r_bg.pos = (x, y)
        self._r_bg.size = (w, h)
        self._r_bg.radius = [self.radius]

    def on_press(self):
        animar_press(self)
        return super().on_press()


class MIconButton(MButton):
    """Botón cuyo contenido es un icono (usa la fuente de iconos).
    `icon` es una property reactiva: funciona tanto desde Python
    (MIconButton(icon='cart')) como desde KV (icon: 'cart')."""
    icon = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.font_name = ICON_FONT_NAME
        # aplicar el icono inicial si vino por kwargs
        if self.icon:
            self.text = ic(self.icon)

    def on_icon(self, *a):
        # se dispara cuando KV o el código asignan icon
        self.font_name = ICON_FONT_NAME
        self.text = ic(self.icon)


class MTextIconButton(MButton):
    """Botón premium con ICONO + TEXTO correctamente combinados.
    El icono usa la fuente de iconos y el texto la fuente normal,
    mostrados uno al lado del otro y centrados.
    Uso en KV:   MTextIconButton:
                     icon: 'cart'
                     label: 'VENDER'
    """
    icon = StringProperty("")
    label = StringProperty("")
    icon_size = NumericProperty(sp(16))
    label_size = NumericProperty(sp(12))
    gap = NumericProperty(dp(7))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.text = ""  # el Button base no dibuja texto; usamos labels propios
        from kivy.uix.boxlayout import BoxLayout as _BL
        from kivy.uix.label import Label as _L
        self._row = _BL(orientation="horizontal", spacing=self.gap,
                        size_hint=(None, None))
        self._ic = _L(font_name=ICON_FONT_NAME, color=self.color,
                      size_hint=(None, None))
        self._tx = _L(bold=True, color=self.color, size_hint=(None, None))
        self._row.add_widget(self._ic)
        self._row.add_widget(self._tx)
        self.add_widget(self._row)
        self.bind(pos=self._relayout, size=self._relayout,
                  icon=self._refresh, label=self._refresh,
                  color=self._refresh, icon_size=self._refresh,
                  label_size=self._refresh, gap=self._refresh,
                  disabled=self._refresh)
        self._refresh()

    def _refresh(self, *a):
        col = self.color if not self.disabled else (1, 1, 1, 0.85)
        self._ic.font_name = ICON_FONT_NAME
        self._ic.font_size = self.icon_size
        self._ic.color = col
        self._ic.text = ic(self.icon) if self.icon else ""
        self._ic.texture_update()
        self._ic.size = self._ic.texture_size
        self._tx.font_size = self.label_size
        self._tx.color = col
        self._tx.text = self.label
        self._tx.texture_update()
        self._tx.size = self._tx.texture_size
        self._row.spacing = self.gap if (self.icon and self.label) else 0
        self._row.width = self._ic.width + self._row.spacing + self._tx.width
        self._row.height = max(self._ic.height, self._tx.height)
        self._relayout()

    def _relayout(self, *a):
        s = self.scale_anim
        self._row.center_x = self.center_x
        self._row.center_y = self.center_y


# ============================================================
# COMPONENTE: TARJETA (Card) con sombra y bordes redondeados
# ============================================================
class MCard(BoxLayout):
    radius = NumericProperty(dp(16))
    bg = ListProperty(COL["card"])
    shadow_on = BooleanProperty(True)
    elev = NumericProperty(dp(3))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._c_shadow = Color(0, 0, 0, 0.10)
            self._r_shadow = RoundedRectangle(radius=[self.radius])
            self._c_bg = Color(*self.bg)
            self._r_bg = RoundedRectangle(radius=[self.radius])
        self.bind(pos=self._sync, size=self._sync, bg=self._sync,
                  radius=self._sync, shadow_on=self._sync, elev=self._sync)
        self._sync()

    def _sync(self, *a):
        self._c_shadow.rgba = (0, 0, 0, 0.10 if self.shadow_on else 0)
        self._r_shadow.pos = (self.x, self.y - self.elev)
        self._r_shadow.size = self.size
        self._r_shadow.radius = [self.radius]
        self._c_bg.rgba = self.bg
        self._r_bg.pos = self.pos
        self._r_bg.size = self.size
        self._r_bg.radius = [self.radius]


# ============================================================
# COMPONENTE: CAMPO DE TEXTO MODERNO
# Fondo blanco redondeado, borde sutil que se ilumina al enfocar.
# ============================================================
class MTextInput(TextInput):
    radius = NumericProperty(dp(12))

    def __init__(self, **kwargs):
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_active", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        kwargs.setdefault("foreground_color", COL["text"])
        kwargs.setdefault("cursor_color", COL["primary"])
        kwargs.setdefault("hint_text_color", COL["text_mute"])
        kwargs.setdefault("multiline", False)
        kwargs.setdefault("padding", [dp(14), dp(12), dp(14), dp(12)])
        super().__init__(**kwargs)
        with self.canvas.before:
            self._c_bg = Color(*COL["card"])
            self._r_bg = RoundedRectangle(radius=[self.radius])
            self._c_bd = Color(*COL["border"])
            self._l_bd = Line(width=1.3)
        self.bind(pos=self._sync, size=self._sync, radius=self._sync, focus=self._sync)
        self._sync()

    def _sync(self, *a):
        self._r_bg.pos = self.pos
        self._r_bg.size = self.size
        self._r_bg.radius = [self.radius]
        self._c_bd.rgba = COL["primary"] if self.focus else COL["border"]
        self._l_bd.rounded_rectangle = (self.x + 1, self.y + 1,
                                        self.width - 2, self.height - 2, self.radius)


# ============================================================
# COMPONENTE: SPINNER MODERNO (dropdown redondeado)
# ============================================================
class _MSpinnerOption(SpinnerOption):
    def __init__(self, **kwargs):
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_color", COL["primary"])
        kwargs.setdefault("color", COL["white"])
        kwargs.setdefault("font_size", sp(12))
        kwargs.setdefault("height", dp(40))
        super().__init__(**kwargs)


class MSpinner(Spinner):
    radius = NumericProperty(dp(12))
    bg = ListProperty(COL["primary"])

    def __init__(self, **kwargs):
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        kwargs.setdefault("color", COL["white"])
        kwargs.setdefault("bold", True)
        kwargs.setdefault("option_cls", _MSpinnerOption)
        super().__init__(**kwargs)
        with self.canvas.before:
            self._c_bg = Color(*self.bg)
            self._r_bg = RoundedRectangle(radius=[self.radius])
        self.bind(pos=self._sync, size=self._sync, bg=self._sync,
                  radius=self._sync, state=self._sync)
        self._sync()

    def _sync(self, *a):
        c = self.bg
        if self.state == "down":
            c = (c[0] * 0.85, c[1] * 0.85, c[2] * 0.85, 1)
        self._c_bg.rgba = c
        self._r_bg.pos = self.pos
        self._r_bg.size = self.size
        self._r_bg.radius = [self.radius]
