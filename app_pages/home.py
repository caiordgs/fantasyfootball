import streamlit as st
from core.sleeper_api import get_user_data, get_user_leagues
import pandas as pd

st.title("🏈 Bem-vindo ao Fantasy AI Hub")
st.markdown("O seu ecossistema de inteligência para dominar ligas de Fantasy Football.")

username = st.session_state.get('username', '')

if username:
    st.markdown(f"### Olá, **{username}** 👋")
    
    with st.spinner("Sincronizando com o Sleeper..."):
        user_id = get_user_data(username)
        
        if user_id:
            leagues = get_user_leagues(user_id)
            if leagues:
                st.success(f"Conectado com sucesso! Encontramos {len(leagues)} ligas na sua conta para a temporada atual.")
                
                # Exibir as ligas num formato bonito
                cols = st.columns(3)
                for i, l in enumerate(leagues):
                    with cols[i % 3]:
                        st.info(f"🏆 **{l.get('name')}**\n\n👥 {l.get('total_rosters')} Times")
            else:
                st.warning("Nenhuma liga encontrada para este usuário no ano atual.")
        else:
            st.error("Usuário do Sleeper não encontrado. Verifique seu username.")
            
else:
    st.info("Configure seu Username do Sleeper no menu lateral para habilitar sincronização automática de elencos.")

st.markdown("---")
st.subheader("🚀 Acesso Rápido")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="Draft War Room", value="Em Alta 📈")
    st.caption("Domine seu draft com recomendações de IA turno a turno.")

with col2:
    st.metric(label="Dynasty Trade Calc", value="Novo 🧠")
    st.caption("Avalie trocas complexas cruzando ADP, Idade e Escassez.")

with col3:
    st.metric(label="Mock Draft Trainer", value="Simulador 🤖")
    st.caption("Treine contra nossa IA e descubra seus pontos fracos.")
