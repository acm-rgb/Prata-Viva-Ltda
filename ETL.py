import pandas as pd
import streamlit as st
import plotly_express as px
from patsy.state import center

#----------------------------------------------------------------------------------------------------------------------#
####################################################### LAYOUT #########################################################
#----------------------------------------------------------------------------------------------------------------------#
st.set_page_config(layout="wide")
st.title('Vistto ETL',anchor='center',text_alignment='center')
col1, col2, col3 = st.columns(3)

metric_qtdvendas = col1.empty()
metric_vendas = col2.empty()
metric_ticket = col3.empty()
#----------------------------------------------------------------------------------------------------------------------#
# Criando função para carregar dados em cache
@st.cache_data
def carregar_dados_completos():
    colecao = {
        "vendas": pd.read_csv('vendas.csv'),
        "clientes": pd.read_csv('clientes.csv'),
        "despesas": pd.read_csv('despesas.csv'),
        "produtos": pd.read_csv('produtos.csv')
    }
    return colecao


#----------------------------------------------------------------------------------------------------------------------#
######################################################### ETL ##########################################################
#----------------------------------------------------------------------------------------------------------------------#
# Extraindo os DataFrames individuais a partir do dicionário de dados carregado
dados = carregar_dados_completos()
df_vendas = dados["vendas"]
df_produtos = dados["produtos"]
df_clientes = dados["clientes"]
df_despesas = dados["despesas"]

#----------------------------------------------------------------------------------------------------------------------#
# Ajustando a tabela de vendas

# Padronizando o formato da data
df_vendas['data'] = pd.to_datetime(df_vendas['data'], format='mixed', dayfirst=True, errors='coerce').dt.date

# Filtrando e removendo registros com datas nulas (inválidas)
df_vendas = df_vendas[df_vendas['data'].notnull()]

# Removendo linhas duplicadas com base nas colunas chave de identificação da venda
df_vendas = df_vendas.drop_duplicates(
    subset=['data', 'produto', 'quantidade', 'valor_total', 'id_cliente'],
    keep='first'
)

# Preenchendo valores vazios na coluna de categoria com texto padrão
df_vendas['categoria'] = df_vendas['categoria'].fillna('Sem categoria')

#Ajustando a coluna de valor para tirar o R$ e poder realizar calculos de forma precisa
colunas_financeiras_vendas = ['valor_unitario', 'valor_total']

for coluna in colunas_financeiras_vendas:
    df_vendas[coluna] = (
        df_vendas[coluna]
        .astype(str)
        .str.replace('R\$','',regex=True)
        .str.replace('.', '', regex=False)
        .str.replace(',', '.', regex=False)
        .str.strip()
        .astype(float)
    )

colunas_tratar = ['produto','forma_pagamento','categoria']
for colunas in colunas_tratar:
    df_vendas[colunas] = df_vendas[colunas].str.strip().str.title()



#----------------------------------------------------------------------------------------------------------------------#
# Ajustando a tabela de clientes

# Criando uma cópia do DataFrame para manipular os dados com segurança
df_clientes_cleaning = df_clientes.copy()

# Definindo a lista de colunas que não serão utilizadas e serão descartadas
colums_drop_clientes = ['contato','telefone','segmento','email','canal_origem']

# Removendo duplicatas, excluindo as colunas desnecessárias e redefinindo o índice
df_clientes_cleaning = (
    df_clientes_cleaning.drop_duplicates(subset=['contato'], keep='first')
    .drop(columns=colums_drop_clientes)
    .reset_index(drop=True)
)

# Padronizando o formato da data de cadastro do cliente
df_clientes_cleaning['data_cadastro'] = (
    pd.to_datetime(
        df_clientes_cleaning['data_cadastro'],
        format='mixed').dt.date
)

df_clientes_class = df_clientes_cleaning.merge(df_vendas, on='id_cliente', how='inner')

#----------------------------------------------------------------------------------------------------------------------#
# Ajustando tabela de despesas

df_despesas_cleaning = df_despesas.copy()
df_despesas_cleaning = (
    df_despesas_cleaning.drop_duplicates(
        subset=['data','categoria','descricao','fornecedor','valor'],
        keep='first')
)

df_despesas_cleaning['descricao'] = df_despesas_cleaning['descricao'].fillna('Sem Descricao')
df_despesas_cleaning['fornecedor'] = df_despesas_cleaning['fornecedor'].fillna('Sem Fornecedor')

colunas_financeiras_despesas = ['valor']

for coluna in colunas_financeiras_despesas:
    df_despesas_cleaning[coluna] = (
        df_despesas_cleaning[coluna]
        .astype(str)
        .str.replace('R\$','',regex=True)
        .str.replace('.', '', regex=False)
        .str.replace(',', '.', regex=False)
        .str.replace('-', '', regex=False)
        .str.strip()
        .astype(float)
    )
df_despesas_cleaning['valor'] = df_despesas_cleaning['valor'].abs()
df_despesas_cleaning['categoria'] = df_despesas_cleaning['categoria'].str.strip().str.title()
#----------------------------------------------------------------------------------------------------------------------#
############################################# EXTRAÇÃO DE PARÂMETROS ###################################################
#----------------------------------------------------------------------------------------------------------------------#
Venda_total = df_vendas['valor_total'].sum()
Ticket_medio = df_vendas['valor_total'].mean()
QTD_Vendas = df_vendas['id_venda'].nunique()

metric_vendas.metric('Venda total', f'R${Venda_total:.2f}')
metric_ticket.metric('Ticket Medio', f'R${Ticket_medio:.2f}')
metric_qtdvendas.metric('Quantidade de Vendas', f'{QTD_Vendas}')

#----------------------------------------------------------------------------------------------------------------------#
############################################# CRIAÇÃO DE GRÁFICOS ###################################################
#----------------------------------------------------------------------------------------------------------------------#
# Agrupando de acordo com interesse
df_vendas = df_vendas.groupby(by='categoria')['valor_total'].sum().reset_index().sort_values(by='valor_total', ascending=False)
df_despesas_cleaning = df_despesas_cleaning.groupby('categoria')['valor'].sum().reset_index().sort_values(by='valor', ascending=False)


# Gerando gráfico Vendas
vendas_por_categoria = (
    px.bar(
        df_vendas,
        x = 'categoria',
        y = 'valor_total',
        labels={'categoria':'Categoria','valor_total':'Valor Total'})
        )
vendas_por_categoria.update_layout(title='Limpeza é líder em vendas',title_x=0.5,title_xanchor='center',title_font = dict(size=30))
st.plotly_chart(vendas_por_categoria, use_container_width=True)

# Gerando gráfico Despesas
despesas_por_categoria = (
    px.bar(
        df_despesas_cleaning,
        x = 'categoria',
        y = 'valor',
        labels={'categoria':'Categoria','valor':'Valor Total'})
)
despesas_por_categoria.update_layout(title='Compras tem a maior despesa seguida de salários',title_x=0.5,title_xanchor='center',title_font = dict(size=30))
st.plotly_chart(despesas_por_categoria, use_container_width=True)