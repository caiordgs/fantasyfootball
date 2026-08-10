import streamlit as st
import pandas as pd
import os
import plotly.express as px

from core.data_utils import load_adp_data

st.title("Trade Value Charts")
st.markdown("Mapas de calor e gráficos de dispersão mostrando o verdadeiro valor de troca dos jogadores.")

scoring_format = st.sidebar.selectbox("Formato", ["PPR", "Half-PPR", "Standard"])
df_adp, player_col, pos_col, adp_col = load_adp_data(scoring_format)

if not df_adp.empty and adp_col and pos_col:
    # Filtra Top 100
    df_filtered = df_adp[df_adp[pos_col].isin(["QB", "RB", "WR", "TE"])].head(100).copy()
    
    # Adiciona a métrica de "Trade Value"
    df_filtered['Trade Value'] = df_filtered[adp_col].apply(lambda x: max(0, 9999 * (0.985 ** (x - 1))))
    
    st.subheader("Curva de Decaimento de Valor")
    st.markdown("O valor de um jogador cai exponencialmente após o Top 10. Estrelas de elite valem múltiplos jogadores medianos.")
    
    # Gráfico Interativo com Plotly
    fig = px.scatter(
        df_filtered, 
        x=adp_col, 
        y="Trade Value", 
        color=pos_col,
        size="Trade Value",
        hover_name=player_col,
        hover_data={adp_col: True, "Trade Value": ':.0f', pos_col: True},
        title="Dispersão de Valor por Posição",
        template="plotly_dark",
        color_discrete_map={"QB": "#00d2ff", "RB": "#ff4b4b", "WR": "#00ff87", "TE": "#ffb703"}
    )
    
    fig.update_layout(
        xaxis_title="ADP (Rank)",
        yaxis_title="Valor de Troca",
        xaxis=dict(autorange="reversed"), # Reverter eixo X (ADP 1 na esquerda)
        hoverlabel=dict(bgcolor="rgba(0,0,0,0.8)", font_size=14, font_family="Inter")
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    st.subheader("Tabela Oficial de Valores (Trade Chart)")
    
    # Formata para visualização
    df_filtered['Trade Value'] = df_filtered['Trade Value'].round(0).astype(int)
    
    st.dataframe(
        df_filtered[[adp_col, player_col, pos_col, 'Trade Value']],
        hide_index=True,
        width='stretch'
    )
else:
    st.error("Dados de ADP não encontrados.")
