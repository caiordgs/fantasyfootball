import streamlit as st
import pandas as pd
import random
import os

from core.data_utils import load_adp_data, apply_format_adjustments

# --- INICIALIZAÇÃO DE ESTADO ---
def init_draft_state():
    st.session_state.draft_active = True
    st.session_state.current_pick = 1
    st.session_state.draft_history = []
    
    num_teams = st.session_state.mock_num_teams
    st.session_state.ai_rosters = {i: {'QB': 0, 'RB': 0, 'WR': 0, 'TE': 0} for i in range(1, num_teams + 1)}
    
    # Carrega dados
    df_adp, player_col, pos_col, adp_col = load_adp_data(st.session_state.mock_scoring)
    
    if df_adp.empty or not player_col:
        st.error("Erro ao carregar dados de ADP.")
        st.session_state.draft_active = False
        return
        
    # Aplica distorção de ADP para formatos especiais
    df_adp = apply_format_adjustments(df_adp, pos_col, adp_col, 
                                      st.session_state.mock_superflex, 
                                      st.session_state.mock_te_premium)
        
    st.session_state.available_players = df_adp.copy()
    st.session_state.player_col = player_col
    st.session_state.pos_col = pos_col
    st.session_state.adp_col = adp_col
    
    # Executa as escolhas da IA se o usuário não for o Pick 1
    fast_forward_ai()

# --- LÓGICA DO DRAFT ---
def get_team_for_pick(pick_num, num_teams):
    # Draft Snake: 1 a N, depois N a 1
    round_num = (pick_num - 1) // num_teams + 1
    pos_in_round = (pick_num - 1) % num_teams + 1
    
    if round_num % 2 != 0:
        return pos_in_round
    else:
        return num_teams - pos_in_round + 1

def execute_ai_pick():
    df = st.session_state.available_players.copy()
    if df.empty: return
    
    pick_num = st.session_state.current_pick
    team = get_team_for_pick(pick_num, st.session_state.mock_num_teams)
    
    roster = st.session_state.ai_rosters.get(team, {'QB': 0, 'RB': 0, 'WR': 0, 'TE': 0})
    pos_col = st.session_state.pos_col
    
    # Lógica de Roster Construction (Penalizar posições já bem supridas)
    if pos_col and pos_col in df.columns:
        def penalize_adp(row):
            adp = row[st.session_state.adp_col]
            p = str(row[pos_col])
            if p == 'QB' and roster.get('QB', 0) >= 1: return adp + 200
            if p == 'TE' and roster.get('TE', 0) >= 1: return adp + 150
            if p == 'RB' and roster.get('RB', 0) >= 4: return adp + 80
            if p == 'WR' and roster.get('WR', 0) >= 5: return adp + 80
            return adp
            
        df['adjusted_adp'] = df.apply(penalize_adp, axis=1)
        df = df.sort_values(by='adjusted_adp')
    
    # AI pega um dos 3 melhores disponíveis baseado em ADP (leve variação)
    top_n = min(3, len(df))
    idx_choice = random.choices(range(top_n), weights=[0.7, 0.2, 0.1][:top_n], k=1)[0]
    
    chosen_row = df.iloc[idx_choice]
    
    # Atualiza tracker da IA
    if pos_col:
        p = str(chosen_row[pos_col])
        if p in roster:
            roster[p] += 1
            
    record_pick(chosen_row)

def fast_forward_ai():
    total_picks = st.session_state.mock_num_teams * st.session_state.mock_rounds
    while st.session_state.current_pick <= total_picks:
        current_team = get_team_for_pick(st.session_state.current_pick, st.session_state.mock_num_teams)
        if current_team == st.session_state.mock_user_pos:
            break
        execute_ai_pick()

def execute_user_pick(player_name):
    df = st.session_state.available_players
    player_col = st.session_state.player_col
    pos_col = st.session_state.pos_col
    
    chosen_row = df[df[player_col] == player_name].iloc[0]
    
    if pos_col:
        p = str(chosen_row[pos_col])
        user_roster = st.session_state.ai_rosters[st.session_state.mock_user_pos]
        if p in user_roster:
            user_roster[p] += 1
        else:
            user_roster[p] = 1
            
    record_pick(chosen_row)
    
    # Após o humano jogar, avança as IAs até o próximo turno do humano
    fast_forward_ai()

def record_pick(chosen_row):
    player_col = st.session_state.player_col
    pos_col = st.session_state.pos_col
    
    player_name = chosen_row[player_col]
    pos = chosen_row[pos_col] if pos_col else "N/A"
    
    pick_num = st.session_state.current_pick
    team = get_team_for_pick(pick_num, st.session_state.mock_num_teams)
    
    # Adiciona ao histórico
    st.session_state.draft_history.append({
        "Pick": pick_num,
        "Time": f"Time {team}" if team != st.session_state.mock_user_pos else "SEU TIME",
        "Jogador": player_name,
        "Posição": pos
    })
    
    # Remove dos disponíveis
    df = st.session_state.available_players
    st.session_state.available_players = df[df[player_col] != player_name]
    
    # Avança pick
    st.session_state.current_pick += 1

def render_draft_board(df_hist, num_teams, num_rounds):
    # Inicializa DataFrame vazio
    columns = [f"Time {i}" if i != st.session_state.mock_user_pos else "SEU TIME" for i in range(1, num_teams + 1)]
    board = pd.DataFrame(index=range(1, num_rounds + 1), columns=columns)
    board.fillna("", inplace=True)
    
    for _, row in df_hist.iterrows():
        pick = row['Pick']
        round_num = (pick - 1) // num_teams + 1
        pos_in_round = (pick - 1) % num_teams + 1
        
        if round_num % 2 != 0:
            team_idx = pos_in_round - 1
        else:
            team_idx = num_teams - pos_in_round
            
        col_name = columns[team_idx]
        player = row['Jogador']
        pos = row['Posição']
        board.at[round_num, col_name] = f"{player} ({pos})"
        
    return board

