import requests
import json

# Cole sua chave de API aqui
API_KEY = "2OCaBQZvWU4JwbxZtQxeiunGBRMwX0c96xiOgp1g"


def testar_api_fantasypros():
    url = "https://api.fantasypros.com/public/v2/json/nfl/2026/consensus-rankings"

    headers = {
        "x-api-key": API_KEY
    }

    # Adicionando o parâmetro que a API exigiu
    params = {
        "position": "RB"
    }

    print("📡 Buscando o ranking de Running Backs (RB)...")

    try:
        # Passando o dicionário 'params' para o requests
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
            jogadores = data.get('players', [])
            qtd_jogadores = len(jogadores)

            print(f"\n✅ Conexão bem-sucedida!")
            print(f"📊 Total de RBs retornados: {qtd_jogadores}")

            if qtd_jogadores > 0:
                print("\n🔥 O Top 1:")
                top1 = jogadores[0]
                print(f"1. {top1.get('player_name')} - ECR: {top1.get('rank_ecr')}")

                print("\n🛑 O Último da Lista:")
                ultimo = jogadores[-1]
                print(f"{qtd_jogadores}. {ultimo.get('player_name')} - ECR: {ultimo.get('rank_ecr')}")

        else:
            print(f"\n❌ Erro {response.status_code}")
            print(response.text)

    except Exception as e:
        print(f"\n❌ Erro de execução no script: {e}")


if __name__ == "__main__":
    testar_api_fantasypros()