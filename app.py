import pandas as pd
import streamlit as st
import plotly_express as px

# =====================================================================================================================
# LAYOUT
# =====================================================================================================================

# Configuração geral da página: modo wide, ícone e título na aba do navegador
st.set_page_config(layout="wide", page_icon='📈', page_title='Distribuidor Prata Viva Ltda')

# Título principal exibido no topo do dashboard
st.title('Vistto ETL', anchor='center', text_alignment='center')

# Criação de 3 colunas para exibir os cards de métricas lado a lado
col1, col2, col3 = st.columns(3)

# Placeholders vazios: serão preenchidos com os valores calculados após o ETL
metric_qtdvendas = col1.empty()
metric_vendas    = col2.empty()
metric_ticket    = col3.empty()

# =====================================================================================================================
# EXTRAÇÃO — Carregamento dos dados brutos
# =====================================================================================================================

# Cache evita recarregar os CSVs a cada interação do usuário com o Streamlit
@st.cache_data
def carregar_dados_completos():
    # Retorna um dicionário com os 4 DataFrames brutos, sem nenhum tratamento
    colecao = {
        "vendas":    pd.read_csv('vendas.csv'),
        "clientes":  pd.read_csv('clientes.csv'),
        "despesas":  pd.read_csv('despesas.csv'),
        "produtos":  pd.read_csv('produtos.csv')
    }
    return colecao


# Chama a função e extrai cada DataFrame individualmente do dicionário
dados       = carregar_dados_completos()
df_vendas   = dados["vendas"]
df_produtos = dados["produtos"]
df_clientes = dados["clientes"]
df_despesas = dados["despesas"]

# =====================================================================================================================
# TRANSFORMAÇÃO — Limpeza e padronização de cada tabela
# =====================================================================================================================

# ---------------------------------------------------------------------------------------------------------------------
# Tabela: VENDAS
# ---------------------------------------------------------------------------------------------------------------------

# Converte a coluna de data para o tipo datetime, aceitando formatos mistos (ex: dd/mm/aaaa e aaaa-mm-dd)
# dayfirst=True garante que datas ambíguas sejam lidas com o dia na frente
# errors='coerce' transforma datas inválidas em NaT ao invés de lançar erro
df_vendas['data'] = pd.to_datetime(df_vendas['data'], format='mixed', dayfirst=True, errors='coerce').dt.date

# Remove registros com data inválida (NaT virou None após .dt.date)
df_vendas = df_vendas[df_vendas['data'].notnull()]

# Remove linhas duplicadas usando as colunas que identificam unicamente uma venda
# keep='first' preserva a primeira ocorrência de cada duplicata
df_vendas = df_vendas.drop_duplicates(
    subset=['data', 'produto', 'quantidade', 'valor_total', 'id_cliente'],
    keep='first'
)

# Preenche células vazias na categoria com valor padrão para evitar problemas em agrupamentos
df_vendas['categoria'] = df_vendas['categoria'].fillna('Sem categoria')

# Limpeza das colunas financeiras: remove "R$", separador de milhar (.) e substitui vírgula por ponto decimal
# O resultado é convertido para float, tornando os valores operáveis matematicamente
colunas_financeiras_vendas = ['valor_unitario', 'valor_total']
for coluna in colunas_financeiras_vendas:
    df_vendas[coluna] = (
        df_vendas[coluna]
        .astype(str)
        .str.replace('R\$', '', regex=True)
        .str.replace('.', '', regex=False)   # remove ponto de milhar
        .str.replace(',', '.', regex=False)  # vírgula decimal → ponto decimal
        .str.strip()
        .astype(float)
    )

# Padroniza as colunas de texto: remove espaços extras e aplica Title Case (ex: "sabão em pó" → "Sabão Em Pó")
colunas_tratar = ['produto', 'forma_pagamento', 'categoria']
for colunas in colunas_tratar:
    df_vendas[colunas] = df_vendas[colunas].str.strip().str.title()


# ---------------------------------------------------------------------------------------------------------------------
# Tabela: CLIENTES
# ---------------------------------------------------------------------------------------------------------------------

# Trabalha em cópia para não modificar o DataFrame original carregado do cache
df_clientes_clean = df_clientes.copy()

# Colunas que não serão usadas nas análises — descartadas para reduzir ruído
colums_drop_clientes = ['contato', 'telefone', 'segmento', 'email', 'canal_origem']

# Remove duplicatas pelo campo 'contato', descarta colunas desnecessárias e reseta o índice
df_clientes_clean = (
    df_clientes_clean.drop_duplicates(subset=['razao_social'], keep='first')
    .drop(columns=colums_drop_clientes)
    .reset_index(drop=True)
)

# Converte a data de cadastro para o tipo date (sem hora)
df_clientes_clean['data_cadastro'] = (
    pd.to_datetime(df_clientes_clean['data_cadastro'], format='mixed').dt.date
)

# Enriquece a tabela de clientes com os dados de vendas via merge pelo id_cliente
# inner join: mantém apenas clientes que realizaram ao menos uma venda
df_clientes_class = df_clientes_clean.merge(df_vendas, on='id_cliente', how='inner')


# ---------------------------------------------------------------------------------------------------------------------
# Tabela: DESPESAS
# ---------------------------------------------------------------------------------------------------------------------

df_despesas_clean = df_despesas.copy()

