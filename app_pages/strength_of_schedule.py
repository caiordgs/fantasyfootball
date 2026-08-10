import streamlit as st
import pandas as pd
import os

st.title("Strength of Schedule (SOS)")
st.markdown("Avalie a dificuldade da tabela de jogos para cada time da NFL, focado nos Fantasy Playoffs (Semanas 15 a 17).")

# Carrega o arquivo local
file_path = "nfl_sos_2026.csv"

if os.path.exists(file_path):
    df_sos = pd.read_csv(file_path)
    
    st.sidebar.header("⚙️ Configurações de SOS")
    # Tenta identificar posições para filtro
    # O arquivo deve ter uma coluna Time, e colunas para QB, RB, WR, TE
    
    # Simulação se o arquivo não tiver essas colunas exatas
    if 'Team' not in df_sos.columns and df_sos.shape[1] > 0:
        team_col = df_sos.columns[0]
    else:
        team_col = 'Team'
        
    st.subheader("Mapa de Calor: Dificuldade da Tabela")
    st.markdown("Cores **verdes** indicam tabelas fáceis (Muitos pontos cedidos pelo adversário). Cores **vermelhas** indicam defesas brutais pela frente.")
    
    # Aplicar formatação condicional se houver colunas numéricas
    numeric_cols = df_sos.select_dtypes(include=['float64', 'int64']).columns
    
    if len(numeric_cols) > 0:
        st.dataframe(
            df_sos.style.background_gradient(subset=numeric_cols, cmap='RdYlGn'),
            hide_index=True,
            width='stretch'
        )
    else:
        st.dataframe(df_sos, hide_index=True, width='stretch')
        
    st.markdown("---")
    st.info("💡 **Dica Dynasty:** O SOS muda drasticamente de um ano para o outro. Use esta tabela principalmente para Redraft e para planejar Trocas faltando poucas semanas para os Playoffs.")
else:
    st.error(f"Arquivo '{file_path}' não encontrado na raiz do projeto. Por favor, faça o upload do arquivo base de SOS.")
