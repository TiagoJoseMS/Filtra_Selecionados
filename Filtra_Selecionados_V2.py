from qgis.core import (
    QgsProject,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsField,
    edit,
    Qgis,
    QgsVectorLayer,
    QgsVectorDataProvider,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtWidgets import QAction, QToolBar
from qgis.PyQt.QtGui import QIcon
import os

def send_qgis_message(iface, message, error=False, duration=10):
    """Exibe mensagens no painel de mensagens do QGIS."""
    if error:
        iface.messageBar().pushMessage("Erro", message, level=Qgis.Critical, duration=duration)
    else:
        iface.messageBar().pushMessage("Informação", message, level=Qgis.Info, duration=duration)

def is_field_unique(layer, field_name):
    """Verifica se os valores de um campo são únicos na camada."""
    print(f"is_field_unique: Verificando unicidade do campo '{field_name}' na camada '{layer.name()}'")
    unique_values = layer.uniqueValues(layer.fields().indexFromName(field_name))
    is_unique = len(unique_values) == layer.featureCount()
    print(f"is_field_unique: O campo '{field_name}' é único? {is_unique}")
    return is_unique

def has_null_values(layer, field_name):
    """Verifica se um campo possui valores nulos (NULL)."""
    print(f"has_null_values: Verificando valores nulos no campo '{field_name}' na camada '{layer.name()}'")
    for feature in layer.getFeatures():
        if feature[field_name] is None:
            print(f"has_null_values: Campo '{field_name}' possui valores nulos.")
            return True
    print(f"has_null_values: Campo '{field_name}' não possui valores nulos.")
    return False

def is_layer_editable(layer):
    """Verifica se a camada é editável."""
    print(f"is_layer_editable: Verificando se a camada '{layer.name()}' é editável")
    editable = layer.dataProvider().capabilities() & QgsVectorDataProvider.AddAttributes
    print(f"is_layer_editable: A camada '{layer.name()}' é editável? {editable}")
    return editable

def create_row_number_field(layer, iface):
    """Cria um campo 'id_row_nr' preenchido com números de linha.
       Retorna None se a camada não for editável."""
    field_name = 'id_row_nr'

    print(f"create_row_number_field: Tentando criar o campo '{field_name}' na camada '{layer.name()}'")

    # Verifica se a camada é editável ANTES de tentar qualquer operação
    if not is_layer_editable(layer):
        print(f"create_row_number_field: Camada '{layer.name()}' não é editável. Retornando None.")
        send_qgis_message(iface, f"A camada '{layer.name()}' não é editável ou não permite adição de atributos, o campo '{field_name}' não será criado.", error=True)
        return None  # Retorna None explicitamente

    # Verificação redundante (garantia extra)
    if not is_layer_editable(layer):
        print(f"create_row_number_field: Camada '{layer.name()}' não é editável (verificação redundante). Retornando None.")
        return None

    with edit(layer):
        if field_name not in layer.fields().names():
            layer.addAttribute(QgsField(field_name, QVariant.Int))
            send_qgis_message(iface, f"Campo '{field_name}' criado.")

            # Preenche o campo com valores sequenciais
            for i, feature in enumerate(layer.getFeatures()):
                layer.changeAttributeValue(feature.id(), layer.fields().indexFromName(field_name), i + 1)
            send_qgis_message(iface, f"Campo '{field_name}' preenchido com números de linha.")
            print(f"create_row_number_field: Campo '{field_name}' criado e preenchido com sucesso.")
            
            # Força a atualização dos metadados da camada
            layer.updateFields()
            
            
            return field_name  # Retorna o nome do campo criado

        else:
            send_qgis_message(iface, f"Campo '{field_name}' já existe, mas será atualizado com números de linha.")
            layer.deleteAttributes([layer.fields().indexFromName(field_name)])
            layer.addAttribute(QgsField(field_name, QVariant.Int))
            # Preenche o campo com valores sequenciais
            for i, feature in enumerate(layer.getFeatures()):
                layer.changeAttributeValue(feature.id(), layer.fields().indexFromName(field_name), i + 1)
            send_qgis_message(iface, f"Campo '{field_name}' preenchido com números de linha.")
            print(f"create_row_number_field: Campo '{field_name}' atualizado com sucesso.")
            
            # Força a atualização dos metadados da camada
            layer.updateFields()
            
            return field_name  # Retorna o nome do campo criado

    # Se chegou até aqui, algo deu errado
    print(f"create_row_number_field: Erro inesperado. Retornando None.")
    return None

def get_suitable_field_for_filter(layer, iface):
    """
    Retorna um campo adequado para filtro.
    Retorna None se nenhum campo adequado for encontrado.
    """
    print(f"get_suitable_field_for_filter: Iniciando busca por campo adequado na camada '{layer.name()}'")
    field_names = [field.name() for field in layer.fields()]
    print(f"get_suitable_field_for_filter: Campos disponíveis: {field_names}")

    # Prioridades para camadas editáveis
    if is_layer_editable(layer):
        print(f"get_suitable_field_for_filter: Camada '{layer.name()}' é editável. Aplicando prioridades para camadas editáveis.")
        # Prioridade 1: Campos 'fid' ou 'id' (se existirem e forem únicos)
        for field_name in ['fid', 'id']:
            if field_name in field_names and is_field_unique(layer, field_name):
                print(f"get_suitable_field_for_filter: Campo '{field_name}' selecionado (Prioridade 1).")
                return field_name

        # Prioridade 2: Campos inteiros com 'id', 'cod' ou 'co_' no nome (se existirem e forem únicos)
        for field_name in field_names:
            if ('id' in field_name.lower() or 'cod' in field_name.lower() or 'co_' in field_name.lower()) and \
               layer.fields().field(field_name).type() == QVariant.Int and \
               is_field_unique(layer, field_name):
                print(f"get_suitable_field_for_filter: Campo '{field_name}' selecionado (Prioridade 2).")
                return field_name
        
        # Prioridade 3: Campos de texto com 'id', 'cod' ou 'co_' no nome (se existirem e forem únicos)
        for field_name in field_names:
            if ('id' in field_name.lower() or 'cod' in field_name.lower() or 'co_' in field_name.lower()) and \
               layer.fields().field(field_name).type() == QVariant.String and \
               is_field_unique(layer, field_name):
                print(f"get_suitable_field_for_filter: Campo '{field_name}' selecionado (Prioridade 3).")
                return field_name

        # Prioridade 4: Campos inteiros (se existirem e forem únicos)
        for field_name in field_names:
            if layer.fields().field(field_name).type() == QVariant.Int and is_field_unique(layer, field_name):
                print(f"get_suitable_field_for_filter: Campo '{field_name}' selecionado (Prioridade 4).")
                return field_name

        # Prioridade 5: Campos de texto (se existirem e forem únicos)
        for field_name in field_names:
            if layer.fields().field(field_name).type() == QVariant.String and is_field_unique(layer, field_name):
                print(f"get_suitable_field_for_filter: Campo '{field_name}' selecionado (Prioridade 5).")
                return field_name

        # Prioridade 6: Se nenhum campo único adequado for encontrado E a camada for editável, cria o campo 'id_row_nr'
        #   - SOMENTE SE a camada não tiver colunas E um campo adequado não tiver sido encontrado nas prioridades anteriores
        if (not layer.fields() or not field_names) and not any(
            [
                # Prioridade 1
                any(field_name in ['fid', 'id'] and is_field_unique(layer, field_name) for field_name in field_names),
                # Prioridade 2
                any(
                    ('id' in field_name.lower() or 'cod' in field_name.lower() or 'co_' in field_name.lower()) and layer.fields().field(field_name).type() == QVariant.Int and is_field_unique(layer, field_name)
                    for field_name in field_names
                ),
                # Prioridade 3
                any(
                    ('id' in field_name.lower() or 'cod' in field_name.lower() or 'co_' in field_name.lower()) and layer.fields().field(field_name).type() == QVariant.String and is_field_unique(layer, field_name)
                    for field_name in field_names
                ),
                # Prioridade 4
                any(layer.fields().field(field_name).type() == QVariant.Int and is_field_unique(layer, field_name) for field_name in field_names),
                # Prioridade 5
                any(layer.fields().field(field_name).type() == QVariant.String and is_field_unique(layer, field_name) for field_name in field_names),
            ]
        ):
            campo_criado = create_row_number_field(layer, iface)
            if campo_criado:
                return campo_criado

    # Prioridades para camadas não editáveis
    else:
        print(f"get_suitable_field_for_filter: Camada '{layer.name()}' não é editável. Aplicando prioridades para camadas não editáveis.")
        # Prioridade 1: Campos 'fid' ou 'id' (se existirem e forem únicos)
        for field_name in ['fid', 'id']:
            if field_name in field_names and is_field_unique(layer, field_name):
                print(f"get_suitable_field_for_filter: Campo '{field_name}' selecionado (Prioridade 1).")
                return field_name
        
        # Prioridade 2: Campos inteiros, longos ou double com 'id', 'cod', 'co_', 'nome' ou 'no_' no nome (se existirem e forem únicos e sem nulos)
        for field_name in field_names:
            if ('id' in field_name.lower() or 'cod' in field_name.lower() or 'co_' in field_name.lower() or 'nome' in field_name.lower() or 'no_' in field_name.lower()) and \
               layer.fields().field(field_name).type() in (QVariant.Int, QVariant.LongLong, QVariant.Double) and \
               is_field_unique(layer, field_name) and not has_null_values(layer, field_name):
                print(f"get_suitable_field_for_filter: Campo '{field_name}' selecionado (Prioridade 2).")
                return field_name

        # Prioridade 3: Campos de texto com 'id', 'cod', 'co_', 'nome' ou 'no_' no nome (se existirem e forem únicos e sem nulos)
        for field_name in field_names:
            if ('id' in field_name.lower() or 'cod' in field_name.lower() or 'co_' in field_name.lower() or 'nome' in field_name.lower() or 'no_' in field_name.lower()) and \
               layer.fields().field(field_name).type() == QVariant.String and \
               is_field_unique(layer, field_name) and not has_null_values(layer, field_name):
                print(f"get_suitable_field_for_filter: Campo '{field_name}' selecionado (Prioridade 3).")
                return field_name.strip()  # Remove espaços em branco

        # Prioridade 4: Campos inteiros, longos ou double (se existirem e forem únicos e sem nulos)
        for field_name in field_names:
            if layer.fields().field(field_name).type() in (QVariant.Int, QVariant.LongLong, QVariant.Double) and \
               is_field_unique(layer, field_name) and not has_null_values(layer, field_name):
                print(f"get_suitable_field_for_filter: Campo '{field_name}' selecionado (Prioridade 4).")
                return field_name

        # Prioridade 5: Campos de texto (se existirem e forem únicos e sem nulos)
        for field_name in field_names:
            if layer.fields().field(field_name).type() == QVariant.String and is_field_unique(layer, field_name) and not has_null_values(layer, field_name):
                print(f"get_suitable_field_for_filter: Campo '{field_name}' selecionado (Prioridade 5).")
                return field_name.strip()  # Remove espaços em branco
        
        # Prioridade 6: Campos inteiros, longos, double ou de texto únicos, mas que POSSAM ter valores nulos
        for field_name in field_names:
            if is_field_unique(layer, field_name) and field_name in field_names:
                print(f"get_suitable_field_for_filter: Campo '{field_name}' selecionado (Prioridade 6 - único, mas pode ter nulos).")
                return field_name.strip() # Remove espaços em branco se for texto

    # Se nenhum campo adequado for encontrado
    print(f"get_suitable_field_for_filter: Nenhum campo adequado encontrado em get_suitable_field_for_filter. Retornando None.")
    return None

def filter_layer(iface):
    """Aplica um filtro na camada ativa com base nas feições selecionadas."""
    print(f"filter_layer: Iniciando filtro na camada '{iface.activeLayer().name() if iface.activeLayer() else 'N/A'}'")
    layer = iface.activeLayer()

    if not layer:
        send_qgis_message(iface, "Nenhuma camada ativa.", error=True)
        return

    if not layer.selectedFeatureCount():
        send_qgis_message(iface, "Nenhuma feição selecionada.", error=True)
        return

    filter_field = get_suitable_field_for_filter(layer, iface)
    print(f"filter_layer: Campo para filtro: '{filter_field}'")

    # Verifica se um campo foi retornado E se ele existe na camada
    if filter_field and filter_field in [field.name() for field in layer.fields()]:
        selected_ids = [feature[filter_field] for feature in layer.selectedFeatures()]
        print(f"filter_layer: IDs selecionados: {selected_ids}")

        if selected_ids:
            # Verifica se o campo é do tipo texto
            if layer.fields().field(filter_field).type() == QVariant.String:
                # Formata a expressão do filtro com aspas simples para campos de texto
                filter_expression = f'"{filter_field}" IN ({", ".join(map(lambda x: f"\'{x}\'", selected_ids))})'
            else:
                # Mantém a formatação original para outros tipos de campo
                filter_expression = f'"{filter_field}" IN ({", ".join(map(str, sorted(selected_ids)))})'

            print(f"filter_layer: Expressão do filtro: {filter_expression}")
            layer.setSubsetString(filter_expression)
            # Mensagem de retorno do resultado (Aprimorada)
            num_selected = len(selected_ids)
            plural_suffix = "s" if num_selected > 1 else ""
            send_qgis_message(
                iface,
                f"Filtro aplicado na camada '{layer.name()}'. "
                f"{num_selected} feição{plural_suffix} selecionada{plural_suffix} filtrada{plural_suffix} "
                f"usando o campo '{filter_field}'. "
                f"Expressão: {filter_expression}",
                duration=10
            )
            return  # Sai da função após aplicar o filtro
        else:
            send_qgis_message(iface, "Nenhum ID encontrado nas feições selecionadas para aplicar o filtro.", error=True)
            return  # Sai da função se não houver IDs

    # Se nenhum campo adequado for encontrado e a camada for editável, tenta criar 'id_row_nr'
    if is_layer_editable(layer):
        print(f"filter_layer: Nenhum campo adequado encontrado anteriormente. Tentando criar 'id_row_nr'.")
        campo_criado = create_row_number_field(layer, iface)
        if campo_criado:
            print(f"filter_layer: Campo 'id_row_nr' criado com sucesso. Aplicando filtro usando 'id_row_nr'.")
            selected_ids = {feature[campo_criado] for feature in layer.selectedFeatures()}
            print(f"filter_layer: IDs selecionados: {selected_ids}")

            if selected_ids:
                filter_expression = f'"{campo_criado}" IN ({", ".join(map(str, sorted(selected_ids)))})'
                print(f"filter_layer: Expressão do filtro: {filter_expression}")
                layer.setSubsetString(filter_expression)
                # Mensagem de retorno do resultado (Aprimorada)
                num_selected = len(selected_ids)
                plural_suffix = "s" if num_selected > 1 else ""
                send_qgis_message(
                    iface,
                    f"Filtro aplicado na camada '{layer.name()}'. "
                    f"{num_selected} feição{plural_suffix} selecionada{plural_suffix} filtrada{plural_suffix} "
                    f"usando o campo '{campo_criado}'. "
                    f"Expressão: {filter_expression}"
                )
                return  # Sai da função após aplicar o filtro

    # Se chegou até aqui, o filtro não foi aplicado em camada não editável
    print(f"filter_layer: Não foi possível aplicar o filtro.")
    if not is_layer_editable(layer):
        send_qgis_message(iface, f"Não foi possível aplicar o filtro na camada '{layer.name()}' (camada não editável) pois não há campos adequados para filtro. Considere a possibilidade de torná-la editável", error=True, duration=10)
    else:
        send_qgis_message(iface, f"Não foi possível aplicar o filtro na camada '{layer.name()}'.", error=True, duration=10)
    return  # Sai da função se o filtro não for aplicado

# As funções classFactory e unload são necessárias para que o QGIS carregue o plugin corretamente.
def classFactory(iface):
    return FiltraSelecionadosPlugin(iface)

def unload():
    iface.removePluginMenu('&Filtra_Selecionados', action)
    iface.removeToolBarIcon(action)

class FiltraSelecionadosPlugin:
    def __init__(self, iface):
        self.iface = iface

    def initGui(self):
        global action
        # Cria a ação do botão
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        action = QAction(QIcon(icon_path), "Filtra Selecionados", self.iface.mainWindow())
        action.triggered.connect(lambda: filter_layer(self.iface))

        # Adiciona o botão à barra de ferramentas
        self.iface.addToolBarIcon(action)

        # Adiciona o botão ao menu de plugins
        self.iface.addPluginToMenu('&Filtra Selecionados', action) #sugestão para colocar em negrito: <b>&Filtra Selecionados</b>

    def unload(self):
        self.iface.removePluginMenu('&Filtra Selecionados', action)
        self.iface.removeToolBarIcon(action)