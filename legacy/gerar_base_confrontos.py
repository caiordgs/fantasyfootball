import json
import pandas as pd

# 1. CRIAÇÃO DO CALENDÁRIO DE JOGOS (nfl_schedule.json)
# Mapeia cada semana -> Time : Adversário
schedule_data = {
    "1": {
        "KC": "BAL", "BAL": "KC",
        "PHI": "GB", "GB": "PHI",
        "DAL": "CLE", "CLE": "DAL",
        "DET": "LAR", "LAR": "DET",
        "SF": "NYJ", "NYJ": "SF",
        "BUF": "ARI", "ARI": "BUF",
        "MIA": "JAX", "JAX": "MIA",
        "CIN": "NE", "NE": "CIN",
        "ATL": "PIT", "PIT": "ATL",
        "IND": "HOU", "HOU": "IND",
        "CHI": "TEN", "TEN": "CHI",
        "NO": "CAR", "CAR": "NO",
        "SEA": "DEN", "DEN": "SEA",
        "TB": "WAS", "WAS": "TB",
        "LAC": "LV", "LV": "LAC"
    }
}

with open("nfl_schedule.json", "w", encoding="utf-8") as f:
    json.dump(schedule_data, f, indent=4)

print("✅ Arquivo 'nfl_schedule.json' gerado com sucesso!")


# 2. CRIAÇÃO DA MATRIZ DVP (nfl_dvp.csv)
# Exemplo de multiplicadores:
# > 1.00 = Defesa vulnerável/fraca (Ganha Bônus / Verde)
# < 1.00 = Defesa elite/forte (Sofre Punição / Vermelho)
dvp_data = {
    'Team': ['BAL', 'WAS', 'CAR', 'SF', 'DAL', 'KC', 'NE', 'NYJ', 'PHI', 'DET'],
    'QB':   [0.85,   1.20,  1.15,  0.85, 0.95,  0.80, 1.10, 0.85,  0.90,  1.05],
    'RB':   [0.80,   1.15,  1.30,  0.85, 1.10,  0.90, 1.05, 0.90,  0.95,  0.80],
    'WR':   [0.90,   1.25,  1.20,  0.85, 0.90,  0.85, 1.15, 0.80,  0.90,  1.10],
    'TE':   [0.85,   1.20,  1.15,  0.90, 0.95,  0.80, 1.10, 0.85,  0.90,  1.00],
    'K':    [1.00,   1.00,  1.00,  1.00, 1.00,  1.00, 1.00, 1.00,  1.00,  1.00],
    'DEF':  [1.00,   1.00,  1.00,  1.00, 1.00,  1.00, 1.00, 1.00,  1.00,  1.00]
}

df_dvp = pd.DataFrame(dvp_data)
df_dvp.to_csv("nfl_dvp.csv", index=False)

print("✅ Arquivo 'nfl_dvp.csv' gerado com sucesso!")