# -*- coding: utf-8 -*-

"""
Esse arquivo é necessário para que o QGIS reconheça a pasta como um plugin.
"""

def classFactory(iface):
    from .Filtra_Selecionados_V1_2 import FiltraSelecionadosPlugin
    return FiltraSelecionadosPlugin(iface)