# Filtra Selecionados - Plugin QGIS

# Descrição:
O Filtra Selecionados é um plugin que aprimora o processo de filtragem no QGIS ao analisar a camada ativa e selecionar o campo mais adequado para aplicar um filtro baseado nas feições selecionadas. Ele foi projetado para proporcionar uma filtragem otimizada, em camadas vetoriais editáveis e não editáveis, como WFS ou CSV.

#Motivação:
A dificuldade em filtrar camadas vetoriais onde campos não seguem padrões claros ou a camada é de um tipo não editável, impossibilitando a criação de campos na tabela de atributos que facilitassem esse processo, motivou o desenvolvimento deste plugin. Ele busca simplificar, de forma rápidda e eficiente o processo de filtragem de camadas vetorias no QGIS.

# Principais Funcionalidades:

- **Seleção Inteligente de Campos:** O plugin prioriza campos geralmente utilizados como identificador único de cada feição, como 'fid' ou 'id' e considera a presença de substrings como 'id', 'cod' ou 'co_' nos nomes dos campos para identificar potenciais chaves únicas.
- **Otimização para Camadas Editáveis e Não Editáveis:** Adaptando-se às capacidades de diferentes tipos de camadas, o plugin garante que a filtragem seja aplicada de forma eficaz em uma ampla gama de fontes de dados vetoriais.
- **Criação Automática de Campo Auxiliar:** Para camadas editáveis que não possuem um campo adequado para filtragem, o plugin cria e preenche um campo 'id_row_nr', permitindo uma filtragem precisa baseada na ordem das linhas, ou seja, atribuindo valores únicos para identificar cada feição. Os valores desse campo **são atualizados cada vez que o plugin é usado**, evitando duplicidade nos valores das feições.
- **Tratamento de Campos de Texto:** Ao filtrar por campos de texto, o plugin ajusta automaticamente a sintaxe do filtro para usar aspas simples, garantindo a compatibilidade com a formatação SQL esperada pelo QGIS.
- **Interface Amigável:** Integrado à interface do QGIS, o plugin adiciona um botão à barra de ferramentas e uma entrada no menu de Plugins, facilitando o acesso e a utilização.

# Exemplo de Caso de Uso:
Uma mesma camada pode ser duplicada e filtrada quabtas vezes forem necessárias para apresentar diferentes dados em diferentes contextos, com simbologia e rótulos diferentes, sem perder a integridade e originalizade dos dados, pois todos terão a mesma fonte. Essa prática pode mitigar a possibilidade de trabalhar com dados desatualizados, por exemplo. Fazer isso atráves de uma simples seleção manual ou por meio das ferramentas de seleção do QGIS, economiza tempo ao trabalhar com camadas complexas ou provenientes com muitas feições.

# Público-Alvo:
- Usuários inciantes ou avançados do QGIS que precisam aplicar filtros em camadas vetoriais com base em feições selecionadas, incluindo profissionais como geógrafos, topógrafos, geólogos, engenheiros e analistas GIS.

# Benefícios:

- Automatização do processo de identificação de campos para filtragem.
- Compatibilidade total com camadas vetoriais, idependente de sua fonte (WFS, KML, SHP, GPKG...).
- Criação automática de campos em camadas vetoriais editáveis para garantir funcionalidade em qualquer situação.
- Integração perfeita com o fluxo de trabalho do QGIS.

#Compatibilidade:

- Versões do QGIS: Compatível com a versão 3.x ou superior.
- Sistemas operacionais: Testado em Windows, MacOS e Linux.

#Como Usar:

1. Selecione as feições na camada ativa que você deseja usar como base para o filtro.
2. Clique no botão `Filtra Selecionados` na barra de ferramentas de complementos ou vá para `Plugins` > `Filtra Selecionados`.
3. O plugin analisará a camada e aplicará o filtro com base nas feições selecionadas, utilizando o campo mais adequado.
4. Uma mensagem será exibida na barra de status do QGIS, informando o resultado da operação.

# Documentação e Suporte:

- Suporte: https://github.com/TiagoJoseMS/Filtra_Selecionados/issues.
- Idiomas: Disponível em Português e Inglês.

# Licença:
Este plugin é distribuído sob a licença **GNU General Public License v2 ou posterior (GPLv2+)**.

# Contribuição
- Este plugin é open-source e está aberto para colaboração no repositório oficial do projeto.

#Notas Finais:
- O O Filtra Selecionados foi desenvolvido para aumentar a eficiência no manejo de camadas vetoriais no QGIS. Independentemente do método de seleção utilizado, seja pelas ferramentas do QGIS ou manualmente, o usuário poderá, com apenas um clique, filtrar camadas sem a necessidade de criar consultas complexas e extensas. Feedback da comunidade é bem-vindo para futuras melhorias.

## Autor

Tiago José M Silva - [tiago.moraessilva@hotmail.com](mailto:tiago.moraessilva@hotmail.com)

