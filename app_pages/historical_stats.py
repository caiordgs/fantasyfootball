import streamlit as st
import pandas as pd
from core.sleeper_api import get_yearly_stats
from core.data_utils import load_players_dict

st.title("Historical Stats & Analytics")
st.markdown("Verifique o histórico completo de um jogador ao longo de múltiplas temporadas, com totais e médias avançadas.")

# 1. Carrega Dicionário de Jogadores
@st.cache_data
def get_fantasy_players():
    players = load_players_dict()
    # Filtra apenas jogadores ofensivos relevantes para não pesar a lista
    relevant = {}
    for pid, p in players.items():
        if p.get('position') in ["QB", "RB", "WR", "TE"] and p.get('full_name'):
            relevant[pid] = {"name": p['full_name'], "pos": p['position'], "team": p.get('team', 'FA')}
    return relevant

fantasy_players = get_fantasy_players()

# 2. Busca do Jogador (Autocomplete)
# Formata os nomes para a caixa de seleção: "Nome - POS (Time)"
player_options = {}
for pid, data in fantasy_players.items():
    label = f"{data['name']} - {data['pos']} ({data.get('team', 'FA')})"
    player_options[label] = pid

selected_label = st.selectbox("🔍 Pesquise e selecione o jogador (Digite para filtrar):", options=[""] + sorted(player_options.keys()), index=0)
selected_pid = player_options.get(selected_label)

# 3. Busca Histórica (Últimos 5 anos)
if selected_pid:
    seasons = ["2021", "2022", "2023", "2024", "2025"]
    history_data = []
    
    with st.spinner("Puxando histórico de 5 anos do Sleeper..."):
        for season in seasons:
            stats = get_yearly_stats(season=season)
            if stats and selected_pid in stats:
                p_stats = stats[selected_pid]
                # Pega apenas os stats relevantes
                history_data.append({
                    "Temporada": season,
                    "Jogos (GP)": p_stats.get("gp", 0),
                    "PPR Pts": p_stats.get("pts_ppr", 0.0),
                    "Half-PPR": p_stats.get("pts_half_ppr", 0.0),
                    "Pass Yds": p_stats.get("pass_yd", 0),
                    "Pass TD": p_stats.get("pass_td", 0),
                    "Rush Yds": p_stats.get("rush_yd", 0),
                    "Rush TD": p_stats.get("rush_td", 0),
                    "Targets": p_stats.get("rec_tgt", 0),
                    "Rec": p_stats.get("rec", 0),
                    "Rec Yds": p_stats.get("rec_yd", 0),
                    "Rec TD": p_stats.get("rec_td", 0)
                })
    
    if not history_data:
        st.info("Nenhuma estatística encontrada para este jogador nos últimos 5 anos.")
    else:
        df_hist = pd.DataFrame(history_data)
        
        # 4. Cálculos Totais e Médias (Carreira Recente)
        df_numeric = df_hist.drop(columns=["Temporada"])
        
        # Linha de TOTAL
        total_row = df_numeric.sum().to_dict()
        total_row["Temporada"] = "TOTAL (5 anos)"
        
        # Linha de MÉDIAS POR JOGO (Usando o total)
        avg_row = {}
        total_gp = total_row["Jogos (GP)"]
        for col in df_numeric.columns:
            if col == "Jogos (GP)":
                avg_row[col] = "-"
            elif total_gp > 0:
                avg_row[col] = round(total_row[col] / total_gp, 2)
            else:
                avg_row[col] = 0
        avg_row["Temporada"] = "MÉDIA (Por Jogo)"
        
        # Junta tudo
        df_final = pd.concat([df_hist, pd.DataFrame([total_row, avg_row])], ignore_index=True)
        
        # Reordenando a coluna Temporada pra frente
        cols = ["Temporada"] + [c for c in df_final.columns if c != "Temporada"]
        df_final = df_final[cols]
        
        st.subheader(f"📊 Histórico: {fantasy_players[selected_pid]['name']} ({fantasy_players[selected_pid]['pos']})")
        st.dataframe(df_final.style.format(precision=1), hide_index=True, width='stretch')
        
        # 5. Stats Avançados Rápidos (Baseado na Posição)
        st.subheader(f"💡 Insights Avançados (Carreira: {fantasy_players[selected_pid]['pos']})")
        col1, col2, col3 = st.columns(3)
        
        pos = fantasy_players[selected_pid]['pos']
        
        # Insight 1: Depende da posição
        if pos == "QB":
            total_pass_yds = total_row.get("Pass Yds", 0)
            total_pass_td = total_row.get("Pass TD", 0)
            col1.metric("Pass TD (Total)", int(total_pass_td), help="Total de touchdowns passados")
        elif pos == "RB":
            total_rush_yds = total_row.get("Rush Yds", 0)
            total_rush_td = total_row.get("Rush TD", 0)
            col1.metric("Rush TD (Total)", int(total_rush_td), help="Total de touchdowns terrestres")
        else:
            total_targets = total_row.get("Targets", 0)
            total_recs = total_row.get("Rec", 0)
            catch_rate = (total_recs / total_targets * 100) if total_targets > 0 else 0
            col1.metric("Catch Rate Médio", f"{catch_rate:.1f}%", help="Porcentagem de passes recebidos vs targets")
        
        # Insight 2: PPR
        avg_ppr = avg_row.get("PPR Pts", 0)
        col2.metric("PPR / Jogo (Média)", f"{avg_ppr:.1f} pts")
        
        # Insight 3: Touchdowns Totais ou Jardas
        total_tds = total_row.get("Pass TD", 0) + total_row.get("Rush TD", 0) + total_row.get("Rec TD", 0)
        col3.metric("Total Touchdowns (Global)", int(total_tds))
