import streamlit as st
import pandas as pd
import requests
import json
import os

st.set_page_config(page_title="Lineup Optimizer Pro", page_icon="🏈", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0A0A0A; }
    [data-testid="stMetricValue"] { font-size: 2rem !important; color: #00FFAA !important; }
    .stDataFrame { border-radius: 8px; overflow: hidden; }
    </style>
""", unsafe_allow_html=True)


# --- 1. API DO SLEEPER E METADADOS ---
@st.cache_data
def load_players_dict():
    file_path = "sleeper_players_cache.json"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@st.cache_data
def get_user_leagues(username):
    res_user = requests.get(f"https://api.sleeper.app/v1/user/{username}")
    if res_user.status_code == 200 and res_user.json():
        user_id = res_user.json().get('user_id')
        res_leagues = requests.get(f"https://api.sleeper.app/v1/user/{user_id}/leagues/nfl/2026")
        return res_leagues.json() if res_leagues.status_code == 200 else [], user_id
    return [], None


@st.cache_data
def get_league_info(league_id):
    res = requests.get(f"https://api.sleeper.app/v1/league/{league_id}")
    if res.status_code == 200:
        data = res.json()
        return data.get('scoring_settings', {}), data.get('roster_positions', [])
    return {}, []


@st.cache_data
def get_my_roster(league_id, user_id):
    res = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/rosters")
    if res.status_code == 200:
        rosters = res.json()
        for r in rosters:
            if str(r.get('owner_id')) == str(user_id):
                return r.get('players', [])
    return []


@st.cache_data
def get_weekly_projections(week):
    url = f"https://api.sleeper.app/v1/projections/nfl/regular/2026/{week}"
    res = requests.get(url)
    return res.json() if res.status_code == 200 else {}


# --- 2. NOVOS MOTORES DE ANÁLISE DE MATCHUP E HISTÓRICO ---
@st.cache_data
def load_weekly_schedule(week, filepath="nfl_schedule.json"):
    # Dicionário mapeando Time -> Adversário na Semana X
    # Exemplo: {'PHI': 'DAL', 'DAL': 'PHI'}
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r") as f:
            tabela = json.load(f)
            return tabela.get(str(week), {})
    except:
        return {}


@st.cache_data
def load_dvp_matrix(filepath="nfl_dvp.csv"):
    if not os.path.exists(filepath): return {}
    try:
        df_dvp = pd.read_csv(filepath)
        df_dvp.columns = df_dvp.columns.str.strip()
        return df_dvp.set_index('Team').to_dict(orient='index')
    except Exception as e:
        st.sidebar.error(f"Erro ao ler DvP: {e}")
        return {}


@st.cache_data
def load_player_history(filepath="nfl_player_history.json"):
    # Bônus pessoal do jogador contra o time. Ex: Derrick Henry contra o Texans (Sempre amassa)
    if not os.path.exists(filepath): return {}
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except:
        return {}


# --- 3. ALGORITMO OTIMIZADOR DE CONFRONTOS ---
def optimize_lineup(my_player_ids, projections, players_dict, scoring_settings, roster_positions, schedule, dvp_matrix,
                    history_matrix):
    elenco = []

    for pid in my_player_ids:
        p_info = players_dict.get(pid, {})
        nome = p_info.get('full_name', 'Desconhecido')
        pos = p_info.get('position', 'UNKNOWN')
        team = p_info.get('team', 'FA')

        # 3.1 Identifica o Adversário da Semana
        # Se a matriz 'schedule' estiver vazia, não joga a liga inteira pro BYE. Assume TBD (To Be Determined).
        if not schedule:
            adversario = 'TBD'
        else:
            adversario = schedule.get(team, 'BYE')

        if adversario == 'BYE':
            # Se está de folga, pontuação é zero e não joga
            pts_finais = 0.0
            matchup_str = "Folga (BYE)"
            mod_visual = 0
        else:
            # 3.2 Calcula a Projeção Base da API
            proj = projections.get(pid, {})
            pts_base = 0.0
            if scoring_settings:
                for stat_key, multiplier in scoring_settings.items():
                    val = proj.get(stat_key, 0.0)
                    if val is not None: pts_base += float(val) * float(multiplier)
            else:
                pts_base = float(proj.get('pts_ppr', 0.0)) if proj.get('pts_ppr') is not None else 0.0

            # 3.3 Aplica o Modificador de Matchup (Defesa do Adversário vs Posição)
            # Busca a defesa do adversário. Se não achar, multiplicador neutro (1.0)
            dvp_mod = dvp_matrix.get(adversario, {}).get(pos, 1.0)

            # 3.4 Aplica o Modificador de Histórico do Jogador contra o Time
            # Ex: history_matrix['Jalen Hurts']['DAL'] = 1.15 (+15% de boost mental/histórico)
            hist_mod = history_matrix.get(nome, {}).get(adversario, 1.0)

            pts_finais = pts_base * dvp_mod * hist_mod

            # Ajustes visuais para a tabela
            if dvp_mod > 1.1:
                mod_visual = 1  # Matchup Verde (Fácil)
            elif dvp_mod < 0.9:
                mod_visual = -1  # Matchup Vermelho (Difícil)
            else:
                mod_visual = 0  # Neutro

            matchup_str = f"vs {adversario}"

        elenco.append({
            'ID': pid,
            'Nome': nome,
            'Posição': pos,
            'Time': team,
            'Matchup': matchup_str,
            'Dificuldade': mod_visual,
            'Proj_Base': round(pts_base, 1) if adversario != 'BYE' else 0.0,
            'Proj_Semana': pts_finais
        })

    df_elenco = pd.DataFrame(elenco).sort_values(by='Proj_Semana', ascending=False)

    # 3.5 Preenchimento do Quebra-Cabeça (Knapsack do Lineup)
    lineup = []
    vagas_restantes = roster_positions.copy()
    vagas_restantes = [v for v in vagas_restantes if v != 'BN']
    jogadores_alocados = set()

    posicoes_fixas = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']
    for pos_alvo in posicoes_fixas:
        vagas_da_posicao = vagas_restantes.count(pos_alvo)
        candidatos = df_elenco[(df_elenco['Posição'] == pos_alvo) & (~df_elenco['ID'].isin(jogadores_alocados))]
        for i in range(min(vagas_da_posicao, len(candidatos))):
            jogador = candidatos.iloc[i]
            if jogador['Proj_Semana'] > 0:  # Não aloca quem está de BYE
                lineup.append({'Vaga': pos_alvo, **jogador.to_dict()})
                jogadores_alocados.add(jogador['ID'])
                vagas_restantes.remove(pos_alvo)

    vagas_flex = [v for v in vagas_restantes if v in ['FLEX', 'W/R/T']]
    for vaga in vagas_flex:
        candidatos_flex = df_elenco[
            (df_elenco['Posição'].isin(['RB', 'WR', 'TE'])) & (~df_elenco['ID'].isin(jogadores_alocados))]
        if not candidatos_flex.empty and candidatos_flex.iloc[0]['Proj_Semana'] > 0:
            jogador = candidatos_flex.iloc[0]
            lineup.append({'Vaga': 'FLEX', **jogador.to_dict()})
            jogadores_alocados.add(jogador['ID'])
            vagas_restantes.remove(vaga)

    vagas_superflex = [v for v in vagas_restantes if v in ['SUPER_FLEX', 'Q/W/R/T']]
    for vaga in vagas_superflex:
        candidatos_sf = df_elenco[
            (df_elenco['Posição'].isin(['QB', 'RB', 'WR', 'TE'])) & (~df_elenco['ID'].isin(jogadores_alocados))]
        if not candidatos_sf.empty and candidatos_sf.iloc[0]['Proj_Semana'] > 0:
            jogador = candidatos_sf.iloc[0]
            lineup.append({'Vaga': 'SUPER_FLEX', **jogador.to_dict()})
            jogadores_alocados.add(jogador['ID'])
            vagas_restantes.remove(vaga)

    # O resto vai pro banco (incluindo quem está de BYE)
    banco = df_elenco[~df_elenco['ID'].isin(jogadores_alocados)].copy()
    banco_list = []
    for _, jogador in banco.iterrows():
        banco_list.append({'Vaga': 'BENCH', **jogador.to_dict()})

    return pd.DataFrame(lineup), pd.DataFrame(banco_list)


# --- 4. INTERFACE ---
st.title("🧠 Otimizador Tático (Semana a Semana)")

st.sidebar.header("Configuração")
username = st.sidebar.text_input("Username (Sleeper)", value="caiordgs")
semana = st.sidebar.slider("Semana da NFL", 1, 18, 1)

if username:
    leagues, user_id = get_user_leagues(username)
    if leagues and user_id:
        league_options = {l['name']: l['league_id'] for l in leagues}
        selected_league_name = st.sidebar.selectbox("Selecione sua Liga", list(league_options.keys()))
        league_id = league_options[selected_league_name]

        if st.sidebar.button("Otimizar Lineup 🚀"):
            with st.spinner(f"Lendo Matchups e Históricos para a Semana {semana}..."):
                players_dict = load_players_dict()
                scoring_settings, roster_positions = get_league_info(league_id)
                my_roster_ids = get_my_roster(league_id, user_id)
                projections_week = get_weekly_projections(semana)

                # Carrega as novas camadas de inteligência
                schedule = load_weekly_schedule(semana)
                dvp_matrix = load_dvp_matrix()
                history_matrix = load_player_history()

                if my_roster_ids:
                    df_titulares, df_banco = optimize_lineup(
                        my_roster_ids, projections_week, players_dict, scoring_settings, roster_positions,
                        schedule, dvp_matrix, history_matrix
                    )

                    pts_projetados = df_titulares['Proj_Semana'].sum() if not df_titulares.empty else 0.0

                    st.metric(f"Projeção Tática (Semana {semana})", f"{pts_projetados:.1f} Pts")

                    col1, col2 = st.columns([1.7, 1])

                    with col1:
                        st.subheader("🔥 Titulares Recomendados")
                        if not df_titulares.empty:
                            st.dataframe(
                                df_titulares[
                                    ['Vaga', 'Nome', 'Posição', 'Matchup', 'Dificuldade', 'Proj_Base', 'Proj_Semana']]
                                .style.background_gradient(cmap='viridis', subset=['Proj_Semana'])
                                .background_gradient(cmap='RdYlGn', subset=['Dificuldade']),
                                # Pinta de verde/vermelho a dificuldade
                                column_config={
                                    "Dificuldade": st.column_config.NumberColumn("DvP Rank",
                                                                                 help="Verde = Defesa Fraca | Vermelho = Defesa Forte",
                                                                                 format="%d"),
                                    "Proj_Base": st.column_config.NumberColumn("Base", format="%.1f"),
                                    "Proj_Semana": st.column_config.NumberColumn("Ajustado", format="%.1f")
                                },
                                use_container_width=True, hide_index=True, height=450
                            )
                        else:
                            st.warning("Nenhum titular encontrado.")

                    with col2:
                        st.subheader("🧊 Banco de Reservas")
                        if not df_banco.empty:
                            st.dataframe(
                                df_banco[['Posição', 'Nome', 'Matchup', 'Proj_Semana']],
                                column_config={"Proj_Semana": st.column_config.NumberColumn("Pts", format="%.1f")},
                                use_container_width=True, hide_index=True, height=450
                            )
                        else:
                            st.info("Banco vazio.")
                else:
                    st.error("Nenhum jogador encontrado no seu time.")
    else:
        st.error("Usuário ou ligas não encontrados.")