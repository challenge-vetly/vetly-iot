"""
Vetly Insights — Geração do dataset sintético para o Índice de Deterioração.

Gera janelas de 30 leituras simuladas (temperatura, BPM, atividade) para as 5
espécies suportadas pela coleira, rotuladas por cenário clínico, e calcula as
6 features de engenharia de atributos descritas em DADOS-IA.md.

Saída: dataset_sintetico.csv (4000 amostras), semente fixa (random_state=42).
"""

import numpy as np
import pandas as pd

RANDOM_STATE = 42
N_AMOSTRAS = 4000
N_JANELA = 30  # leituras por janela (replica HISTORICO_MAX do dashboard)

# Perfis fisiológicos — devem bater exatamente com o objeto PERFIS em index.html
PERFIS = {
    "cao":    {"nome": "Cão",    "temp_min": 37.5, "temp_max": 39.2, "bpm_min": 60,  "bpm_max": 140},
    "gato":   {"nome": "Gato",   "temp_min": 38.0, "temp_max": 39.2, "bpm_min": 140, "bpm_max": 220},
    "bovino": {"nome": "Bovino", "temp_min": 38.0, "temp_max": 39.5, "bpm_min": 40,  "bpm_max": 80},
    "ave":    {"nome": "Ave",    "temp_min": 40.0, "temp_max": 42.0, "bpm_min": 250, "bpm_max": 400},
    "coelho": {"nome": "Coelho", "temp_min": 38.5, "temp_max": 40.0, "bpm_min": 130, "bpm_max": 325},
}

# Atividade basal por espécie (índice bruto 0-1, mesmo campo "idx" publicado pelo firmware).
# Reflete o nível médio de movimento esperado num animal saudável em repouso/rotina normal.
# Valores de cao/gato/coelho ancorados nos mesmos basais usados na simulação do sketch.ino
# (atvBase 0.35 para o gato virtual, 0.40 para o coelho virtual); bovino e ave são estimativas
# de metabolismo/comportamento documentadas em DADOS-IA.md.
ATIVIDADE_BASAL = {
    "cao": 0.30,
    "gato": 0.35,
    "bovino": 0.25,
    "ave": 0.45,
    "coelho": 0.40,
}

# --- Fragmentação do repouso: histerese + referência por espécie ---
#
# Defeito corrigido: LIMIAR_ATIVO (0.25) fica próximo — ou, no caso do bovino,
# exatamente em cima — da atividade basal de algumas espécies. Com o ruído normal
# do sensor, um animal saudável cruzava a fronteira repouso/ativo a cada leitura e
# a feature saturava em 1.0 (medido: 98% das janelas de cão e 100% das de bovino),
# inflando o score de base e levando animais saudáveis à faixa de Vigilância.
#
# Correção 1 — histerese: uma mudança de estado só é contada se o novo estado
# persistir por pelo menos PERSISTENCIA_MIN leituras consecutivas. Chaveamento de
# uma única leitura é ruído de sensor; fragmentação real de repouso é um episódio
# (o animal levanta, fica um tempo de pé, volta a deitar) e dura várias leituras.
PERSISTENCIA_MIN = 2

# Correção 2 — referência por espécie, em vez de um valor global de 0.20.
# Calibrada por ia/calibrar_fragmentacao.py de modo que um animal SAUDÁVEL daquela
# espécie produza fragmentacao_repouso em torno de 0.2 (e não 1.0):
#     FRAGMENTACAO_REF[especie] = max(PISO, 5 x média de transições saudáveis)
# O piso evita o efeito oposto: em espécies cuja basal está muito acima do limiar
# (coelho, ave), a média saudável é quase zero e um divisor minúsculo tornaria a
# feature hipersensível, saturando com uma única transição confirmada.
FRAGMENTACAO_PISO = 0.15
FRAGMENTACAO_REF = {
    "cao": 0.4924,
    "gato": 0.15,
    "bovino": 0.8134,
    "coelho": 0.15,
    "ave": 0.15,
}

# Limiares de nível de atividade — idênticos aos usados em publicaAtividade() no sketch.ino
LIMIAR_ATIVO = 0.25
LIMIAR_INTENSO = 0.65

FEATURE_NAMES = [
    "desvio_termico",
    "desvio_bpm",
    "variabilidade_bpm",
    "queda_atividade",
    "fragmentacao_repouso",
    "taquicardia_repouso",
]


def nivel_de_indice(idx):
    if idx > LIMIAR_INTENSO:
        return 2
    if idx > LIMIAR_ATIVO:
        return 1
    return 0


def contar_transicoes_com_histerese(estados, persistencia=PERSISTENCIA_MIN):
    """Conta transições repouso<->ativo ignorando chaveamento por ruído.

    `estados` é uma lista de booleanos (True = em repouso). Uma mudança só é
    contada quando o novo estado se mantém por `persistencia` leituras seguidas.
    Precisa ser idêntica à versão JavaScript no bloco FUNCOES-IA do index.html.
    """
    n = len(estados)
    if n == 0:
        return 0
    confirmado = estados[0]
    transicoes = 0
    for i in range(1, n):
        if estados[i] == confirmado:
            continue
        duracao = 1
        j = i + 1
        while j < n and estados[j] == estados[i]:
            duracao += 1
            j += 1
        if duracao >= persistencia:
            transicoes += 1
            confirmado = estados[i]
    return transicoes


