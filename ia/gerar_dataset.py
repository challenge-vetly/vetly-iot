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

# Fração de referência de transições repouso<->ativo por janela num animal saudável.
# Calibrada empiricamente: um animal saudável alterna de estado algumas vezes por janela
# (levanta, anda um pouco, volta a deitar) sem caracterizar inquietação patológica.
FRAGMENTACAO_REF = 0.20

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

    transicoes = sum(
        1 for i in range(1, len(niveis))
        if (niveis[i] == 0) != (niveis[i - 1] == 0)
    )
    frag_bruta = transicoes / (len(niveis) - 1)
    fragmentacao_repouso = min(1.0, frag_bruta / FRAGMENTACAO_REF)

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

    rampa = np.linspace(1, 0.15, N_JANELA)
    idxs_base = basal * rampa
    # inquietação: ruído maior + probabilidade de picos curtos, gerando muitas transições
    ruido = rng.normal(0, 0.18, N_JANELA)
    picos = (rng.random(N_JANELA) < 0.35) * rng.uniform(0.3, 0.6, N_JANELA)
    idxs = np.clip(idxs_base + ruido + picos, 0, 1)
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
