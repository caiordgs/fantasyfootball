import requests
import pandas as pd
import time
import os

# --- CONFIGURAÇÕES DO SCRAPER ---
SEED_USERNAME = ["caiordgs", "rafitsxeod", "mautimaolhp"]
SEASONS_TO_SCRAPE = ["2023", "2024", "2025", "2026"]
OUTPUT_FILE = "dataset_drafts_raw.csv"


def get_user_id(username):
    res = requests.get(f"https://api.sleeper.app/v1/user/{username}")
    return res.json().get('user_id') if res.status_code == 200 and res.json() else None


def get_leagues_for_user(user_id, season):
    res = requests.get(f"https://api.sleeper.app/v1/user/{user_id}/leagues/nfl/{season}")
    return res.json() if res.status_code == 200 else []


def get_users_in_league(league_id):
    res = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/users")
    return res.json() if res.status_code == 200 else []


def get_draft_info(draft_id):
    res = requests.get(f"https://api.sleeper.app/v1/draft/{draft_id}")
    return res.json() if res.status_code == 200 else {}


def get_draft_picks(draft_id):
    res = requests.get(f"https://api.sleeper.app/v1/draft/{draft_id}/picks")
    return res.json() if res.status_code == 200 else []


def run_snowball_scraper():
    print(f"🚀 Iniciando Snowball Scraper (Sementes: {SEED_USERNAME})...")

    users_queue = []
    # Loop para processar múltiplos amigos como sementes
    for username in SEED_USERNAME:
        uid = get_user_id(username)
        if uid:
            users_queue.append(uid)
            print(f"✅ Semente '{username}' adicionada com sucesso.")
        else:
            print(f"⚠️ Usuário '{username}' não encontrado. Pulando...")

    if not users_queue:
        print("❌ Nenhum usuário semente válido encontrado. Abortando.")
        return

    # Conjuntos para evitar raspar a mesma coisa duas vezes
    scraped_users = set()
    scraped_leagues = set()
    draft_ids_to_scrape = set()

    # PASSO 1: Mapear a Rede de Drafts (Spider)
    print("\n🕸️ Fase 1: Mapeando a rede de usuários e ligas...")

    # Aumentando o limite proporcionalmente (50 por amigo)
    max_users_to_explore = len(SEED_USERNAME) * 50

    while users_queue and len(scraped_users) < max_users_to_explore:
        current_user = users_queue.pop(0)
        if current_user in scraped_users:
            continue

        scraped_users.add(current_user)
        print(f"Explorando usuário {len(scraped_users)}/{max_users_to_explore}...")

        for season in SEASONS_TO_SCRAPE:
            leagues = get_leagues_for_user(current_user, season)
            for league in leagues:
                league_id = league.get('league_id')
                draft_id = league.get('draft_id')

                if league_id not in scraped_leagues:
                    scraped_leagues.add(league_id)
                    if draft_id:
                        draft_ids_to_scrape.add(draft_id)

                    # Adiciona os adversários dessa liga na fila para expandir a rede
                    league_users = get_users_in_league(league_id)
                    for u in league_users:
                        uid = u.get('user_id')
                        if uid not in scraped_users:
                            users_queue.append(uid)

            time.sleep(0.5)  # Respeito ao limite da API do Sleeper

    print(f"\n✅ Mapeamento concluído! Encontramos {len(draft_ids_to_scrape)} drafts únicos para minerar.")

    # PASSO 2: Extrair os Dados Reais com Contexto da Liga
    print("\n⛏️ Fase 2: Extraindo as escolhas pick a pick (com metadados da liga)...")

    all_picks_data = []

    for idx, draft_id in enumerate(draft_ids_to_scrape):
        if idx % 10 == 0:
            print(f"Baixando draft {idx}/{len(draft_ids_to_scrape)}...")

        # Puxa as regras deste draft específico
        draft_info = get_draft_info(draft_id)
        draft_type = draft_info.get('type', 'snake')

        # Pula drafts de Leilão (Auction), mantendo apenas Snake/Linear
        if draft_type not in ['snake', 'linear']:
            continue

        settings = draft_info.get('settings', {})
        metadata = draft_info.get('metadata', {})

        # Identificadores cruciais para o Machine Learning
        scoring_type = metadata.get('scoring_type', 'unknown')
        teams = settings.get('teams', 12)

        picks = get_draft_picks(draft_id)

        for pick in picks:
            if pick.get('player_id'):
                all_picks_data.append({
                    'draft_id': draft_id,
                    'scoring_type': scoring_type,  # PPR, Half-PPR, STD
                    'teams_count': teams,  # 8, 10, 12, 14 times
                    'pick_no': pick.get('pick_no'),
                    'round': pick.get('round'),
                    'draft_slot': pick.get('draft_slot'),
                    'player_id': str(pick.get('player_id')),
                })

        time.sleep(0.3)

    # PASSO 3: Salvar no Dataset
    if all_picks_data:
        df = pd.DataFrame(all_picks_data)
        df.to_csv(OUTPUT_FILE, index=False)
        print(f"\n🎉 SUCESSO! Dataset gerado com {len(df)} escolhas de draft.")
        print(f"Arquivo salvo como: {OUTPUT_FILE}")
    else:
        print("\nNenhum dado de draft foi encontrado.")


if __name__ == "__main__":
    run_snowball_scraper()