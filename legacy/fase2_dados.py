import requests
import pandas as pd
import nfl_data_py as nfl


def get_league_settings(league_id):
    print(f"Buscando configurações da liga {league_id}...")
    url = f"https://api.sleeper.app/v1/league/{league_id}"
    response = requests.get(url)

    if response.status_code != 200:
        print("Erro ao acessar a liga.")
        return None

    data = response.json()

    # Extraindo as posições titulares e banco
    roster_positions = data.get('roster_positions', [])
    print("\nFormato do Elenco (Roster):")
    print(roster_positions)

    # Extraindo as regras de pontuação
    scoring_settings = data.get('scoring_settings', {})
    print("\nRegras de Pontuação (Destaques):")
    print(f"- Ponto por Recepção (PPR): {scoring_settings.get('rec', 0)}")
    print(f"- Ponto por Passe para TD: {scoring_settings.get('pass_td', 0)}")

    return data


def get_nfl_players():
    print("\nBaixando base de jogadores da NFL (isso pode levar alguns segundos)...")

    # Correção: O método atualizado da biblioteca
    df_players = nfl.import_players()

    # O import_players mapeia as colunas com nomes um pouco diferentes
    colunas_importantes = ['gsis_id', 'display_name', 'position', 'team_abbr']

    # Filtra as colunas com segurança e remove linhas vazias de metadados
    colunas_disponiveis = [col for col in colunas_importantes if col in df_players.columns]
    df_filtrado = df_players[colunas_disponiveis].dropna(subset=['display_name', 'position'])

    print(f"Base carregada! Total de jogadores na NFL: {len(df_filtrado)}")
    print(df_filtrado.head())

    return df_filtrado


if __name__ == "__main__":
    # COLOQUE O ID DA SUA LIGA AQUI (O número longo retornado no script anterior)
    LEAGUE_ID = "1349790788724211712"

    league_data = get_league_settings(LEAGUE_ID)
    players_df = get_nfl_players()