import requests
import json
import os
import streamlit as st

# Helper para tratamento de erros em chamadas da API
def _fetch_sleeper_data(url):
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return res.json()
        elif res.status_code == 404:
            return None # Não encontrado (ex: usuário inválido)
    except requests.exceptions.RequestException as e:
        st.toast("Erro de conexão com o servidor do Sleeper.", icon="⚠️")
        print(f"Sleeper API Error: {e}")
    return None

@st.cache_data(ttl=3600) # Cache de 1h para user_id
def get_user_data(username):
    if not username: return None
    url = f"https://api.sleeper.app/v1/user/{username}"
    data = _fetch_sleeper_data(url)
    return data.get('user_id') if data else None

@st.cache_data(ttl=3600)
def get_user_leagues(user_id, season="2026"):
    if not user_id: return []
    url = f"https://api.sleeper.app/v1/user/{user_id}/leagues/nfl/{season}"
    data = _fetch_sleeper_data(url)
    return data if data else []

@st.cache_data(ttl=600) # Cache de 10 minutos para rosters
def get_league_rosters(league_id):
    if not league_id: return []
    url = f"https://api.sleeper.app/v1/league/{league_id}/rosters"
    data = _fetch_sleeper_data(url)
    return data if data else []

@st.cache_data(ttl=3600)
def get_league_users(league_id):
    if not league_id: return {}
    url = f"https://api.sleeper.app/v1/league/{league_id}/users"
    data = _fetch_sleeper_data(url)
    if data:
        return {u['user_id']: u.get('display_name', 'Unknown') for u in data}
    return {}

@st.cache_data(ttl=600)
def get_real_roster(league_id, user_id):
    rosters = get_league_rosters(league_id)
    for r in rosters:
        if str(r.get('owner_id')) == str(user_id):
            return r.get('players', [])
    return []

@st.cache_data(ttl=600)
def get_league_rostered_players(league_id):
    rosters = get_league_rosters(league_id)
    rostered = set()
    for r in rosters:
        players = r.get('players')
        if players:
            rostered.update([str(p) for p in players])
    return rostered

@st.cache_data(ttl=3600)
def get_weekly_projections(season="2026", week=1):
    url = f"https://api.sleeper.app/v1/projections/nfl/regular/{season}/{week}"
    data = _fetch_sleeper_data(url)
    return data if data else {}

@st.cache_data(ttl=3600)
def get_yearly_stats(season="2025"):
    url = f"https://api.sleeper.app/v1/stats/nfl/regular/{season}"
    data = _fetch_sleeper_data(url)
    return data if data else {}
