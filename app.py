import streamlit as st
import json
import os

# --- INICIALIZAÇÃO DE ESTADO GLOBAL (USERNAME) ---
CONFIG_FILE = "config_app.json"

if "username" not in st.session_state:
    saved_user = "caiordgs" # Padrão definido pelo usuário
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                saved_user = json.load(f).get("username", "caiordgs")
        except:
            pass
    st.session_state.username = saved_user

# Carregar CSS Global Premium
def load_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# Configuração Base do App
st.set_page_config(
    page_title="Fantasy AI Hub",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Injeta CSS (precisa ser depois do set_page_config)
load_css("assets/style.css")

st.title("🏈 Fantasy AI Hub")

# Configurando a Navegação Principal
page = st.navigation(
    {
        "DASHBOARD": [
            st.Page("app_pages/home.py", title="Home Hub", icon=":material/home:"),
        ],
        "DRAFT-SEASON": [
            st.Page("app_pages/draft_war_room.py", title="Draft War Room", icon=":material/dashboard:"),
            st.Page("app_pages/mock_draft_trainer.py", title="Mock Draft Trainer", icon=":material/sports_football:"),
            st.Page("app_pages/keeper_calculator.py", title="Keeper Calculator", icon=":material/calculate:"),
            st.Page("app_pages/adp_market_index.py", title="ADP Market Index", icon=":material/trending_up:"),
            st.Page("app_pages/league_analyzer.py", title="League Analyzer", icon=":material/analytics:"),
            st.Page("app_pages/dynasty_trade_calc.py", title="Dynasty Trade Calculator", icon=":material/currency_exchange:"),
        ],
        "IN-SEASON": [
            st.Page("app_pages/team_dashboard.py", title="Team Dashboard", icon=":material/space_dashboard:"),
            st.Page("app_pages/who_to_start.py", title="Who to Start", icon=":material/front_hand:"),
            st.Page("app_pages/free_agent_finder.py", title="Free Agent Finder", icon=":material/person_add:"),
            st.Page("app_pages/trade_navigator.py", title="Trade Navigator", icon=":material/swap_horiz:"),
            st.Page("app_pages/trade_value_charts.py", title="Trade Value Charts", icon=":material/bar_chart:"),
        ],
        "INTEL": [
            st.Page("app_pages/injury_predictor.py", title="Injury Predictor", icon=":material/healing:"),
            st.Page("app_pages/rookie_model.py", title="Rookie Model", icon=":material/school:"),
            st.Page("app_pages/depth_charts.py", title="Depth Charts", icon=":material/format_list_numbered:"),
            st.Page("app_pages/historical_stats.py", title="Historical Stats", icon=":material/history:"),
            st.Page("app_pages/strength_of_schedule.py", title="Strength of Schedule", icon=":material/calendar_month:"),
            st.Page("app_pages/fantasy_points_allowed.py", title="Fantasy Points Allowed", icon=":material/shield:"),
        ]
    },
    position="sidebar"
)

# Renderiza a página selecionada
page.run()

# Hack global para corrigir o bug de layout do Streamlit:
# Adiciona um bloco invisível no final da barra lateral para garantir 
# que dropdowns grandes (como as Ligas) não sejam cortados pelo fim da tela.
st.sidebar.markdown("<br>" * 15, unsafe_allow_html=True)
