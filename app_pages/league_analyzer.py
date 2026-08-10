import streamlit as st
import pandas as pd
import requests
import json
import os

# Reaproveitando chamadas de API do Sleeper
from core.sleeper_api import get_user_data, get_user_leagues, get_league_rosters, get_league_users
from core.data_utils import load_players_dict, load_adp_data

st.title("League Analyzer")
st.markdown("Avalie a força (Power Ranking) dos times da sua liga com base no Valor de Mercado atual de seus elencos.")

st.sidebar.header("⚙️ Configurações")
username = st.sidebar.text_input("Username (Sleeper)", value=st.session_state.username)
scoring_format = st.sidebar.selectbox("Formato da Liga", ["PPR", "Half-PPR", "Standard"])

if username != st.session_state.username:
    st.session_state.username = username

if username:
    user_id = get_user_data(username)
    if user_id:
        leagues = get_user_leagues(user_id)
        if leagues:
            league_options = {l['name']: l['league_id'] for l in leagues}
            selected_league = st.sidebar.selectbox("Selecione a Liga", list(league_options.keys()))
            league_id = league_options[selected_league]
            
            if st.button("Analisar Liga", type="primary"):
                with st.spinner("Buscando elencos e cruzando dados..."):
                    rosters = get_league_rosters(league_id)
                    users = get_league_users(league_id)
                    df_adp, player_col, pos_col, adp_col = load_adp_data(scoring_format)
                    players_dict = load_players_dict()
                    
                    if not df_adp.empty and rosters and players_dict:
                        power_rankings = []
                        
                        def calculate_player_value(player_name):
                            row = df_adp[df_adp[player_col] == player_name]
                            if not row.empty and adp_col in row.columns:
                                adp = float(row[adp_col].values[0])
                                # Fórmula base exponencial
                                return max(0, 1000 * (0.98 ** (adp - 1)))
                            return 0
                        
                        for roster in rosters:
                            owner_id = roster.get('owner_id')
                            owner_name = users.get(owner_id, "Desconhecido")
                            
                            team_value = 0
                            top_player = None
                            top_player_val = -1
                            
                            for pid in (roster.get('players') or []):
                                p_info = players_dict.get(str(pid), {})
                                p_name = p_info.get('full_name', '')
                                if p_name:
                                    val = calculate_player_value(p_name)
                                    team_value += val
                                    if val > top_player_val:
                                        top_player_val = val
                                        top_player = p_name
                                        
                            power_rankings.append({
                                "Manager": owner_name,
                                "Power Score": round(team_value, 0),
                                "Franchise Player": top_player
                            })
                            
                        df_pr = pd.DataFrame(power_rankings).sort_values(by="Power Score", ascending=False)
                        df_pr['Rank'] = range(1, len(df_pr) + 1)
                        
                        st.subheader(f"🏆 Power Ranking: {selected_league}")
                        
                        def highlight_top(row):
                            if row['Rank'] == 1:
                                return ['background-color: #ffd700; color: black'] * len(row)
                            elif row['Rank'] <= 3:
                                return ['background-color: #1a1a1a; color: white'] * len(row)
                            elif row['Rank'] >= len(df_pr) - 1:
                                return ['background-color: #4d0000; color: white'] * len(row)
                            return [''] * len(row)
                            
                        st.dataframe(
                            df_pr[['Rank', 'Manager', 'Power Score', 'Franchise Player']].style.apply(highlight_top, axis=1),
                            hide_index=True,
                            width='stretch'
                        )
                        
                        st.caption("O Power Score é calculado sumariando o valor exponencial de cada jogador do elenco com base em seu ADP atual.")
                    else:
                        st.error("Erro ao carregar dados da liga ou do ADP.")
        else:
            st.warning("Nenhuma liga encontrada.")
    else:
        st.error("Usuário não encontrado.")
