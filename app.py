#%%
#v0.1.3
import os
import re
import unicodedata

import pandas as pd
import streamlit as st
import plotly.express as px  # FIX 1: era 'plotly_express' (módulo inexistente)

# ======================================================================================================================
# CONFIGURAÇÃO DA PÁGINA
# ======================================================================================================================

st.set_page_config(layout="wide", page_icon="📈", page_title="Distribuidor Prata Viva Ltda")
st.title("Vistto ETL - Dashboard de Performance")

# ======================================================================================================================
# CONFIGURAÇÃO DE CAMINHOS
# FIX 2: caminhos absolutos. Em produção (Streamlit Cloud), __file__ resolve para o diretório do script.
# Em desenvolvimento local, troque BASE_DIR por r"C:\Users\andre\Documentos\Workspace\prata-viva"
# ======================================================================================================================

try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE_DIR = os.getcwd()

CAMINHO_VENDAS   = os.path.join(BASE_DIR, "vendas.csv")
CAMINHO_CLIENTES = os.path.join(BASE_DIR, "clientes.csv")
CAMINHO_DESPESAS = os.path.join(BASE_DIR, "despesas.csv")
CAMINHO_PRODUTOS = os.path.join(BASE_DIR, "produtos.csv")

# ======================================================================================================================
# DICIONÁRIOS DE PADRONIZAÇÃO
# ======================================================================================================================

# Mapa de variações de nome de produto → nome padrão (igual a descricao_padrao em produtos.csv, sem acento)
# Por que aqui e não no código: facilita manutenção quando o cliente manda novos dados com novas variações
MAPA_NOMES_PRODUTO = {
    "deterg. neutro 500ml"  : "detergente neutro 500ml",
    "agua sanitaria 1 litro": "agua sanitaria 1l",
    "agua sanitaria 1l"     : "agua sanitaria 1l",
    "sabao em po 1kg"       : "sabao em po 1kg",
    "sabao po 1kg"          : "sabao em po 1kg",
    "luva borracha m"       : "luva de borracha m",
    "luva borracha media"   : "luva de borracha m",
    "luva de borracha m"    : "luva de borracha m",
    "desinfetante pinho 500ml": "desinfetante pinho 500ml",
    "esponja de aco c/8"    : "esponja de aco c/8",
    "esponja dupla face"    : "esponja dupla face",
    "pano de chao 60x80"    : "pano de chao 60x80",
}

# Mapa de variações de categoria de despesa → nome padronizado
# Problema original: 'fornecedor', 'fornecedores', 'compras', 'compra' geravam 4 barras separadas no gráfico
MAPA_CATEGORIAS_DESPESA = {
    "fornecedor"      : "compras (mercadoria)",
    "fornecedores"    : "compras (mercadoria)",
    "compras"         : "compras (mercadoria)",
    "compra"          : "compras (mercadoria)",
    "salario"         : "salarios",
    "salarios"        : "salarios",
    "energia"         : "energia eletrica",
    "energia eletrica": "energia eletrica",
    "aluguel"         : "aluguel",
    "devolucao"       : "devolucao / ajuste",
    "contabilidade"   : "contabilidade",
    "transporte"      : "transporte",
    "manutencao"      : "manutencao",
    "marketing"       : "marketing",
    "impostos"        : "impostos",
}

# ======================================================================================================================
# FUNÇÕES UTILITÁRIAS
# ======================================================================================================================

