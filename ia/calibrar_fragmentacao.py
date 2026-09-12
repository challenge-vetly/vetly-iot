"""
Vetly Insights — Calibração da referência de fragmentação do repouso.

Mede, por espécie, quantas transições repouso<->ativo (já com histerese) um animal
SAUDÁVEL produz numa janela, e deriva o divisor FRAGMENTACAO_REF de modo que esse
animal saudável fique em torno de 0.2 na feature — e não saturando em 1.0.

    FRAGMENTACAO_REF[especie] = max(FRAGMENTACAO_PISO, 5 x média_saudável)

O fator 5 vem direto do alvo: se a média saudável dividida pela referência deve dar
0.2, então a referência é 1/0.2 = 5 vezes a média saudável.

O piso existe para o problema simétrico: em espécies cuja atividade basal está muito
acima do limiar (coelho 0.40, ave 0.45), a média saudável é praticamente zero e um
divisor minúsculo tornaria a feature hipersensível — uma única transição confirmada
já saturaria o sinal.

Este script é a procedência dos números em FRAGMENTACAO_REF; ele apenas reporta, não
escreve nada. Execução: python ia/calibrar_fragmentacao.py
"""

import numpy as np

from gerar_dataset import (
    PERFIS,
    ATIVIDADE_BASAL,
    FRAGMENTACAO_PISO,
    FRAGMENTACAO_REF,
    N_JANELA,
    contar_transicoes_com_histerese,
    gerar_janela_saudavel,
    gerar_janela_letargia,
    nivel_de_indice,
)

N_JANELAS = 500
SEMENTE = 2024
ALVO_SAUDAVEL = 0.2


def fragmentacao_bruta(idxs):
    niveis = [nivel_de_indice(i) for i in idxs]
    estados = [n == 0 for n in niveis]
    return contar_transicoes_com_histerese(estados) / (len(estados) - 1)


def medir(gerador, especie, semente):
    rng = np.random.default_rng(semente)
    perfil = PERFIS[especie]
    return np.array([
        fragmentacao_bruta(gerador(rng, perfil, especie)[2])
        for _ in range(N_JANELAS)
    ])


def main():
    print("=" * 78)
    print("Calibração de FRAGMENTACAO_REF por espécie")
    print(f"{N_JANELAS} janelas por espécie · {N_JANELA} leituras por janela · "
          f"alvo saudável = {ALVO_SAUDAVEL}")
    print("=" * 78)
    print()
    print(f"{'espécie':9s} {'basal':>6s} {'saudável':>9s} {'letargia':>9s} "
          f"{'5x saud.':>9s} {'REF adotada':>12s} {'feat.saud':>10s} {'feat.letar':>11s}")
    print("-" * 78)

    sugestoes = {}
    for especie in PERFIS:
        saudavel = medir(gerar_janela_saudavel, especie, SEMENTE)
        letargia = medir(gerar_janela_letargia, especie, SEMENTE + 1)

        bruta = 5 * saudavel.mean()
        ref = max(FRAGMENTACAO_PISO, round(float(bruta), 4))
        sugestoes[especie] = ref

        feat_saud = min(1.0, saudavel.mean() / ref)
        feat_letar = min(1.0, letargia.mean() / ref)

        print(f"{especie:9s} {ATIVIDADE_BASAL[especie]:6.2f} {saudavel.mean():9.4f} "
              f"{letargia.mean():9.4f} {bruta:9.4f} {ref:12.4f} "
              f"{feat_saud:10.3f} {feat_letar:11.3f}")

    print()
    print("Constantes sugeridas (replicar em gerar_dataset.py e no bloco FUNCOES-IA):")
    print("FRAGMENTACAO_REF = {")
    for especie, ref in sugestoes.items():
        print(f'    "{especie}": {ref},')
    print("}")

    print()
    divergentes = {
        e: (sugestoes[e], FRAGMENTACAO_REF[e])
        for e in sugestoes
        if abs(sugestoes[e] - FRAGMENTACAO_REF[e]) > 1e-6
    }
    if divergentes:
        print("ATENÇÃO — os valores em uso divergem da calibração medida agora:")
        for e, (novo, atual) in divergentes.items():
            print(f"  {e}: em uso {atual} | medido {novo}")
    else:
        print("OK — os valores em uso conferem com a calibração medida.")


if __name__ == "__main__":
    main()
