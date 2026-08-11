import streamlit as st
import pandas as pd
import requests
import json
import os
import time

# Importa o nosso ETL e o Tradutor que criamos na Fase 5
from core.data_loader import load_master_dataframe
from core.draft_sync import get_sleeper_translator
from core.ml_models import get_breakout_predictor_model, add_algorithmic_tiers

# Configuração movida para app.py

st.markdown("""
    <style>
    .stApp { background-color: #0A0A0A; }
    [data-testid="stMetricValue"] { font-size: 2rem !important; color: #00FFAA !important; }
    [data-testid="stMetricLabel"] { font-weight: bold !important; color: #888888 !important; }
    .stDataFrame { border-radius: 8px; overflow: hidden; box-shadow: 0 4px 15px rgba(0, 255, 170, 0.1); }
    </style>
""", unsafe_allow_html=True)

CONFIG_FILE = "config_draft.json"


def load_saved_username():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f).get("username", "")
    return ""


def save_username(username):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"username": username}, f)


@st.cache_data
def get_league_settings(league_id):
    url = f"https://api.sleeper.app/v1/league/{league_id}"
    res = requests.get(url)
    if res.status_code == 200:
        data = res.json()
        return data.get('scoring_settings', {}), data.get('roster_positions', [])
    return {}, []


@st.cache_data
def get_user_data(username):
    res = requests.get(f"https://api.sleeper.app/v1/user/{username}")
    return res.json().get('user_id') if res.status_code == 200 and res.json() else None


@st.cache_data
def get_nfl_state():
    url = "https://api.sleeper.app/v1/state/nfl"
    res = requests.get(url)
    return res.json() if res.status_code == 200 else {"season": "2026"}


@st.cache_data
def get_user_leagues(user_id):
    season = get_nfl_state().get('season', '2026')
    res = requests.get(f"https://api.sleeper.app/v1/user/{user_id}/leagues/nfl/{season}")
    return res.json() if res.status_code == 200 else []


@st.cache_data
def load_sos_matrix(filepath="nfl_sos_2026.csv"):
    if not os.path.exists(filepath): return {}
    try:
        df_sos = pd.read_csv(filepath, sep=',', quoting=3)
        df_sos.columns = df_sos.columns.str.replace('"', '').str.strip()
        for col in df_sos.columns:
            if df_sos[col].dtype == 'object' or df_sos[col].dtype == 'string':
                df_sos[col] = df_sos[col].astype(str).str.replace('"', '').str.strip()
        for col in df_sos.columns:
            if col != 'Team': df_sos[col] = pd.to_numeric(df_sos[col], errors='coerce')
        df_sos = df_sos.set_index('Team')
        return df_sos.to_dict(orient='index')
    except Exception as e:
        return {}


@st.cache_data
def load_players_dict():
    file_path = "sleeper_players_cache.json"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@st.cache_data
def get_season_projections():
    season = get_nfl_state().get('season', '2026')
    url = f"https://api.sleeper.app/v1/projections/nfl/regular/{season}"
    res = requests.get(url)
    return res.json() if res.status_code == 200 else {}


def get_live_draft_data(draft_id):
    url = f"https://api.sleeper.app/v1/draft/{draft_id}/picks"
    res = requests.get(url)
    return res.json() if res.status_code == 200 else []


@st.cache_data
def get_draft_metadata(draft_id):
    url = f"https://api.sleeper.app/v1/draft/{draft_id}"
    res = requests.get(url)
    return res.json() if res.status_code == 200 else {}


# NOVA FUNÇÃO: Busca todos os jogadores retidos nos elencos da liga (Filtro Dynasty)
@st.cache_data(ttl=300)  # Atualiza a cada 5 min para não sobrecarregar
def get_league_rostered_players(league_id):
    if not league_id: return set()
    url = f"https://api.sleeper.app/v1/league/{league_id}/rosters"
    res = requests.get(url)
    rostered = set()
    if res.status_code == 200:
        for roster in res.json():
            players = roster.get('players')
            if players:
                rostered.update([str(p) for p in players])
    return rostered


