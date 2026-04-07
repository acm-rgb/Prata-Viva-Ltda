import pandas as pd
import streamlit as st
import plotly_express as px
import re

# =====================================================================================================================
# CONFIGURAÇÃO DA PÁGINA
# =====================================================================================================================

st.set_page_config(layout="wide", page_icon='📈', page_title='Distribuidor Prata Viva Ltda')
st.title('Vistto ETL - Dashboard de Performance', anchor='center')


# =====================================================================================================================
# EXTRAÇÃO E TRANSFORMAÇÃO (O MOTOR DE DADOS)
# =====================================================================================================================

@st.cache_data
def carregar_dados_completos():
    colecao = {
        "vendas": pd.read_csv('vendas.csv'),
        "clientes": pd.read_csv('clientes.csv'),
        "despesas": pd.read_csv('despesas.csv'),
        "produtos": pd.read_csv('produtos.csv')
    }
    return colecao


dados_brutos = carregar_dados_completos()


def limpar_moeda_robusto(val):
    if pd.isna(val) or val == '': return 0.0
    val_str = str(val)
    numeros = re.sub(r'[^\d,\-]', '', val_str)
    if not numeros: return 0.0
    numeros = numeros.replace(',', '.')
    if numeros.count('.') > 1:
        partes = numeros.split('.')
        numeros = "".join(partes[:-1]) + "." + partes[-1]
    try:
        return float(numeros)
    except:
        return 0.0


def normalizar_texto(serie):
    return serie.astype(str).str.lower().str.strip()


@st.cache_data
def transformar_dados(colecao_bruta):
    df_vendas = colecao_bruta['vendas'].copy()
    df_clientes = colecao_bruta['clientes'].copy()
    df_despesas = colecao_bruta['despesas'].copy()
    df_produtos = colecao_bruta['produtos'].copy()

    # 1. Tratamento de Datas
    df_vendas['data'] = pd.to_datetime(df_vendas['data'], dayfirst=True, errors='coerce')
    df_despesas['data'] = pd.to_datetime(df_despesas['data'], dayfirst=True, errors='coerce')
    df_clientes['data_cadastro'] = pd.to_datetime(df_clientes['data_cadastro'], dayfirst=True, errors='coerce')

    # 2. Tratamento de Valores
    df_vendas['valor_unitario_num'] = df_vendas['valor_unitario'].apply(limpar_moeda_robusto)
    df_vendas['valor_total_num'] = df_vendas['valor_total'].apply(limpar_moeda_robusto)
    df_despesas['valor_num'] = df_despesas['valor'].apply(limpar_moeda_robusto)
    df_produtos['custo_num'] = df_produtos['custo_unitario'].apply(limpar_moeda_robusto)
    df_produtos['preco_num'] = df_produtos['preco_venda'].apply(limpar_moeda_robusto)
    df_produtos['margem_num'] = df_produtos['margem_percentual'].apply(limpar_moeda_robusto)

    # Tratamento absoluto do estoque (corrige números negativos)
    df_produtos['estoque_atual'] = df_produtos['estoque_atual'].abs()
    df_produtos['estoque_minimo'] = df_produtos['estoque_minimo'].abs()

    # 3. Normalização
    df_vendas['produto_norm'] = normalizar_texto(df_vendas['produto'])
    df_produtos['produto_norm'] = normalizar_texto(df_produtos['descricao_padrao'])
    df_clientes['canal_origem'] = normalizar_texto(df_clientes['canal_origem'])
    df_despesas['categoria'] = normalizar_texto(df_despesas['categoria'])

    # 4. Cruzamento de Dados (Merges)
    df_vendas = df_vendas.merge(
        df_produtos[['produto_norm', 'custo_num', 'categoria', 'codigo']],
        on='produto_norm', how='left', suffixes=('', '_prod')
    )

    df_vendas = df_vendas.merge(
        df_clientes[['id_cliente', 'canal_origem', 'cidade']],
        on='id_cliente', how='left'
    )

    df_vendas['custo_total_venda'] = df_vendas['quantidade'] * df_vendas['custo_num'].fillna(0)
    df_vendas['lucro_bruto_venda'] = df_vendas['valor_total_num'] - df_vendas['custo_total_venda']
    df_produtos = df_produtos.sort_values(by='margem_num', ascending=False)

    return df_vendas, df_clientes, df_despesas, df_produtos


df_vendas_clean, df_clientes_clean, df_despesas_clean, df_produtos_clean = transformar_dados(dados_brutos)

# =====================================================================================================================
# CARGA / DASHBOARD E GRÁFICOS (ESTRUTURA DE ABAS)
# =====================================================================================================================

# Criando as 4 abas principais
aba1, aba2, aba3, aba4 = st.tabs([
    "📊 Visão Executiva",
    "🎯 Performance e Vistto",
    "📦 Inteligência de Estoque",
    "💸 Saúde Financeira"
])

