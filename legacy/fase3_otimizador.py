import pandas as pd
import pulp


def optimize_lineup(df_players):
    print("Iniciando o motor de otimização com PuLP...\n")

    # Cria o problema de maximização
    prob = pulp.LpProblem("Fantasy_Football_Optimizer", pulp.LpMaximize)

    # Variáveis de decisão: 1 se o jogador for titular, 0 se for banco
    # O dicionário usa o índice do DataFrame como chave
    player_vars = pulp.LpVariable.dicts("Titular", df_players.index, cat='Binary')

    # FUNÇÃO OBJETIVO: Maximizar os Pontos Projetados
    prob += pulp.lpSum(
        [df_players.loc[i, 'Pontos_Projetados'] * player_vars[i] for i in df_players.index]), "Total_Points"

    # ---------------------------------------------------------
    # REGRAS E RESTRIÇÕES DA SUA LIGA (O Roster de 11 Titulares)
    # ---------------------------------------------------------

    # 1. Exatamente 1 QB
    prob += pulp.lpSum(
        [player_vars[i] for i in df_players.index if df_players.loc[i, 'Posição'] == 'QB']) == 1, "Exatamente_1_QB"

    # 2. Exatamente 5 FLEX Ofensivos (Qualquer combinação de RB, WR, TE)
    prob += pulp.lpSum([player_vars[i] for i in df_players.index if
                        df_players.loc[i, 'Posição'] in ['RB', 'WR', 'TE']]) == 5, "Exatamente_5_FLEX"

    # 3. Restrições de IDP (Defesa)
    # Mínimo de 1 para cada posição defensiva base
    prob += pulp.lpSum([player_vars[i] for i in df_players.index if
                        df_players.loc[i, 'Posição'] == 'DL' or df_players.loc[i, 'Posição'] == 'DE' or df_players.loc[
                            i, 'Posição'] == 'DT']) >= 1, "Min_1_DL"
    prob += pulp.lpSum(
        [player_vars[i] for i in df_players.index if df_players.loc[i, 'Posição'] == 'LB']) >= 1, "Min_1_LB"
    prob += pulp.lpSum(
        [player_vars[i] for i in df_players.index if df_players.loc[i, 'Posição'] == 'DB']) >= 1, "Min_1_DB"

    # Total de defensores deve ser exatamente 4 (1 DL + 1 LB + 1 DB + 1 IDP_FLEX)
    prob += pulp.lpSum([player_vars[i] for i in df_players.index if
                        df_players.loc[i, 'Posição'] in ['DL', 'DE', 'DT', 'LB', 'DB']]) == 4, "Total_4_IDP"

    # (Ignorando Kicker por enquanto, já que o mock data não tinha um, mas a lógica seria a mesma)

    # Resolve o problema
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    # Verifica o status da solução
    if pulp.LpStatus[prob.status] != 'Optimal':
        print(
            "Não foi possível encontrar uma escalação válida. Verifique se o time tem jogadores suficientes para todas as posições.")
        return None

    # Extrai os titulares escolhidos
    titulares = []
    for i in df_players.index:
        if player_vars[i].varValue == 1.0:
            titulares.append(i)

    # Cria o DataFrame final
    df_titulares = df_players.loc[titulares].copy()

    print("================ ESCALAÇÃO IDEAL ================")
    print(df_titulares[['Nome', 'Posição', 'Pontos_Projetados']].sort_values(by=['Posição']))
    print("=================================================")
    print(f"Pontuação Total Projetada: {pulp.value(prob.objective):.2f}")

    return df_titulares


if __name__ == "__main__":
    # DataFrame simulado da Fase 3.1 para testes
    data = {
        "Nome": [
            "Taylen Green", "Ty Simpson",  # QBs
            "George Holani", "Sean Tucker", "Tyrone Tracy",  # RBs
            "Jayden Reed", "Justin Jefferson", "Keenan Allen", "Luther Burden",  # WRs
            "Jake Ferguson",  # TEs
            "Maxx Crosby", "Zach Sieler", "Aaron Donald",  # DL/DE/DT
            "Roquan Smith", "Tyrel Dodson", "Tyrice Knight",  # LBs
            "Justin Reid", "AJ Haulcy", "Evan Williams"  # DBs
        ],
        "Posição": [
            "QB", "QB",
            "RB", "RB", "RB",
            "WR", "WR", "WR", "WR",
            "TE",
            "DE", "DT", "DT",
            "LB", "LB", "LB",
            "DB", "DB", "DB"
        ],
        "Pontos_Projetados": [
            18.0, 12.0,
            9.5, 8.0, 11.2,
            15.2, 21.5, 12.0, 10.5,
            11.8,
            13.0, 8.5, 0.0,  # (Donald se aposentou, pontuação 0 pra testar o modelo!)
            14.5, 9.0, 6.5,
            10.0, 7.5, 8.2
        ]
    }
    df_teste = pd.DataFrame(data)

    optimize_lineup(df_teste)