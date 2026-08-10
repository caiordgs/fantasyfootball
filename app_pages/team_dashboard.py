import streamlit as st
import pandas as pd
from core.sleeper_api import get_user_data, get_user_leagues, get_league_rosters
from core.data_utils import load_players_dict

st.title("Team Dashboard")
st.markdown("Visão geral da sua franquia. Acompanhe a força do seu time e o valor dos seus ativos.")

st.sidebar.header("⚙️ Configurações")
username = st.sidebar.text_input("Username (Sleeper)", value=st.session_state.username)
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
            
            with st.spinner("Analisando seu time..."):
                rosters = get_league_rosters(league_id)
                players_dict = load_players_dict()
                
                my_roster = None
                for r in rosters:
                    if str(r.get('owner_id')) == str(user_id):
                        my_roster = r
                        break
                        
                if my_roster and players_dict:
                    # Métricas Principais
                    wins = my_roster['settings'].get('wins', 0)
                    losses = my_roster['settings'].get('losses', 0)
                    fpts = my_roster['settings'].get('fpts', 0.0)
                    fpts_against = my_roster['settings'].get('fpts_against', 0.0)
                    
                    st.subheader(f"📊 Resumo da Temporada ({wins}W - {losses}L)")
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Vitórias", wins)
                    c2.metric("Derrotas", losses)
                    c3.metric("Pontos Feitos (PF)", f"{fpts:.1f}")
                    c4.metric("Pontos Sofridos (PA)", f"{fpts_against:.1f}")
                    
                    st.markdown("---")
                    st.subheader("📋 Elenco Atual")
                    
                    # Detalhando Elenco
                    roster_data = []
                    for pid in (my_roster.get('players') or []):
                        p_info = players_dict.get(str(pid), {})
                        pos = p_info.get('position', 'N/A')
                        name = p_info.get('full_name', 'Unknown')
                        team = p_info.get('team', 'FA')
                        age = p_info.get('age', 'N/A')
                        
                        status = "Titular" if pid in (my_roster.get('starters') or []) else "Banco"
                        
                        roster_data.append({
                            "Status": status,
                            "Posição": pos,
                            "Jogador": name,
                            "Time": team,
                            "Idade": age
                        })
                        
                    df_roster = pd.DataFrame(roster_data)
                    
                    # Customizando a visualização com Altair ou Dataframe nativo
                    def highlight_starters(row):
                        if row['Status'] == 'Titular':
                            return ['background-color: #002244; color: white'] * len(row)
                        return [''] * len(row)
                        
                    st.dataframe(
                        df_roster.style.apply(highlight_starters, axis=1),
                        width='stretch',
                        hide_index=True
                    )
                else:
                    st.error("Elenco não encontrado nesta liga.")
        else:
            st.warning("Nenhuma liga encontrada.")
    else:
        st.error("Usuário não encontrado.")
