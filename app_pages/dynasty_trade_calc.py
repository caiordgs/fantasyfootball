import streamlit as st
import pandas as pd
import os
# Force reload
import os

from core.data_utils import load_adp_data, load_players_dict, get_player_name_by_id
from core.ml_models import get_dynasty_ml_model, evaluate_player_ml
from core.sleeper_api import get_user_data, get_user_leagues, get_league_users, get_real_roster

st.title("Dynasty Trade Calculator (AI Powered)")
st.markdown("Analise trocas na sua liga cruzando o valor dos jogadores avaliados pelo nosso modelo de Machine Learning.")
st.info("O modelo de Random Forest avalia a curva de idade, posição e valor atual (ADP) para prever o valor real do jogador a longo prazo.")

scoring_format = st.sidebar.selectbox("Formato de Avaliação", ["PPR", "Half-PPR", "Standard"])

df_adp, player_col, pos_col, adp_col = load_adp_data(scoring_format)
players_dict = load_players_dict()

if not df_adp.empty and player_col and players_dict:
    # Carrega o modelo de ML treinado (Cache)
    with st.spinner("Iniciando Motor de IA..."):
        model, le = get_dynasty_ml_model()
        
    # Injetar Draft Picks no banco de dados de jogadores
    picks = [
        "2026 Pick 1.01", "2026 Pick Early 1st", "2026 Pick Mid 1st", "2026 Pick Late 1st", "2026 Pick 2nd", "2026 Pick 3rd",
        "2027 Pick Early 1st", "2027 Pick Mid 1st", "2027 Pick Late 1st", "2027 Pick 2nd", "2027 Pick 3rd",
        "2028 Pick Early 1st", "2028 Pick Mid 1st", "2028 Pick Late 1st", "2028 Pick 2nd", "2028 Pick 3rd"
    ]
    all_players = sorted(df_adp[player_col].dropna().astype(str).tolist()) + picks
    
    # Opção de Sincronização com o Sleeper
    sync_mode = st.radio("Modo de Busca", ["🌍 Livre (Todos os Jogadores)", "🔗 Sincronizar com Liga (Sleeper)"], horizontal=True)
    
    options_a_base = all_players
    options_b_base = all_players
    
    if sync_mode == "🔗 Sincronizar com Liga (Sleeper)":
        username = st.session_state.get('username', '')
        if not username:
            st.warning("Configure seu Username do Sleeper no menu lateral ou arquivo config.")
        else:
            user_id = get_user_data(username)
            leagues = get_user_leagues(user_id) if user_id else []
            if leagues:
                league_options = {l['name']: l['league_id'] for l in leagues}
                selected_league = st.selectbox("Selecione sua Liga", list(league_options.keys()))
                league_id = league_options[selected_league]
                
                users = get_league_users(league_id)
                if users:
                    col_u1, col_u2 = st.columns(2)
                    manager_a = col_u1.selectbox("Manager A", list(users.values()), key="mgr_a")
                    manager_b = col_u2.selectbox("Manager B", list(users.values()), index=1 if len(users) > 1 else 0, key="mgr_b")
                    
                    id_a = [k for k, v in users.items() if v == manager_a][0]
                    id_b = [k for k, v in users.items() if v == manager_b][0]
                    
                    roster_a_ids = get_real_roster(league_id, id_a) or []
                    roster_b_ids = get_real_roster(league_id, id_b) or []
                    
                    roster_a_names = [get_player_name_by_id(pid, players_dict) for pid in roster_a_ids]
                    roster_b_names = [get_player_name_by_id(pid, players_dict) for pid in roster_b_ids]
                    
                    # Permite picks também
                    options_a_base = sorted(roster_a_names) + picks
                    options_b_base = sorted(roster_b_names) + picks
    
    col_a, col_b = st.columns(2)
    
    # Filtro de Exclusividade
    selected_b = st.session_state.get("team_b", [])
    options_a = [p for p in options_a_base if p not in selected_b]
    
    with col_a:
        st.subheader("Time A Envia")
        team_a_players = st.multiselect("Selecione os jogadores", options_a, key="team_a")
        
    selected_a = st.session_state.get("team_a", [])
    options_b = [p for p in options_b_base if p not in selected_a]
    
    with col_b:
        st.subheader("Time B Envia")
        team_b_players = st.multiselect("Selecione os jogadores", options_b, key="team_b")
        
    st.markdown("---")
    
    if team_a_players or team_b_players:
        
        def calculate_ai_player_value(player_name):
            val, mod, age, pos = evaluate_player_ml(player_name, model, le, df_adp, player_col, adp_col, pos_col, players_dict)
            return val, mod, age, pos
            
        a_results = [calculate_ai_player_value(p) for p in team_a_players]
        b_results = [calculate_ai_player_value(p) for p in team_b_players]
        
        value_a = sum([r[0] for r in a_results])
        value_b = sum([r[0] for r in b_results])
        
        # Premium de Consolidação (Package Adjustment)
        # Se um time manda 3 jogadores e o outro manda 1, o time que recebe 1 (o melhor jogador) 
        # precisa pagar uma taxa (premium) por estar consolidando valor em uma vaga só.
        len_a = len(a_results)
        len_b = len(b_results)
        premium_b = 0
        premium_a = 0
        
        if len_a > len_b and len_b > 0:
            premium_b = (len_a - len_b) * 1500
            value_b += premium_b
        elif len_b > len_a and len_a > 0:
            premium_a = (len_b - len_a) * 1500
            value_a += premium_a
        
        col_res1, col_res2, col_res3 = st.columns(3)
        col_res1.metric("Valor Total do Lado A", f"{value_a:.0f}")
        col_res3.metric("Valor Total do Lado B", f"{value_b:.0f}")
        
        diff = value_a - value_b
        
        if diff > 100:
            winner = "Time B Vence"
            color = "green"
        elif diff < -100:
            winner = "Time A Vence"
            color = "green"
        else:
            winner = "Troca Justa"
            color = "gray"
            
        col_res2.markdown(f"<h2 style='text-align: center; color: {color};'>{winner}</h2>", unsafe_allow_html=True)
        
        if diff > 100:
            col_res2.caption(f"O Time B está lucrando {diff:.0f} pontos de valor Dynasty.")
        elif diff < -100:
            col_res2.caption(f"O Time A está lucrando {abs(diff):.0f} pontos de valor Dynasty.")
            
        if premium_a > 0:
            col_res2.info(f"O Lado A recebe uma taxa de Consolidação de +{premium_a} pts por ceder mais jogadores.")
        elif premium_b > 0:
            col_res2.info(f"O Lado B recebe uma taxa de Consolidação de +{premium_b} pts por ceder mais jogadores.")
            
        # Tabela Detalhada com ML Insights
        st.subheader("🧠 Análise da Inteligência Artificial")
        
        def build_breakdown(players, results):
            data = []
            for p, r in zip(players, results):
                val, mod, age, pos = r
                
                if "Pick" in p:
                    adp = "N/A"
                else:
                    row = df_adp[df_adp[player_col] == p].iloc[0]
                    adp = float(row[adp_col])
                
                # Modificador formatado
                if mod > 1.05:
                    insight = f"🟢 Bônus Jovem (+{int((mod-1)*100)}%)"
                elif mod < 0.95:
                    insight = f"🔴 Penalidade Idade (-{int((1-mod)*100)}%)"
                else:
                    insight = "⚪ Neutro"
                    
                data.append({
                    "Jogador": p, 
                    "Idade": age,
                    "Pos": pos, 
                    "ADP": adp, 
                    "Valor Base": round(val / mod if mod > 0 else 0, 0),
                    "Impacto da IA": insight,
                    "Valor Final (Dynasty)": round(val, 0)
                })
            return pd.DataFrame(data)
            
        c1, c2 = st.columns(2)
        if team_a_players:
            c1.dataframe(build_breakdown(team_a_players, a_results), hide_index=True, width='stretch')
        if team_b_players:
            c2.dataframe(build_breakdown(team_b_players, b_results), hide_index=True, width='stretch')
else:
    st.error("Não foi possível carregar os dados base ou modelos de IA.")
