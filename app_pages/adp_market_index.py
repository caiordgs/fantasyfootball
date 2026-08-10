import streamlit as st
import pandas as pd
import os

from core.data_utils import load_adp_data

st.title("ADP Market Index")
st.markdown("Visualize as tendências de mercado e o valor das posições (Positional Tiers) baseado no ADP atual.")

scoring_format = st.sidebar.selectbox("Formato (ADP)", ["PPR", "Half-PPR", "Standard"])
df_adp, player_col, pos_col, adp_col = load_adp_data(scoring_format)

if not df_adp.empty and adp_col and pos_col:
    # Filtra as posições principais para não poluir o gráfico
    main_positions = ["QB", "RB", "WR", "TE"]
    df_filtered = df_adp[df_adp[pos_col].isin(main_positions)].head(150) # Top 150 players
    
    st.subheader("Curva de Valor por Posição (Top 150)")
    st.markdown("Este gráfico mostra a escassez posicional. Observe como RBs e WRs somem rápido do topo do draft.")
    
    # Prepara dados para o gráfico
    chart_data = df_filtered[[adp_col, pos_col]].copy()
    chart_data['Count'] = 1
    # Cria Tiers de 12 escolhas (Rodadas)
    chart_data['Rodada'] = ((chart_data[adp_col] - 1) // 12) + 1
    
    # Agrupa por Rodada e Posição
    tier_dist = chart_data.groupby(['Rodada', pos_col]).size().unstack(fill_value=0)
    
    st.bar_chart(tier_dist)
    
    st.markdown("---")
    
    st.subheader("Lista Completa do Índice")
    st.dataframe(df_adp[[adp_col, player_col, pos_col, 'Team']], hide_index=True, width='stretch')
else:
    st.error("Dados de ADP ou Posição não encontrados no arquivo.")
