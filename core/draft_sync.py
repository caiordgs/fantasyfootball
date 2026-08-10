import requests
import json
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


def load_players_dict():
    # Carrega aquele dicionário gigante que salvamos na Fase 2
    file_path = "sleeper_players_cache.json"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    print("Erro: Dicionário de jogadores não encontrado.")
    return {}


@st.cache_data
def get_sleeper_translator():
    """
    Gera o dicionário tradutor (Sleeper ID -> Nome Limpo)
    usando o cache local da Fase 2 para ser instantâneo.
    """
    raw_dict = load_players_dict()
    translator = {}

    for player_id, info in raw_dict.items():
        # Tratamento para Defesas (Sleeper usa a sigla do time como ID, ex: "BUF")
        if info.get('position') == 'DEF':
            translator[player_id] = player_id.lower()
        else:
            first = info.get('first_name', '')
            last = info.get('last_name', '')
            full_name = f"{first} {last}".strip()
            translator[player_id] = clean_player_name(full_name)

    return translator


def get_draft_picks(draft_id):
    print(f"Sincronizando com o Draft {draft_id}...")
    url = f"https://api.sleeper.app/v1/draft/{draft_id}/picks"
    response = requests.get(url)

    if response.status_code == 200:
        return response.json()
    else:
        print("Erro ao acessar a API de Draft do Sleeper.")
        return []


def get_drafted_clean_names(draft_id):
    """
    Função utilitária para a Fase 5 UI:
    Retorna uma lista simples com os 'Nomes Limpos' de todos os jogadores já draftados.
    """
    picks = get_draft_picks(draft_id)
    translator = get_sleeper_translator()

    drafted_names = []
    for pick in picks:
        pid = str(pick.get('player_id'))
        clean_name = translator.get(pid)
        if clean_name:
            drafted_names.append(clean_name)

    return drafted_names


if __name__ == "__main__":
    # O ID do seu Mock Draft
    DRAFT_ID = "1389755952130949121"

    translator = get_sleeper_translator()
    picks = get_draft_picks(DRAFT_ID)

    print(f"✅ Dicionário tradutor carregado com {len(translator)} jogadores mapeados.")

    if picks:
        print(f"\nTotal de escolhas feitas até agora: {len(picks)}")
        print("\nÚltimas 5 escolhas do Draft (Traduzidas para o FantasyPros):")

        # Pega as últimas 5 escolhas da lista
        ultimas_escolhas = picks[-5:] if len(picks) >= 5 else picks

        for pick in ultimas_escolhas:
            pick_no = pick.get('pick_no')
            player_id = str(pick.get('player_id'))

            # Busca o nome limpo no dicionário
            nome_limpo = translator.get(player_id, 'defesa/desconhecido')

            print(f"Pick {pick_no}: ID {player_id} -> Nome Limpo: '{nome_limpo}'")
    else:
        print("\nNenhuma escolha foi feita ainda neste draft (ou o ID está incorreto).")