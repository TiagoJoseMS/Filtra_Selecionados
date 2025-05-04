"""
Plugin QGIS 'Filtra Selecionados' - Versão 3.0
Suporte: Camadas Vetoriais incluindo CSV, KML/KMZ e diversos provedores
Autor: Tiago José M Silva
"""
from qgis.core import (
    Qgis,
    QgsField,
    QgsVectorLayer,
    QgsVectorDataProvider,
    QgsDataSourceUri,
    QgsFeatureRequest,
    QgsMessageLog,
    edit
)
from qgis.PyQt.QtCore import QVariant, QLocale, QMetaType, QT_VERSION_STR
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.PyQt.QtGui import QIcon
import os

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def exibir_mensagem(iface, mensagem, erro=False, sucesso=False):
    """Exibe mensagens com durações personalizadas"""
    nivel = Qgis.Critical if erro else Qgis.Success if sucesso else Qgis.Info
    duracao = 3 if erro else 3 if sucesso else 4
    iface.messageBar().pushMessage(
        traduzir("Filter Selected"),
        mensagem,
        level=nivel,
        duration=duracao
    )

def campo_e_unico(camada, nome_campo):
    """Verifica se todos os valores de um campo são únicos (case-insensitive para strings)"""
    valores = set()
    indice = camada.fields().lookupField(nome_campo)
    
    if indice == -1:
        return False
        
    for feat in camada.getFeatures():
        valor = feat[indice]
        
        if isinstance(valor, str):
            valor = valor.strip().lower()
            
        if valor in valores:
            return False
        valores.add(valor)
        
    return len(valores) == camada.featureCount()

def possui_valores_nulos(camada, nome_campo):
    """Identifica a presença de valores nulos em um campo"""
    for feat in camada.getFeatures():
        if feat[nome_campo] is None:
            return True
    return False

def camada_editavel(camada):
    """Determina se a camada permite edição de atributos"""
    return camada.dataProvider().capabilities() & QgsVectorDataProvider.AddAttributes

def identificar_tipo_camada(camada):
    """Classifica a camada pelo provedor de dados"""
    provedor = camada.dataProvider().name().lower()
    uri = camada.source().lower()
    
    if 'wfs' in uri or provedor == 'wfs':
        return 'wfs'
    elif provedor in ('postgres', 'postgresql', 'oracle', 'mssql', 'mysql', 'spatialite'):
        return 'database'
    elif provedor == 'delimitedtext' or '.csv' in uri:
        return 'csv'
    elif 'libkml' in provedor or any(ext in uri for ext in ['.kml', '.kmz']):
        return 'kml'
    elif provedor == 'ogr' and any(ext in uri for ext in ['.shp', '.gpkg']):
        return 'file'
    elif camada.isTemporary():
        return 'temporary'
    return 'other'

# =============================================================================
# GERENCIAMENTO DE CHAVES PRIMÁRIAS (SGBDs)
# =============================================================================

def obter_chave_primaria(camada):
    """Identifica chaves primárias em camadas de banco de dados"""
    try:
        uri = QgsDataSourceUri(camada.dataProvider().dataSourceUri())
        provedor = camada.dataProvider().name().lower()
        
        if provedor in ('postgres', 'postgresql'):
            sql = f"""
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = '{uri.schema()}.{uri.table()}'::regclass
                AND i.indisprimary"""
        
        elif provedor == 'mysql':
            sql = f"""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = '{uri.database()}'
                AND TABLE_NAME = '{uri.table()}'
                AND COLUMN_KEY = 'PRI'"""
        
        elif provedor == 'mssql':
            tabela = uri.table().split('.')[-1] if '.' in uri.table() else uri.table()
            sql = f"""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE TABLE_NAME = '{tabela}'
                AND CONSTRAINT_NAME = 'PRIMARY'"""
        
        elif provedor == 'spatialite':
            sql = f"PRAGMA table_info({uri.table()})"
            
        elif provedor == 'oracle':
            sql = f"""
                SELECT column_name
                FROM all_cons_columns
                WHERE constraint_name = (
                    SELECT constraint_name
                    FROM all_constraints
                    WHERE table_name = '{uri.table().upper()}'
                    AND owner = '{uri.schema().upper()}'
                    AND constraint_type = 'P'
                )
                AND owner = '{uri.schema().upper()}'
            """
        else:
            return None

        resultado = camada.dataProvider().executeSql(sql)
        
        if provedor == 'spatialite':
            for coluna in resultado:
                if coluna[5] == 1:
                    return coluna[1]
        elif resultado:
            return resultado[0][0]

    except Exception as e:
        QgsMessageLog.logMessage(f"Erro ao obter PK: {str(e)}", "FiltraSelecionados", Qgis.Warning)
    
    return None