# ---------------------------------------------------------------------------------------------------------------------
# ABA 1: VISÃO EXECUTIVA
# ---------------------------------------------------------------------------------------------------------------------
with aba1:
    st.header("Visão Executiva do Negócio")

    col1, col2, col3 = st.columns(3)

    # Nota: Mantido df_vendas_clean para visão histórica. Se quiser que esta aba também seja filtrada pelo mês,
    # basta trocar "df_vendas_clean" por "df_vendas_filtrado" nas próximas linhas.
    qtd_vendas_realizadas = len(df_vendas_clean)
    faturamento_total = df_vendas_clean['valor_total_num'].sum()
    ticket_medio = faturamento_total / qtd_vendas_realizadas if qtd_vendas_realizadas > 0 else 0

    col1.metric("Qtd. Vendas (Total)", f"{qtd_vendas_realizadas}")
    col2.metric("Faturamento Total (Histórico)", f"R$ {faturamento_total:,.2f}")
    col3.metric("Ticket Médio (Histórico)", f"R$ {ticket_medio:,.2f}")

    st.markdown("---")

    df_agrupado_categoria = df_vendas_clean.groupby('categoria', as_index=False)['valor_total_num'].sum()

    vendas_por_categoria = px.bar(
        df_agrupado_categoria,
        x='categoria',
        y='valor_total_num',
        text_auto=True,
        labels={'categoria': 'Categoria', 'valor_total_num': 'Valor Total (R$)'},
        color_discrete_sequence=['#1f77b4']
    )

    vendas_por_categoria.update_layout(
        title='Faturamento por Categoria (Visão Geral)',
        title_x=0.5,
        title_font=dict(size=20),
        xaxis_title="",
        yaxis_title=""
    )
    st.plotly_chart(vendas_por_categoria, use_container_width=True)

# ---------------------------------------------------------------------------------------------------------------------
# ABA 2: PERFORMANCE E VISTTO
# ---------------------------------------------------------------------------------------------------------------------
with aba2:
    st.header("Performance de Vendas e Marketing")
    st.markdown("Análise de eficiência de aquisição de clientes e rentabilidade da operação.")

    despesas_mkt = df_despesas_clean[df_despesas_clean['categoria'].str.contains('marketing', na=False)][
        'valor_num'].sum()
    novos_clientes = len(df_clientes_clean)
    cac_geral = despesas_mkt / novos_clientes if novos_clientes > 0 else 0
    lucro_bruto_total = df_vendas_clean['lucro_bruto_venda'].sum()

    col_mkt1, col_mkt2, col_mkt3 = st.columns(3)
    col_mkt1.metric("Investimento em Marketing (Total)", f"R$ {despesas_mkt:,.2f}")
    col_mkt2.metric("CAC Geral", f"R$ {cac_geral:,.2f}",
                    help="Custo médio gasto em marketing para trazer cada novo cliente.")
    col_mkt3.metric("Lucro Bruto (Total Vendas - Custos)", f"R$ {lucro_bruto_total:,.2f}",
                    help="O que sobra das vendas após pagar os fornecedores.")

    st.markdown("---")

    col_graf1, col_graf2 = st.columns(2)

    with col_graf1:
        df_canal = df_vendas_clean.groupby('canal_origem', as_index=False)['valor_total_num'].sum()
        df_canal = df_canal.sort_values(by='valor_total_num', ascending=True)

        fig_canal = px.bar(
            df_canal,
            x='valor_total_num',
            y='canal_origem',
            orientation='h',
            text_auto=True,
            title="Faturamento por Canal de Aquisição",
            labels={'valor_total_num': 'Faturamento (R$)', 'canal_origem': 'Canal'},
            color_discrete_sequence=['#2ca02c']
        )
        fig_canal.update_layout(xaxis_title="", yaxis_title="", title_x=0.5)
        st.plotly_chart(fig_canal, use_container_width=True)

    with col_graf2:
        df_vendas_clientes = df_vendas_clean.merge(df_clientes_clean[['id_cliente', 'segmento']], on='id_cliente',
                                                   how='left')

        df_ticket_seg = df_vendas_clientes.groupby('segmento').agg(
            faturamento=('valor_total_num', 'sum'),
            qtd_vendas=('id_venda', 'nunique')
        ).reset_index()

        df_ticket_seg['ticket_medio'] = df_ticket_seg['faturamento'] / df_ticket_seg['qtd_vendas'].replace(0, 1)
        df_ticket_seg = df_ticket_seg.sort_values(by='ticket_medio', ascending=True)

        fig_ticket = px.bar(
            df_ticket_seg,
            x='ticket_medio',
            y='segmento',
            orientation='h',
            text_auto=True,
            title="Ticket Médio por Segmento",
            labels={'ticket_medio': 'Ticket Médio (R$)', 'segmento': 'Segmento'},
            color_discrete_sequence=['#ff7f0e']
        )
        fig_ticket.update_layout(xaxis_title="", yaxis_title="", title_x=0.5)
        st.plotly_chart(fig_ticket, use_container_width=True)

