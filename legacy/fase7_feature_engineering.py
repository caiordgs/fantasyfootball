import pandas as pd
import json
import os


def load_players_dict():
    file_path = "sleeper_players_cache.json"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    print("⚠️ Dicionário de jogadores não encontrado.")
    return {}


def run_feature_engineering():
    print("1. Carregando dados brutos do Draft...")
    df = pd.read_csv("dataset_drafts_raw.csv")
    players_dict = load_players_dict()

    # --- 1. FILTRO DE ALTA QUALIDADE (REMOVENDO ANOMALIAS EXTREMAS) ---
    print("2. Filtrando dados (Mantendo Ligas de 10 a 16 times)...")
    # Ignoramos ligas de 32 times (comportamento anômalo) e ligas minúsculas (4 a 8)
    df = df[df['teams_count'].isin([10, 12, 14, 16])].copy()

    # --- 2. MAPEAMENTO DE POSIÇÕES (INCLUINDO IDP) ---
    print("3. Cruzando IDs com as Posições dos Jogadores...")
    df['player_id'] = df['player_id'].astype(str)
    df['position'] = df['player_id'].map(lambda x: players_dict.get(x, {}).get('position', 'UNKNOWN'))

    # Adicionamos as posições defensivas padrão do Sleeper
    posicoes_alvo = ['QB', 'RB', 'WR', 'TE', 'DL', 'LB', 'DB', 'DE', 'DT']
    df = df[df['position'].isin(posicoes_alvo)].copy()

    # --- 3. ENGENHARIA DE VARIÁVEIS DINÂMICA ---
    print("4. Construindo Variáveis de Teoria dos Jogos (Efeito Manada)...")
    df = df.sort_values(by=['draft_id', 'pick_no'])

    # Cria flags booleanas de forma dinâmica
    for pos in posicoes_alvo:
        df[f'is_{pos}'] = (df['position'] == pos).astype(int)

    def rolling_sum_shifted(series):
        return series.rolling(5, min_periods=1).sum().shift(1).fillna(0)

    for pos in posicoes_alvo:
        # Escassez Global: Quantos saíram ANTES dessa escolha
        df[f'{pos}s_gone_total'] = df.groupby('draft_id')[f'is_{pos}'].cumsum().shift(1).fillna(0)

        # Efeito Manada (Runs): Quantos saíram nas últimas 5 escolhas
        df[f'{pos}s_gone_last_5'] = df.groupby('draft_id')[f'is_{pos}'].transform(rolling_sum_shifted)

    # MANTEMOS 'teams_count' e 'scoring_type' para o XGBoost aprender o contexto da liga!
    colunas_para_remover = [f'is_{pos}' for pos in posicoes_alvo] + ['roster_id']
    df = df.drop(columns=[col for col in colunas_para_remover if col in df.columns], errors='ignore')

    print("5. Salvando Dataset Preparado para Machine Learning...")
    df.to_csv("dataset_features.csv", index=False)

    print(f"\n✅ SUCESSO! Dataset final salvo com {len(df)} escolhas (incluindo IDP).")


if __name__ == "__main__":
    run_feature_engineering()