# =============================================================================
# LÓGICA DE SELEÇÃO DE CAMPOS
# =============================================================================

def identificar_campo_filtro(camada, iface):
    """Seleciona o campo ideal seguindo a hierarquia definida"""
    tipo_camada = identificar_tipo_camada(camada)
    
    # 1. Bancos de dados
    if tipo_camada == 'database':
        pk = obter_chave_primaria(camada)
        if pk and campo_e_unico(camada, pk) and not possui_valores_nulos(camada, pk):
            return pk
        for campo in camada.fields():
            nome_campo = campo.name()
            if (campo_e_unico(camada, nome_campo) 
                and not possui_valores_nulos(camada, nome_campo)):
                return nome_campo
        return None

    # 2. WFS/CSV/Camadas não editáveis
    if tipo_camada in ('wfs', 'csv') or not camada_editavel(camada):
        for campo in camada.fields():
            nome_campo = campo.name()
            if (campo_e_unico(camada, nome_campo) 
                and not possui_valores_nulos(camada, nome_campo)):
                return nome_campo
        return None

    # 3. Camadas editáveis (KML/KMZ, arquivos, temporárias)
    elif tipo_camada in ('kml', 'file', 'temporary'):
        prioridades = [
            {'nomes': ['fid', 'id', 'objectid'], 'tipos': [QVariantInt, QVariantLongLong]},
            {'nomes': ['id', 'cod', 'co'], 'tipos': [QVariantInt]},
            {'nomes': ['id', 'cod', 'co', 'nome', 'no'], 'tipos': [QVariantString]},
            {'nomes': [], 'tipos': [QVariantInt]},
            {'nomes': [], 'tipos': [QVariantString]}
        ]

        for grupo in prioridades:
            for campo in camada.fields():
                nome_campo = campo.name().lower()
                tipo_valido = campo.type() in grupo['tipos']
                nome_valido = (not grupo['nomes'] or 
                              any(n in nome_campo for n in grupo['nomes']))
                
                if nome_valido and tipo_valido:
                    if (campo_e_unico(camada, campo.name()) 
                        and not possui_valores_nulos(camada, campo.name())):
                        return campo.name()
        
        return gerenciar_campo_auxiliar(camada, iface)

    return None

def gerenciar_campo_auxiliar(camada, iface):
    """Cria/atualiza campo auxiliar sequencial como fallback"""
    if identificar_tipo_camada(camada) in ('wfs', 'csv') or not camada_editavel(camada):
        return None

    nome_campo = 'id_row_nr'
    try:
        with edit(camada):
            if nome_campo not in camada.fields().names():
                camada.dataProvider().addAttributes([QgsField(nome_campo, QVariantInt)])
                camada.updateFields()
            
            for i, feat in enumerate(camada.getFeatures()):
                feat[nome_campo] = i + 1
                camada.updateFeature(feat)
                
        return nome_campo
    except Exception as e:
        exibir_mensagem(iface, traduzir("Failed to create auxiliary field: ") + str(e), erro=True)
        return None

# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def executar_filtragem(iface):
    """Controla todo o processo de filtragem"""
    camada = iface.activeLayer()
    
    if not camada or not isinstance(camada, QgsVectorLayer) or not camada.isValid():
        exibir_mensagem(iface, traduzir("Select a valid vector layer"), erro=True)
        return

    selected_ids = camada.selectedFeatureIds()
    if not selected_ids:
        exibir_mensagem(iface, traduzir("No features selected"), erro=True)
        return

    tipo_camada = identificar_tipo_camada(camada)
    if tipo_camada == 'wfs' and len(selected_ids) > 20:
        resposta = QMessageBox.warning(
            iface.mainWindow(),
            traduzir("Warning: Large number of selected features in WFS layer!\n\n"),
            traduzir(
            f"{len(selected_ids)} selected features can result in excessively long URLs, affecting the visualization of the layer in QGIS.\n\n"
            "It is recommended to save the layer locally to apply filters to a large number of features.\n\n"
            "Do you want to proceed anyway?", len(selected_ids)),
            QMessageBoxYes | QMessageBoxNo
        )
        if resposta == QMessageBoxNo:
            exibir_mensagem(iface, traduzir("Filter cancelled by user"))
            return

    try:
        camada.setSubsetString('')
        
        campo = identificar_campo_filtro(camada, iface)
        if not campo:
            exibir_mensagem(iface, traduzir("No field with unique values found"), erro=True)
            return

        request = QgsFeatureRequest().setFilterFids(selected_ids)
        valores = [str(feat[campo]) for feat in camada.getFeatures(request)]
        
        tipo_campo = camada.fields().field(campo).type()
        valores_formatados = (
            ",".join(f"'{v}'" for v in valores) 
            if tipo_campo in (QVariantString, QVariantChar) 
            else ",".join(valores)
        )
        
        camada.setSubsetString(f'"{campo}" IN ({valores_formatados})')
        
        mensagem = (
            traduzir("Layer: ") + f"{camada.name()} - \n" +
            traduzir("Filtered features: ") + f"{len(valores)} - \n" +
            traduzir("Field used: ") + f"{campo}"
        )
        exibir_mensagem(iface, mensagem, sucesso=True)

    except Exception as e:
        exibir_mensagem(iface, traduzir(f"Error during filtering: {str(e)}"), erro=True)
        QgsMessageLog.logMessage(f"Erro detalhado: {str(e)}", "FiltraSelecionados", Qgis.Critical)