def color_draft_board(val):
    if not val: return ""
    color = ""
    if "(QB)" in val: color = "background-color: rgba(255, 105, 180, 0.4);" # Rosa/Vermelho
    elif "(RB)" in val: color = "background-color: rgba(144, 238, 144, 0.4);" # Verde
    elif "(WR)" in val: color = "background-color: rgba(135, 206, 235, 0.4);" # Azul
    elif "(TE)" in val: color = "background-color: rgba(255, 165, 0, 0.4);" # Laranja
    else: color = "background-color: rgba(128, 128, 128, 0.4);" # Cinza
    return f"{color} color: white; font-weight: 600;"

# ==========================================
# INTERFACE
# ==========================================
st.title("Mock Draft Trainer")
st.markdown("Treine para o seu draft real! Simule um draft snake completo contra IAs baseadas nos dados de ADP atuais.")

# --- BARRA LATERAL (CONFIGURAÇÃO) ---
st.sidebar.header("⚙️ Configurações do Mock")

if not st.session_state.get('draft_active', False):
    mock_num_teams = st.sidebar.number_input("Número de Times", min_value=8, max_value=16, value=12, step=2)
    mock_user_pos = st.sidebar.number_input("Sua Posição no Draft", min_value=1, max_value=mock_num_teams, value=4)
    mock_rounds = st.sidebar.number_input("Total de Rodadas", min_value=5, max_value=20, value=15)
    mock_scoring = st.sidebar.selectbox("Formato (ADP)", ["PPR", "Half-PPR", "Standard"])
    mock_superflex = st.sidebar.checkbox("Superflex (2 QBs)", value=False)
    mock_te_premium = st.sidebar.checkbox("TE Premium", value=False)
    
    if st.sidebar.button("🚀 Iniciar Mock Draft", type="primary"):
        st.session_state.mock_num_teams = mock_num_teams
        st.session_state.mock_user_pos = mock_user_pos
        st.session_state.mock_rounds = mock_rounds
        st.session_state.mock_scoring = mock_scoring
        st.session_state.mock_superflex = mock_superflex
        st.session_state.mock_te_premium = mock_te_premium
        init_draft_state()
        st.rerun()
else:
    st.sidebar.success("Draft em Andamento!")
    if st.sidebar.button("🛑 Cancelar Draft"):
        st.session_state.draft_active = False
        st.rerun()


# --- TELA PRINCIPAL (DRAFT ATIVO) ---
if st.session_state.get('draft_active', False):
    total_picks = st.session_state.mock_num_teams * st.session_state.mock_rounds
    
    if st.session_state.current_pick > total_picks:
        st.success("🎉 Mock Draft Finalizado!")
        st.balloons()
        st.session_state.draft_active = False
    else:
        current_team = get_team_for_pick(st.session_state.current_pick, st.session_state.mock_num_teams)
        
        # Métrica do topo
        col1, col2, col3 = st.columns(3)
        col1.metric("Pick Atual", st.session_state.current_pick)
        col2.metric("No Relógio", "VOCÊ" if current_team == st.session_state.mock_user_pos else f"Time {current_team} (IA)")
        col3.metric("Rodada", (st.session_state.current_pick - 1) // st.session_state.mock_num_teams + 1)
        
        st.markdown("---")
        
        # Lógica de quem escolhe
        if current_team == st.session_state.mock_user_pos:
            st.subheader("🎯 Sua Vez! Faça sua escolha.")
            
            # --- MEU ELENCO ---
            my_roster = st.session_state.ai_rosters.get(st.session_state.mock_user_pos, {})
            my_roster_str = " | ".join([f"{k}: {v}" for k, v in my_roster.items() if v > 0])
            if not my_roster_str: my_roster_str = "Vazio"
            st.markdown(f"**Meu Elenco:** <span style='color:#00d2ff; font-weight:bold;'>{my_roster_str}</span>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            df_avail = st.session_state.available_players.head(20) # Mostra os top 20 para escolha
            
            with st.form("user_pick_form"):
                col_sel, col_btn = st.columns([3,1])
                player_options = df_avail[st.session_state.player_col].tolist()
                selected = col_sel.selectbox("Escolha um jogador:", player_options)
                
                if col_btn.form_submit_button("Draftar Jogador", type="primary"):
                    execute_user_pick(selected)
                    st.rerun()
                    
            # Prevenindo KeyError se pos_col ou adp_col não existirem
            cols_to_show = [st.session_state.player_col]
            if st.session_state.pos_col: cols_to_show.append(st.session_state.pos_col)
            if st.session_state.adp_col: cols_to_show.append(st.session_state.adp_col)
            
            st.dataframe(df_avail[cols_to_show], hide_index=True)
            
    # --- HISTÓRICO / DRAFT BOARD ---
    st.markdown("---")
    with st.expander("📋 Draft Board Completo (Grid)", expanded=True):
        if st.session_state.draft_history:
            df_hist = pd.DataFrame(st.session_state.draft_history)
            board_df = render_draft_board(df_hist, st.session_state.mock_num_teams, st.session_state.mock_rounds)
            
            st.dataframe(
                board_df.style.map(color_draft_board),
                use_container_width=True,
                height=600
            )
        else:
            st.caption("Nenhum jogador selecionado ainda.")
