import requests
import json
import os
import pandas as pd


def load_players_dict():
    file_path = "sleeper_players_cache.json"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_drafted_players(draft_id):
    url = f"https://api.sleeper.app/v1/draft/{draft_id}/picks"
    response = requests.get(url)
    if response.status_code == 200:
        # Retorna uma lista apenas com os IDs dos jogadores já escolhidos
        return [str(pick.get('player_id')) for pick in response.json()]
    return []


def get_season_projections(season="2025"):
    # Note que não passamos a "week", isso traz a projeção do ANO INTEIRO
    url = f"https://api.sleeper.app/v1/projections/nfl/regular/{season}"
    return requests.get(url).json()


def get_my_drafted_players(draft_id, my_user_id):
    # Nova função para pegar apenas as SUAS escolhas
    url = f"https://api.sleeper.app/v1/draft/{draft_id}/picks"
    response = requests.get(url).json()
    my_picks = []
    for pick in response:
        if str(pick.get('picked_by')) == str(my_user_id):
            my_picks.append(str(pick.get('player_id')))
    return my_picks


def calculate_vorp(draft_id, my_user_id):
    print("1. Coletando dados em tempo real...")
    players_dict = load_players_dict()

    url = f"https://api.sleeper.app/v1/draft/{draft_id}/picks"
    todas_escolhas = requests.get(url).json()
    drafted_ids = [str(pick.get('player_id')) for pick in todas_escolhas]

    # Isola o seu time atual no draft
    my_roster_ids = [str(pick.get('player_id')) for pick in todas_escolhas if
                     str(pick.get('picked_by')) == str(my_user_id)]

    projections = get_season_projections("2025")

    # 2. CONSTRUÇÃO DO CONTEXTO DE ROSTER
    my_roster_counts = {'QB': 0, 'RB': 0, 'WR': 0, 'TE': 0}
    for pid in my_roster_ids:
        pos = players_dict.get(pid, {}).get('position', '')
        if pos in my_roster_counts:
            my_roster_counts[pos] += 1

    print(
        f"\n[Análise do Seu Time] RBs: {my_roster_counts['RB']} | WRs: {my_roster_counts['WR']} | QBs: {my_roster_counts['QB']} | TEs: {my_roster_counts['TE']}")

    # Matriz de Punição (Diminishing Returns)
    # Se você já tem X jogadores da posição, o VORP dos próximos é multiplicado por Y
    multipliers = {
        'QB': {0: 1.0, 1: 0.2, 2: 0.05},  # Ex: Se já tem 1 QB, não precisa de outro cedo
        'RB': {0: 1.0, 1: 0.95, 2: 0.6, 3: 0.4},
        'WR': {0: 1.0, 1: 0.95, 2: 0.8, 3: 0.6, 4: 0.4},
        'TE': {0: 1.0, 1: 0.3, 2: 0.1}
    }

    baseline_ranks = {'QB': 12, 'RB': 36, 'WR': 40, 'TE': 12}

    print("3. Removendo draftados e calculando projeções...")
    available_players = []

    for pid, proj in projections.items():
        if pid in drafted_ids:
            continue

        p_info = players_dict.get(pid, {})
        pos = p_info.get('position', '')

        if pos not in baseline_ranks:
            continue

        pts = proj.get('pts_ppr', 0.0)
        pts = float(pts) if pts is not None else 0.0

        if pts > 20.0:
            available_players.append({
                'ID': pid,
                'Nome': p_info.get('full_name', 'Desconhecido'),
                'Posição': pos,
                'Time': p_info.get('team', 'FA'),
                'Pts_Projetados': pts
            })

    df = pd.DataFrame(available_players)
    if df.empty:
        print("Erro: A tabela está vazia.")
        return

    print("4. Calculando VORP com Inteligência de Contexto (Diminishing Returns)...")
    df['VORP_Bruto'] = 0.0
    df['VORP_Ajustado'] = 0.0

    for pos, rank_baseline in baseline_ranks.items():
        df_pos = df[df['Posição'] == pos].sort_values(by='Pts_Projetados', ascending=False)

        if not df_pos.empty:
            idx_baseline = min(rank_baseline - 1, len(df_pos) - 1)
            baseline_points = df_pos.iloc[idx_baseline]['Pts_Projetados']

            # Cálculo Bruto
            df.loc[df['Posição'] == pos, 'VORP_Bruto'] = df['Pts_Projetados'] - baseline_points

            # Aplicação do Multiplicador de Contexto
            qtd_atual = my_roster_counts[pos]
            mult = multipliers[pos].get(qtd_atual, 0.1)  # Se estourou o limite, o peso é quase 0

            # Se o VORP bruto for negativo (jogador pior que o baseline), não multiplica, mantém negativo
            df.loc[(df['Posição'] == pos) & (df['VORP_Bruto'] > 0), 'VORP_Ajustado'] = df['VORP_Bruto'] * mult
            df.loc[(df['Posição'] == pos) & (df['VORP_Bruto'] <= 0), 'VORP_Ajustado'] = df['VORP_Bruto']

    df_recomendacoes = df.sort_values(by='VORP_Ajustado', ascending=False).head(10)

    print("\n================ TÁTICA DE DRAFT (ADAPTADA AO SEU ELENCO) ================")
    print(df_recomendacoes[['Nome', 'Posição', 'Pts_Projetados', 'VORP_Ajustado', 'VORP_Bruto']].to_string(index=False))
    print("==========================================================================")


if __name__ == "__main__":
    DRAFT_ID = "1388956246383554560"
    # ATENÇÃO: Substitua pelo SEU ID numérico de usuário do Sleeper
    MY_USER_ID = "1127629625020121088"

    calculate_vorp(DRAFT_ID, MY_USER_ID)