def calcular_features(temps, bpms, idxs, perfil, especie):
    temps = np.asarray(temps, dtype=float)
    bpms = np.asarray(bpms, dtype=float)
    idxs = np.clip(np.asarray(idxs, dtype=float), 0.0, 1.0)
    niveis = [nivel_de_indice(i) for i in idxs]

    tmin, tmax = perfil["temp_min"], perfil["temp_max"]
    bmin, bmax = perfil["bpm_min"], perfil["bpm_max"]

    c_t, h_t = (tmin + tmax) / 2, (tmax - tmin) / 2
    z_t = (temps.mean() - c_t) / h_t
    desvio_termico = min(1.0, max(0.0, abs(z_t) - 1.0))

    c_b, h_b = (bmin + bmax) / 2, (bmax - bmin) / 2
    z_b = (bpms.mean() - c_b) / h_b
    desvio_bpm = min(1.0, max(0.0, abs(z_b) - 1.0))

    media_bpm = bpms.mean()
    variabilidade_bpm = min(1.0, (bpms.std() / media_bpm)) if media_bpm > 0 else 0.0

    basal = ATIVIDADE_BASAL[especie]
    queda_atividade = min(1.0, max(0.0, 1.0 - (idxs.mean() / basal)))

    estados_repouso = [n == 0 for n in niveis]
    transicoes = contar_transicoes_com_histerese(estados_repouso)
    frag_bruta = transicoes / (len(niveis) - 1)
    fragmentacao_repouso = min(1.0, frag_bruta / FRAGMENTACAO_REF[especie])

    taquicardia_repouso = sum(
        1 for b, n in zip(bpms, niveis) if b > bmax and n == 0
    ) / len(bpms)

    return {
        "desvio_termico": desvio_termico,
        "desvio_bpm": desvio_bpm,
        "variabilidade_bpm": variabilidade_bpm,
        "queda_atividade": queda_atividade,
        "fragmentacao_repouso": fragmentacao_repouso,
        "taquicardia_repouso": taquicardia_repouso,
    }


def gerar_janela_saudavel(rng, perfil, especie):
    tmed = (perfil["temp_min"] + perfil["temp_max"]) / 2
    bmed = (perfil["bpm_min"] + perfil["bpm_max"]) / 2
    amp_t = (perfil["temp_max"] - perfil["temp_min"]) / 2
    amp_b = (perfil["bpm_max"] - perfil["bpm_min"]) / 2
    basal = ATIVIDADE_BASAL[especie]

    temps = rng.normal(tmed, amp_t * 0.12, N_JANELA)
    bpms = rng.normal(bmed, amp_b * 0.10, N_JANELA)
    idxs = np.clip(rng.normal(basal, 0.08, N_JANELA), 0, 1)
    return temps, bpms, idxs


def gerar_janela_atividade_intensa(rng, perfil, especie):
    bmax = perfil["bpm_max"]
    tmed = (perfil["temp_min"] + perfil["temp_max"]) / 2
    amp_t = (perfil["temp_max"] - perfil["temp_min"]) / 2

    temps = rng.normal(tmed, amp_t * 0.15, N_JANELA)
    bpms = rng.normal(bmax * 1.10, bmax * 0.06, N_JANELA)
    idxs = np.clip(rng.normal(0.80, 0.08, N_JANELA), 0, 1)
    return temps, bpms, idxs


def gerar_janela_febre(rng, perfil, especie):
    tmax = perfil["temp_max"]
    tmed = (perfil["temp_min"] + perfil["temp_max"]) / 2
    bmed = (perfil["bpm_min"] + perfil["bpm_max"]) / 2
    amp_b = (perfil["bpm_max"] - perfil["bpm_min"]) / 2
    basal = ATIVIDADE_BASAL[especie]

    rampa = np.linspace(0, 1, N_JANELA)
    pico_temp = tmax + rng.uniform(0.8, 2.0)
    temps = tmed + rampa * (pico_temp - tmed) + rng.normal(0, 0.12, N_JANELA)
    pico_bpm = bmed + amp_b * rng.uniform(0.9, 1.5)
    bpms = bmed + rampa * (pico_bpm - bmed) + rng.normal(0, amp_b * 0.08, N_JANELA)
    idxs = np.clip(rng.normal(basal * 0.85, 0.08, N_JANELA), 0, 1)
    return temps, bpms, idxs


def gerar_janela_taquicardia_repouso(rng, perfil, especie):
    bmax = perfil["bpm_max"]
    tmed = (perfil["temp_min"] + perfil["temp_max"]) / 2
    amp_t = (perfil["temp_max"] - perfil["temp_min"]) / 2

    temps = rng.normal(tmed, amp_t * 0.15, N_JANELA)
    bpms = rng.normal(bmax * 1.25, bmax * 0.06, N_JANELA)
    idxs = np.clip(rng.normal(0.08, 0.05, N_JANELA), 0, 1)
    return temps, bpms, idxs


