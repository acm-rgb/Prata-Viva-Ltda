# %%
# v0.2.2 - Vistto Inteligência Financeira (Nomenclatura Limpa)
import os
import re
import unicodedata
import pandas as pd
import streamlit as st
import plotly.express as px

# ======================================================================================================================
# CONFIGURAÇÃO DA PÁGINA E CSS
# ======================================================================================================================
st.set_page_config(layout="wide", page_icon="📈", page_title="Vistto - Inteligência de Negócios")

st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 28px; color: #2ca02c; font-weight: bold; }
    [data-testid="stMetricLabel"] { font-size: 14px; color: #555; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { 
        height: 45px; 
        background-color: #f8f9fa; 
        border-radius: 5px 5px 0 0; 
        padding: 10px 20px;
        border: 1px solid #ddd;
    }
    .stTabs [aria-selected="true"] { background-color: #2ca02c !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# ======================================================================================================================
# CONFIGURAÇÃO DE CAMINHOS
# ======================================================================================================================
try:
    DIRETORIO_BASE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    DIRETORIO_BASE = os.getcwd()

CAMINHO_ARQUIVO_VENDAS = os.path.join(DIRETORIO_BASE, "vendas.csv")
CAMINHO_ARQUIVO_CLIENTES = os.path.join(DIRETORIO_BASE, "clientes.csv")
CAMINHO_ARQUIVO_DESPESAS = os.path.join(DIRETORIO_BASE, "despesas.csv")
CAMINHO_ARQUIVO_PRODUTOS = os.path.join(DIRETORIO_BASE, "produtos.csv")

# ======================================================================================================================
# DICIONÁRIOS DE PADRONIZAÇÃO
# ======================================================================================================================
MAPA_PADRONIZACAO_PRODUTOS = {
    "deterg. neutro 500ml": "detergente neutro 500ml",
    "agua sanitaria 1 litro": "agua sanitaria 1l",
    "agua sanitaria 1l": "agua sanitaria 1l",
    "sabao em po 1kg": "sabao em po 1kg",
    "sabao po 1kg": "sabao em po 1kg",
    "luva borracha m": "luva de borracha m",
    "luva borracha media": "luva de borracha m",
    "luva de borracha m": "luva de borracha m",
    "desinfetante pinho 500ml": "desinfetante pinho 500ml",
    "esponja de aco c/8": "esponja de aco c/8",
    "esponja dupla face": "esponja dupla face",
    "pano de chao 60x80": "pano de chao 60x80",
}

MAPA_PADRONIZACAO_DESPESAS = {
    "fornecedor": "compras (mercadoria)",
    "fornecedores": "compras (mercadoria)",
    "compras": "compras (mercadoria)",
    "compra": "compras (mercadoria)",
    "salario": "salarios",
    "salarios": "salarios",
    "energia": "energia eletrica",
    "energia eletrica": "energia eletrica",
    "aluguel": "aluguel",
    "devolucao": "devolucao / ajuste",
    "contabilidade": "contabilidade",
    "transporte": "transporte",
    "manutencao": "manutencao",
    "marketing": "marketing",
    "impostos": "impostos",
}


# ======================================================================================================================
# FUNÇÕES UTILITÁRIAS
# ======================================================================================================================
def ler_csv_com_fallback_de_codificacao(caminho, tipos_de_dados):
    """Tenta ler em UTF-8, se falhar, usa Latin-1 para evitar quebra com caracteres especiais do Windows."""
    try:
        return pd.read_csv(caminho, dtype=tipos_de_dados, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(caminho, dtype=tipos_de_dados, encoding="latin-1")


def extrair_valor_monetario_limpo(valor_texto):
    """Remove R$, espaços e converte vírgula para ponto."""
    if pd.isna(valor_texto) or valor_texto == "": return 0.0
    numeros_extraidos = re.sub(r"[^\d,\.\-]", "", str(valor_texto)).replace(",", ".")
    if numeros_extraidos.count(".") > 1:
        partes_numero = numeros_extraidos.split(".")
        numeros_extraidos = "".join(partes_numero[:-1]) + "." + partes_numero[-1]
    try:
        return float(numeros_extraidos)
    except:
        return 0.0


def remover_acentuacao_e_caracteres_especiais(texto):
    if not isinstance(texto, str): return ""
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def padronizar_coluna_texto(serie_pandas):
    """Converte para minúsculas, remove espaços extras e remove acentos."""
    return serie_pandas.astype(str).str.lower().str.strip().apply(remover_acentuacao_e_caracteres_especiais)


# ======================================================================================================================
# TRANSFORMAÇÃO — ETL COMPLETO
# ======================================================================================================================
@st.cache_data
def executar_pipeline_etl_vistto():
    # 1. Definição estrita de tipos para evitar inferência errada
    tipos_vendas = {"id_venda": str, "produto": str, "quantidade": str, "valor_total": str, "id_cliente": str}
    tipos_clientes = {"id_cliente": str, "email": str, "telefone": str, "segmento": str, "canal_origem": str}
    tipos_despesas = {"id_despesa": str, "categoria": str, "valor": str}
    tipos_produtos = {"codigo": str, "descricao_padrao": str, "custo_unitario": str, "estoque_atual": str,
                      "estoque_minimo": str}

    # 2. Carga dos Dados Brutos
    df_vendas_bruto = ler_csv_com_fallback_de_codificacao(CAMINHO_ARQUIVO_VENDAS, tipos_vendas)
    df_clientes_bruto = ler_csv_com_fallback_de_codificacao(CAMINHO_ARQUIVO_CLIENTES, tipos_clientes)
    df_despesas_bruto = ler_csv_com_fallback_de_codificacao(CAMINHO_ARQUIVO_DESPESAS, tipos_despesas)
    df_produtos_bruto = ler_csv_com_fallback_de_codificacao(CAMINHO_ARQUIVO_PRODUTOS, tipos_produtos)

    # 3. Limpeza e Tratamento da Base de Vendas
    df_vendas_limpo = df_vendas_bruto.copy()
    df_vendas_limpo["data_formatada"] = pd.to_datetime(df_vendas_limpo["data"], dayfirst=True, errors="coerce")
    df_vendas_limpo["valor_total_numerico"] = df_vendas_limpo["valor_total"].apply(extrair_valor_monetario_limpo)
    df_vendas_limpo["quantidade_inteira"] = pd.to_numeric(df_vendas_limpo["quantidade"], errors="coerce").fillna(
        0).astype(int)

    # Removemos vendas zeradas ou canceladas
    df_vendas_limpo = df_vendas_limpo[df_vendas_limpo["valor_total_numerico"] > 0].copy()

    # Padroniza nome do produto consultando o dicionário Vistto
    df_vendas_limpo["produto_padronizado"] = padronizar_coluna_texto(df_vendas_limpo["produto"]).map(
        lambda nome: MAPA_PADRONIZACAO_PRODUTOS.get(nome, nome)
    )

    # 4. Limpeza e Tratamento da Base de Produtos
    df_produtos_limpo = df_produtos_bruto.copy()
    df_produtos_limpo["custo_numerico"] = df_produtos_limpo["custo_unitario"].apply(extrair_valor_monetario_limpo)
    df_produtos_limpo["estoque_atual_numerico"] = pd.to_numeric(df_produtos_limpo["estoque_atual"],
                                                                errors="coerce").fillna(0).abs()
    df_produtos_limpo["estoque_minimo_numerico"] = pd.to_numeric(df_produtos_limpo["estoque_minimo"],
                                                                 errors="coerce").fillna(0).abs()
    df_produtos_limpo["produto_padronizado"] = padronizar_coluna_texto(df_produtos_limpo["descricao_padrao"])

    # 5. Limpeza e Deduplicação da Base de Clientes
    df_clientes_limpo = df_clientes_bruto.copy()
    df_clientes_limpo["telefone_apenas_numeros"] = df_clientes_limpo["telefone"].astype(str).str.replace(r"\D", "",
                                                                                                         regex=True)
    df_clientes_limpo = df_clientes_limpo.drop_duplicates(subset=["id_cliente"]).reset_index(drop=True)

    # 6. Limpeza e Tratamento da Base de Despesas
    df_despesas_limpo = df_despesas_bruto.copy()
    df_despesas_limpo["data_formatada"] = pd.to_datetime(df_despesas_limpo["data"], dayfirst=True, errors="coerce")
    df_despesas_limpo["valor_numerico"] = df_despesas_limpo["valor"].apply(extrair_valor_monetario_limpo)
    df_despesas_limpo["categoria_padronizada"] = padronizar_coluna_texto(df_despesas_limpo["categoria"]).map(
        lambda cat: MAPA_PADRONIZACAO_DESPESAS.get(cat, cat)
    )

    # 7. Cruzamento de Dados (Joins Analíticos)
    # Trazemos custo e categoria do cadastro de produtos para a tabela de vendas
    df_vendas_limpo = df_vendas_limpo.merge(
        df_produtos_limpo[["produto_padronizado", "custo_numerico", "categoria", "codigo"]],
        on="produto_padronizado",
        how="left",
        suffixes=("", "_do_produto")
    )

    # Trazemos dados de segmentação do cliente para a tabela de vendas
    df_vendas_limpo = df_vendas_limpo.merge(
        df_clientes_limpo[["id_cliente", "canal_origem", "segmento", "cidade"]],
        on="id_cliente",
        how="left"
    )

    # Cálculo das métricas brutas financeiras por venda
    df_vendas_limpo["custo_total_da_venda"] = df_vendas_limpo["quantidade_inteira"] * df_vendas_limpo["custo_numerico"]
    df_vendas_limpo["lucro_bruto_da_venda"] = df_vendas_limpo["valor_total_numerico"] - df_vendas_limpo[
        "custo_total_da_venda"]

    # Retorna os DataFrames consolidados
    return df_vendas_limpo, df_clientes_limpo, df_despesas_limpo, df_produtos_limpo


# Execução do pipeline e atribuição às variáveis base do sistema
df_vendas_base, df_clientes_base, df_despesas_base, df_produtos_base = executar_pipeline_etl_vistto()

# ======================================================================================================================
# SIDEBAR — FILTROS GLOBAIS
# ======================================================================================================================
with st.sidebar:
    st.title("🛡️ Vistto Intelligence")
    st.markdown("---")

    # Criamos uma coluna de Mes/Ano para facilitar o filtro de competência
    df_vendas_base["competencia_mes_ano"] = df_vendas_base["data_formatada"].dt.strftime("%m/%Y")

    lista_de_competencias_disponiveis = sorted(df_vendas_base["competencia_mes_ano"].dropna().unique().tolist(),
                                               reverse=True)

    periodo_selecionado = st.selectbox("Período de Análise", ["Todo o Histórico"] + lista_de_competencias_disponiveis)

# Aplicar filtros globais criando os DataFrames que irão de fato alimentar os gráficos
if periodo_selecionado != "Todo o Histórico":
    df_vendas_filtrado = df_vendas_base[df_vendas_base["competencia_mes_ano"] == periodo_selecionado].copy()

    # Precisamos calcular o mês/ano das despesas em tempo real para o filtro
    mascara_mes_despesa = df_despesas_base["data_formatada"].dt.strftime("%m/%Y") == periodo_selecionado
    df_despesas_filtrado = df_despesas_base[mascara_mes_despesa].copy()
else:
    df_vendas_filtrado = df_vendas_base.copy()
    df_despesas_filtrado = df_despesas_base.copy()

# ======================================================================================================================
# DASHBOARD — ESTRUTURA DE ABAS
# ======================================================================================================================
aba_executiva, aba_performance, aba_estoque, aba_financeiro = st.tabs([
    "📊 Executivo",
    "🎯 Performance",
    "📦 Estoque",
    "💸 Financeiro"
])

# ----------------------------------------------------------------------------------------------------------------------
# ABA 1 — VISÃO EXECUTIVA
# ----------------------------------------------------------------------------------------------------------------------
with aba_executiva:
    st.subheader(f"Resumo Estratégico: {periodo_selecionado}")

    with st.container(border=True):
        coluna_kpi_1, coluna_kpi_2, coluna_kpi_3, coluna_kpi_4 = st.columns(4)

        faturamento_total_periodo = df_vendas_filtrado["valor_total_numerico"].sum()
        quantidade_total_vendas = len(df_vendas_filtrado)
        ticket_medio_periodo = faturamento_total_periodo / quantidade_total_vendas if quantidade_total_vendas > 0 else 0
        lucro_bruto_total_periodo = df_vendas_filtrado["lucro_bruto_da_venda"].sum()

        coluna_kpi_1.metric("Faturamento", f"R$ {faturamento_total_periodo:,.2f}")
        coluna_kpi_2.metric("Qtd. Vendas", f"{quantidade_total_vendas}")
        coluna_kpi_3.metric("Ticket Médio", f"R$ {ticket_medio_periodo:,.2f}")
        coluna_kpi_4.metric("Lucro Bruto", f"R$ {lucro_bruto_total_periodo:,.2f}")

    with st.container(border=True):
        st.markdown("#### Ranking de Faturamento por Categoria de Produto")
        df_faturamento_por_categoria = (
            df_vendas_filtrado.groupby("categoria")["valor_total_numerico"]
            .sum()
            .reset_index()
            .sort_values("valor_total_numerico")
        )
        grafico_faturamento_categoria = px.bar(
            df_faturamento_por_categoria,
            x="valor_total_numerico",
            y="categoria",
            orientation="h",
            text_auto=".2s",
            color_discrete_sequence=["#2ca02c"]
        )
        st.plotly_chart(grafico_faturamento_categoria, use_container_width=True)

# ----------------------------------------------------------------------------------------------------------------------
# ABA 2 — PERFORMANCE (CAC / LTV)
# ----------------------------------------------------------------------------------------------------------------------
with aba_performance:
    st.subheader("Eficiência de Aquisição e Valor do Cliente")

    with st.container(border=True):
        coluna_metrica_1, coluna_metrica_2, coluna_metrica_3 = st.columns(3)

        investimento_marketing_periodo = \
        df_despesas_filtrado[df_despesas_filtrado["categoria_padronizada"] == "marketing"]["valor_numerico"].sum()
        total_clientes_base = df_clientes_base.shape[0]
        custo_aquisicao_cliente = investimento_marketing_periodo / total_clientes_base if total_clientes_base > 0 else 0

        clientes_unicos_com_compra = df_vendas_filtrado["id_cliente"].nunique()
        lifetime_value_estimado = faturamento_total_periodo / clientes_unicos_com_compra if clientes_unicos_com_compra > 0 else 0

        coluna_metrica_1.metric("Investimento Marketing", f"R$ {investimento_marketing_periodo:,.2f}")
        coluna_metrica_2.metric("CAC Geral Estimado", f"R$ {custo_aquisicao_cliente:,.2f}")
        coluna_metrica_3.metric("LTV Médio", f"R$ {lifetime_value_estimado:,.2f}")

    coluna_grafico_esquerda, coluna_grafico_direita = st.columns(2)

    with coluna_grafico_esquerda:
        with st.container(border=True):
            df_faturamento_por_canal = (
                df_vendas_filtrado.groupby("canal_origem")["valor_total_numerico"]
                .sum()
                .reset_index()
                .sort_values("valor_total_numerico")
            )
            grafico_canal = px.bar(
                df_faturamento_por_canal,
                x="valor_total_numerico",
                y="canal_origem",
                orientation="h",
                title="Faturamento por Canal de Origem"
            )
            st.plotly_chart(grafico_canal, use_container_width=True)

    with coluna_grafico_direita:
        with st.container(border=True):
            df_ticket_por_segmento = (
                df_vendas_filtrado.groupby("segmento")["valor_total_numerico"]
                .mean()
                .reset_index()
                .sort_values("valor_total_numerico")
            )
            grafico_segmento = px.bar(
                df_ticket_por_segmento,
                x="valor_total_numerico",
                y="segmento",
                orientation="h",
                title="Ticket Médio por Segmento de Cliente"
            )
            st.plotly_chart(grafico_segmento, use_container_width=True)

# ----------------------------------------------------------------------------------------------------------------------
# ABA 3 — INTELIGÊNCIA DE ESTOQUE
# ----------------------------------------------------------------------------------------------------------------------
with aba_estoque:
    st.subheader("Análise de Inventário e Capital Imobilizado")

    # Criamos um DataFrame específico para análise da aba de estoque
    df_analise_estoque = df_produtos_base.copy()
    df_analise_estoque["valor_total_imobilizado"] = df_analise_estoque["estoque_atual_numerico"] * df_analise_estoque[
        "custo_numerico"]

    montante_total_imobilizado = df_analise_estoque["valor_total_imobilizado"].sum()
    df_produtos_em_ruptura = df_analise_estoque[
        df_analise_estoque["estoque_atual_numerico"] <= df_analise_estoque["estoque_minimo_numerico"]]
    quantidade_itens_ruptura = len(df_produtos_em_ruptura)

    coluna_estoque_1, coluna_estoque_2 = st.columns(2)
    coluna_estoque_1.metric("Capital Imobilizado", f"R$ {montante_total_imobilizado:,.2f}")
    coluna_estoque_2.metric(
        "Alertas de Reposição Necessária",
        f"{quantidade_itens_ruptura} itens",
        delta=f"{quantidade_itens_ruptura} críticos",
        delta_color="inverse"
    )

    if not df_produtos_em_ruptura.empty:
        st.error("🚨 Atenção: Identificamos produtos abaixo da margem de segurança do estoque mínimo!")
        st.dataframe(
            df_produtos_em_ruptura[["codigo", "descricao_padrao", "estoque_atual_numerico", "estoque_minimo_numerico"]],
            use_container_width=True,
            hide_index=True
        )

    with st.container(border=True):
        grafico_matriz_estoque = px.scatter(
            df_analise_estoque,
            x="custo_numerico",
            y="valor_total_imobilizado",
            size="estoque_atual_numerico",
            color="categoria",
            hover_name="descricao_padrao",
            title="Matriz de Avaliação do Estoque"
        )
        st.plotly_chart(grafico_matriz_estoque, use_container_width=True)

# ----------------------------------------------------------------------------------------------------------------------
# ABA 4 — SAÚDE FINANCEIRA
# ----------------------------------------------------------------------------------------------------------------------
with aba_financeiro:
    st.subheader("Fluxo de Caixa e Custos Operacionais")

    despesas_totais_periodo = df_despesas_filtrado["valor_numerico"].sum()
    saldo_operacional_periodo = faturamento_total_periodo - despesas_totais_periodo

    with st.container(border=True):
        coluna_fin_1, coluna_fin_2, coluna_fin_3 = st.columns(3)
        coluna_fin_1.metric("Total de Entradas (Vendas)", f"R$ {faturamento_total_periodo:,.2f}")
        coluna_fin_2.metric("Total de Saídas (Despesas)", f"R$ {despesas_totais_periodo:,.2f}")
        coluna_fin_3.metric(
            "Saldo Operacional (EBITDA Aproximado)",
            f"R$ {saldo_operacional_periodo:,.2f}",
            delta="Positivo" if saldo_operacional_periodo > 0 else "Negativo"
        )

    with st.container(border=True):
        # Agrupamento diário para o gráfico de fluxo de caixa
        df_entradas_diarias = (
            df_vendas_filtrado.groupby(df_vendas_filtrado["data_formatada"].dt.date)["valor_total_numerico"]
            .sum()
            .reset_index(name="valor_transacionado")
        )
        df_entradas_diarias["natureza_movimentacao"] = "Entrada"

        df_saidas_diarias = (
            df_despesas_filtrado.groupby(df_despesas_filtrado["data_formatada"].dt.date)["valor_numerico"]
            .sum()
            .reset_index(name="valor_transacionado")
        )
        df_saidas_diarias["natureza_movimentacao"] = "Saída"

        df_fluxo_caixa_diario = pd.concat([df_entradas_diarias, df_saidas_diarias])

        grafico_fluxo_diario = px.line(
            df_fluxo_caixa_diario,
            x="data_formatada",
            y="valor_transacionado",
            color="natureza_movimentacao",
            title="Evolução Diária do Caixa"
        )
        st.plotly_chart(grafico_fluxo_diario, use_container_width=True)

    with st.container(border=True):
        df_ranking_despesas = (
            df_despesas_filtrado.groupby("categoria_padronizada")["valor_numerico"]
            .sum()
            .reset_index()
            .sort_values("valor_numerico")
        )
        grafico_ranking_despesas = px.bar(
            df_ranking_despesas,
            x="valor_numerico",
            y="categoria_padronizada",
            orientation="h",
            title="Maiores Centros de Custo (Curva ABC de Despesas)",
            color_discrete_sequence=["#d62728"]
        )
        st.plotly_chart(grafico_ranking_despesas, use_container_width=True)