from qgis.core import (
    Qgis,
    QgsField,
    QgsVectorLayer,
    QgsVectorDataProvider,
    QgsDataSourceUri,
    QgsProject
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtWidgets import QAction, QToolBar, QMessageBox
from qgis.PyQt.QtGui import QIcon
import os

def send_qgis_message(iface, message, error=False, duration=10):
    """
    Exibe mensagens na barra de mensagens do QGIS.

    Args:
        iface: Referência à interface do QGIS (QgisInterface).
        message: A mensagem a ser exibida.
        error: Define se a mensagem é um erro (True) ou informação (False).
        duration: Duração da mensagem em segundos.
    """
    if error:
        iface.messageBar().pushMessage("Erro", message, level=Qgis.Critical, duration=duration)
    else:
        iface.messageBar().pushMessage("Informação", message, level=Qgis.Info, duration=duration)

def is_field_unique(layer, field_name):
    """
    Verifica se os valores de um campo são únicos na camada.

    Args:
        layer: A camada vetorial (QgsVectorLayer).
        field_name: O nome do campo a ser verificado.

    Returns:
        True se os valores do campo forem únicos, False caso contrário.
    """
    unique_values = layer.uniqueValues(layer.fields().indexFromName(field_name))
    return len(unique_values) == layer.featureCount()

def has_null_values(layer, field_name):
    """
    Verifica se um campo possui valores nulos (NULL).

    Args:
        layer: A camada vetorial (QgsVectorLayer).
        field_name: O nome do campo a ser verificado.

    Returns:
        True se o campo possuir pelo menos um valor nulo, False caso contrário.
    """
    for feature in layer.getFeatures():
        if feature[field_name] is None:
            return True
    return False

def is_layer_editable(layer):
    """
    Verifica se a camada é editável.

    Args:
        layer: A camada vetorial (QgsVectorLayer).

    Returns:
        True se a camada for editável, False caso contrário.
    """
    return layer.dataProvider().capabilities() & QgsVectorDataProvider.AddAttributes

def get_layer_type(layer):
    """
    Retorna o tipo da camada, com base no provedor de dados.

    Args:
        layer: A camada vetorial (QgsVectorLayer).

    Returns:
        Uma string representando o tipo da camada: 'database', 'wfs', 'file', 'temporary' ou 'other'.
    """
    provider_type = layer.providerType()
    uri = QgsDataSourceUri(layer.dataProvider().dataSourceUri())

    if provider_type in ('postgres', 'spatialite', 'mysql', 'oracle'):
        return 'database'
    elif provider_type == 'wfs':
        return 'wfs'
    elif provider_type == 'ogr' and uri.table() and not uri.uri().startswith('http'):
        # Camada baseada em arquivo (ex: GPKG, SHP) e não é um serviço WFS.
        return 'file'
    elif layer.isTemporary():
        return 'temporary'
    else:
        return 'other'

def get_primary_key_field_name(layer):
    """
    Retorna o nome do campo de chave primária da camada, se houver.

    Busca a chave primária (PK) em camadas de banco de dados (PostGIS, MySQL, SpatiaLite).
    Para outros tipos de camada, retorna None.

    Args:
        layer: A camada vetorial (QgsVectorLayer).

    Returns:
        O nome do campo da chave primária, ou None se não for encontrado ou se o tipo de camada não for suportado.
    """
    provider = layer.dataProvider()
    uri = QgsDataSourceUri(provider.dataSourceUri())
    layer_type = get_layer_type(layer)

    if layer_type == 'database':
        if 'PG:' in uri.uri():
            # Camada PostGIS
            try:
                schema = uri.schema()
                table = uri.table()
                # Query SQL para identificar a PK.
                sql = f"""
                    SELECT pg_attribute.attname
                    FROM pg_index, pg_class, pg_attribute, pg_namespace
                    WHERE
                        pg_class.oid = '{schema}'.'{table}'::regclass AND
                        indrelid = pg_class.oid AND
                        nspname = '{schema}' AND
                        pg_class.relnamespace = pg_namespace.oid AND
                        pg_attribute.attrelid = pg_class.oid AND
                        pg_attribute.attnum = any(pg_index.indkey)
                        AND indisprimary
                    """
                (result, returned_data) = provider.executeSql(sql)
                if result and returned_data:
                    return returned_data[0][0]  # Retorna o nome da coluna da chave primária
            except Exception as e:
                print(f"Erro ao obter a chave primária da camada PostGIS: {e}")
                return None

        elif 'MySQL:' in uri.uri():
            # Camada MySQL
            try:
                database = uri.database()
                table = uri.table()
                sql = f"""
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA = '{database}'
                    AND TABLE_NAME = '{table}'
                    AND CONSTRAINT_NAME = 'PRIMARY';
                """
                (result, returned_data) = provider.executeSql(sql)
                if result:
                    for row in returned_data:
                        return row[0]
            except Exception as e:
                print(f"Erro ao obter a chave primária da camada MySQL: {e}")
                return None

        elif 'SpatiaLite:' in uri.uri():
            # Camada SpatiaLite
            try:
                table = uri.table()
                # Consulta para obter a chave primária em SpatiaLite.
                sql = f"PRAGMA table_info('{table}');"
                (result, returned_data) = provider.executeSql(sql)
                if result:
                    for row in returned_data:
                        # A coluna 5 (índice 5) indica se é chave primária (1) ou não (0)
                        if row[5] == 1:
                            return row[1]  # Retorna o nome do campo
            except Exception as e:
                print(f"Erro ao obter a chave primária da camada SpatiaLite: {e}")
                return None

    return None  # Não é um banco de dados suportado ou não foi possível obter a chave primária

def create_row_number_field(layer, iface):
    """
    Cria um campo 'id_row_nr' preenchido com números de linha na camada, se necessário.

    Este campo é útil como um identificador único para camadas que não possuem um campo
    adequado para serem usados como filtro.

    Args:
        layer: A camada vetorial (QgsVectorLayer).
        iface: Referência à interface do QGIS (QgisInterface).

    Returns:
        O nome do campo criado ('id_row_nr'), ou None se a camada não for editável ou se ocorrer um erro.
    """
    field_name = 'id_row_nr'
    layer_type = get_layer_type(layer)

    if not is_layer_editable(layer):
        send_qgis_message(iface, f"A camada '{layer.name()}' não é editável ou não permite adição de atributos, o campo '{field_name}' não será criado.", error=True)
        return None

    provider = layer.dataProvider()

    try:
        if field_name not in layer.fields().names():
            if layer_type == 'database':
                # Usa executeSql() para camadas de banco de dados
                uri = provider.dataSourceUri()
                if 'PG:' in uri:
                    # Camada PostGIS
                    parts = uri.split(' ')
                    for part in parts:
                        if part.startswith('schema='):
                            schema_name = part.split('=')[1].replace("'", "").replace('"', '')
                            break
                    else:
                        schema_name = 'public'
                    sql = f'ALTER TABLE "{schema_name}"."{layer.name()}" ADD COLUMN "{field_name}" INTEGER'

                # Adicione outros tipos de banco de dados aqui, se necessário

                if not provider.executeSql(sql):
                    raise Exception(f"Falha ao executar a query SQL: {sql}")

            elif layer_type in ('file', 'temporary'):
                # Usa addAttributes() para camadas baseadas em arquivo e temporárias
                provider.addAttributes([QgsField(field_name, QVariant.Int)])

            else:
                raise Exception(f"Tipo de camada não suportado para criação de campo: {layer_type}")

            layer.updateFields()
            send_qgis_message(iface, f"Campo '{field_name}' criado.")

        # Preenche o campo criado com os números de linha
        new_values = {}
        for i, feature in enumerate(layer.getFeatures()):
            new_values[feature.id()] = {layer.fields().indexFromName(field_name): i + 1}

        provider.changeAttributeValues(new_values)
        send_qgis_message(iface, f"Campo '{field_name}' preenchido com números de linha.")

        layer.updateFields()
        return field_name

    except Exception as e:
        send_qgis_message(iface, f"Erro ao criar o campo '{field_name}' na camada '{layer.name()}'. Detalhes: {e}", error=True, duration=15)
        return None

def get_suitable_field_for_filter(layer, iface):
    """
    Retorna um campo adequado para aplicar um filtro na camada, considerando o tipo da camada e as prioridades estabelecidas.

    Para camadas SHP, a função prioriza a reutilização do campo que foi utilizado em um filtro anterior e está armazenado
    na variável `shp_filter_fields` da classe do plugin.
    Caso contrário, segue uma ordem de prioridade para selecionar um campo:

    Prioridades:
        0. Chave Primária (para todos os tipos de camada)
        1. Campos 'fid' ou 'id' (inteiros) para camadas editáveis baseadas em arquivo
        2. Campos 'id', 'cod' ou 'co' (inteiros) para camadas editáveis baseadas em arquivo
        3. Campos 'id', 'cod', 'co', 'nome' ou 'no' (texto) para camadas editáveis baseadas em arquivo
        4. Qualquer campo do tipo inteiro para camadas editáveis baseadas em arquivo
        5. Qualquer campo do tipo texto para camadas editáveis baseadas em arquivo
        6. (Somente para camadas editáveis) Se nenhum campo adequado for encontrado, cria o campo 'id_row_nr'.

    Para camadas de banco de dados (qualquer tipo, editáveis ou não) e camadas não editáveis, as prioridades são as mesmas,
    mas desconsiderando valores nulos (exceto na prioridade 6).

    Args:
        layer: A camada vetorial (QgsVectorLayer).
        iface: Referência à interface do QGIS (QgisInterface).

    Returns:
        O nome do campo adequado para o filtro, ou None se nenhum campo adequado for encontrado.
    """
    field_names = [field.name() for field in layer.fields()]
    pk_field_name = get_primary_key_field_name(layer)
    layer_type = get_layer_type(layer)

    # Prioridade para camadas SHP: Reutilizar campo do filtro anterior (se existir)
    if layer_type == 'file' and layer.dataProvider().storageType() == 'ESRI Shapefile':
        last_used_field = iface.shp_filter_fields.get(layer.id())
        if last_used_field:
            send_qgis_message(iface, f"Reutilizando campo '{last_used_field}' para o filtro em camada SHP.", duration=5)
            return last_used_field

    # Prioridades para camadas editáveis (GPKG, SHP, Temporárias)
    if is_layer_editable(layer) and layer_type == 'file':
        # Prioridade 0: Chave Primária
        if pk_field_name and is_field_unique(layer, pk_field_name):
            return pk_field_name

        # Prioridades de 1 a 5: Campos 'fid', 'id', inteiros ou texto, com nomes ou tipos específicos
        for priority_keywords in [['fid', 'id'],
                                  ['id', 'cod', 'co'],
                                  ['id', 'cod', 'co', 'nome', 'no'],
                                  [], []]:  # Prioridades 4 e 5 não têm palavras-chave específicas
            for field_name in field_names:
                field = layer.fields().field(field_name)
                is_priority_type = (
                    (priority_keywords == ['fid', 'id'] and field_name.lower() in priority_keywords and field.type() in (QVariant.Int, QVariant.LongLong)) or
                    (priority_keywords == ['id', 'cod', 'co'] and ('id' in field_name.lower() or 'cod' in field_name.lower() or 'co' in field_name.lower()) and field.type() == QVariant.Int) or
                    (priority_keywords == ['id', 'cod', 'co', 'nome', 'no'] and ('id' in field_name.lower() or 'cod' in field_name.lower() or 'co' in field_name.lower() or 'nome' in field_name.lower() or 'no' in field_name.lower()) and field.type() == QVariant.String) or
                    (priority_keywords == [] and field.type() == QVariant.Int) or
                    (priority_keywords == [] and field.type() == QVariant.String)
                )
                if is_priority_type and is_field_unique(layer, field_name):
                    return field_name

        # Prioridade 6: Se nenhum campo único adequado for encontrado, cria o campo 'id_row_nr'
        if not any(
            [
                bool(pk_field_name and is_field_unique(layer, pk_field_name)),
                any(field_name in ['fid', 'id'] and is_field_unique(layer, field_name) for field_name in field_names),
                any(('id' in field_name.lower() or 'cod' in field_name.lower() or 'co' in field_name.lower()) and layer.fields().field(field_name).type() == QVariant.Int and is_field_unique(layer, field_name)
                    for field_name in field_names),
                any(('id' in field_name.lower() or 'cod' in field_name.lower() or 'co' in field_name.lower() or 'nome' in field_name.lower() or 'no' in field_name.lower()) and layer.fields().field(field_name).type() == QVariant.String and is_field_unique(layer, field_name)
                    for field_name in field_names),
                any(layer.fields().field(field_name).type() == QVariant.Int and is_field_unique(layer, field_name) for field_name in field_names),
                any(layer.fields().field(field_name).type() == QVariant.String and is_field_unique(layer, field_name) for field_name in field_names),
            ]
        ):
            campo_criado = create_row_number_field(layer, iface)
            if campo_criado:
                return campo_criado

    # Prioridades para camadas de banco de dados (qualquer tipo, editáveis ou não) e camadas não editáveis
    else:
        # Prioridade 0: Chave Primária
        if pk_field_name and is_field_unique(layer, pk_field_name):
            return pk_field_name

        # Prioridades de 1 a 5: Campos 'fid', 'id', inteiros ou texto, com nomes ou tipos específicos (sem nulos)
        for priority_keywords in [['fid', 'id'],
                                  ['id', 'cod', 'co', 'nome', 'no'],
                                  ['id', 'cod', 'co', 'nome', 'no'],
                                  [], []]:  # Prioridades 4 e 5 não têm palavras-chave específicas
            for field_name in field_names:
                field = layer.fields().field(field_name)
                is_priority_type = (
                    (priority_keywords == ['fid', 'id'] and field_name.lower() in priority_keywords) or
                    (priority_keywords == ['id', 'cod', 'co', 'nome', 'no'] and ('id' in field_name.lower() or 'cod' in field_name.lower() or 'co' in field_name.lower() or 'nome' in field_name.lower() or 'no' in field_name.lower()) and field.type() in (QVariant.Int, QVariant.LongLong, QVariant.Double)) or
                    (priority_keywords == ['id', 'cod', 'co', 'nome', 'no'] and ('id' in field_name.lower() or 'cod' in field_name.lower() or 'co' in field_name.lower() or 'nome' in field_name.lower() or 'no' in field_name.lower()) and field.type() == QVariant.String) or
                    (priority_keywords == [] and field.type() in (QVariant.Int, QVariant.LongLong, QVariant.Double)) or
                    (priority_keywords == [] and field.type() == QVariant.String)
                )
                if is_priority_type and is_field_unique(layer, field_name) and not has_null_values(layer, field_name):
                    return field_name.strip() if field.type() == QVariant.String else field_name

        # Prioridade 6: Campos únicos, mas que POSSAM ter valores nulos
        for field_name in field_names:
            if is_field_unique(layer, field_name):
                return field_name.strip() if layer.fields().field(field_name).type() == QVariant.String else field_name

    return None

def filter_layer(iface):
    """
    Aplica um filtro na camada ativa com base nas feições selecionadas.

    O filtro é aplicado usando um campo da camada que atenda aos critérios definidos na
    função `get_suitable_field_for_filter`.

    Para camadas SHP, o campo utilizado no primeiro filtro é armazenado em um dicionário na classe do plugin
    e será reutilizado em chamadas subsequentes da função, assumindo que o campo ainda exista na camada.

    Args:
        iface: Referência à interface do QGIS (QgisInterface).
    """
    layer = iface.activeLayer()

    if layer is None:
        send_qgis_message(iface, "Nenhuma camada ativa.", error=True)
        return

    # Verifica se há feições selecionadas
    if not layer.selectedFeatureCount():
        send_qgis_message(iface, "Nenhuma feição selecionada.", error=True)
        return

    # Verifica o tipo da camada
    layer_type = get_layer_type(layer)

    # Se for WFS e tiver mais de 20 feições selecionadas, exibe mensagem de aviso.
    if layer_type == 'wfs' and layer.selectedFeatureCount() > 20:
        send_qgis_message(iface,
                         f"A camada '{layer.name()}' é um serviço WFS e mais de 20 feições estão selecionadas. "
                         f"A URL gerada pelo filtro pode ser muito longa e causar erros de requisição. "
                         f"Recomenda-se salvar a camada em um formato local como Geopackage ou Shapefile antes de aplicar o filtro.",
                         error=False, duration=15)

    # Obtém o campo para o filtro
    filter_field = get_suitable_field_for_filter(layer, iface)

    if filter_field:
        selected_ids = [feature[filter_field] for feature in layer.selectedFeatures()]

        if selected_ids:
            # Formata a expressão do filtro
            if layer.fields().field(filter_field).type() == QVariant.String:
                filter_expression = f'"{filter_field}" IN ({", ".join(map(lambda x: f"\'{x}\'", selected_ids))})'
            else:
                filter_expression = f'"{filter_field}" IN ({", ".join(map(str, sorted(selected_ids)))})'

            layer.setSubsetString(filter_expression)

            # Armazena o campo utilizado no filtro para camadas SHP
            if layer_type == 'file' and layer.dataProvider().storageType() == 'ESRI Shapefile':
                iface.shp_filter_fields[layer.id()] = filter_field

            # Mensagem de retorno do resultado
            num_selected = len(selected_ids)
            if num_selected == 1:
                send_qgis_message(
                    iface,
                    f"Filtro aplicado na camada '{layer.name()}'. "
                    f"1 feição selecionada e filtrada "
                    f"usando o campo '{filter_field}'. "
                    f"Expressão: {filter_expression}",
                    duration=7
                )
            else:
                send_qgis_message(
                    iface,
                    f"Filtro aplicado na camada '{layer.name()}'. "
                    f"{num_selected} feições selecionadas e filtradas "
                    f"usando o campo '{filter_field}'. "
                    f"Expressão: {filter_expression}",
                    duration=7
                )
            return
        else:
            send_qgis_message(iface, "Nenhum ID encontrado nas feições selecionadas para aplicar o filtro.", error=True)
            return

    # Se chegou até aqui, o filtro não foi aplicado
    # Camadas de banco de dados
    if layer_type == 'database':
        pk_field_name = get_primary_key_field_name(layer)
        if pk_field_name is None:
            send_qgis_message(iface, f"Não foi possível aplicar o filtro na camada '{layer.name()}'. A camada é proveniente de um banco de dados e não foi possível identificar uma chave primária definida. Considere definir uma chave primária para a tabela.", error=True, duration=10)
        else:
            send_qgis_message(iface, f"Não foi possível aplicar o filtro na camada '{layer.name()}'. Não foram encontrados campos adequados para o filtro.", error=True, duration=10)
    # Camadas editáveis que não são de banco de dados (GPKG, SHP, temporárias)
    elif is_layer_editable(layer) and layer_type in ('file', 'temporary'):
        campo_criado = create_row_number_field(layer, iface)
        if campo_criado:
            selected_ids = {feature[campo_criado] for feature in layer.selectedFeatures()}
            if selected_ids:
                filter_expression = f'"{campo_criado}" IN ({", ".join(map(str, sorted(selected_ids)))})'
                layer.setSubsetString(filter_expression)

                # Mensagem de retorno do resultado
                num_selected = len(selected_ids)
                if num_selected == 1:
                    send_qgis_message(
                        iface,
                        f"Filtro aplicado na camada '{layer.name()}'. "
                        f"1 feição selecionada e filtrada "
                        f"usando o campo '{campo_criado}'. "
                        f"Expressão: {filter_expression}"
                    )
                else:
                    send_qgis_message(
                        iface,
                        f"Filtro aplicado na camada '{layer.name()}'. "
                        f"{num_selected} feições selecionadas e filtradas "
                        f"usando o campo '{campo_criado}'. "
                        f"Expressão: {filter_expression}"
                    )
                return
        else:
            send_qgis_message(iface, f"Não foi possível aplicar o filtro na camada '{layer.name()}'. Não foram encontrados campos adequados para o filtro e a camada não tem campos para criar um campo auxiliar.", error=True, duration=10)
    # Camadas não editáveis que não são de banco de dados
    else:
        send_qgis_message(iface, f"Não foi possível aplicar o filtro na camada '{layer.name()}'. Não foram encontrados campos adequados para o filtro.", error=True, duration=10)
    return

def classFactory(iface):
    """
    Cria a instância do plugin 'FiltraSelecionadosPlugin'.

    Esta função é chamada pelo QGIS para carregar o plugin.

    Args:
        iface: Referência à interface do QGIS (QgisInterface).

    Returns:
        Uma instância da classe FiltraSelecionadosPlugin.
    """
    return FiltraSelecionadosPlugin(iface)

def unload():
    """
    Remove o plugin do QGIS.

    Esta função é chamada pelo QGIS quando o plugin é desabilitado ou desinstalado.
    """
    iface.removePluginMenu('&Filtra Selecionados', action)
    iface.removeToolBarIcon(action)

class FiltraSelecionadosPlugin:
    """
    Classe principal do plugin 'Filtra Selecionados'.

    Este plugin permite filtrar as feições de uma camada vetorial com base nas feições selecionadas.
    """
    def __init__(self, iface):
        """
        Inicializa a classe do plugin.

        Args:
            iface: Referência à interface do QGIS (QgisInterface).
        """
        self.iface = iface
        self.shp_filter_fields = {}  # Dicionário para armazenar o último campo usado para cada camada SHP

    def initGui(self):
        """
        Inicializa a interface gráfica do plugin.

        Cria um botão na barra de ferramentas e uma entrada no menu 'Plugins' para acionar a função de filtro.
        """
        global action
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        action = QAction(QIcon(icon_path), "Filtra Selecionados", self.iface.mainWindow())
        action.triggered.connect(lambda: filter_layer(self.iface))

        self.iface.addToolBarIcon(action)
        self.iface.addPluginToMenu('&Filtra Selecionados', action)

    def unload(self):
        """
        Remove os elementos da interface gráfica do plugin.

        Remove o botão da barra de ferramentas e a entrada do menu 'Plugins'.
        """
        self.iface.removePluginMenu('&Filtra Selecionados', action)
        self.iface.removeToolBarIcon(action)