# ---------------------------------------------------------------------------------------------------------------------
# ABA 3: INTELIGÊNCIA DE ESTOQUE
# ---------------------------------------------------------------------------------------------------------------------
with aba3:
    st.header("Gestão e Alertas de Estoque")
    st.markdown("Monitoramento de inventário, alertas de reposição e análise de capital imobilizado.")

    df_produtos_clean['valor_imobilizado'] = df_produtos_clean['estoque_atual'] * df_produtos_clean['custo_num']
    capital_imobilizado_total = df_produtos_clean['valor_imobilizado'].sum()

    df_ruptura = df_produtos_clean[df_produtos_clean['estoque_atual'] <= df_produtos_clean['estoque_minimo']]
    qtd_produtos_ruptura = len(df_ruptura)

    col_est1, col_est2 = st.columns(2)
    col_est1.metric("Capital Imobilizado em Estoque", f"R$ {capital_imobilizado_total:,.2f}",
                    help="Custo total de todas as mercadorias armazenadas.")

    cor_alerta = "inverse" if qtd_produtos_ruptura > 0 else "normal"
    col_est2.metric("Alertas de Reposição (Ruptura)", f"{qtd_produtos_ruptura} itens",
                    delta="- Ação Necessária" if qtd_produtos_ruptura > 0 else "Estoque Seguro", delta_color=cor_alerta)

    st.markdown("---")

    if qtd_produtos_ruptura > 0:
        st.error(
            f"🚨 **Atenção:** Você possui {qtd_produtos_ruptura} produto(s) no estoque mínimo ou abaixo dele. Emita pedido de compra junto aos fornecedores abaixo.")
        tabela_compras = df_ruptura[
            ['codigo', 'descricao_padrao', 'fornecedor_principal', 'estoque_atual', 'estoque_minimo',
             'custo_num']].copy()
        tabela_compras.columns = ['Cód.', 'Produto', 'Fornecedor', 'Estoque Atual', 'Mínimo Permitido',
                                  'Custo Ref. (R$)']
        st.dataframe(tabela_compras, use_container_width=True, hide_index=True)
    else:
        st.success("✅ **Estoque saudável!** Nenhum produto abaixo da margem de segurança no momento.")

    st.markdown("---")

    st.subheader("Matriz de Estoque: Capital Imobilizado vs. Margem de Lucro")

    fig_matriz_estoque = px.scatter(
        df_produtos_clean,
        x='margem_num',
        y='valor_imobilizado',
        size='estoque_atual',
        color='categoria',
        hover_name='descricao_padrao',
        title="Onde está o dinheiro do estoque? (Tamanho do círculo = Qtd. Armazenada)",
        labels={
            'margem_num': 'Margem de Lucro (%)',
            'valor_imobilizado': 'Capital Imobilizado (R$)',
            'categoria': 'Categoria do Produto',
            'estoque_atual': 'Qtd. em Estoque'
        },
        size_max=40
    )
    fig_matriz_estoque.update_layout(title_x=0.5)
    st.plotly_chart(fig_matriz_estoque, use_container_width=True)

