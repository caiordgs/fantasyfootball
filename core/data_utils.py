import pandas as pd
import json
import os
import streamlit as st

@st.cache_data(ttl=86400, show_spinner=False) # Cache longo (1 dia) para dicionário pesado
def load_players_dict(force_refresh=False):
    file_path = "sleeper_players_cache.json"
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for pid, info in data.items():
                    if info.get('position') == 'DEF' and not info.get('full_name'):
                        first = info.get('first_name', '')
                        last = info.get('last_name', '')
                        info['full_name'] = f"{first} {last}".strip() if first or last else info.get('team', 'DEF')
                return data
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
    return {}

@st.cache_data(ttl=86400)
def load_adp_data(scoring_format):
    files = {
        "PPR": "nfl-adp-PPR.csv",
        "Half-PPR": "nfl-adp-HPPR.csv",
        "Standard": "nfl-adp-STD.csv"
    }
    file_path = files.get(scoring_format)
    
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path, header=1, on_bad_lines='skip')
            player_col = 'Name' if 'Name' in df.columns else ('Player' if 'Player' in df.columns else df.columns[1])
            pos_col = 'Pos' if 'Pos' in df.columns else ('POS' if 'POS' in df.columns else None)
            adp_col = 'Rank' if 'Rank' in df.columns else ('ADP' if 'ADP' in df.columns else None)
            
            if adp_col:
                df[adp_col] = pd.to_numeric(df[adp_col], errors='coerce')
                df = df.sort_values(by=adp_col).dropna(subset=[adp_col, player_col])
            return df, player_col, pos_col, adp_col
        except Exception as e:
            print(f"Error reading CSV {file_path}: {e}")
            
    return pd.DataFrame(), None, None, None

def apply_format_adjustments(df, pos_col, adp_col, is_superflex=False, is_te_premium=False):
    if df.empty or not pos_col or not adp_col:
        return df
        
    df = df.copy()
    
    if is_superflex:
        # QBs ganham um boost absurdo de ADP
        mask_qb = df[pos_col].astype(str).str.contains('QB')
        df.loc[mask_qb, adp_col] = df.loc[mask_qb, adp_col] * 0.35 - 5
        
    if is_te_premium:
        # TEs ganham boost de ADP
        mask_te = df[pos_col].astype(str).str.contains('TE')
        df.loc[mask_te, adp_col] = df.loc[mask_te, adp_col] * 0.75 - 2

    # Garante que não exista ADP menor que 1
    df[adp_col] = df[adp_col].apply(lambda x: max(1.0, x))
    
    # Re-ordena o dataframe
    df = df.sort_values(by=adp_col).reset_index(drop=True)
    return df

def get_player_name_by_id(player_id, players_dict):
    p_info = players_dict.get(str(player_id), {})
    return p_info.get('full_name', f"ID: {player_id}")
