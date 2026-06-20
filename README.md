# Vistto — Inteligência de Negócios (Prata-Viva Ltda)

Dashboard de inteligência financeira e comercial construído em **Streamlit**, voltado
para uma distribuidora de produtos de limpeza. A aplicação executa um pipeline de
ETL sobre arquivos CSV brutos e apresenta indicadores executivos, de performance,
estoque e saúde financeira em um painel interativo.

## Funcionalidades

O dashboard é organizado em quatro abas:

- **📊 Executivo** — KPIs principais (Faturamento, Qtd. de Vendas, Ticket Médio e
  Lucro Bruto) e ranking de faturamento por categoria de produto.
- **🎯 Performance** — Métricas de aquisição e valor do cliente (Investimento em
  Marketing, CAC estimado e LTV médio), faturamento por canal de origem e ticket
  médio por segmento.
- **📦 Estoque** — Capital imobilizado, alertas de ruptura (itens abaixo do estoque
  mínimo) e matriz de avaliação de inventário.
- **💸 Financeiro** — Fluxo de caixa (entradas x saídas), saldo operacional
  aproximado e curva ABC das despesas por centro de custo.

Um filtro global na barra lateral permite analisar todo o histórico ou uma
competência (mês/ano) específica.

## Pipeline de dados (ETL)

A função `executar_pipeline_etl_vistto()` faz:

1. **Carga** dos CSVs com *fallback* de codificação (UTF-8 → Latin-1).
2. **Limpeza** de valores monetários (`R$`, separadores) e datas (`dd/mm/aaaa`).
3. **Padronização** de texto (minúsculas, remoção de acentos) com dicionários de
   normalização para produtos e categorias de despesas.
4. **Deduplicação** da base de clientes.
5. **Cruzamento (joins)** das vendas com produtos (custo/categoria) e clientes
   (segmento/canal), calculando custo e lucro bruto por venda.

## Fontes de dados

| Arquivo | Conteúdo | Colunas principais |
| --- | --- | --- |
| `vendas.csv` | Transações de venda | id_venda, data, produto, categoria, quantidade, valor_total, forma_pagamento, id_cliente |
| `clientes.csv` | Cadastro de clientes | id_cliente, razao_social, telefone, cidade, segmento, canal_origem |
| `despesas.csv` | Despesas operacionais | id_despesa, data, categoria, descricao, fornecedor, valor |
| `produtos.csv` | Catálogo e estoque | codigo, descricao_padrao, categoria, custo_unitario, preco_venda, estoque_atual, estoque_minimo |

## Como executar

```bash
pip install -r requirements.txt
streamlit run app.py
```

A aplicação abre no navegador (por padrão em `http://localhost:8501`).

## Requisitos

- Python 3.9+
- pandas, streamlit 1.32.0, plotly-express (ver `requirements.txt`)
