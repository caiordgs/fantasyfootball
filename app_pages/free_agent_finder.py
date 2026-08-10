import streamlit as st
import pandas as pd
from core.sleeper_api import get_user_data, get_user_leagues, get_league_rostered_players
from core.data_utils import load_players_dict, load_adp_data

st.title("Free Agent Finder")
st.markdown("Encontre os melhores jogadores (Waiver Wire / Free Agents) disponíveis na sua liga atual que NINGUÉM tem no elenco.")

st.sidebar.header("⚙️ Configurações")
username = st.sidebar.text_input("Username (Sleeper)", value=st.session_state.username)
scoring_format = st.sidebar.selectbox("Filtro de Valor (Base)", ["PPR", "Half-PPR", "Standard"])

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
            
            if st.button("Buscar Free Agents", type="primary"):
                with st.spinner("Analisando mercado de Free Agents na sua liga..."):
                    rostered_ids = get_league_rostered_players(league_id)
                    players_dict = load_players_dict()
                    df_adp, player_col, pos_col, adp_col = load_adp_data(scoring_format)
                    
                    if not df_adp.empty and players_dict:
                        # Extraindo lista de nomes já rostados
                        rostered_names = set()
                        for pid in rostered_ids:
                            p_info = players_dict.get(str(pid), {})
                            p_name = p_info.get('full_name')
                            if p_name:
                                rostered_names.add(p_name.strip().lower())
                        
                        # Procurando os melhores no ADP que NÃO estão rostados
                        free_agents = []
                        for idx, row in df_adp.iterrows():
                            name = str(row[player_col]).strip()
                            if name.lower() not in rostered_names:
                                pos = row[pos_col] if pos_col else "N/A"
                                rank = row[adp_col] if adp_col else 999
                                
                                # Apenas posições úteis
                                if pos in ["QB", "RB", "WR", "TE", "K", "DEF"]:
                                    free_agents.append({
                                        "Jogador": name,
                                        "Posição": pos,
                                        "Valor (Rank Global)": rank
                                    })
                                    
                                if len(free_agents) >= 50:
                                    break
                                    
                        df_fa = pd.DataFrame(free_agents)
                        
                        st.subheader(f"🔍 Top 50 Free Agents Disponíveis")
                        st.info(f"O sistema cruzou o banco de dados e removeu **{len(rostered_ids)} jogadores** que já pertencem a algum time na liga '{selected_league}'.")
                        
                        st.dataframe(df_fa, hide_index=True, width='stretch')
                    else:
                        st.error("Dicionário de jogadores ou dados de ADP indisponíveis.")
        else:
            st.warning("Nenhuma liga encontrada.")
    else:
        st.error("Usuário não encontrado.")
