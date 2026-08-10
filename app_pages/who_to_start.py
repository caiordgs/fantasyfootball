import streamlit as st
import pandas as pd
import pulp
from core.sleeper_api import get_user_data, get_user_leagues, get_real_roster, get_weekly_projections
from core.data_utils import load_players_dict


# --- MOTOR DE OTIMIZAÇÃO ---
def optimize_lineup(df):
    prob = pulp.LpProblem("Fantasy_Optimizer", pulp.LpMaximize)
    player_vars = pulp.LpVariable.dicts("Titular", df.index, cat='Binary')

    prob += pulp.lpSum([df.loc[i, 'Proj_Points'] * player_vars[i] for i in df.index])

    # Configuração Padrão: 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX (RB/WR/TE), 1 K (opcional), 1 DEF (opcional)
    prob += pulp.lpSum([player_vars[i] for i in df.index if df.loc[i, 'Posição'] == 'QB']) == 1
    prob += pulp.lpSum([player_vars[i] for i in df.index if df.loc[i, 'Posição'] == 'RB']) >= 2
    prob += pulp.lpSum([player_vars[i] for i in df.index if df.loc[i, 'Posição'] == 'WR']) >= 2
    prob += pulp.lpSum([player_vars[i] for i in df.index if df.loc[i, 'Posição'] == 'TE']) >= 1
    prob += pulp.lpSum([player_vars[i] for i in df.index if df.loc[i, 'Posição'] in ['RB', 'WR', 'TE']]) == 6
    
    # Opcionais (Se tiver K ou DEF no elenco, o otimizador tenta escalar no máximo 1)
    prob += pulp.lpSum([player_vars[i] for i in df.index if df.loc[i, 'Posição'] == 'K']) <= 1
    prob += pulp.lpSum([player_vars[i] for i in df.index if df.loc[i, 'Posição'] == 'DEF']) <= 1

    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    if pulp.LpStatus[prob.status] != 'Optimal':
        return pd.DataFrame(), 0.0

    titulares = [i for i in df.index if player_vars[i].varValue == 1.0]

    # CORREÇÃO DO BUG AQUI: Garantindo que o valor seja float e não None
    obj_value = pulp.value(prob.objective)
    total_points = float(obj_value) if obj_value is not None else 0.0

    return df.loc[titulares].copy(), total_points


# ==========================================
# CONSTRUÇÃO DA INTERFACE VISUAL
# ==========================================

st.title("🏈 AI Fantasy Football Optimizer")

if st.button("🔄 Atualizar Projeções da API (Limpar Cache)"):
    st.cache_data.clear()
    st.rerun()

# 1. Barra Lateral de Configurações
st.sidebar.header("⚙️ Configurações")

username = st.sidebar.text_input("Seu Username no Sleeper", value=st.session_state.username, placeholder="Ex: seunome")
if username != st.session_state.username:
    st.session_state.username = username

# 2. Fluxo Principal de Dados
if username:
    user_id = get_user_data(username)

    if user_id:
        leagues = get_user_leagues(user_id)

        if leagues:
            # Cria um dicionário para o Selectbox (Nome da liga -> ID da liga)
            league_options = {l['name']: l['league_id'] for l in leagues}
            selected_league_name = st.sidebar.selectbox("Selecione a Liga", list(league_options.keys()))
            league_id = league_options[selected_league_name]

            st.sidebar.markdown("---")
            st.sidebar.header("📅 Período")
            temporada = st.sidebar.selectbox("Temporada das Projeções", ["2026", "2025", "2024"])
            semana = st.sidebar.slider("Semana", 1, 18, 1)

            st.sidebar.success("Conectado com sucesso!")


            # Carrega dados
            players_dict = load_players_dict()
            my_roster_ids = get_real_roster(league_id, user_id)
            projections_data = get_weekly_projections(season=temporada, week=semana)

            if my_roster_ids and players_dict:
                meu_time = []
                for pid in my_roster_ids:
                    p_info = players_dict.get(str(pid), {})  # Forçando conversão para string
                    nome = p_info.get('full_name', 'Desconhecido')
                    pos = p_info.get('position', 'NA')

                    # Forçando o ID da projeção também para string
                    proj_stats = projections_data.get(str(pid), {})

                    # Tenta extrair a pontuação PPR, se não achar no dicionário 'stats', retorna 0.0
                    pts = proj_stats.get('pts_ppr', 0.0)
                    pts = float(pts) if pts is not None else 0.0

                    meu_time.append({"Nome": nome, "Posição": pos, "Proj_Points": pts})

                df_players = pd.DataFrame(meu_time)

                col1, col2 = st.columns([1, 2])

                with col1:
                    st.subheader("Elenco Atual")
                    st.dataframe(df_players.sort_values(by="Proj_Points", ascending=False), width='stretch',
                                 hide_index=True)

                    # Ferramenta de Debugging: Ver como a API enviou o Justin Jefferson (ID 6794)
                    with st.expander("🛠️ Debug: Ver raw data do Justin Jefferson (ID 6794)"):
                        st.json(projections_data.get("6794", {"Erro": "Jogador não encontrado na projeção"}))

                with col2:
                    st.subheader("Escalação Ideal (AI)")
                    if st.button("Executar Otimizador (Dados Reais)", type="primary"):
                        with st.spinner("Analisando projeções da Semana 1..."):
                            df_ideal, total_points = optimize_lineup(df_players)

                            if not df_ideal.empty:
                                st.success(f"Pontuação Máxima Projetada: **{total_points:.2f} pontos**")
                                st.dataframe(
                                    df_ideal[['Posição', 'Nome', 'Proj_Points']].sort_values(by='Posição'),
                                    width='stretch',
                                    hide_index=True
                                )
                            else:
                                st.error(
                                    "Não foi possível otimizar. Verifique se você possui jogadores suficientes para as posições obrigatórias (1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX).")
            else:
                st.warning("Elenco não encontrado ou dicionário não gerado.")
        else:
            st.sidebar.warning("Nenhuma liga encontrada para 2026.")
    else:
        st.sidebar.error("Usuário não encontrado.")
else:
    st.info("👈 Digite seu nome de usuário do Sleeper na barra lateral para começar.")