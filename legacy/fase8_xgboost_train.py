import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
import time


def train_draft_predictor():
    print("🧠 Inicializando treinamento do modelo XGBoost...")
    start_time = time.time()

    # 1. Carregar os Dados
    try:
        df = pd.read_csv("dataset_features.csv")
    except FileNotFoundError:
        print("❌ Erro: Arquivo 'dataset_features.csv' não encontrado. Rode a Fase 7 primeiro.")
        return

    print(f"📊 Dataset carregado: {len(df)} escolhas históricas.")

    # 2. Criar a Variável Alvo (O que queremos prever?)
    # A pergunta é: "Se eu não pegar esse cara agora, ele some até a minha próxima escolha?"
    # Para simplificar matematicamente neste primeiro modelo, vamos prever a probabilidade
    # de um jogador sair nas próximas X posições (X = tamanho da liga, ex: 12 picks).
    # Em produção, o ideal é cruzar com o 'draft_slot', mas vamos focar na escassez imediata.

    print("🎯 Calculando a Variável Alvo (Target)...")

    # Criamos uma variável que olha o "ADP" empírico (em qual pick o cara saiu de fato)
    # Mas como o dataset é composto das escolhas feitas, a variável preditora será a posição
    # e o contexto do board, para tentar adivinhar a 'pick_no' exata.

    # Para o Predictor Binário de "Roubo":
    # Nós queremos prever a probabilidade de uma POSIÇÃO (ex: RB) sair na próxima rodada.
    # Mas para recomendar JOGADORES específicos, prever o Pick Number (Regressão) é melhor.
    # Vamos usar Regressão para prever o EXPECTED PICK NUMBER (EPN).

    # --- FEATURES (O que o modelo usa para pensar) ---
    feature_cols = [
        'teams_count',
        'round',
        'draft_slot'
    ]

    # Adicionamos dinamicamente as colunas de escassez que criamos na Fase 7
    posicoes_alvo = ['QB', 'RB', 'WR', 'TE', 'DL', 'LB', 'DB', 'DE', 'DT']
    for pos in posicoes_alvo:
        feature_cols.append(f'{pos}s_gone_total')
        feature_cols.append(f'{pos}s_gone_last_5')

    # Garantir que as colunas existam no dataframe
    features_presentes = [col for col in feature_cols if col in df.columns]

    X = df[features_presentes]
    y = df['pick_no']  # O alvo é prever em qual número geral o jogador vai sair

    print(f"🧩 Features selecionadas ({len(features_presentes)}): {features_presentes}")

    # 3. Separar Treino e Teste
    print("✂️ Separando dados em Treino (80%) e Teste (20%)...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # 4. Configurar e Treinar o XGBoost
    print("🔥 Treinando as Árvores de Decisão (Isso pode levar alguns segundos)...")

    # Usamos XGBRegressor porque estamos tentando prever um número contínuo (Pick Number)
    model = xgb.XGBRegressor(
        objective='reg:squarederror',
        n_estimators=200,
        learning_rate=0.1,
        max_depth=6,
        random_state=42,
        n_jobs=-1  # Usa todos os núcleos do processador
    )

    model.fit(X_train, y_train)

    # 5. Avaliar a Inteligência do Modelo
    print("\n📈 Avaliando a precisão da IA...")
    y_pred = model.predict(X_test)

    # Métrica de Erro: MAE (Mean Absolute Error)
    # Diz, em média, quantos "picks" de erro o modelo cometeu ao prever o futuro
    mae = np.mean(np.abs(y_test - y_pred))
    print(f"🎯 Erro Médio Absoluto (MAE): {mae:.2f} picks.")
    print("   (Isso significa que o modelo erra a previsão de saída por aprox. esse número de escolhas).")

    # 6. Salvar o Modelo
    model_filename = "draft_predictor_model.json"
    model.save_model(model_filename)
    print(f"\n💾 Modelo salvo com sucesso em: {model_filename}")

    end_time = time.time()
    print(f"⏱️ Tempo total de treinamento: {end_time - start_time:.2f} segundos.")


if __name__ == "__main__":
    train_draft_predictor()