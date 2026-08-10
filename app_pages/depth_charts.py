import streamlit as st
import pandas as pd
import json
import os

from core.data_utils import load_players_dict

st.title("Depth Charts (NFL Oficial)")
st.markdown("Acompanhe quem é o Titular (QB1, RB1, WR1) e quem são os reservas imediatos em cada time da NFL.")

players_dict = load_players_dict()

if players_dict:
    # Processar o dicionário para montar o DataFrame
    depth_data = []
    
    for pid, p_info in players_dict.items():
        team = p_info.get('team')
        status = p_info.get('status')
        pos = p_info.get('position')
        
        # Só jogadores ativos, que têm time e que importam para o Fantasy
        if team and status == 'Active' and pos in ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']:
            dc_pos = p_info.get('depth_chart_position')
            dc_order = p_info.get('depth_chart_order')
            
            if dc_pos and dc_order:
                depth_data.append({
                    "Time": team,
                    "Posição Real": dc_pos,
                    "Ordem": dc_order,
                    "Jogador": p_info.get('full_name', 'Unknown')
                })
                
    df_depth = pd.DataFrame(depth_data)
    
    if not df_depth.empty:
        teams = sorted(df_depth['Time'].unique())
        selected_team = st.selectbox("Selecione o Time da NFL", teams)
        
        df_team = df_depth[df_depth['Time'] == selected_team].copy()
        
        # Filtra e agrupa por posição principal
        col1, col2 = st.columns(2)
        
        for idx, pos in enumerate(['QB', 'RB', 'WR', 'TE']):
            df_pos = df_team[df_team['Posição Real'] == pos].sort_values(by="Ordem")
            
            # Formatar para exibição
            display_str = ""
            for _, row in df_pos.iterrows():
                order = int(row['Ordem'])
                player = row['Jogador']
                if order == 1:
                    display_str += f"**{pos}1: {player}** (Titular)\n\n"
                else:
                    display_str += f"- {pos}{order}: {player}\n\n"
                    
            if idx % 2 == 0:
                with col1:
                    st.subheader(f"🏈 {pos}s")
                    if display_str:
                        st.markdown(display_str)
                    else:
                        st.caption("Dados de Depth Chart não encontrados para esta posição.")
            else:
                with col2:
                    st.subheader(f"🏈 {pos}s")
                    if display_str:
                        st.markdown(display_str)
                    else:
                        st.caption("Dados de Depth Chart não encontrados para esta posição.")
                        
        st.markdown("---")
        st.info("Os dados de Depth Chart são puxados diretamente do banco de dados oficial do Sleeper. As posições são atualizadas pelas próprias franquias da NFL.")
    else:
        st.warning("Nenhum dado de Depth Chart estruturado encontrado no cache do Sleeper.")
else:
    st.error("Arquivo sleeper_players_cache.json não encontrado ou vazio.")
