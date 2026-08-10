import streamlit as st
import pandas as pd

st.title("Rookie Model (Hit Rate Predictor)")
st.markdown("Avalie a probabilidade de um novato (Rookie) se tornar uma estrela de Fantasy baseado em dados históricos de Capital de Draft (Draft Capital).")

st.sidebar.header("⚙️ Avaliador de Novato")
rookie_name = st.sidebar.text_input("Nome do Novato", placeholder="Ex: Marvin Harrison Jr.")
position = st.sidebar.selectbox("Posição", ["QB", "RB", "WR", "TE"])
draft_round = st.sidebar.selectbox("Rodada que foi Draftado (NFL Real)", [1, 2, 3, 4, 5, 6, 7, "UDFA (Não Draftado)"])
pick_number = st.sidebar.number_input("Pick Geral (Se souber, senão deixe 0)", min_value=0, max_value=259, value=0)

if st.sidebar.button("Analisar Hit Rate", type="primary"):
    if not rookie_name:
        st.sidebar.error("Digite o nome do novato.")
    else:
        # Lógica Heurística Baseada em Draft Capital Histórico da NFL
        hit_rate = 0.0
        details = []
        
        # O Hit Rate é a probabilidade do jogador ter pelo menos UMA temporada Top 24 (RB/WR/QB) ou Top 12 (TE) nos primeiros 3 anos.
        if draft_round == 1:
            if position == 'QB':
                hit_rate = 40.0 # QBs têm alto bust rate mesmo na 1ª rodada
                if pick_number > 0 and pick_number <= 3:
                    hit_rate = 55.0
                    details.append("QBs selecionados no Top 3 do Draft têm chances substancialmente maiores de garantir a titularidade no Ano 1.")
            elif position == 'RB':
                hit_rate = 70.0
                details.append("RBs de 1ª rodada recebem volume imediato. O piso (floor) é altíssimo.")
            elif position == 'WR':
                hit_rate = 45.0
                if pick_number > 0 and pick_number <= 10:
                    hit_rate = 60.0
                details.append("WRs de 1ª rodada têm uma taxa de sucesso muito sólida, mas dependem do QB da franquia que os draftou.")
            elif position == 'TE':
                hit_rate = 35.0
                details.append("TEs demoram de 2 a 3 anos para quebrar no Fantasy, mesmo os de 1ª rodada (exceções como Sam LaPorta e Kyle Pitts são raras).")
                
        elif draft_round == 2:
            if position == 'QB': hit_rate = 15.0
            elif position == 'RB': hit_rate = 45.0; details.append("Muitos RBs de 2ª rodada formam comitês e acabam roubando a vaga do veterano.")
            elif position == 'WR': hit_rate = 35.0; details.append("O 'Sweet Spot' para WRs. Jogadores como Tee Higgins, AJ Brown, Michael Pittman saíram aqui.")
            elif position == 'TE': hit_rate = 25.0
            
        elif draft_round == 3:
            if position == 'QB': hit_rate = 5.0; details.append("Raríssimo QBs de 3ª rodada virarem estrelas (Russell Wilson é um ponto fora da curva).")
            elif position == 'RB': hit_rate = 30.0; details.append("RBs de 3ª rodada geralmente precisam de uma lesão do titular para ganhar o backfield.")
            elif position == 'WR': hit_rate = 20.0
            elif position == 'TE': hit_rate = 15.0
            
        elif draft_round == 4:
            hit_rate = 10.0 if position == 'RB' else 5.0
            details.append("Daqui em diante, estamos no território de 'Dart Throws' (Tiros no Escuro).")
            
        else: # 5, 6, 7, UDFA
            hit_rate = 2.0
            if pick_number == 199 and position == 'QB':
                details.append("Lembre-se de Tom Brady, pick 199. Mas não conte com isso.")
            details.append("O Draft Capital é baixíssimo. Se a franquia o cortar amanhã, não perderá dinheiro. Fuja em ligas Dynasty.")
            
        st.subheader(f"Avaliação de: {rookie_name}")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            st.metric("Fantasy Hit Rate (%)", f"{hit_rate}%")
            
        with col2:
            st.markdown("### Contexto de Draft Capital")
            st.write(f"- **Posição:** {position}")
            st.write(f"- **Rodada Selecionada:** {draft_round}")
            
            for d in details:
                st.info(d)
                
        st.markdown("---")
        
        # Comparação visual de Expectativa
        st.subheader("Expectativa de Produção no Ano 1 vs. Ano 3")
        chart_data = pd.DataFrame(
            {
                "Ano": ["Ano 1", "Ano 2", "Ano 3"],
                "Projeção Relativa": [
                    hit_rate * 0.4 if position == 'TE' else hit_rate * 0.8,
                    hit_rate * 0.8 if position == 'TE' else hit_rate * 1.1,
                    hit_rate * 1.0 if position == 'TE' else hit_rate * 1.2
                ]
            }
        )
        st.bar_chart(chart_data, x="Ano", y="Projeção Relativa", color="#ff4b4b")
        
        st.caption("O Gráfico demonstra a curva de crescimento esperada. TEs demoram mais para pontuar bem do que RBs, por exemplo.")
else:
    st.info("Insira os dados do novato na barra lateral para gerar o relatório preditivo.")
