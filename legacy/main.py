import requests


def get_user_leagues(username, season="2026"):
    # 1. Busca o ID interno do usuário no Sleeper
    print(f"Buscando dados para o usuário: {username}...")
    user_url = f"https://api.sleeper.app/v1/user/{username}"
    response = requests.get(user_url)

    if response.status_code != 200 or response.json() is None:
        print("Usuário não encontrado. Verifique o nome digitado.")
        return

    user_id = response.json().get('user_id')
    print(f"ID interno encontrado: {user_id}")

    # 2. Busca as ligas desse usuário na temporada atual
    leagues_url = f"https://api.sleeper.app/v1/user/{user_id}/leagues/nfl/{season}"
    leagues_response = requests.get(leagues_url)

    if leagues_response.status_code == 200:
        leagues = leagues_response.json()
        print(f"\nVocê está em {len(leagues)} liga(s) nesta temporada:")
        for league in leagues:
            print(f"- {league['name']} (ID: {league['league_id']})")
    else:
        print("Erro ao buscar as ligas do usuário.")


if __name__ == "__main__":
    # Substitua pela sua conta do Sleeper
    username = "caiordgs"
    get_user_leagues(username)