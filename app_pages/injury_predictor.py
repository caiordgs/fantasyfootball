import streamlit as st
import pandas as pd
from core.sleeper_api import get_user_data, get_user_leagues, get_real_roster
from core.data_utils import load_players_dict

def calculate_injury_risk(player_data):
    """
    Modelo Heurístico (Simulação de ML) inspirado no DraftSharks
    Calcula risco baseado em Idade, Posição e Status de Lesão Atual.
    """
    pos = player_data.get('position', 'NA')
    age = player_data.get('age', 25)
    if not isinstance(age, (int, float)):
        age = 25
        
    injury_status = player_data.get('injury_status', '')
    
    # 1. Risco Base por Posição (RBs apanham mais)
    base_risk = 0.0
    if pos == 'RB': base_risk = 35.0
    elif pos == 'WR': base_risk = 25.0
    elif pos == 'TE': base_risk = 30.0
    elif pos == 'QB': base_risk = 15.0
    else: base_risk = 10.0
    
    # 2. Curva de Idade (Apex)
    age_modifier = 0.0
    if pos == 'RB':
        if age >= 28: age_modifier = (age - 27) * 8.0 # RBs caem duro pós 28
    elif pos == 'WR':
        if age >= 30: age_modifier = (age - 29) * 4.0
    elif pos == 'TE':
        if age >= 31: age_modifier = (age - 30) * 3.0
    elif pos == 'QB':
        if age >= 36: age_modifier = (age - 35) * 2.0
        
    # 3. Status Atual de Lesão
    status_modifier = 0.0
    if injury_status == 'Questionable': status_modifier = 40.0
    elif injury_status == 'Doubtful': status_modifier = 70.0
    elif injury_status == 'Out': status_modifier = 99.0
    elif injury_status == 'IR': status_modifier = 100.0
    elif injury_status == 'PUP': status_modifier = 100.0
    
    # Risco Total Capado em 99% (ou 100% se IR)
    total_risk = base_risk + age_modifier + status_modifier
    total_risk = min(99.0, total_risk) if status_modifier < 100 else 100.0
    
    # Durabilidade é o inverso
    durability_score = max(0, 100 - total_risk)
    
    return total_risk, durability_score, base_risk, age_modifier, status_modifier

st.title("Injury Predictor (Heuristics)")
st.markdown("Analise o risco de lesão do seu elenco utilizando a heurística baseada na Curva de Idade (Apex) e Posição.")

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
            
            if st.button("Analisar Risco do Meu Elenco", type="primary"):
                with st.spinner("Rodando motor de heurística preditiva..."):
                    my_roster_ids = get_real_roster(league_id, user_id)
                    players_dict = load_players_dict()
                    
                    if my_roster_ids and players_dict:
                        risk_data = []
                        for pid in my_roster_ids:
                            p_info = players_dict.get(str(pid), {})
                            name = p_info.get('full_name', 'Unknown')
                            pos = p_info.get('position', 'NA')
                            age = p_info.get('age', 'N/A')
                            status = p_info.get('injury_status', 'Healthy') or 'Healthy'
                            
                            risk, dur, br, am, sm = calculate_injury_risk(p_info)
                            
                            risk_data.append({
                                "Jogador": name,
                                "Posição": pos,
                                "Idade": age,
                                "Status Oficial": status,
                                "Durability Score": int(dur),
                                "Risco de Lesão (%)": f"{risk:.1f}%"
                            })
                            
                        df_risk = pd.DataFrame(risk_data).sort_values(by="Durability Score")
                        
                        st.subheader("Painel de Risco (Elenco)")
                        
                        def color_risk(val):
                            if isinstance(val, int):
                                if val >= 80: return 'background-color: #004d00; color: white'
                                if val >= 60: return 'background-color: #808000; color: white'
                                return 'background-color: #800000; color: white'
                            return ''
                            
                        st.dataframe(
                            df_risk.style.map(color_risk, subset=['Durability Score']),
                            hide_index=True,
                            width='stretch'
                        )
                        
                        st.markdown("---")
                        st.info("💡 **Como funciona a Matemática (Heurística):** Inspirado por modelos como DraftSharks, nosso algoritmo assume que a posição (RBs apanham mais) e a curva de envelhecimento (Apex) são fatores primordiais. Se um RB passa dos 28 anos, seu risco escala exponencialmente. Lesões atuais somam penalidades massivas ao cálculo.")
                    else:
                        st.error("Elenco ou dicionário não encontrado.")
        else:
            st.warning("Nenhuma liga encontrada.")
    else:
        st.error("Usuário não encontrado.")
