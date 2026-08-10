import streamlit as st
import pandas as pd
from core.sleeper_api import get_user_data, get_user_leagues, get_league_rosters, get_league_users
from core.data_utils import load_players_dict

st.title("Trade Navigator")
st.markdown("Encontre parceiros de troca ideais na sua liga baseado no excesso e carência de posições.")

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
            
            if st.button("Mapear Necessidades", type="primary"):
                with st.spinner("Analisando elencos da liga..."):
                    rosters = get_league_rosters(league_id)
                    users = get_league_users(league_id)
                    players_dict = load_players_dict()
                    
                    if rosters and players_dict:
                        team_needs = []
                        my_team = None
                        
                        for roster in rosters:
                            owner_id = roster.get('owner_id')
                            owner_name = users.get(owner_id, "Desconhecido")
                            
                            # Contagem básica por posição
                            pos_counts = {"QB": 0, "RB": 0, "WR": 0, "TE": 0}
                            
                            for pid in (roster.get('players') or []):
                                p_info = players_dict.get(str(pid), {})
                                pos = p_info.get('position')
                                if pos in pos_counts:
                                    pos_counts[pos] += 1
                                    
                            needs = {
                                "Time": owner_name,
                                "QB": pos_counts["QB"],
                                "RB": pos_counts["RB"],
                                "WR": pos_counts["WR"],
                                "TE": pos_counts["TE"]
                            }
                            
                            team_needs.append(needs)
                            
                            if str(owner_id) == str(user_id):
                                my_team = needs
                                
                        df_needs = pd.DataFrame(team_needs)
                        
                        st.subheader("Mapa de Profundidade Posicional")
                        st.markdown("Veja quem está acumulando RBs ou desesperado por um TE.")
                        
                        def highlight_excess(val):
                            if isinstance(val, int):
                                if val >= 6: return 'background-color: #003300' # Excesso
                                if val <= 2: return 'background-color: #4d0000' # Escassez
                            return ''
                            
                        st.dataframe(df_needs.style.map(highlight_excess), hide_index=True, width='stretch')
                        
                        if my_team:
                            st.markdown("---")
                            st.subheader("🤝 Parceiros Sugeridos")
                            
                            # Logica ultra-simplificada: Procuro alguém que tem excesso onde tenho carência
                            # e que tem carência onde tenho excesso
                            for index, row in df_needs.iterrows():
                                if row['Time'] == my_team['Time']: continue
                                
                                match_points = 0
                                reason = []
                                
                                for pos in ["QB", "RB", "WR", "TE"]:
                                    # Se ele tem muito e eu tenho pouco
                                    if row[pos] >= 5 and my_team[pos] <= 3:
                                        match_points += 1
                                        reason.append(f"Ele tem excesso de {pos}.")
                                    # Se ele tem pouco e eu tenho muito
                                    if row[pos] <= 3 and my_team[pos] >= 5:
                                        match_points += 1
                                        reason.append(f"Ele precisa de {pos} (você tem excesso).")
                                        
                                if match_points >= 1:
                                    st.success(f"**Alvo de Troca: {row['Time']}** - {', '.join(reason)}")
                        
                    else:
                        st.error("Dados insuficientes para análise.")
        else:
            st.warning("Nenhuma liga encontrada.")
    else:
        st.error("Usuário não encontrado.")
