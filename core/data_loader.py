import pandas as pd
import os
import re
import streamlit as st


def clean_player_name(name):
    """
    Limpa o nome do jogador para garantir o MATCH perfeito entre Sleeper e FantasyPros.
    Remove sufixos (Jr, Sr, II, III), pontuações e espaços extras.
    """
    if not isinstance(name, str):
        return ""

    name = re.sub(r'\b(Jr\.?|Sr\.?|III|II|IV|V)\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[^\w\s]', '', name)
    return " ".join(name.split()).lower()


@st.cache_data
def load_master_dataframe(data_dir="source_files"):
    """
    Lê todos os CSVs do FantasyPros na pasta e consolida em um único DataFrame Mestre.
    """
    print("🔄 [ETL] Iniciando consolidação de dados do FantasyPros...")

    # --- 1. CARREGAR PROJEÇÕES (O Motor Base) ---
    proj_files = [f for f in os.listdir(data_dir) if
                  f.startswith("FantasyPros_Fantasy_Football_Projections_") and f.endswith(".csv") and "FLX" not in f]

    df_proj_list = []
    for f in proj_files:
        try:
            df_temp = pd.read_csv(os.path.join(data_dir, f))
            pos = f.split('_')[-1].replace('.csv', '')
            df_temp['Pos_Base'] = pos
            df_proj_list.append(df_temp)
        except Exception as e:
            pass

    if not df_proj_list:
        print("⚠️ Erro: Nenhum arquivo de projeção encontrado na pasta 'source_files'.")
        return pd.DataFrame()

    df_master = pd.concat(df_proj_list, ignore_index=True)

    if 'Player' in df_master.columns:
        df_master['Match_Name'] = df_master['Player'].apply(clean_player_name)
        df_master = df_master.drop_duplicates(subset=['Match_Name'], keep='first')
    else:
        print("⚠️ Erro crítico: Coluna 'Player' não encontrada nas projeções.")
        return pd.DataFrame()

    # --- 2. CARREGAR RANKINGS & ADP (O Mercado) ---
    ranking_file = "FantasyPros_2026_Draft_ALL_Rankings.csv"
    if os.path.exists(os.path.join(data_dir, ranking_file)):
        try:
            df_rank = pd.read_csv(os.path.join(data_dir, ranking_file))
            if 'PLAYER NAME' in df_rank.columns:
                df_rank['Match_Name'] = df_rank['PLAYER NAME'].apply(clean_player_name)
                colunas_uteis = ['Match_Name', 'TIERS', 'BYE WEEK', 'UPSIDE ', 'BUST ', 'SOS SEASON', 'ECR VS. ADP']
                df_rank = df_rank[[c for c in colunas_uteis if c in df_rank.columns]]
                df_master = pd.merge(df_master, df_rank, on='Match_Name', how='left')
                print("✅ Rankings e Tiers integrados com sucesso.")
        except Exception as e:
            print(f"Erro ao ler Rankings: {e}")

        # --- 3. CARREGAR RED ZONE (O Teto/Upside) ---
        rz_files = [f for f in os.listdir(data_dir) if
                    f.startswith("FantasyPros_Fantasy_Football_Red_Zone_Report_") and f.endswith(".csv")]

        df_rz_list = []
        for f in rz_files:
            try:
                df_temp = pd.read_csv(os.path.join(data_dir, f))
                # Força MAIÚSCULO para evitar erros de digitação do FantasyPros
                df_temp.columns = [str(c).upper().strip() for c in df_temp.columns]
                df_rz_list.append(df_temp)
            except Exception as e:
                pass

        if df_rz_list:
            df_rz = pd.concat(df_rz_list, ignore_index=True)

            # Agora usamos a coluna exata que o log revelou
            if 'PLAYERS PLAYER' in df_rz.columns:
                df_rz['Match_Name'] = df_rz['PLAYERS PLAYER'].apply(clean_player_name)

                # Calcula o Total de Oportunidades na Red Zone (Passe + Corrida + Recepção)
                # Usamos fillna(0) caso o jogador não tenha estatísticas em alguma dessas categorias
                pass_att = pd.to_numeric(df_rz.get('PASSING ATT', pd.Series(0, index=df_rz.index)),
                                         errors='coerce').fillna(0)
                rush_att = pd.to_numeric(df_rz.get('RUSHING ATT', pd.Series(0, index=df_rz.index)),
                                         errors='coerce').fillna(0)
                rec_tgt = pd.to_numeric(df_rz.get('RECEIVING TGT', pd.Series(0, index=df_rz.index)),
                                        errors='coerce').fillna(0)

                df_rz['RZ_Targets'] = pass_att + rush_att + rec_tgt

                # Filtra apenas o nome e a nova métrica consolidada
                df_rz_clean = df_rz[['Match_Name', 'RZ_Targets']].drop_duplicates(subset=['Match_Name'], keep='first')

                # JOIN final
                df_master = pd.merge(df_master, df_rz_clean, on='Match_Name', how='left')
                df_master['RZ_Targets'] = df_master['RZ_Targets'].fillna(0)
                print("✅ Dados de Red Zone integrados (Oportunidades totais calculadas com sucesso).")
            else:
                print("⚠️ Coluna 'PLAYERS PLAYER' não encontrada nos arquivos de Red Zone.")
        else:
            print("ℹ️ Nenhum arquivo de Red Zone encontrado na pasta 'source_files' (pulando etapa).")

    # --- LIMPEZA FINAL ROBUSTA (Fora dos blocos if/else) ---
    df_master = df_master.dropna(subset=['Player'])
    df_master = df_master[df_master['Player'].astype(str).str.strip() != '']

    print(f"🚀 ETL Concluído! Base consolidada com {len(df_master)} jogadores.")
    return df_master


# Bloco de Teste
if __name__ == "__main__":
    df_teste = load_master_dataframe()
    # Adicionada proteção extra aqui para não quebrar o terminal caso retorne vazio
    if df_teste is not None and not df_teste.empty:
        print("\n--- AMOSTRA DOS DADOS ---")
        print(df_teste[['Player', 'Pos_Base', 'Team', 'FPTS', 'TIERS']].head())
