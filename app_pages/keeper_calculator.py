import streamlit as st
import pandas as pd
import math
import os

# Função para converter número da escolha global (ADP) em Rodada.Pick
def adp_to_round_pick(adp, num_teams):
    if pd.isna(adp) or adp <= 0:
        return "N/A"
    
    round_num = math.ceil(adp / num_teams)
    pick_num = round(adp) % num_teams
    if pick_num == 0:
        pick_num = num_teams
        
    return f"{round_num}.{pick_num:02d}"

from core.data_utils import load_adp_data

st.title("Keeper Calculator")
st.markdown("Analise quais jogadores valem a pena ser mantidos no seu elenco (Keepers) com base no custo (Rodada que você perde) vs. o Valor de Mercado (ADP Atual).")

# 1. Configurações da Liga
st.sidebar.header("⚙️ Configuração da Liga")
num_teams = st.sidebar.number_input("Número de Times na Liga", min_value=8, max_value=32, value=12, step=2)
scoring_format = st.sidebar.selectbox("Formato de Pontuação", ["PPR", "Half-PPR", "Standard"])

df_adp, player_col, pos_col, adp_col = load_adp_data(scoring_format)

if not df_adp.empty and player_col and adp_col:
    # 2. Entrada de Dados dos Keepers
    st.subheader("Candidatos a Keeper")
    
    # Criamos um estado na sessão para armazenar a lista de keepers adicionados
    if 'keepers_list' not in st.session_state:
        st.session_state.keepers_list = []
        
    with st.form("add_keeper_form", clear_on_submit=True):
        col1, col2, col3 = st.columns([3, 1, 1])
        
        # As colunas já foram resolvidas pelo data_utils
        
        # Filtramos jogadores disponíveis
        available_players = sorted(df_adp[player_col].dropna().astype(str).tolist())
        
        with col1:
            selected_player = st.selectbox("Selecione o Jogador", [""] + available_players)
        with col2:
            cost_round = st.number_input("Custo (Rodada)", min_value=1, max_value=30, value=10)
        with col3:
            st.markdown("<br>", unsafe_allow_html=True) # Espaçamento
            add_btn = st.form_submit_button("Adicionar")
            
        if add_btn and selected_player:
            # Busca o ADP do jogador
            player_row = df_adp[df_adp[player_col] == selected_player]
            
            adp_val = 999.0
            if not player_row.empty and adp_col and adp_col in player_row.columns:
                adp_raw = player_row[adp_col].values[0]
                try:
                    adp_val = float(adp_raw)
                except:
                    adp_val = 999.0
            
            # Adiciona na lista
            st.session_state.keepers_list.append({
                "Jogador": selected_player,
                "Custo (Rodada)": cost_round,
                "ADP Global": adp_val
            })
            
    # 3. Exibição e Análise
    if st.session_state.keepers_list:
        df_keepers = pd.DataFrame(st.session_state.keepers_list)
        
        # Cálculos de valor
        # Custo equivalente em ADP (Ex: Rodada 10 em liga de 12 = Escolha 115)
        # Vamos assumir que a escolha é no meio da rodada para uma média
        df_keepers['Custo Estimado (Escolha)'] = ((df_keepers['Custo (Rodada)'] - 1) * num_teams) + (num_teams / 2)
        
        # Gap (Diferença entre o custo e o valor real). Valores Positivos = Lucro.
        df_keepers['Ganho de Valor (Picks)'] = df_keepers['Custo Estimado (Escolha)'] - df_keepers['ADP Global']
        
        df_keepers['Rodada do ADP'] = df_keepers['ADP Global'].apply(lambda x: adp_to_round_pick(x, num_teams))
        
        def highlight_value(val):
            if val > 24:
                return 'background-color: #004d00; color: #00FFAA;' # Muito bom
            elif val > 0:
                return 'background-color: #003300; color: #aaffaa;' # Bom
            elif val > -12:
                return 'background-color: #331a00; color: #ffcc99;' # Ruim
            else:
                return 'background-color: #4d0000; color: #ff9999;' # Horrível
                
        st.markdown("### 📊 Análise de Keepers")
        
        # Reordenando colunas para exibição
        display_df = df_keepers[['Jogador', 'Custo (Rodada)', 'ADP Global', 'Rodada do ADP', 'Ganho de Valor (Picks)']]
        display_df = display_df.sort_values(by='Ganho de Valor (Picks)', ascending=False)
        
        st.dataframe(
            display_df.style.map(highlight_value, subset=['Ganho de Valor (Picks)']),
            width='stretch',
            hide_index=True
        )
        
        if st.button("Limpar Lista"):
            st.session_state.keepers_list = []
            st.rerun()
            
else:
    st.error(f"Arquivo de ADP para {scoring_format} não encontrado na raiz do projeto.")