def ler_csv_seguro(caminho: str, dtype: dict) -> pd.DataFrame:
    """
    Lê CSV tentando UTF-8 primeiro, com fallback para latin-1.
    Regra 3: dtype obrigatório. Regra 4: encoding com fallback.
    """
    try:
        return pd.read_csv(caminho, dtype=dtype, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(caminho, dtype=dtype, encoding="latin-1")


def limpar_moeda(val) -> float:
    """
    Converte representações monetárias brasileiras para float.
    Cobre: 'R$ 3,50' → 3.5 | '12,90' → 12.9 | '-R$ 480,00' → -480.0 | 150 → 150.0
    Retorna 0.0 para valores vazios ou não parseáveis.
    Regra 5: valores monetários limpos antes de qualquer conversão.
    """
    if pd.isna(val) or val == "":
        return 0.0
    val_str = str(val)
    # Mantém dígitos, vírgula, ponto e sinal de negativo
    numeros = re.sub(r"[^\d,\.\-]", "", val_str)
    if not numeros or numeros in ("-", ".", ","):
        return 0.0
    # Troca vírgula decimal por ponto
    numeros = numeros.replace(",", ".")
    # Mais de um ponto = separadores de milhar antes do último
    if numeros.count(".") > 1:
        partes = numeros.split(".")
        numeros = "".join(partes[:-1]) + "." + partes[-1]
    try:
        return float(numeros)
    except ValueError:
        return 0.0


def remover_acentos(texto: str) -> str:
    """
    Remove acentos para comparações seguras entre tabelas.
    Ex.: 'Sabão em Pó' → 'Sabao em Po'
    """
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def normalizar_nome_produto(serie: pd.Series) -> pd.Series:
    """
    Normaliza nomes de produto para viabilizar o join com produtos.csv:
    1. Lowercase + strip
    2. Remove acentos
    3. Consulta MAPA_NOMES_PRODUTO para resolver abreviações e variantes
    """
    base = serie.astype(str).str.lower().str.strip().apply(remover_acentos)
    return base.map(lambda x: MAPA_NOMES_PRODUTO.get(x, x))


def normalizar_texto(serie: pd.Series) -> pd.Series:
    """Lowercase + strip + sem acentos. Uso geral em colunas categóricas."""
    return serie.astype(str).str.lower().str.strip().apply(remover_acentos)


# ======================================================================================================================
# EXTRAÇÃO — LEITURA DOS CSVs
# FIX 3: dtype definido para todas as colunas em todas as tabelas (Regra 3)
# ======================================================================================================================

@st.cache_data
def carregar_dados_brutos() -> dict:
    # Colunas monetárias e datas chegam como str — serão convertidas no ETL
    dtype_vendas = {
        "id_venda": str, "produto": str, "categoria": str,
        "quantidade": str, "valor_unitario": str, "valor_total": str,
        "forma_pagamento": str, "id_cliente": str,
    }
    dtype_clientes = {
        "id_cliente": str, "razao_social": str, "contato": str,
        "telefone": str, "email": str, "cidade": str,
        "segmento": str, "canal_origem": str,
    }
    dtype_despesas = {
        "id_despesa": str, "categoria": str, "descricao": str,
        "fornecedor": str, "valor": str, "forma_pagamento": str,
    }
    dtype_produtos = {
        "codigo": str, "descricao_padrao": str, "categoria": str,
        "custo_unitario": str, "preco_venda": str, "margem_percentual": str,
        "estoque_atual": str, "estoque_minimo": str,
        "unidade": str, "fornecedor_principal": str,
    }
    return {
        "vendas"  : ler_csv_seguro(CAMINHO_VENDAS,   dtype_vendas),
        "clientes": ler_csv_seguro(CAMINHO_CLIENTES, dtype_clientes),
        "despesas": ler_csv_seguro(CAMINHO_DESPESAS, dtype_despesas),
        "produtos": ler_csv_seguro(CAMINHO_PRODUTOS, dtype_produtos),
    }


dados_brutos = carregar_dados_brutos()


# ======================================================================================================================
# TRANSFORMAÇÃO — ETL COMPLETO
# ======================================================================================================================

@st.cache_data
def transformar_dados(colecao: dict):
    """
    Retorna: df_vendas, df_clientes, df_despesas, df_produtos, auditoria
    Regra 7: cada coluna com política explícita de nulos — sem fillna() genérico.
    Regra 8: auditoria completa ao final.
    """
    auditoria = {}

    # ------------------------------------------------------------------------------------------------------------------
    # VENDAS
    # ------------------------------------------------------------------------------------------------------------------
    df_v = colecao["vendas"].copy()
    auditoria["vendas_entrada"] = len(df_v)

    # FIX 4: remoção de duplicatas antes de qualquer transformação
    n_antes_dup = len(df_v)
    df_v = df_v.drop_duplicates(
        subset=["data", "produto", "quantidade", "valor_total", "id_cliente"]
    )
    auditoria["vendas_duplicatas_removidas"] = n_antes_dup - len(df_v)

    # Regra 6: datas parseadas com tolerância a formatos mistos (BR e ISO)
    df_v["data"] = pd.to_datetime(df_v["data"], dayfirst=True, errors="coerce")
    auditoria["vendas_datas_invalidas"] = int(df_v["data"].isna().sum())

    # Quantidade: numérico com política explícita para NaN → 0
    df_v["quantidade"] = pd.to_numeric(df_v["quantidade"], errors="coerce").fillna(0).astype(int)

    # Regra 5: monetários limpos antes de qualquer operação numérica
    df_v["valor_unitario_num"] = df_v["valor_unitario"].apply(limpar_moeda)
    df_v["valor_total_num"]    = df_v["valor_total"].apply(limpar_moeda)

    # Política explícita: remover linhas com valor zero (registros incompletos ou cancelamentos)
    n_antes_zero = len(df_v)
    df_v = df_v[df_v["valor_total_num"] > 0].copy()
    auditoria["vendas_valor_zero_removidas"] = n_antes_zero - len(df_v)

    # Normalização para join com produtos
    df_v["produto_norm"] = normalizar_nome_produto(df_v["produto"])

    # ------------------------------------------------------------------------------------------------------------------
    # PRODUTOS
    # ------------------------------------------------------------------------------------------------------------------
    df_p = colecao["produtos"].copy()

    df_p["custo_num"]  = df_p["custo_unitario"].apply(limpar_moeda)
    df_p["preco_num"]  = df_p["preco_venda"].apply(limpar_moeda)
    df_p["margem_num"] = df_p["margem_percentual"].apply(limpar_moeda)

    # Estoque: política explícita — registrar negativos ANTES de corrigir (não silenciar)
    df_p["estoque_atual"]  = pd.to_numeric(df_p["estoque_atual"],  errors="coerce").fillna(0)
    df_p["estoque_minimo"] = pd.to_numeric(df_p["estoque_minimo"], errors="coerce").fillna(0)
    auditoria["produtos_estoque_negativo"] = int((df_p["estoque_atual"] < 0).sum())
    df_p["estoque_atual"]  = df_p["estoque_atual"].abs()
    df_p["estoque_minimo"] = df_p["estoque_minimo"].abs()

    # Política para custo zero: limpar_moeda retorna 0.0 quando o campo é vazio
    auditoria["produtos_sem_custo"] = int((df_p["custo_num"] == 0).sum())

    df_p["produto_norm"] = normalizar_nome_produto(df_p["descricao_padrao"])
    df_p = df_p.sort_values("margem_num", ascending=False)

    # ------------------------------------------------------------------------------------------------------------------
    # CLIENTES
    # ------------------------------------------------------------------------------------------------------------------
    df_c = colecao["clientes"].copy()
    auditoria["clientes_entrada"] = len(df_c)

    df_c["data_cadastro"] = pd.to_datetime(df_c["data_cadastro"], dayfirst=True, errors="coerce")
    df_c["canal_origem"]  = normalizar_texto(df_c["canal_origem"])
    df_c["segmento"]      = normalizar_texto(df_c["segmento"])

    # FIX 5: deduplicação de clientes — C001 e C011 são o mesmo (Mercadinho Bom Preço)
    # Política: deduplicar por email quando disponível, depois por telefone normalizado
    n_antes_dup_c = len(df_c)
    df_c["tel_norm"] = df_c["telefone"].astype(str).str.replace(r"\D", "", regex=True)
    df_c_com_email  = df_c[df_c["email"].notna() & (df_c["email"].str.strip() != "")].drop_duplicates(subset=["email"])
    df_c_sem_email  = df_c[df_c["email"].isna() | (df_c["email"].str.strip() == "")].drop_duplicates(subset=["tel_norm"])
    df_c = (
        pd.concat([df_c_com_email, df_c_sem_email])
        .drop_duplicates(subset=["id_cliente"])
        .reset_index(drop=True)
    )
    auditoria["clientes_duplicatas_removidas"] = n_antes_dup_c - len(df_c)

    # ------------------------------------------------------------------------------------------------------------------
    # DESPESAS
    # ------------------------------------------------------------------------------------------------------------------
    df_d = colecao["despesas"].copy()

    df_d["data"]      = pd.to_datetime(df_d["data"], dayfirst=True, errors="coerce")
    df_d["valor_num"] = df_d["valor"].apply(limpar_moeda)

    # FIX 6: padronização de categorias com mapa de-para
    # Problema original: 'fornecedor'/'fornecedores'/'compras'/'compra' = 4 barras para a mesma coisa
    df_d["categoria_raw"] = normalizar_texto(df_d["categoria"]).replace("", "sem categoria")
    df_d["categoria"]     = df_d["categoria_raw"].map(
        lambda x: MAPA_CATEGORIAS_DESPESA.get(x, x)
    )
    cats_nao_mapeadas = df_d.loc[
        ~df_d["categoria_raw"].isin(MAPA_CATEGORIAS_DESPESA), "categoria_raw"
    ].unique().tolist()
    auditoria["despesas_categorias_nao_mapeadas"] = cats_nao_mapeadas

    # ------------------------------------------------------------------------------------------------------------------
    # JOINS
    # ------------------------------------------------------------------------------------------------------------------

    # Vendas ↔ Produtos
    df_v = df_v.merge(
        df_p[["produto_norm", "custo_num", "categoria", "codigo"]],
        on="produto_norm", how="left", suffixes=("", "_prod"),
    )
    # FIX 7: custo NaN após join = produto não encontrado no cadastro → política explícita: NaN preservado
    # NÃO usar fillna(0) — zeraria o custo e inflaria o lucro bruto silenciosamente
    n_sem_join = int(df_v["custo_num"].isna().sum())
    auditoria["vendas_sem_join_produto"] = n_sem_join

    # Vendas ↔ Clientes
    df_v = df_v.merge(
        df_c[["id_cliente", "canal_origem", "cidade"]],
        on="id_cliente", how="left",
    )

    # Custo e lucro: NaN propagado onde custo não foi encontrado (comportamento correto)
    df_v["custo_total_venda"] = df_v["quantidade"] * df_v["custo_num"]
    df_v["lucro_bruto_venda"] = df_v["valor_total_num"] - df_v["custo_total_venda"]

    auditoria["vendas_saida"] = len(df_v)

    # ------------------------------------------------------------------------------------------------------------------
    # AUDITORIA FINAL — Regra 8
    # ------------------------------------------------------------------------------------------------------------------
    auditoria["resumo_linhas"] = {
        "Vendas"  : (
            f"{auditoria['vendas_entrada']} registros de entrada | "
            f"{auditoria['vendas_duplicatas_removidas']} duplicatas removidas | "
            f"{auditoria['vendas_datas_invalidas']} datas inválidas (NaT) | "
            f"{auditoria['vendas_valor_zero_removidas']} com valor zero removidas | "
            f"{auditoria['vendas_sem_join_produto']} sem custo no cadastro de produtos"
        ),
        "Clientes": (
            f"{auditoria['clientes_entrada']} registros de entrada | "
            f"{auditoria['clientes_duplicatas_removidas']} duplicatas removidas"
        ),
        "Produtos": (
            f"{auditoria['produtos_sem_custo']} sem custo cadastrado | "
            f"{auditoria['produtos_estoque_negativo']} com estoque negativo (corrigido para positivo)"
        ),
        "Despesas": (
            f"Categorias não mapeadas: {auditoria['despesas_categorias_nao_mapeadas'] or 'nenhuma'}"
        ),
    }

    return df_v, df_c, df_d, df_p, auditoria


df_vendas, df_clientes, df_despesas, df_produtos, auditoria_etl = transformar_dados(dados_brutos)


# ======================================================================================================================
# ALERTA DE QUALIDADE DOS DADOS (fixado no topo, antes das abas)
# Regra 8: o resumo da auditoria precisa ser visível, não escondido num log
# ======================================================================================================================

n_problemas = (
    auditoria_etl["vendas_duplicatas_removidas"]
    + auditoria_etl["vendas_datas_invalidas"]
    + auditoria_etl["vendas_sem_join_produto"]
    + auditoria_etl["produtos_sem_custo"]
)

if n_problemas > 0:
    with st.expander(f"⚠️ Auditoria ETL — {n_problemas} ocorrências detectadas nos dados", expanded=False):
        for tabela, msg in auditoria_etl["resumo_linhas"].items():
            st.markdown(f"**{tabela}:** {msg}")
        if auditoria_etl["vendas_sem_join_produto"] > 0:
            st.warning(
                "Atenção: linhas sem custo de produto não entram no cálculo de Lucro Bruto. "
                "Verifique se todos os produtos de vendas.csv estão cadastrados em produtos.csv."
            )


# ======================================================================================================================
# CARGA / DASHBOARD — 4 ABAS
# ======================================================================================================================

aba1, aba2, aba3, aba4 = st.tabs([
    "📊 Visão Executiva",
    "🎯 Performance e Vistto",
    "📦 Inteligência de Estoque",
    "💸 Saúde Financeira",
])


# ----------------------------------------------------------------------------------------------------------------------
# ABA 1 — VISÃO EXECUTIVA
# ----------------------------------------------------------------------------------------------------------------------
with aba1:
    st.header("Visão Executiva do Negócio")

    col1, col2, col3 = st.columns(3)

    qtd_vendas         = len(df_vendas)
    faturamento_total  = df_vendas["valor_total_num"].sum()
    ticket_medio       = faturamento_total / qtd_vendas if qtd_vendas > 0 else 0

    col1.metric("Qtd. Vendas (Total Histórico)", f"{qtd_vendas}")
    col2.metric("Faturamento Total (Histórico)", f"R$ {faturamento_total:,.2f}")
    col3.metric("Ticket Médio (Histórico)",      f"R$ {ticket_medio:,.2f}")

    st.markdown("---")

    # FIX 8: Aba 1 usava barras VERTICAIS — regra de visualização exige barras HORIZONTAIS
    df_cat = (
        df_vendas.groupby("categoria", as_index=False)["valor_total_num"]
        .sum()
        .sort_values("valor_total_num", ascending=True)  # crescente → a maior fica no topo
    )

    fig_cat = px.bar(
        df_cat,
        x="valor_total_num",
        y="categoria",
        orientation="h",           # horizontal obrigatório
        text_auto=True,
        labels={"valor_total_num": "Faturamento (R$)", "categoria": ""},
        color_discrete_sequence=["#1f77b4"],
    )
    fig_cat.update_layout(
        title="Faturamento por Categoria (Visão Geral)",
        title_x=0.5,
        title_font=dict(size=20),
        xaxis_title="",
        yaxis_title="",
    )
    st.plotly_chart(fig_cat, use_container_width=True)


# ----------------------------------------------------------------------------------------------------------------------
# ABA 2 — PERFORMANCE E VISTTO (CAC + LTV adicionados)
# ----------------------------------------------------------------------------------------------------------------------
with aba2:
    st.header("Performance de Vendas e Marketing")
    st.markdown("Análise de eficiência de aquisição de clientes e rentabilidade da operação.")

    # Cálculo de CAC
    despesas_mkt  = df_despesas[df_despesas["categoria"] == "marketing"]["valor_num"].sum()
    novos_clientes = len(df_clientes)
    cac_geral      = despesas_mkt / novos_clientes if novos_clientes > 0 else 0

    # Cálculo de Lucro Bruto (apenas linhas com custo conhecido)
    lucro_bruto_total = df_vendas["lucro_bruto_venda"].dropna().sum()

    # FIX 9: LTV calculado — ausente na versão original
    # LTV estimado = faturamento total / clientes únicos com compra
    # É uma estimativa de receita por cliente; com mais histórico, refinar por cohort
    clientes_com_compra = df_vendas["id_cliente"].nunique()
    ltv_estimado = faturamento_total / clientes_com_compra if clientes_com_compra > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Investimento em Marketing",    f"R$ {despesas_mkt:,.2f}")
    col2.metric(
        "CAC (Custo por Cliente)",              f"R$ {cac_geral:,.2f}",
        help="Investimento em marketing dividido pelo total de clientes cadastrados."
    )
    col3.metric(
        "LTV Estimado (por cliente)",           f"R$ {ltv_estimado:,.2f}",
        help="Faturamento total ÷ clientes únicos com compra. Estimativa — refinar com histórico maior."
    )
    col4.metric(
        "Lucro Bruto (Vendas − Custo Mercadoria)", f"R$ {lucro_bruto_total:,.2f}",
        help="Calculado apenas para produtos com custo cadastrado. Itens sem custo foram excluídos."
    )

    st.markdown("---")

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        df_canal = (
            df_vendas.groupby("canal_origem", as_index=False)["valor_total_num"]
            .sum()
            .sort_values("valor_total_num", ascending=True)
        )
        fig_canal = px.bar(
            df_canal,
            x="valor_total_num", y="canal_origem",
            orientation="h", text_auto=True,
            title="Faturamento por Canal de Aquisição",
            labels={"valor_total_num": "Faturamento (R$)", "canal_origem": "Canal"},
            color_discrete_sequence=["#2ca02c"],
        )
        fig_canal.update_layout(
            xaxis_title="", yaxis_title="", title_x=0.5,
        )
        st.plotly_chart(fig_canal, use_container_width=True)

    with col_g2:
        df_vc = df_vendas.merge(
            df_clientes[["id_cliente", "segmento"]], on="id_cliente", how="left"
        )
        df_ticket_seg = (
            df_vc.groupby("segmento")
            .agg(faturamento=("valor_total_num", "sum"), qtd_vendas=("id_venda", "nunique"))
            .reset_index()
        )
        df_ticket_seg["ticket_medio"] = (
            df_ticket_seg["faturamento"] / df_ticket_seg["qtd_vendas"].replace(0, 1)
        )
        df_ticket_seg = df_ticket_seg.sort_values("ticket_medio", ascending=True)

        fig_ticket = px.bar(
            df_ticket_seg,
            x="ticket_medio", y="segmento",
            orientation="h", text_auto=True,
            title="Ticket Médio por Segmento",
            labels={"ticket_medio": "Ticket Médio (R$)", "segmento": "Segmento"},
            color_discrete_sequence=["#ff7f0e"],
        )
        fig_ticket.update_layout(
            xaxis_title="", yaxis_title="", title_x=0.5,
        )
        st.plotly_chart(fig_ticket, use_container_width=True)


# ----------------------------------------------------------------------------------------------------------------------
# ABA 3 — INTELIGÊNCIA DE ESTOQUE
# ----------------------------------------------------------------------------------------------------------------------
with aba3:
    st.header("Gestão e Alertas de Estoque")
    st.markdown("Monitoramento de inventário, alertas de reposição e análise de capital imobilizado.")

    df_produtos["valor_imobilizado"] = df_produtos["estoque_atual"] * df_produtos["custo_num"]
    capital_imobilizado = df_produtos["valor_imobilizado"].sum()

    df_ruptura      = df_produtos[df_produtos["estoque_atual"] <= df_produtos["estoque_minimo"]]
    qtd_ruptura     = len(df_ruptura)

    col_e1, col_e2 = st.columns(2)
    col_e1.metric(
        "Capital Imobilizado em Estoque", f"R$ {capital_imobilizado:,.2f}",
        help="Custo total de todas as mercadorias armazenadas."
    )
    col_e2.metric(
        "Alertas de Reposição (Ruptura)", f"{qtd_ruptura} itens",
        delta="- Ação Necessária" if qtd_ruptura > 0 else "Estoque Seguro",
        delta_color="inverse" if qtd_ruptura > 0 else "normal",
    )

    st.markdown("---")

    if qtd_ruptura > 0:
        st.error(
            f"🚨 **Atenção:** {qtd_ruptura} produto(s) no estoque mínimo ou abaixo. "
            "Emita pedido de compra para os fornecedores abaixo."
        )
        tabela_ruptura = df_ruptura[[
            "codigo", "descricao_padrao", "fornecedor_principal",
            "estoque_atual", "estoque_minimo", "custo_num",
        ]].copy()
        tabela_ruptura.columns = [
            "Cód.", "Produto", "Fornecedor",
            "Estoque Atual", "Mínimo Permitido", "Custo Ref. (R$)",
        ]
        st.dataframe(tabela_ruptura, use_container_width=True, hide_index=True)
    else:
        st.success("✅ **Estoque saudável!** Nenhum produto abaixo da margem de segurança.")

    st.markdown("---")
    st.subheader("Matriz de Estoque: Capital Imobilizado vs. Margem de Lucro")

    fig_matriz = px.scatter(
        df_produtos,
        x="margem_num",
        y="valor_imobilizado",
        size="estoque_atual",
        color="categoria",
        hover_name="descricao_padrao",
        title="Onde está o dinheiro do estoque? (Tamanho = Qtd. Armazenada)",
        labels={
            "margem_num"       : "Margem de Lucro (%)",
            "valor_imobilizado": "Capital Imobilizado (R$)",
            "categoria"        : "Categoria",
            "estoque_atual"    : "Qtd. em Estoque",
        },
        size_max=40,
    )
    fig_matriz.update_layout(
        title_x=0.5,
    )
    st.plotly_chart(fig_matriz, use_container_width=True)


# ----------------------------------------------------------------------------------------------------------------------
# ABA 4 — SAÚDE FINANCEIRA E FLUXO DE CAIXA
# ----------------------------------------------------------------------------------------------------------------------
with aba4:
    # Prepara coluna Mês/Ano antes do layout
    df_vendas["mes_ano"]   = df_vendas["data"].dt.strftime("%m/%Y")
    df_despesas["mes_ano"] = df_despesas["data"].dt.strftime("%m/%Y")

    meses_disponiveis = sorted(list(
        set(df_vendas["mes_ano"].dropna().unique()) |
        set(df_despesas["mes_ano"].dropna().unique())
    ))
    opcoes_filtro = ["Visão Geral (Todos os Meses)"] + meses_disponiveis

    col_titulo, col_filtro = st.columns([7, 3])

    with col_filtro:
        mes_selecionado = st.selectbox("Selecione o Período", opcoes_filtro, index=0)

    with col_titulo:
        titulo_periodo = (
            "Panorama Histórico"
            if mes_selecionado == "Visão Geral (Todos os Meses)"
            else mes_selecionado
        )
        st.header(f"Saúde Financeira ({titulo_periodo})")
        st.markdown("Acompanhamento de entradas, saídas e custos operacionais no período.")

    st.markdown("---")

    # Filtro condicional
    if mes_selecionado != "Visão Geral (Todos os Meses)":
        df_v_f = df_vendas[df_vendas["mes_ano"] == mes_selecionado]
        df_d_f = df_despesas[df_despesas["mes_ano"] == mes_selecionado]
    else:
        df_v_f = df_vendas
        df_d_f = df_despesas

    faturamento_periodo = df_v_f["valor_total_num"].sum()
    despesas_periodo    = df_d_f["valor_num"].sum()
    saldo_operacional   = faturamento_periodo - despesas_periodo

    col_f1, col_f2, col_f3 = st.columns(3)
    col_f1.metric("Faturamento", f"R$ {faturamento_periodo:,.2f}")
    col_f2.metric("Despesas",    f"R$ {despesas_periodo:,.2f}")
    col_f3.metric(
        "Resultado",             f"R$ {saldo_operacional:,.2f}",
        delta="Lucro" if saldo_operacional >= 0 else "Déficit",
        delta_color="normal" if saldo_operacional >= 0 else "inverse",
    )

    st.markdown("---")

    # Fluxo diário
    df_entradas = df_v_f.groupby("data", as_index=False)["valor_total_num"].sum()
    df_entradas["Tipo"] = "Entrada (Vendas)"
    df_entradas.rename(columns={"valor_total_num": "Valor (R$)"}, inplace=True)

    df_saidas = df_d_f.groupby("data", as_index=False)["valor_num"].sum()
    df_saidas["Tipo"] = "Saída (Despesas)"
    df_saidas.rename(columns={"valor_num": "Valor (R$)"}, inplace=True)

    df_fluxo = pd.concat([df_entradas, df_saidas]).sort_values("data")

    col_fluxo, col_desp = st.columns([7, 3])

    with col_fluxo:
        st.subheader("Movimentação Diária")
        df_fluxo_plot = df_fluxo.dropna(subset=["data"])

        if not df_fluxo_plot.empty:
            fig_fluxo = px.bar(
                df_fluxo_plot,
                x="data", y="Valor (R$)",
                color="Tipo", barmode="group",
                color_discrete_map={
                    "Entrada (Vendas)": "#2ca02c",
                    "Saída (Despesas)": "#d62728",
                },
                labels={"data": ""},
            )
            fig_fluxo.update_layout(
                xaxis=dict(tickformat="%d/%m\n%Y"),
                legend_title_text="",
            )
            st.plotly_chart(fig_fluxo, use_container_width=True)
        else:
            st.info("Não há movimentações financeiras registradas neste período.")

    with col_desp:
        st.subheader("Ranking de Custos")
        df_rank = (
            df_d_f.groupby("categoria", as_index=False)["valor_num"]
            .sum()
            .query("valor_num > 0")
            .sort_values("valor_num", ascending=True)
        )

        if not df_rank.empty:
            fig_rank = px.bar(
                df_rank,
                x="valor_num", y="categoria",
                orientation="h", text_auto=True,
                color_discrete_sequence=["#d62728"],
                labels={"valor_num": "Valor (R$)", "categoria": ""},
            )
            fig_rank.update_layout(
                xaxis_title="", yaxis_title="",
                xaxis=dict(showticklabels=False),
            )
            st.plotly_chart(fig_rank, use_container_width=True)
        else:
            st.info("Não há despesas lançadas neste período.")