def gerar_janela_letargia(rng, perfil, especie):
    tmed = (perfil["temp_min"] + perfil["temp_max"]) / 2
    bmed = (perfil["bpm_min"] + perfil["bpm_max"]) / 2
    amp_t = (perfil["temp_max"] - perfil["temp_min"]) / 2
    amp_b = (perfil["bpm_max"] - perfil["bpm_min"]) / 2
    basal = ATIVIDADE_BASAL[especie]

    temps = rng.normal(tmed, amp_t * 0.12, N_JANELA)
    bpms = rng.normal(bmed, amp_b * 0.12, N_JANELA)

    # Inquietação real: episódios alternados de repouso e atividade, cada um com
    # 2 a 4 leituras de duração. Não são picos de uma única leitura — esses seriam
    # (corretamente) descartados pela histerese, por serem indistinguíveis de ruído
    # de sensor. Sono agitado de verdade é um episódio, não um blip.
    idxs = np.zeros(N_JANELA)
    i = 0
    em_repouso = True
    while i < N_JANELA:
        duracao = int(rng.integers(2, 5))
        fim = min(N_JANELA, i + duracao)
        # Patamar de repouso bem abaixo do limiar; patamar ativo claramente acima,
        # para que o episódio seja detectável mesmo com o ruído do sensor.
        patamar = LIMIAR_ATIVO * 0.32 if em_repouso else LIMIAR_ATIVO + 0.10
        idxs[i:fim] = patamar
        i = fim
        em_repouso = not em_repouso

    # Declínio global de atividade sobreposto aos episódios (letargia progressiva),
    # suave o bastante para não apagar os patamares ativos.
    rampa = np.linspace(1.0, 0.80, N_JANELA)
    idxs = np.clip(idxs * rampa + rng.normal(0, 0.02, N_JANELA), 0, 1)
    return temps, bpms, idxs


def gerar_janela_hipotermia(rng, perfil, especie):
    tmin = perfil["temp_min"]
    bmin = perfil["bpm_min"]
    tmed = (perfil["temp_min"] + perfil["temp_max"]) / 2
    bmed = (perfil["bpm_min"] + perfil["bpm_max"]) / 2

    rampa = np.linspace(0, 1, N_JANELA)
    vale_temp = tmin - rng.uniform(1.0, 2.5)
    temps = tmed + rampa * (vale_temp - tmed) + rng.normal(0, 0.10, N_JANELA)
    vale_bpm = bmin * rng.uniform(0.55, 0.80)
    bpms = bmed + rampa * (vale_bpm - bmed) + rng.normal(0, bmin * 0.05, N_JANELA)
    idxs = np.clip(rng.normal(0.04, 0.03, N_JANELA), 0, 1)
    return temps, bpms, idxs


CENARIOS = [
    ("saudavel",              1600, 0, gerar_janela_saudavel),
    ("atividade_intensa",      400, 0, gerar_janela_atividade_intensa),
    ("febre",                  600, 1, gerar_janela_febre),
    ("taquicardia_repouso",    600, 1, gerar_janela_taquicardia_repouso),
    ("letargia",               480, 1, gerar_janela_letargia),
    ("hipotermia_choque",      320, 1, gerar_janela_hipotermia),
]


def main():
    rng = np.random.default_rng(RANDOM_STATE)
    especies = list(PERFIS.keys())

    linhas = []
    for cenario, quantidade, risco, gerador in CENARIOS:
        for i in range(quantidade):
            especie = especies[rng.integers(0, len(especies))]
            perfil = PERFIS[especie]
            temps, bpms, idxs = gerador(rng, perfil, especie)
            bpms = np.clip(bpms, 1, None)
            feats = calcular_features(temps, bpms, idxs, perfil, especie)
            linha = {"especie": especie, "cenario": cenario}
            linha.update(feats)
            linha["risco"] = risco
            linhas.append(linha)

    df = pd.DataFrame(linhas)
    # embaralha para não deixar amostras agrupadas por cenário
    df = df.sample(frac=1.0, random_state=RANDOM_STATE).reset_index(drop=True)

    assert len(df) == N_AMOSTRAS, f"esperado {N_AMOSTRAS} amostras, obtido {len(df)}"

    saida = "dataset_sintetico.csv"
    import os
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), saida)
    df.to_csv(caminho, index=False)

    print(f"Dataset sintético gerado: {caminho}")
    print(f"Total de amostras: {len(df)}")
    print("\nDistribuição por cenário:")
    print(df["cenario"].value_counts())
    print("\nDistribuição por espécie:")
    print(df["especie"].value_counts())
    print("\nDistribuição de risco:")
    print(df["risco"].value_counts())
    print("\nEstatísticas das features:")
    print(df[FEATURE_NAMES].describe())


if __name__ == "__main__":
    main()
