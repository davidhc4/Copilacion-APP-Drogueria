# -*- coding: utf-8 -*-
"""
================================================================================
                    MÓDULO DE LICENCIA — PRECIOS FARMACENTER
================================================================================
AVISO DE DERECHO DE AUTOR
    © 2026 Santiago Rincón Chávez y Juan David Chávez Garavito.
    Obra de soporte lógico protegida por la Ley 23 de 1982 y la Decisión
    Andina 351 de 1993 sobre Derecho de Autor en Colombia.
    Todos los derechos reservados.

    Este módulo contiene la lógica de licenciamiento del producto.
    ESTE ARCHIVO ESTÁ DISEÑADO PARA COMPILARSE CON CYTHON (.so / .pyd)
    de modo que su contenido NO quede en texto plano dentro del APK.
================================================================================

IMPORTANTE PARA EL DESARROLLADOR:
    - Cada cliente debe recibir un build con un CLIENTE_SECRETO distinto.
      Así, si un comprador descubre su propio secreto, no puede generar
      códigos de activación válidos para los dispositivos de otros clientes.
    - El valor de abajo es solo un marcador. Cámbialo por cliente antes
      de compilar (ej: "FC_2026_CLIENTE_MAIZAMARILLO_a8f3").
"""

import hashlib

# ----------------------------------------------------------------------
# Secreto por cliente. CAMBIAR ESTE VALOR EN CADA BUILD QUE SE ENTREGUE.
# Idealmente generado al azar y guardado en TU registro privado de ventas.
# ----------------------------------------------------------------------
CLIENTE_SECRETO = "FC_2026_MAIZAMARILLO_befda9"

# Sufijo de versión del esquema de licencia. No es secreto.
_LIC_VERSION = "v2"


def generar_device_id(base_material: str) -> str:
    """
    Recibe el material de identificación del dispositivo (android_id +
    modelo + fabricante, o el nombre del equipo en escritorio) y devuelve
    un device_id corto y estable. La app llama a esta función pasando el
    material; así la recolección del hardware queda en main.py y la
    lógica sensible aquí (compilable con Cython).
    """
    return hashlib.sha256(base_material.encode()).hexdigest()[:16]


def _firma(device_id: str) -> str:
    """Firma interna. No exponer."""
    material = f"{device_id}|{CLIENTE_SECRETO}|{_LIC_VERSION}"
    return hashlib.sha256(material.encode()).hexdigest()[:12].upper()


def generar_codigo_activacion(device_id: str) -> str:
    """
    Usar SOLO en tu herramienta interna de generación de códigos
    (la que tú ejecutas en tu PC). No se llama desde la app del cliente.
    """
    return _firma(device_id)


def verificar_codigo(device_id: str, codigo_ingresado: str) -> bool:
    """
    Valida el código que el cliente escribe en la pantalla de activación.
    """
    if not codigo_ingresado:
        return False
    return codigo_ingresado.strip().upper() == _firma(device_id)
