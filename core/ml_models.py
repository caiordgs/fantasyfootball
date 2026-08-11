import pandas as pd
import numpy as np
import streamlit as st
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.cluster import KMeans

@st.cache_resource(show_spinner=False)
def get_dynasty_ml_model():
    """
    Treina um RandomForestRegressor em um dataset sintético que emula
    o julgamento de um especialista em Dynasty Fantasy Football.
    """
    # 1. Gerando Dataset Sintético de Treinamento
    # Simulamos 5000 jogadores hipotéticos para o modelo aprender as regras
    np.random.seed(42)
    n_samples = 5000
    
    positions = np.random.choice(['QB', 'RB', 'WR', 'TE'], size=n_samples)
    adps = np.random.uniform(1, 300, size=n_samples)
    
    # Distribuição de idade realista por posição
    ages = []
    for pos in positions:
        if pos == 'RB': ages.append(np.random.normal(24, 2.5))
        elif pos == 'WR': ages.append(np.random.normal(25, 3.0))
        elif pos == 'TE': ages.append(np.random.normal(26, 3.5))
        else: ages.append(np.random.normal(28, 4.0))
    
    ages = np.clip(ages, 21, 40)
    
    df_train = pd.DataFrame({'Position': positions, 'ADP': adps, 'Age': ages})
    
    # 2. Definindo as Regras Especialistas (Target Value)
    values = []
    for _, row in df_train.iterrows():
        pos = row['Position']
        adp = row['ADP']
        age = row['Age']
        
        # Ajuste Posicional para transformar ADP Redraft em "ADP Dynasty"
        dynasty_adp = adp
        if pos == 'QB': dynasty_adp = adp / 2.0
        elif pos == 'TE': dynasty_adp = adp / 1.5
        elif pos == 'RB': dynasty_adp = adp + 10.0
        
        # Valor base na Escala KTC (~9999 máx) com curva mais suave
        base_value = max(0, 9999 * (0.985 ** (dynasty_adp - 1)))
        
        # Modificador de Idade (The Dynasty Age Cliff) - Agressivo igual ao KTC
        age_mod = 1.0
        if pos == 'RB':
            if age <= 23: age_mod = 1.35
            elif age <= 25: age_mod = 1.15
            elif age >= 26: age_mod = 0.80 - ((age - 26) * 0.20)
        elif pos == 'WR':
            if age <= 24: age_mod = 1.30
            elif age <= 26: age_mod = 1.10
            elif age >= 28: age_mod = 0.85 - ((age - 28) * 0.15)
        elif pos == 'TE':
            if age <= 24: age_mod = 1.25
            elif age <= 27: age_mod = 1.05
            elif age >= 30: age_mod = 0.85 - ((age - 30) * 0.10)
        elif pos == 'QB':
            if age <= 24: age_mod = 1.20
            elif age <= 28: age_mod = 1.05
            elif age >= 32: age_mod = 0.85 - ((age - 32) * 0.10)
            
        age_mod = max(0.1, age_mod) # Nunca zera totalmente, mas destrói o valor de velhos
        
        # Valor final treinado
        final_value = base_value * age_mod
        values.append(final_value)
        
    df_train['Target_Value'] = values
    
    # 3. Encoding e Treinamento
    le = LabelEncoder()
    df_train['Pos_Encoded'] = le.fit_transform(df_train['Position'])
    
    X = df_train[['Pos_Encoded', 'ADP', 'Age']]
    y = df_train['Target_Value']
    
    model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
    model.fit(X, y)
    
    return model, le

