import streamlit as st
import pandas as pd
from core.sleeper_api import get_yearly_stats
from core.data_utils import load_players_dict

st.title("Fantasy Points Allowed (FPA)")
st.markdown("Veja quais defesas cederam mais pontos (em média) para os oponentes em 2025.")

with st.spinner("Processando estatísticas das Defesas..."):
    stats_2025 = get_yearly_stats(season="2025")
    players_dict = load_players_dict()

if stats_2025 and players_dict:
    defense_stats = []
    
    for pid, p_stats in stats_2025.items():
        p_info = players_dict.get(str(pid), {})
        pos = p_info.get('position')
        
        # O Sleeper armazena as estatísticas defensivas associadas ao ID da Defesa (DEF)
        if pos == 'DEF':
            team_id = p_info.get('full_name') # O Sleeper guarda o ID da defesa (Ex: 'SF') aqui, agora parseado pra 'San Francisco 49ers'
            if not team_id: continue
                
            pts_allowed = p_stats.get("pts_allow", 0)
            yards_allowed = p_stats.get("yds_allow", 0)
            sacks = p_stats.get("sack", 0)
            ints = p_stats.get("int", 0)
            
            defense_stats.append({
                "Time": team_id,
                "Pontos Cedidos (Total)": pts_allowed,
                "Jardas Cedidas (Total)": yards_allowed,
                "Sacks Efetuados": sacks,
                "Interceptações": ints
            })
            
    if defense_stats:
        df_def = pd.DataFrame(defense_stats)
        
        st.subheader("Matriz Defensiva NFL (2025)")
        st.markdown("Quanto **maior** o número de Pontos e Jardas cedidos, **mais fraca** é a defesa. Use isso para escalar seus QBs e RBs.")
        
        # Ordenando pelas piores defesas primeiro
        df_def = df_def.sort_values(by="Pontos Cedidos (Total)", ascending=False)
        
        st.dataframe(
            df_def.style.background_gradient(subset=['Pontos Cedidos (Total)', 'Jardas Cedidas (Total)'], cmap='Reds'),
            hide_index=True,
            width='stretch'
        )
    else:
        st.warning("Não foi possível processar as estatísticas das defesas.")
else:
    st.error("Falha ao baixar dados do Sleeper.")