# Remove despesas duplicadas com base nas colunas que identificam unicamente um lançamento
df_despesas_clean = (
    df_despesas_clean.drop_duplicates(
        subset=['data', 'categoria', 'descricao', 'fornecedor', 'valor'],
        keep='first')
)

# Preenche campos de texto vazios com valores padrão para evitar NaN em exibições e agrupamentos
df_despesas_clean['descricao']  = df_despesas_clean['descricao'].fillna('Sem Descricao')
df_despesas_clean['fornecedor'] = df_despesas_clean['fornecedor'].fillna('Sem Fornecedor')

# Limpeza da coluna financeira: remove "R$", separadores e sinal de negativo antes de converter para float
colunas_financeiras_despesas = ['valor']
for coluna in colunas_financeiras_despesas:
    df_despesas_clean[coluna] = (
        df_despesas_clean[coluna]
        .astype(str)
        .str.replace('R\$', '', regex=True)
        .str.replace('.', '', regex=False)
        .str.replace(',', '.', regex=False)
        .str.replace('-', '', regex=False)  # remove sinal negativo de lançamentos a débito
        .str.strip()
        .astype(float)
    )

# Garante que todos os valores de despesa sejam positivos (abs() por segurança caso reste algum negativo)
df_despesas_clean['valor'] = df_despesas_clean['valor'].abs()

# Padroniza o texto da categoria
df_despesas_clean['categoria'] = df_despesas_clean['categoria'].str.strip().str.title()


# ---------------------------------------------------------------------------------------------------------------------
# Tabela: PRODUTOS
# ---------------------------------------------------------------------------------------------------------------------

df_produtos_clean = df_produtos.copy()

# Remove linhas que contenham qualquer campo nulo — produtos incompletos não entram nas análises
df_produtos_clean = df_produtos_clean.dropna()

# Limpeza das colunas de preço e custo, seguindo o mesmo padrão das outras tabelas financeiras
colunas_financeiras_produtos = ['custo_unitario', 'preco_venda']
for coluna in colunas_financeiras_produtos:
    df_produtos_clean[coluna] = (
        df_produtos_clean[coluna]
        .astype(str)
        .str.replace('R\$', '', regex=True)
        .str.replace('.', '', regex=False)
        .str.replace(',', '.', regex=False)
        .str.replace('-', '', regex=False)
        .str.strip()
        .astype(float)
    )
df_produtos_clean['margem_percentual'] = df_produtos_clean['margem_percentual'].str.replace(',','.')
# =====================================================================================================================
# EXTRAÇÃO DE PARÂMETROS — KPIs do dashboard
# =====================================================================================================================

# Soma de todos os valores de venda no período
Venda_total = df_vendas['valor_total'].sum()

# Valor médio por venda (ticket médio)
Ticket_medio = df_vendas['valor_total'].mean()

# Contagem de vendas únicas pelo id da venda
QTD_Vendas = df_vendas['id_venda'].nunique()

# Preenche os placeholders criados no início com os valores calculados
metric_vendas.metric('Venda total', f'R${Venda_total:.2f}')
metric_ticket.metric('Ticket Medio', f'R${Ticket_medio:.2f}')
metric_qtdvendas.metric('Quantidade de Vendas', f'{QTD_Vendas}')

# =====================================================================================================================
# VISUALIZAÇÃO — Criação e renderização dos gráficos
# =====================================================================================================================

# Agrupa vendas por categoria e ordena do maior para o menor valor
df_vendas = df_vendas.groupby(by='categoria')['valor_total'].sum().reset_index().sort_values(by='valor_total', ascending=False)

# Agrupa despesas por categoria e ordena do maior para o menor valor
df_despesas_clean = df_despesas_clean.groupby('categoria')['valor'].sum().reset_index().sort_values(by='valor', ascending=False)

# Ordena produtos pela margem percentual (maior margem primeiro)
df_produtos_clean = df_produtos_clean.sort_values(by='margem_percentual', ascending=False)


# Gráfico de barras: distribuição do faturamento por categoria de produto
vendas_por_categoria = (
    px.bar(
        df_vendas,
        x='categoria',
        y='valor_total',
        labels={'categoria': 'Categoria', 'valor_total': 'Valor Total'})
)
vendas_por_categoria.update_layout(
    title='Limpeza é líder em vendas',
    title_x=0.5, title_xanchor='center', title_font=dict(size=30)
)
st.plotly_chart(vendas_por_categoria, use_container_width=True)

# Gráfico de barras: distribuição das despesas por categoria
despesas_por_categoria = (
    px.bar(
        df_despesas_clean,
        x='categoria',
        y='valor',
        labels={'categoria': 'Categoria', 'valor': 'Valor Total'})
)
despesas_por_categoria.update_layout(
    title='Compras tem a maior despesa seguida de salários',
    title_x=0.5, title_xanchor='center', title_font=dict(size=30)
)
st.plotly_chart(despesas_por_categoria, use_container_width=True)

# Gráfico de barras: ranking de produtos por margem percentual
produtos_por_categoria = (
    px.bar(
        df_produtos_clean,
        x='descricao_padrao',
        y='margem_percentual',
        labels={'descricao_padrao': 'Nome do produto', 'margem_percentual': 'Margem'})
)
produtos_por_categoria.update_layout(
    title='Lustra móveis tem a maior margem percentual',
    title_x=0.5, title_xanchor='center', title_font=dict(size=30)
)
st.plotly_chart(produtos_por_categoria, use_container_width=True)