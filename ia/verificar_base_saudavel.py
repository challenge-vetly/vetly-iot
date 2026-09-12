"""
Vetly Insights — Verificação do score de base em animais saudáveis.

Regressão de calibração: garante que um animal SAUDÁVEL não entre espontaneamente
em faixa de alerta por defeito de feature. Foi assim que o problema de saturação da
`fragmentacao_repouso` apareceu — um bovino saudável entrava em Vigilância em 19,7%
das janelas sem nada de errado acontecer.

CRITÉRIO DE ACEITE: em TODAS as espécies, menos de 2% das janelas saudáveis podem
atingir score >= 40 (faixa de Vigilância).

Execução: python ia/verificar_base_saudavel.py
Saída: código 0 se todas as espécies passarem, 1 se qualquer uma falhar.
"""

import json
import os
import sys

import numpy as np

from gerar_dataset import PERFIS, ATIVIDADE_BASAL, calcular_features, gerar_janela_saudavel

N_JANELAS = 300
SEMENTE = 4242
LIMITE_PCT = 2.0

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def carregar_modelo():
    with open(os.path.join(BASE_DIR, "modelo_coeficientes.json"), encoding="utf-8") as f:
        return json.load(f)


def score_de(modelo, features):
    z = modelo["intercepto"] + sum(
        c * features[n] for c, n in zip(modelo["coeficientes"], modelo["features"])
    )
    return float(1.0 / (1.0 + np.exp(-z)) * 100.0)


def main():
    modelo = carregar_modelo()
    vigilancia = modelo["limiares"]["vigilancia"]
    deterioracao = modelo["limiares"]["deterioracao"]

    print("=" * 82)
    print("Score de base em animais SAUDÁVEIS")
    print(f"{N_JANELAS} janelas por espécie · limiar de Vigilância = {vigilancia} · "
          f"critério: < {LIMITE_PCT}% das janelas")
    print("=" * 82)
    print()
    print(f"{'espécie':9s} {'basal':>6s} {'frag.méd':>9s} {'score méd':>10s} "
          f"{'score p95':>10s} {'score máx':>10s} {'>=40':>7s} {'>=70':>7s} {'status':>9s}")
    print("-" * 82)

    falhas = []
    for especie in PERFIS:
        rng = np.random.default_rng(SEMENTE)
        perfil = PERFIS[especie]
        frags, scores = [], []
        for _ in range(N_JANELAS):
            temps, bpms, idxs = gerar_janela_saudavel(rng, perfil, especie)
            feats = calcular_features(temps, np.clip(bpms, 1, None), idxs, perfil, especie)
            frags.append(feats["fragmentacao_repouso"])
            scores.append(score_de(modelo, feats))

        frags, scores = np.array(frags), np.array(scores)
        pct_vig = float((scores >= vigilancia).mean() * 100)
        pct_det = float((scores >= deterioracao).mean() * 100)
        passou = pct_vig < LIMITE_PCT
        if not passou:
            falhas.append((especie, pct_vig))

        print(f"{especie:9s} {ATIVIDADE_BASAL[especie]:6.2f} {frags.mean():9.3f} "
              f"{scores.mean():10.1f} {np.percentile(scores, 95):10.1f} {scores.max():10.1f} "
              f"{pct_vig:6.1f}% {pct_det:6.1f}% {'OK' if passou else 'FALHOU':>9s}")

    print()
    if falhas:
        print("CRITÉRIO DE ACEITE VIOLADO:")
        for especie, pct in falhas:
            print(f"  {especie}: {pct:.1f}% das janelas saudáveis atingem Vigilância "
                  f"(limite {LIMITE_PCT}%)")
        sys.exit(1)

    print(f"OK - Criterio de aceite atendido: em todas as {len(PERFIS)} especies, menos de "
          f"{LIMITE_PCT}% das janelas saudaveis atingem a faixa de Vigilancia.")
    sys.exit(0)


if __name__ == "__main__":
    main()