# NOVO MOTOR VORP (Agora com suporte a rostered_ids para Dynasty)
def run_vorp_engine(draft_id, my_user_id, players_dict, df_master, translator, projections, scoring_settings=None,
                    roster_positions=None, rostered_ids=None, use_ml=False):
    if roster_positions is None: roster_positions = []
    if rostered_ids is None: rostered_ids = set()

    is_superflex = roster_positions.count('QB') > 1 or 'SUPER_FLEX' in roster_positions
    is_te_premium = scoring_settings and scoring_settings.get('bonus_rec_te', 0.0) > 0

    posicoes_liga = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF', 'DL', 'LB', 'DB', 'DE', 'DT', 'CB', 'S']

    todas_escolhas = get_live_draft_data(draft_id)
    draft_meta = get_draft_metadata(draft_id)

    settings = draft_meta.get('settings') or {}
    num_teams = settings.get('teams', 12)
    if not num_teams or num_teams < 2: num_teams = 12

    drafted_pids = [str(pick.get('player_id')) for pick in todas_escolhas]
    drafted_clean_names = [translator.get(pid) for pid in drafted_pids if translator.get(pid)]

    draft_order = draft_meta.get('draft_order') or {}
    my_slot = draft_order.get(my_user_id)
    if not my_slot:
        for p in todas_escolhas:
            if str(p.get('picked_by')) == str(my_user_id):
                my_slot = p.get('draft_slot')
                break
    if not my_slot: my_slot = 1

    current_pick = len(todas_escolhas) + 1
    current_round = (current_pick - 1) // num_teams + 1

    def get_pick_for_round(r, slot, teams):
        return (r - 1) * teams + slot if r % 2 != 0 else (r - 1) * teams + (teams - slot + 1)

    my_next_pick = get_pick_for_round(current_round, my_slot, num_teams)
    if my_next_pick <= current_pick:
        my_next_pick = get_pick_for_round(current_round + 1, my_slot, num_teams)
    picks_ate_minha_vez = my_next_pick - current_pick

    sos_matrix = load_sos_matrix()

    bye_weeks = {
        'PHI': 10, 'LAC': 7, 'DET': 6, 'TEN': 9, 'KC': 5, 'MIA': 6, 'MIN': 6, 'LAR': 11,
        'DAL': 14, 'CHI': 10, 'LV': 13, 'CAR': 5, 'BAL': 13, 'NYG': 8, 'CLE': 11, 'PIT': 9,
        'SF': 8, 'DEN': 10, 'IND': 13, 'JAX': 7, 'BUF': 7, 'CIN': 6, 'NO': 8, 'ATL': 11,
        'NYJ': 13, 'SEA': 11, 'TB': 10, 'WAS': 7, 'GB': 11, 'HOU': 8, 'ARI': 14, 'NE': 11, 'FA': 0
    }

    # --- 3. CÁLCULO DA LINHA DE BASE (HÍBRIDO FP + SLEEPER) ---
    # --- 3. CÁLCULO DA LINHA DE BASE (HÍBRIDO FP + SLEEPER) ---
    all_players_by_pos = {}
    fp_processed_pids = set()

    # NOVO: Dicionário tradutor inteligente (Nome + Posição) para evitar clones como Lamar Jackson
    inv_translator = {}
    inv_translator_fallback = {}

    for pid_key, p_info in players_dict.items():
        pid_str = str(pid_key)
        clean_n = translator.get(pid_str)
        if not clean_n: continue

        pos_sleeper = p_info.get('position', '')
        inv_translator[(clean_n, pos_sleeper)] = pid_str

        # Fallback: Prioriza jogadores de ataque para casos de homônimos
        if clean_n not in inv_translator_fallback:
            inv_translator_fallback[clean_n] = pid_str
        else:
            old_pid = inv_translator_fallback[clean_n]
            old_pos = players_dict.get(old_pid, {}).get('position', '')
            if pos_sleeper in ['QB', 'RB', 'WR', 'TE'] and old_pos not in ['QB', 'RB', 'WR', 'TE']:
                inv_translator_fallback[clean_n] = pid_str

    # 3.1 Prioriza o FantasyPros (Geralmente Ataque)
    for idx, row in df_master.iterrows():
        pos = row.get('Pos_Base', '')
        if pos == 'DST': pos = 'DEF'
        pts = float(row.get('FPTS', 0.0))
        if pos not in all_players_by_pos: all_players_by_pos[pos] = []
        all_players_by_pos[pos].append(pts)

        match_name = row['Match_Name']
        # Tenta achar o match perfeito de Nome + Posição
        pid = inv_translator.get((match_name, pos))
        if not pid: pid = inv_translator_fallback.get(match_name)

        if pid: fp_processed_pids.add(str(pid))

    for pid, proj in projections.items():
        pid_str = str(pid)
        if pid_str in fp_processed_pids: continue

        p_info = players_dict.get(pid_str, {})
        pos = p_info.get('position', '')
        if not pos: continue

        pts = 0.0
        if scoring_settings:
            for stat_key, multiplier in scoring_settings.items():
                val = proj.get(stat_key, 0.0)
                if val is not None: pts += float(val) * float(multiplier)
        else:
            pts = float(proj.get('pts_ppr', 0.0)) if proj.get('pts_ppr') is not None else 0.0

        if pos not in all_players_by_pos: all_players_by_pos[pos] = []
        all_players_by_pos[pos].append(pts)

    for pos in all_players_by_pos:
        all_players_by_pos[pos].sort(reverse=True)

    req_qb = max(1, roster_positions.count('QB') + roster_positions.count('SUPER_FLEX'))
    req_rb = max(1, roster_positions.count('RB'))
    req_wr = max(1, roster_positions.count('WR'))
    req_te = max(1, roster_positions.count('TE'))
    req_flex = roster_positions.count('FLEX') + roster_positions.count('WRRB_FLEX')

    baseline_ranks = {
        'QB': req_qb * num_teams,
        'RB': max(12, int((req_rb + (req_flex * 0.4)) * num_teams)),
        'WR': max(12, int((req_wr + (req_flex * 0.6)) * num_teams)),
        'TE': req_te * num_teams,
        'DL': max(12, int((roster_positions.count('DL') + roster_positions.count('DE') + roster_positions.count(
            'DT')) * num_teams)),
        'LB': max(12, int(roster_positions.count('LB') * num_teams)),
        'DB': max(12, int((roster_positions.count('DB') + roster_positions.count('CB') + roster_positions.count(
            'S')) * num_teams)),
        'K': max(1, roster_positions.count('K')) * num_teams,
        'DEF': max(1, roster_positions.count('DEF')) * num_teams
    }

    baseline_points_map = {}
    for pos, rank_target in baseline_ranks.items():
        pool = all_players_by_pos.get(pos, [])
        if pool:
            target_idx = min(max(1, rank_target) - 1, len(pool) - 1)
            baseline_points_map[pos] = pool[target_idx]
        else:
            baseline_points_map[pos] = 0.0

    # --- 4. MAPEAMENTO DE ADVERSÁRIOS E HEURÍSTICA DE RISCO ---
    rosters_by_slot = {i: {p: 0 for p in posicoes_liga} for i in range(1, num_teams + 1)}
    for i in rosters_by_slot: rosters_by_slot[i]['Players'] = []

    for pick in todas_escolhas:
        slot = pick.get('draft_slot')
        pid = str(pick.get('player_id'))
        p_info = players_dict.get(pid, {})
        pos = p_info.get('position', '')
        if slot in rosters_by_slot:
            if pos in rosters_by_slot[slot]: rosters_by_slot[slot][pos] += 1
            rosters_by_slot[slot]['Players'].append(f"{p_info.get('full_name', 'Desconhecido')} ({pos})")

    slots_between = []
    for p in range(current_pick, my_next_pick):
        r = (p - 1) // num_teams + 1
        pos_in_round = (p - 1) % num_teams + 1
        slot = pos_in_round if r % 2 != 0 else num_teams - pos_in_round + 1
        slots_between.append(slot)

    threat_level = {p: 0 for p in posicoes_liga}
    threat_pct = {p: 0 for p in posicoes_liga}

    if picks_ate_minha_vez > 0:
        demand_urgency = {p: 0.0 for p in posicoes_liga}
        for slot in slots_between:
            roster_adv = rosters_by_slot.get(slot, {})
            for pos in posicoes_liga:
                have = roster_adv.get(pos, 0)
                need = baseline_ranks.get(pos, 1) // num_teams
                if have == 0:
                    demand_urgency[pos] += 1.0
                elif have < need:
                    demand_urgency[pos] += 0.4
                elif have >= need:
                    demand_urgency[pos] += 0.1

        ultimos_5 = todas_escolhas[-5:] if len(todas_escolhas) >= 5 else todas_escolhas
        momentum_count = {p: 0 for p in posicoes_liga}
        for pick in ultimos_5:
            pos_pick = players_dict.get(str(pick.get('player_id')), {}).get('position', 'UNKNOWN')
            if pos_pick in momentum_count: momentum_count[pos_pick] += 1

        total_slots = len(slots_between)
        for pos in posicoes_liga:
            if pos in ['K', 'DEF']: continue
            base_risk = (demand_urgency[pos] / total_slots) * 60 if total_slots > 0 else 0
            manada_bonus = momentum_count[pos] * 12
            threat_pct[pos] = min(99, int(base_risk + manada_bonus))

    # --- 5. MEU ELENCO ---
    my_roster_counts = {p: 0 for p in posicoes_liga}
    my_roster_byes = {}
    meu_time_detalhado = []

    for pick in todas_escolhas:
        if str(pick.get('picked_by')) == str(my_user_id):
            pid = str(pick.get('player_id'))
            clean_n = translator.get(pid, "")

            p_info = players_dict.get(pid, {})
            pos = p_info.get('position', '')
            team = p_info.get('team', 'FA')
            nome = p_info.get('full_name', 'Desconhecido')
            bw = bye_weeks.get(team, 0)

            pick_num = pick.get('pick_no', 0)

            row_fp = df_master[df_master['Match_Name'] == clean_n]
            if not row_fp.empty:
                pts = float(row_fp.iloc[0].get('FPTS', 0.0))

                adp = pick_num
                if 'ECR VS. ADP' in row_fp.columns and pd.notna(row_fp.iloc[0]['ECR VS. ADP']):
                    val_str = str(row_fp.iloc[0]['ECR VS. ADP']).strip()
                    if val_str != '-' and val_str != '':
                        try:
                            adp = pick_num - float(val_str)
                        except ValueError:
                            pass
            else:
                proj = projections.get(pid, {})
                pts = 0.0
                if scoring_settings:
                    for stat_key, multiplier in scoring_settings.items():
                        val = proj.get(stat_key, 0.0)
                        if val is not None: pts += float(val) * float(multiplier)
                else:
                    pts = float(proj.get('pts_ppr', 0.0)) if proj.get('pts_ppr') is not None else 0.0
                adp = pick_num

            gap = adp - pick_num

            if pos in my_roster_counts: my_roster_counts[pos] += 1
            if bw > 0: my_roster_byes[bw] = my_roster_byes.get(bw, 0) + 1

            meu_time_detalhado.append({
                "Pick": pick_num, "Nome": nome, "Pos": pos, "Bye": f"Sem {bw}",
                "Proj": round(pts, 1), "ADP": round(adp, 1), "Custo/Ben": round(gap, 1)
            })

    # --- 6. MULTIPLICADORES DE ELENCO ---
    def build_multiplier(req_base, req_flx=0):
        res = {}
        for i in range(15):
            if i < req_base:
                res[i] = 1.0
            elif i < req_base + req_flx:
                res[i] = 0.7
            else:
                res[i] = max(0.0, 0.4 - ((i - (req_base + req_flx)) * 0.1))
        return res

    multipliers = {
        'RB': build_multiplier(roster_positions.count('RB'), req_flex),
        'WR': build_multiplier(roster_positions.count('WR'), req_flex),
        'TE': build_multiplier(roster_positions.count('TE')),
        'DL': build_multiplier(roster_positions.count('DL'), roster_positions.count('IDP_FLEX')),
        'LB': build_multiplier(roster_positions.count('LB'), roster_positions.count('IDP_FLEX')),
        'DB': build_multiplier(roster_positions.count('DB'), roster_positions.count('IDP_FLEX')),
        'K': build_multiplier(roster_positions.count('K')),
        'DEF': build_multiplier(roster_positions.count('DEF'))
    }

    if is_superflex:
        multipliers['QB'] = {0: 1.2, 1: 1.0, 2: 0.3}
        for i in range(3, 15): multipliers['QB'][i] = 0.0
    else:
        multipliers['QB'] = {0: 1.0, 1: 0.3}
        for i in range(2, 15): multipliers['QB'][i] = 0.0

    if is_te_premium: multipliers['TE'] = {i: 1.1 if i < roster_positions.count('TE') else 0.8 for i in range(15)}

    # --- 7. MONTAGEM DAS RECOMENDAÇÕES (HÍBRIDA) ---
    available_players = []
    added_to_board = set()
    nomes_processados = set()

    df_master_unique = df_master.drop_duplicates(subset=['Match_Name'])

    # 7.1 Varre o FantasyPros
    for idx, row in df_master_unique.iterrows():
        match_name = row['Match_Name']
        if match_name in drafted_clean_names or match_name in nomes_processados: continue

        pos = row.get('Pos_Base', '')
        if pos == 'DST': pos = 'DEF'
        if not pos or pos not in baseline_ranks: continue

        # ESCUDO ANTI-CLONE (Homônimos): Pega o ID batendo Nome + Posição
        pid = inv_translator.get((match_name, pos))
        if not pid: pid = inv_translator_fallback.get(match_name, "0")

        # ESCUDO DYNASTY: Ignora o jogador se ele já estiver no elenco de alguém
        if pid in rostered_ids: continue

        time_jogador = row.get('Team', 'FA')
        nome_jogador = row.get('Player', 'Desconhecido')

        pts = float(row.get('FPTS', 0.0))
        tier_oficial = row.get('TIERS', 99)
        red_zone = row.get('RZ_Targets', 0.0)

        sos_modifier = sos_matrix.get(time_jogador, {}).get(pos, 1.0)
        pts_ajustado = pts * sos_modifier

        if pts_ajustado > 20.0:
            bw = bye_weeks.get(time_jogador, 0)
            alerta_bye = f"⚠️ Folga Sem {bw}" if my_roster_byes.get(bw, 0) >= 2 else f"Sem {bw}"

            adp_jogador = current_pick + 10
            if 'ECR VS. ADP' in row and pd.notna(row['ECR VS. ADP']):
                val_str = str(row['ECR VS. ADP']).strip()
                if val_str != '-' and val_str != '':
                    try:
                        adp_jogador = current_pick - float(val_str)
                    except ValueError:
                        pass
            
            # Distorção visual do ADP para refletir SF e TEP na War Room
            if is_superflex and pos == 'QB':
                adp_jogador = (adp_jogador * 0.35) - 5
            if is_te_premium and pos == 'TE':
                adp_jogador = (adp_jogador * 0.75) - 2
            adp_jogador = max(1.0, adp_jogador)

            diferenca_adp = current_pick - adp_jogador
            risco_base_pos = threat_pct.get(pos, 0)

            if diferenca_adp > 4:
                risco_calculado = min(99, risco_base_pos + 40)
            elif diferenca_adp < -24:
                risco_calculado = max(0, risco_base_pos - 40)
            elif diferenca_adp < -12:
                risco_calculado = max(0, risco_base_pos - 20)
            else:
                risco_calculado = risco_base_pos

            # --- FANTASY POINTS LEAGUE WINNER NARRATIVES ---
            if pos == 'RB':
                n_clean = match_name.lower()
                if n_clean in ["chase brown", "ashton jeanty", "omarion hampton", "kenneth walker", "cam skattebo"]:
                    nome_jogador = f"🏆 {nome_jogador}"
                    risco_calculado = max(0, risco_calculado - 30)
                elif n_clean in ["devon achane", "de'von achane", "saquon barkley"]:
                    nome_jogador = f"🚨 {nome_jogador}"
                    risco_calculado = min(99, risco_calculado + 40)
                elif n_clean in ["breece hall"]:
                    nome_jogador = f"⚠️ {nome_jogador}"

            base_pts = baseline_points_map.get(pos, 0.0)
            vorp_bruto = pts_ajustado - base_pts

            qtd_atual = my_roster_counts.get(pos, 0)
            mult = multipliers.get(pos, {}).get(qtd_atual, 0.1)
            vorp_pessoal = vorp_bruto * mult if vorp_bruto > 0 else vorp_bruto

            added_to_board.add(str(pid))
            nomes_processados.add(match_name)

            available_players.append({
                'Foto': f"https://sleepercdn.com/content/nfl/players/thumb/{pid}.jpg",
                'ID': pid, 'Nome': nome_jogador, 'Pos': pos, 'Time': time_jogador,
                'Bye': alerta_bye, 'ADP': adp_jogador, 'Custo/Ben': diferenca_adp,
                'Risco': risco_calculado, 'Pts': pts_ajustado, 'RZ_Vol': red_zone,
                'VORP_Bruto': vorp_bruto, 'VORP': vorp_pessoal, 'Tier': tier_oficial
            })

    # 7.2 Varre o Sleeper para incluir IDP e Kickers
    for pid, proj in projections.items():
        pid_str = str(pid)
        # ESCUDO DYNASTY + Escudo Anti-Clone
        if pid_str in fp_processed_pids or pid_str in drafted_pids or pid_str in added_to_board or pid_str in rostered_ids: continue

        p_info = players_dict.get(pid_str, {})
        pos = p_info.get('position', '')
        if not pos or pos not in baseline_ranks: continue

        nome_jogador = p_info.get('full_name', 'Desconhecido')
        clean_n = translator.get(pid_str, nome_jogador.lower().strip())

        if clean_n in drafted_clean_names or clean_n in nomes_processados: continue

        pts = 0.0
        if scoring_settings:
            for stat_key, multiplier in scoring_settings.items():
                val = proj.get(stat_key, 0.0)
                if val is not None: pts += float(val) * float(multiplier)
        else:
            pts = float(proj.get('pts_ppr', 0.0)) if proj.get('pts_ppr') is not None else 0.0

        time_jogador = p_info.get('team', 'FA')
        sos_modifier = sos_matrix.get(time_jogador, {}).get(pos, 1.0)
        pts_ajustado = pts * sos_modifier

        if pts_ajustado > 20.0:
            bw = bye_weeks.get(time_jogador, 0)
            alerta_bye = f"⚠️ Folga Sem {bw}" if my_roster_byes.get(bw, 0) >= 2 else f"Sem {bw}"

            adp_jogador = current_pick
            
            if is_superflex and pos == 'QB':
                adp_jogador = (adp_jogador * 0.35) - 5
            if is_te_premium and pos == 'TE':
                adp_jogador = (adp_jogador * 0.75) - 2
            adp_jogador = max(1.0, adp_jogador)
            
            diferenca_adp = current_pick - adp_jogador
            risco_calculado = threat_pct.get(pos, 0)
            
            # --- FANTASY POINTS LEAGUE WINNER NARRATIVES ---
            if pos == 'RB':
                n_clean = clean_n.lower()
                if n_clean in ["chase brown", "ashton jeanty", "omarion hampton", "kenneth walker", "cam skattebo"]:
                    nome_jogador = f"🏆 {nome_jogador}"
                    risco_calculado = max(0, risco_calculado - 30)
                elif n_clean in ["devon achane", "de'von achane", "saquon barkley"]:
                    nome_jogador = f"🚨 {nome_jogador}"
                    risco_calculado = min(99, risco_calculado + 40)
                elif n_clean in ["breece hall"]:
                    nome_jogador = f"⚠️ {nome_jogador}"

            base_pts = baseline_points_map.get(pos, 0.0)
            vorp_bruto = pts_ajustado - base_pts

            if pos in ['DL', 'LB', 'DB', 'DE', 'DT', 'CB', 'S']:
                vorp_bruto = vorp_bruto * 0.4

            qtd_atual = my_roster_counts.get(pos, 0)
            mult = multipliers.get(pos, {}).get(qtd_atual, 0.1)
            vorp_pessoal = vorp_bruto * mult if vorp_bruto > 0 else vorp_bruto

            nomes_processados.add(clean_n)

            available_players.append({
                'Foto': f"https://sleepercdn.com/content/nfl/players/thumb/{pid_str}.jpg",
                'ID': pid_str, 'Nome': nome_jogador, 'Pos': pos, 'Time': time_jogador,
                'Bye': alerta_bye, 'ADP': adp_jogador, 'Custo/Ben': diferenca_adp,
                'Risco': risco_calculado, 'Pts': pts_ajustado, 'RZ_Vol': 0.0,
                'VORP_Bruto': vorp_bruto, 'VORP': vorp_pessoal, 'Tier': 99
            })

    df = pd.DataFrame(available_players)
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(meu_time_detalhado), my_roster_counts, len(
            todas_escolhas), picks_ate_minha_vez, threat_level, rosters_by_slot, draft_meta

    max_vorp = df['VORP'].max()
    
    # --- INJEÇÃO DA INTELIGÊNCIA ARTIFICIAL ---
    if use_ml:
        try:
            df = add_algorithmic_tiers(df)
            rf_model = get_breakout_predictor_model()
            pos_map = {'QB': 0, 'RB': 1, 'TE': 2, 'WR': 3}
            pos_encoded = df['Pos'].map(pos_map).fillna(3)
            X_pred = pd.DataFrame({'Age': 25, 'Custo/Ben': df['Custo/Ben'], 'Risco': df['Risco'], 'Pos_Encoded': pos_encoded})
            df['🔥 Breakout %'] = (rf_model.predict_proba(X_pred)[:, 1] * 100).round(1)
        except Exception:
            df['AI_Tier'] = df['Tier']
            df['🔥 Breakout %'] = 0.0
    else:
        df['AI_Tier'] = df['Tier']
        df['🔥 Breakout %'] = 0.0

    if max_vorp > 0:
        df['Nota_Calc'] = (df['VORP'] / max_vorp) * 10.0
    else:
        df['Nota_Calc'] = 1.0

    df.loc[df['Custo/Ben'] < -12, 'Nota_Calc'] -= 2.0
    df.loc[(df['Custo/Ben'] > 5) & (df['Risco'] > 50), 'Nota_Calc'] += 1.5
    
    if use_ml:
        df.loc[df['🔥 Breakout %'] > 60.0, 'Nota_Calc'] += 1.5
        
    df['Nota_Calc'] = df['Nota_Calc'].clip(lower=1.0, upper=10.0).round(1)

    def format_nota(n):
        if n >= 8.5:
            return f"🔥 {n}"
        elif n >= 7.0:
            return f"👍 {n}"
        elif n >= 5.0:
            return f"🤔 {n}"
        else:
            return f"⚠️ {n}"

    df['Nota'] = df['Nota_Calc'].apply(format_nota)
    df_recomendacoes = df.sort_values(by=['Nota_Calc', 'VORP'], ascending=[False, False])

    return (df_recomendacoes, pd.DataFrame(meu_time_detalhado), my_roster_counts, len(todas_escolhas),
            picks_ate_minha_vez, threat_level, rosters_by_slot, draft_meta)