# ---------------------------------------------------------------------------------------------------------------------
# ABA 4: SAÚDE FINANCEIRA E FLUXO DE CAIXA
# ---------------------------------------------------------------------------------------------------------------------
with aba4:
    # 1. LAYOUT DO TOPO (TÍTULO DE UM LADO, FILTRO DO OUTRO)
    col_titulo, col_filtro = st.columns([7, 3])

    # 2. PREPARAÇÃO DAS OPÇÕES DE DATAS (O motor do filtro agora mora aqui dentro)
    # Criamos a coluna formatada de 'Mês/Ano'
    df_vendas_clean['mes_ano'] = df_vendas_clean['data'].dt.strftime('%m/%Y')
    df_despesas_clean['mes_ano'] = df_despesas_clean['data'].dt.strftime('%m/%Y')

    # Coletamos os meses únicos
    meses_vendas = set(df_vendas_clean['mes_ano'].dropna().unique())
    meses_despesas = set(df_despesas_clean['mes_ano'].dropna().unique())
    meses_disponiveis = sorted(list(meses_vendas | meses_despesas))

    # Montamos as opções finais
    opcoes_filtro = ["Visão Geral (Todos os Meses)"] + meses_disponiveis

    with col_filtro:
        # O seletor agora é renderizado na tela principal da aba, e não mais na sidebar
        mes_selecionado = st.selectbox("Selecione o Período", opcoes_filtro, index=0)

    with col_titulo:
        titulo_periodo = "Panorama Histórico" if mes_selecionado == "Visão Geral (Todos os Meses)" else mes_selecionado
        st.header(f"Saúde Financeira ({titulo_periodo})")
        st.markdown("Acompanhamento de entradas, saídas e detalhamento dos custos operacionais no período selecionado.")

    st.markdown("---")

    # 3. APLICAÇÃO DO FILTRO (Lógica Condicional)
    if mes_selecionado != "Visão Geral (Todos os Meses)":
        df_vendas_filtrado = df_vendas_clean[df_vendas_clean['mes_ano'] == mes_selecionado]
        df_despesas_filtrado = df_despesas_clean[df_despesas_clean['mes_ano'] == mes_selecionado]
    else:
        df_vendas_filtrado = df_vendas_clean
        df_despesas_filtrado = df_despesas_clean

    # --- 4. CÁLCULOS TOTAIS DO CAIXA (FILTRADOS) ---
    faturamento_periodo = df_vendas_filtrado['valor_total_num'].sum()
    despesas_periodo = df_despesas_filtrado['valor_num'].sum()
    saldo_operacional = faturamento_periodo - despesas_periodo

    # --- 5. EXIBIÇÃO DE MÉTRICAS FINANCEIRAS ---
    col_fin1, col_fin2, col_fin3 = st.columns(3)

    col_fin1.metric("Faturamento", f"R$ {faturamento_periodo:,.2f}")
    col_fin2.metric("Despesas", f"R$ {despesas_periodo:,.2f}")

    cor_saldo = "normal" if saldo_operacional >= 0 else "inverse"
    col_fin3.metric("Resultado", f"R$ {saldo_operacional:,.2f}",
                    delta="Lucro/Geração de Caixa" if saldo_operacional >= 0 else "Déficit/Queima de Caixa",
                    delta_color=cor_saldo)

    st.markdown("---")

    # --- 6. PREPARAÇÃO DE DADOS PARA FLUXO NO TEMPO ---
    df_entradas_dia = df_vendas_filtrado.groupby('data', as_index=False)['valor_total_num'].sum()
    df_entradas_dia['Tipo Movimentacao'] = 'Entrada (Vendas)'
    df_entradas_dia.rename(columns={'valor_total_num': 'Valor (R$)'}, inplace=True)

    df_saidas_dia = df_despesas_filtrado.groupby('data', as_index=False)['valor_num'].sum()
    df_saidas_dia['Tipo Movimentacao'] = 'Saída (Despesas)'
    df_saidas_dia.rename(columns={'valor_num': 'Valor (R$)'}, inplace=True)

    df_fluxo_caixa = pd.concat([df_entradas_dia, df_saidas_dia]).sort_values(by='data')

    # --- 7. GRÁFICOS FINANCEIROS ---
    col_graf_fluxo, col_graf_desp = st.columns([7, 3])

    with col_graf_fluxo:
        st.subheader("Movimentação Diária")
        df_fluxo_caixa_plot = df_fluxo_caixa.dropna(subset=['data'])

        if not df_fluxo_caixa_plot.empty:
            fig_fluxo = px.bar(
                df_fluxo_caixa_plot,
                x='data',
                y='Valor (R$)',
                color='Tipo Movimentacao',
                barmode='group',
                color_discrete_map={'Entrada (Vendas)': '#2ca02c', 'Saída (Despesas)': '#d62728'},
                labels={'data': 'Data da Movimentação'}
            )
            fig_fluxo.update_layout(xaxis=dict(tickformat="%d/%m\n%Y"), legend_title_text='', xaxis_title="")
            st.plotly_chart(fig_fluxo, use_container_width=True)
        else:
            st.info("Não há movimentações financeiras registradas neste mês específico.")

    with col_graf_desp:
        st.subheader("Ranking de Custos")
        df_despesas_grupo = df_despesas_filtrado.groupby('categoria', as_index=False)['valor_num'].sum()
        df_despesas_grupo = df_despesas_grupo[df_despesas_grupo['valor_num'] > 0]

        if not df_despesas_grupo.empty:
            df_despesas_grupo = df_despesas_grupo.sort_values(by='valor_num', ascending=True)

            fig_bar_desp = px.bar(
                df_despesas_grupo,
                x='valor_num',
                y='categoria',
                orientation='h',
                text_auto=True,
                color_discrete_sequence=['#d62728'],
                labels={'valor_num': 'Valor (R$)', 'categoria': ''}
            )

            fig_bar_desp.update_layout(
                xaxis_title="",
                yaxis_title="",
                xaxis=dict(showticklabels=False)
            )
            st.plotly_chart(fig_bar_desp, use_container_width=True)
        else:
            st.info("Não há despesas lançadas neste mês.")