# =============================================================================
# TRADUÇÃO
# =============================================================================

def traduzir(texto, n_selecionados=0):
    """Traduz o texto para Português do Brasil"""
    locale = QLocale().languageToString(QLocale().language())
    if locale == "Portuguese (Brazil)" or locale == "Portuguese":
        translations = {
            "Filter Selected": "Filtra Selecionados",
            "Select a valid vector layer": "Selecione uma camada vetorial válida",
            "No features selected": "Nenhuma feição selecionada",
            "Filter cancelled by user": "Filtro cancelado pelo usuário",
            "No field with unique values found": "Nenhum campo com valores únicos encontrado",
            "Failed to create auxiliary field: ": "Falha ao criar campo auxiliar: ",
            "Error during filtering: ": "Erro durante a filtragem: ",
            "Layer: ": "Camada: ",
            "Filtered features: ": "Feições filtradas: ",
            "Field used: ": "Campo utilizado: ",
            "Warning: Large number of selected features in WFS layer!\n\n": "Aviso: Grande número de feições selecionadas na camada WFS!\n\n"
        }
        translated_text = translations.get(texto, texto)
        if "selected features can result in excessively long URLs" in texto:
            translated_text = translated_text.replace(f"{n_selecionados} selected features can result in excessively long URLs, "
            "affecting the visualization of the layer in QGIS.\n\nIt is recommended to save the layer locally to apply filters to a large number of features."
            "\n\nDo you want to proceed anyway?", f"{n_selecionados} feições selecionadas podem resultar em URLs excessivamente longas, "
            "comprometendo a visualização da camada no QGIS.\n\nRecomenda-se salvar a camada localmente para aplicar filtros em um grande número de feições."
            "\n\nDeseja prosseguir mesmo assim?")
        return translated_text
    else:
        return texto

# =============================================================================
# INTEGRAÇÃO COM QGIS
# =============================================================================

class FiltraSelecionadosPlugin:
    """Interface do plugin no QGIS"""
    
    def __init__(self, iface):
        self.iface = iface
        self.acao = None

    def initGui(self):
        """Configura a interface gráfica"""
        caminho_icone = os.path.join(os.path.dirname(__file__), "icon.png")
        self.acao = QAction(QIcon(caminho_icone), traduzir("Filter Selected"), self.iface.mainWindow())
        self.acao.triggered.connect(lambda: executar_filtragem(self.iface))
        self.iface.addToolBarIcon(self.acao)
        self.iface.addPluginToMenu(traduzir("Filter Selected"), self.acao)

    def unload(self):
        """Remove os elementos da interface"""
        self.iface.removePluginMenu(traduzir("Filter Selected"), self.acao)
        self.iface.removeToolBarIcon(self.acao)

def classFactory(iface):
    """Inicialização padrão do QGIS"""
    return FiltraSelecionadosPlugin(iface)


# Compatibility check for Qt version (Qt6 first)
QVariantInt = QMetaType.Type.Int
QVariantLongLong = QMetaType.Type.LongLong
QVariantString = QMetaType.Type.QString
QVariantChar = QMetaType.Type.Char
QMessageBoxYes = QMessageBox.StandardButton.Yes
QMessageBoxNo = QMessageBox.StandardButton.No

if QT_VERSION_STR.startswith("5."):
    QVariantInt = QVariant.Int
    QVariantLongLong = QVariant.LongLong
    QVariantString = QVariant.String
    QVariantChar = QVariant.Char
    QMessageBoxYes = QMessageBox.Yes
    QMessageBoxNo = QMessageBox.No