def evaluate_player_ml(player_name, model, le, df_adp, player_col, adp_col, pos_col, players_dict):
    """
    Avalia um jogador real usando o modelo treinado.
    """
    # 1. Verifica se é uma Escolha de Draft (Draft Pick)
    if "Pick" in player_name:
        # Padrão de Nomes: "2026 Pick 1.01", "2026 Pick Mid 1st", "2027 Pick 2nd", etc.
        base_pick_values = {
            "1.01": 8500,
            "Early 1st": 7000,
            "Mid 1st": 5500,
            "Late 1st": 4000,
            "2nd": 2000,
            "3rd": 800
        }
        
        # Acha o valor base
        pick_val = 2000 # Default se não achar
        for k, v in base_pick_values.items():
            if k in player_name:
                pick_val = v
                break
                
        # Calcula o desconto por ano (Time Value of Assets)
        discount = 1.0
        if "2027" in player_name:
            discount = 0.85
        elif "2028" in player_name:
            discount = 0.70
            
        final_val = pick_val * discount
        return final_val, discount, "N/A", "PICK"

    # 2. Continua o fluxo normal para jogadores
    row = df_adp[df_adp[player_col] == player_name]
    if row.empty:
        return 0, 1.0, 25, "N/A"
        
    adp = float(row[adp_col].values[0])
    pos = row[pos_col].values[0] if pos_col in row.columns else "N/A"
    
    # Busca a idade real no dicionário do Sleeper
    real_age = 25 # Padrão
    real_pos = pos
    
    for pid, info in players_dict.items():
        if info.get('full_name') == player_name:
            if info.get('age'):
                real_age = float(info.get('age'))
            if info.get('position'):
                real_pos = info.get('position')
            break
            
    if real_pos not in ['QB', 'RB', 'WR', 'TE']:
        real_pos = 'WR' # Fallback para o encoder não quebrar
        
    # Preparar Input para o ML
    try:
        pos_encoded = le.transform([real_pos])[0]
    except:
        pos_encoded = le.transform(['WR'])[0]
        
    X_pred = pd.DataFrame({'Pos_Encoded': [pos_encoded], 'ADP': [adp], 'Age': [real_age]})
    
    # Predição da IA
    ml_value = model.predict(X_pred)[0]
    
    # Calcular o valor "Burro" (Baseado só em ADP Redraft original) na nova escala
    base_value = max(0, 9999 * (0.985 ** (adp - 1)))
    
    # Razão de ganho/perda da IA (ex: 1.2 = Ganhou 20% por ser jovem, 0.6 = Perdeu 40% por ser velho)
    ai_modifier = ml_value / base_value if base_value > 0 else 1.0
    
    return ml_value, ai_modifier, real_age, real_pos

@st.cache_resource(show_spinner=False)
def get_breakout_predictor_model():
    """
    Treina um RandomForestClassifier para prever a probabilidade de Breakout (estourar a projeção).
    """
    np.random.seed(42)
    n_samples = 3000
    
    # Gerando dados sintéticos
    ages = np.random.uniform(20, 35, size=n_samples)
    adp_diff = np.random.uniform(-30, 30, size=n_samples) # Custo/Ben (Diferença entre ECR e ADP)
    risk = np.random.uniform(0, 100, size=n_samples)
    pos_encoded = np.random.choice([0, 1, 2, 3], size=n_samples) # 0:QB, 1:RB, 2:TE, 3:WR
    
    # Regras de Breakout Sintéticas:
    # 1. Jovens (<24 anos) têm maior propensão ao breakout
    # 2. Custo/Ben positivo (Especialistas rankeando muito acima do ADP)
    # 3. Risco muito alto prejudica
    labels = []
    for i in range(n_samples):
        score = 0
        if ages[i] <= 24: score += 40
        if adp_diff[i] > 10: score += 35
        elif adp_diff[i] > 0: score += 15
        
        if risk[i] < 30: score += 20
        elif risk[i] > 70: score -= 30
        
        # RB jovens têm chance bônus
        if pos_encoded[i] == 1 and ages[i] <= 23:
            score += 20
            
        is_breakout = 1 if score > 65 else 0
        labels.append(is_breakout)
        
    X_train = pd.DataFrame({'Age': ages, 'Custo/Ben': adp_diff, 'Risco': risk, 'Pos_Encoded': pos_encoded})
    y_train = np.array(labels)
    
    model = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42)
    model.fit(X_train, y_train)
    return model

def add_algorithmic_tiers(df_players):
    """
    Usa K-Means Clustering para criar Tiers Dinâmicas baseadas em VORP, Pts e Risco.
    """
    if df_players.empty or len(df_players) < 5:
        return df_players
        
    df_copy = df_players.copy()
    
    features = ['VORP', 'Pts', 'Risco']
    X = df_copy[features].fillna(0)
    
    # Normalização Simples (Min-Max)
    X_norm = (X - X.min()) / (X.max() - X.min() + 1e-9)
    
    # Determinar número de clusters (Tiers) dinamicamente com base no tamanho do dataset
    n_clusters = max(2, min(8, len(df_players) // 15))
    
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(X_norm)
    
    # Agora precisamos ordernar os clusters para que Tier 1 seja os melhores jogadores.
    # Vamos ranquear os clusters baseados na média de VORP do cluster.
    df_copy['cluster_raw'] = clusters
    cluster_means = df_copy.groupby('cluster_raw')['VORP'].mean().sort_values(ascending=False)
    
    # Mapeando: o cluster com maior VORP vira Tier 1, o segundo vira Tier 2, etc.
    tier_mapping = {raw_id: new_tier for new_tier, raw_id in enumerate(cluster_means.index, 1)}
    
    df_copy['AI_Tier'] = df_copy['cluster_raw'].map(tier_mapping)
    df_copy = df_copy.drop(columns=['cluster_raw'])
    
    return df_copy