# --- INTERFACE VISUAL ---
st.title("🤖 Draft War Room (Live Pro)")

st.sidebar.header("⚙️ Configuração da Conta")
saved_user = load_saved_username()
username = st.sidebar.text_input("Username (Sleeper)", value=saved_user)

if username and username != saved_user: save_username(username)

if username:
    user_id = get_user_data(username)
    if user_id:
        st.sidebar.success("Usuário conectado!")
        st.sidebar.markdown("---")
        modo_draft = st.sidebar.radio("Tipo de Conexão", ["Ligas Oficiais", "Mock Draft Manual"])
        draft_id = None
        league_id = None

        if modo_draft == "Ligas Oficiais":
            leagues = get_user_leagues(user_id)
            if leagues:
                league_options = {l['name']: {'draft_id': l.get('draft_id'), 'league_id': l.get('league_id')} for l in
                                  leagues if l.get('draft_id')}
                if league_options:
                    selected_league = st.sidebar.selectbox("Selecione sua Liga", list(league_options.keys()))
                    draft_id = league_options[selected_league]['draft_id']
                    league_id = league_options[selected_league]['league_id']
                    scoring_settings, roster_positions = get_league_settings(league_id)
                else:
                    st.sidebar.warning("Nenhum draft configurado nas suas ligas atuais.")
            else:
                st.sidebar.warning("Nenhuma liga encontrada.")
        else:
            draft_id = st.sidebar.text_input("Insira o ID do Mock Draft", value="1388956246383554560")
            leagues = get_user_leagues(user_id)
            if leagues:
                league_options = {l['name']: l['league_id'] for l in leagues}
                selected_rule_league = st.sidebar.selectbox("Herdar pontuação da liga:", list(league_options.keys()))
                league_id = league_options[selected_rule_league]
                scoring_settings, roster_positions = get_league_settings(league_id)
            else:
                scoring_settings, roster_positions = None, None

        st.sidebar.markdown("---")
        # NOVO: O Toggle Manual para limpar os Rookies Drafts
        is_dynasty_mode = st.sidebar.checkbox("👑 Ocultar jogadores já em elencos (Dynasty)", value=False,
                                              help="Remove da lista de recomendados qualquer veterano que já pertença a algum time nesta liga.")
                                              
        is_ml_mode = st.sidebar.checkbox("🤖 Ativar Módulo Preditivo de IA", value=False,
                                         help="Usa K-Means para reorganizar as Tiers e Random Forest para prever a chance de Breakout.")

        st.sidebar.markdown("---")
        auto_refresh = st.sidebar.checkbox("🔴 Habilitar Live Sync")

        if draft_id:
            # INICIALIZAÇÃO SEGURA DO SESSION STATE (Evita qualquer erro de atributo)
            if 'total_picks' not in st.session_state:
                st.session_state.total_picks = -1
            if 'dados_cache' not in st.session_state:
                st.session_state.dados_cache = None
            if 'last_dynasty_toggle' not in st.session_state:
                st.session_state.last_dynasty_toggle = False

            with st.spinner("Carregando Dados (FP + Sleeper)..."):
                df_master = load_master_dataframe()
                translator = get_sleeper_translator()
                players_dict = load_players_dict()
                projections = get_season_projections()

            picks_atuais = get_live_draft_data(draft_id)
            qtd_picks_atuais = len(picks_atuais)

            # Compara com segurança usando as variáveis já garantidas
            if (qtd_picks_atuais != st.session_state.total_picks) or (
                    is_dynasty_mode != st.session_state.last_dynasty_toggle) or (
                    'last_ml_toggle' not in st.session_state or is_ml_mode != st.session_state.last_ml_toggle):
                with st.spinner("Calculando Heurísticas e Lendo Elencos..."):
                    rostered_ids = get_league_rostered_players(league_id) if is_dynasty_mode and league_id else set()

                    df_rec, df_meu_time, counts, _, picks_dist, threat, adversarios, draft_meta = run_vorp_engine(
                        draft_id, user_id, players_dict, df_master, translator, projections, scoring_settings,
                        roster_positions, rostered_ids, is_ml_mode)

                    st.session_state.last_ml_toggle = is_ml_mode
                    st.session_state.dados_cache = (df_rec, df_meu_time, counts, picks_dist, threat, adversarios,
                                                    draft_meta)
                    st.session_state.total_picks = qtd_picks_atuais
                    st.session_state.last_dynasty_toggle = is_dynasty_mode
            else:
                df_rec, df_meu_time, counts, picks_dist, threat, adversarios, draft_meta = st.session_state.dados_cache

            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Status do Draft", f"{st.session_state.total_picks} Escolhas")
            col_m2.metric("Sua Próxima Escolha em:", f"{picks_dist} picks" if picks_dist > 0 else "AGORA!")
            roster_str = " ".join([f"{k}:{v}" for k, v in counts.items() if v > 0])
            col_m3.metric("Seu Roster", roster_str if roster_str else "Vazio")

            st.markdown("---")
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "🎯 War Room", "👥 Adversários", "📊 Meu Elenco", "⚙️ Regras da Liga", "🏆 Pós-Draft (Review)"
            ])

            with tab1:
                st.subheader("Filtros de Posição")
                ordem_oficial = ["QB", "RB", "WR", "TE", "K", "DEF", "DL", "LB", "DB", "CB", "S"]
                opcoes_validas = [p for p in ordem_oficial if p in df_rec['Pos'].unique()] if not df_rec.empty else [
                    "QB", "RB", "WR", "TE"]
                opcoes_padrao = [p for p in ["QB", "RB", "WR", "TE"] if p in opcoes_validas]

                filtro_pos = st.multiselect("Quais posições você quer analisar?", options=opcoes_validas,
                                            default=opcoes_padrao)

                if not df_rec.empty:
                    df_filtrado = df_rec[df_rec['Pos'].isin(filtro_pos)].head(50)
                    
                    cols_to_show = ['AI_Tier', 'Nota', 'Foto', 'Pos', 'Nome', 'Bye', 'ADP', 'Custo/Ben', '🔥 Breakout %', 'Risco', 'RZ_Vol', 'VORP']
                    
                    event = st.dataframe(
                        df_filtrado[cols_to_show]
                        .style.background_gradient(cmap='viridis', subset=['VORP'])
                        .background_gradient(cmap='RdYlGn', subset=['Custo/Ben']),
                        column_config={
                            "AI_Tier": st.column_config.NumberColumn("🧠 AI Tier", format="%d", help="Tier gerado via K-Means Clustering"),
                            "Nota": st.column_config.TextColumn("⭐ Rating", help="Nota Tática Integrada (1 a 10)"),
                            "Foto": st.column_config.ImageColumn("Player", help="Foto oficial"),
                            "Bye": st.column_config.TextColumn("📅 Folga"),
                            "ADP": st.column_config.NumberColumn("🎯 ADP", format="%.1f"),
                            "Custo/Ben": st.column_config.NumberColumn("⚖️ Gap",
                                                                       help="+ Positivo = Steal / - Negativo = Reach",
                                                                       format="%+.1f"),
                            "🔥 Breakout %": st.column_config.ProgressColumn("🔥 Breakout", format="%.1f%%", min_value=0.0, max_value=100.0, help="Predição via Random Forest"),
                            "Risco": st.column_config.ProgressColumn("🚨 Risco Real", format="%d%%", min_value=0,
                                                                     max_value=100),
                            "RZ_Vol": st.column_config.NumberColumn("🔴 RZ", help="Toques na Red Zone (Teto)",
                                                                    format="%d"),
                            "VORP": st.column_config.NumberColumn("🔥 VORP", format="%.1f")
                        },
                        width='stretch', hide_index=True, height=650,
                        on_select="rerun", selection_mode="single-row"
                    )
                    
                    if hasattr(event, 'selection') and len(event.selection.rows) > 0:
                        selected_idx = event.selection.rows[0]
                        sp = df_filtrado.iloc[selected_idx]
                        
                        st.markdown("---")
                        st.subheader(f"🔍 Auditoria Matemática: {sp['Nome']}")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.info(f"**A Matemática do VORP (Value Over Replacement)**\n\n"
                                    f"A projeção bruta deste jogador é **{sp['Pts']:.1f} pts**.\n"
                                    f"A linha de base (o último titular projetado que sobrará na waiver para a posição {sp['Pos']}) projeta fazer **{(sp['Pts'] - sp['VORP_Bruto']):.1f} pts**.\n\n"
                                    f"O *VORP Bruto* gerado por ele é a diferença: **{sp['VORP_Bruto']:.1f} pts extras**. \n\n"
                                    f"Ajustando pela necessidade do seu elenco atual, o VORP final disparou para **{sp['VORP']:.1f}**.")
                        with col2:
                            if is_ml_mode:
                                st.success(f"**A Mente da IA (Random Forest)**\n\n"
                                           f"A IA previu **{sp['🔥 Breakout %']}%** de chance de Breakout por causa dos seguintes fatores injetados no modelo:\n\n"
                                           f"- **O Gap de Preço (Custo/Ben)** dele é **{sp['Custo/Ben']:+.1f}**.\n"
                                           f"- **O Risco Sistêmico** é de **{sp['Risco']}%**.\n"
                                           f"- *Notas > 60% ganham um bônus multiplicativo na nota final da estrela.*")
                            else:
                                st.warning("Ative o Módulo Preditivo de IA no menu lateral para ler a justificativa do modelo preditivo.")
                else:
                    st.warning("Calculando recomendações...")

            with tab2:
                st.subheader("Elencos por Slot de Draft")
                cols = st.columns(4)
                idx = 0
                for slot, data in adversarios.items():
                    with cols[idx % 4]:
                        with st.container(border=True):
                            st.markdown(f"**Slot {slot}**")
                            resumo_roster = " | ".join(
                                [f"{p}: {v}" for p, v in data.items() if p != 'Players' and v > 0])
                            st.caption(resumo_roster)
                            for p in data['Players']: st.text(f"• {p}")
                    idx += 1

            with tab3:
                if not df_meu_time.empty:
                    st.dataframe(
                        df_meu_time.style.background_gradient(cmap='RdYlGn', subset=['Custo/Ben']),
                        width='stretch', hide_index=True
                    )
                else:
                    st.info("Sua fila está vazia.")

            with tab4:
                st.subheader("Pontuação e Configurações")
                if scoring_settings:
                    from collections import Counter
                    roster_counts = Counter(roster_positions)
                    roster_badges = " ".join([f"<span style='background-color:#1e3a8a; padding:6px 12px; border-radius:6px; margin-right:8px; display:inline-block; margin-bottom:8px;'><b>{count}x</b> {pos}</span>" for pos, count in roster_counts.items()])
                    st.markdown(f"**Posições Ativas:**<br><br>{roster_badges}", unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    def format_scoring_key(key):
                        mapping = {
                            "pass_yd": "Jardas de Passe (Por Jarda)",
                            "pass_td": "TD de Passe",
                            "pass_int": "Passe Interceptado",
                            "rush_yd": "Jardas Terrestres (Por Jarda)",
                            "rush_td": "TD Terrestre",
                            "rec_yd": "Jardas de Recepção (Por Jarda)",
                            "rec_td": "TD de Recepção",
                            "rec": "Recepção (PPR)",
                            "bonus_rec_te": "Bônus de Recepção TE (TE Premium)",
                            "sack": "Sack Sofrido (Ataque) / Sack Defensivo",
                            "def_st_td": "TD de Defesa/Especiais",
                            "def_st_ff": "Fumble Forçado (Defesa)",
                            "def_st_fum_rec": "Fumble Recuperado (Defesa)",
                            "def_td": "TD Defensivo",
                            "int": "Interceptação (Defesa)",
                            "fum_rec": "Fumble Recuperado",
                            "fum_lost": "Fumble Perdido",
                            "pts_allow_0": "Pontos Cedidos: 0",
                            "pts_allow_1_6": "Pontos Cedidos: 1-6",
                            "pts_allow_7_13": "Pontos Cedidos: 7-13",
                            "pts_allow_14_20": "Pontos Cedidos: 14-20",
                            "pts_allow_21_27": "Pontos Cedidos: 21-27",
                            "pts_allow_28_34": "Pontos Cedidos: 28-34",
                            "pts_allow_35p": "Pontos Cedidos: 35+",
                            "fgm": "Field Goal Feito",
                            "fgm_0_19": "FG (0-19 Jardas)",
                            "fgm_20_29": "FG (20-29 Jardas)",
                            "fgm_30_39": "FG (30-39 Jardas)",
                            "fgm_40_49": "FG (40-49 Jardas)",
                            "fgm_50p": "FG (50+ Jardas)",
                            "fgmiss": "FG Perdido",
                            "xpm": "Extra Point Feito",
                            "xpmiss": "Extra Point Perdido",
                            "pass_2pt": "Conversão 2 Pontos (Passe)",
                            "rush_2pt": "Conversão 2 Pontos (Corrida)",
                            "rec_2pt": "Conversão 2 Pontos (Recepção)",
                            "idp_tkl": "Tackle (IDP)",
                            "idp_tkl_ast": "Assistência Tackle (IDP)",
                            "idp_sack": "Sack (IDP)",
                            "idp_int": "Interceptação (IDP)",
                            "idp_ff": "Fumble Forçado (IDP)",
                            "idp_fum_rec": "Fumble Recuperado (IDP)",
                            "idp_pass_def": "Passe Defendido (IDP)",
                            "idp_blk_kick": "Chute Bloqueado (IDP)",
                            "idp_safe": "Safety (IDP)",
                            "st_td": "TD Special Teams",
                            "safe": "Safety (Defesa)"
                        }
                        if key in mapping: return mapping[key]
                        return key.replace("_", " ").title()

                    formatted_scoring = {format_scoring_key(k): v for k, v in scoring_settings.items()}
                    df_scoring = pd.DataFrame(list(formatted_scoring.items()), columns=["Métrica", "Pontos"])
                    
                    st.dataframe(df_scoring, width='stretch', hide_index=True)
                else:
                    st.info("Nenhuma regra de pontuação carregada.")

            with tab5:
                st.subheader("Avaliação Pós-Draft")
                status = draft_meta.get('status', '')
                if status == 'complete' or st.session_state.total_picks >= (
                        len(roster_positions) * draft_meta.get('settings', {}).get('teams', 12)):
                    st.success("🎉 Draft Finalizado! Confira a sua análise:")
                    if not df_meu_time.empty:
                        total_pts = df_meu_time['Proj'].sum()
                        st.metric("Poder Total Projetado", f"{total_pts:.1f} Pts")
                        best_pick = df_meu_time.loc[df_meu_time['Custo/Ben'].idxmax()]
                        worst_pick = df_meu_time.loc[df_meu_time['Custo/Ben'].idxmin()]
                        col1, col2 = st.columns(2)
                        col1.info(f"🏆 **Maior Roubo (Steal):** {best_pick['Nome']} (+{best_pick['Custo/Ben']} Picks)")
                        col2.warning(
                            f"⚠️ **Maior Forçação (Reach):** {worst_pick['Nome']} ({worst_pick['Custo/Ben']} Picks)")
                        st.dataframe(df_meu_time.style.background_gradient(cmap='RdYlGn', subset=['Custo/Ben']),
                                     width='stretch', hide_index=True)
                    else:
                        st.info("O seu elenco está vazio.")
                else:
                    st.info("⏳ O Draft ainda está em andamento.")

            if auto_refresh:
                time.sleep(3)
                st.rerun()
    else:
        st.sidebar.error("Usuário não encontrado.")
else:
    st.info("👈 Digite seu nome de usuário na barra lateral.")