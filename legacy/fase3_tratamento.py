import pandas as pd
import nfl_data_py as nfl
import json


def load_local_roster():
    # Simulando o dataframe gerado na Fase 2 para darmos continuidade
    # Na prática, você passaria o dataframe gerado pela função get_my_roster()
    data = {
        "Sleeper_ID": ["10222", "6794", "1479", "8110", "4960", "5991", "13306"],
        "Nome": ["Jayden Reed", "Justin Jefferson", "Keenan Allen", "Jake Ferguson", "Roquan Smith", "Maxx Crosby",
                 "Taylen Green"],
        "Posição": ["WR", "WR", "WR", "TE", "LB", "DE", "QB"]
    }
    return pd.DataFrame(data)


def fix_player_ids(df_roster):
    print("Baixando Tabela Mestre de IDs do nflverse...")
    # Traz o mapeamento universal
    df_ids = nfl.import_ids()

    # Filtra as colunas que importam para nós
    id_mapping = df_ids[['sleeper_id', 'gsis_id']].dropna(subset=['sleeper_id'])

    # O sleeper_id no nflverse vem como float/string. Vamos padronizar como string.
    id_mapping['sleeper_id'] = id_mapping['sleeper_id'].astype(str).str.replace(".0", "", regex=False)
    df_roster['Sleeper_ID'] = df_roster['Sleeper_ID'].astype(str)

    print("\nCruzando dados e corrigindo NaNs...")
    # Faz o Join (PROCV) usando o Sleeper_ID como chave primária
    df_clean = pd.merge(df_roster, id_mapping, how='left', left_on='Sleeper_ID', right_on='sleeper_id')

    # Remove a coluna duplicada
    df_clean = df_clean.drop(columns=['sleeper_id'])

    print("IDs corrigidos com sucesso!")
    return df_clean


def add_mock_projections(df_clean):
    # Para o Draft Companion e o Otimizador, precisamos de uma coluna "Pontos_Projetados".
    # Em produção, substituiremos isso por um scraper do FantasyPros ou projeções do nflverse.
    print("\nAdicionando modelo de projeção para a semana/temporada...")

    # Simulando pontuações baseadas em "Tiers" simplificados
    mock_points = {
        "Justin Jefferson": 21.5,
        "Jayden Reed": 15.2,
        "Keenan Allen": 12.0,
        "Jake Ferguson": 11.8,
        "Taylen Green": 18.0,
        "Roquan Smith": 14.5,
        "Maxx Crosby": 13.0
    }

    df_clean['Pontos_Projetados'] = df_clean['Nome'].map(mock_points).fillna(8.0)

    print("\nTabela Final Pronta para o Motor de Otimização:")
    print(df_clean.to_string(index=False))
    return df_clean


if __name__ == "__main__":
    meu_time_df = load_local_roster()
    time_corrigido = fix_player_ids(meu_time_df)
    time_com_projecoes = add_mock_projections(time_corrigido)