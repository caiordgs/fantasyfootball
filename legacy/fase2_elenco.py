import requests
import pandas as pd
import json
import os


def get_sleeper_players():
    # Caminho do arquivo de cache local
    file_path = "sleeper_players_cache.json"

    # Se o arquivo já existe, carrega do disco (muito mais rápido)
    if os.path.exists(file_path):
        print("Carregando dicionário de jogadores do cache local...")
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    print("Baixando dicionário do Sleeper (Isso pode demorar alguns segundos, arquivo grande)...")
    response = requests.get("https://api.sleeper.app/v1/players/nfl")
    players_data = response.json()

    # Salva no disco para as próximas execuções
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(players_data, f)

    return players_data


def get_my_roster(league_id, user_id, players_data):
    print(f"\nBuscando elencos da liga {league_id}...")
    rosters_url = f"https://api.sleeper.app/v1/league/{league_id}/rosters"
    rosters = requests.get(rosters_url).json()

    my_roster = None
    for roster in rosters:
        # Cruza o owner_id do elenco com o seu user_id
        if str(roster.get('owner_id')) == str(user_id):
            my_roster = roster
            break

    if not my_roster:
        print("Elenco não encontrado. Verifique o USER_ID.")
        return

    player_ids = my_roster.get('players', [])
    if not player_ids:
        print("\nSeu time está vazio (Talvez o draft ainda não tenha acontecido).")
        return

    print(f"\nSeu time possui {len(player_ids)} jogadores. Aqui estão eles:")

    meu_time = []
    for pid in player_ids:
        p_info = players_data.get(pid, {})
        # Captura os dados vitais para os joins futuros
        name = p_info.get('full_name', 'Defesa/Desconhecido')
        pos = p_info.get('position', 'NA')
        team = p_info.get('team', 'FA')
        gsis_id = p_info.get('gsis_id', None)

        meu_time.append({
            "Sleeper_ID": pid,
            "GSIS_ID (NFL)": gsis_id,
            "Nome": name,
            "Posição": pos,
            "Time": team
        })

    # Exibe formatado usando o Pandas
    df_meu_time = pd.DataFrame(meu_time)
    print(df_meu_time.sort_values(by=["Posição", "Nome"]).to_string(index=False))
    return df_meu_time


if __name__ == "__main__":
    LEAGUE_ID = "1349790788724211712"

    # ATENÇÃO: Substitua pelo ID interno que apareceu no primeiro script
    # (Não é o seu username, é a sequência numérica)
    USER_ID = "1127629625020121088"

    sleeper_players_dict = get_sleeper_players()
    df_meu_time = get_my_roster(LEAGUE_ID, USER_ID, sleeper_players_dict)