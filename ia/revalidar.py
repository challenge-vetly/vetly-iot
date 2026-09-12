"""
Vetly Insights — Revalidação completa do pipeline de IA, do zero.

Regenera o dataset, retreina o modelo, reinjeta os coeficientes no index.html e
roda todas as verificações automatizadas, reportando OK/FALHOU por etapa.

    python ia/revalidar.py

Código de saída 0 somente se TODAS as etapas passarem.

A verificação do Modo Demonstração precisa de jsdom (`npm install jsdom`). Se ele
não estiver disponível, essa etapa é reportada como PULADA e não derruba o
resultado — todas as demais são obrigatórias.
"""

import json
import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)

AUC_MINIMO = 0.90


def rodar(titulo, comando, obrigatoria=True, aceita_pulo=False):
    print("=" * 78)
    print(f"» {titulo}")
    print("=" * 78)
    proc = subprocess.run(comando, cwd=REPO_DIR, shell=False)
    if proc.returncode == 0:
        print(f"\n[OK] {titulo}\n")
        return "ok"
    if aceita_pulo and proc.returncode == 2:
        print(f"\n[PULADA] {titulo} — dependência de teste ausente\n")
        return "pulada"
    print(f"\n[FALHOU] {titulo} (codigo {proc.returncode})\n")
    return "falhou"


def conferir_auc():
    print("=" * 78)
    print("» AUC-ROC >= 0.90")
    print("=" * 78)
    caminho = os.path.join(BASE_DIR, "modelo_coeficientes.json")
    with open(caminho, encoding="utf-8") as f:
        auc = json.load(f)["metricas"]["auc_roc"]
    passou = auc >= AUC_MINIMO
    print(f"AUC medido: {auc:.4f} (minimo {AUC_MINIMO})")
    print(f"\n[{'OK' if passou else 'FALHOU'}] AUC-ROC\n")
    return "ok" if passou else "falhou"


def conferir_constantes():
    """Confere que as constantes do Python e do bloco FUNCOES-IA são as mesmas."""
    import re
    print("=" * 78)
    print("» Constantes sincronizadas Python <-> JavaScript")
    print("=" * 78)

    sys.path.insert(0, BASE_DIR)
    import gerar_dataset as g

    with open(os.path.join(REPO_DIR, "index.html"), encoding="utf-8") as f:
        html = f.read()
    bloco = re.search(r"FUNCOES-IA:INICIO.*?FUNCOES-IA:FIM", html, re.S).group(0)

    problemas = []

    def escalar(nome):
        m = re.search(nome + r"\s*=\s*([0-9.]+)", bloco)
        return float(m.group(1)) if m else None

    def mapa(nome):
        trecho = re.search(nome + r"\s*=\s*\{(.*?)\}", bloco, re.S).group(1)
        return {k: float(v) for k, v in re.findall(r"(\w+):\s*([0-9.]+)", trecho)}

    for nome, valor_py in (("LIMIAR_ATIVO", g.LIMIAR_ATIVO),
                           ("LIMIAR_INTENSO", g.LIMIAR_INTENSO),
                           ("PERSISTENCIA_MIN", g.PERSISTENCIA_MIN)):
        valor_js = escalar(nome)
        estado = "ok" if valor_js == valor_py else "DIVERGE"
        print(f"  {nome:22s} py={valor_py:<8} js={valor_js:<8} {estado}")
        if estado != "ok":
            problemas.append(nome)

    for nome, dic_py in (("ATIVIDADE_BASAL", g.ATIVIDADE_BASAL),
                         ("FRAGMENTACAO_REF", g.FRAGMENTACAO_REF)):
        dic_js = mapa(nome)
        iguais = all(abs(dic_js.get(k, -1) - v) < 1e-12 for k, v in dic_py.items())
        print(f"  {nome:22s} {'ok' if iguais else 'DIVERGE'}  {dic_py}")
        if not iguais:
            problemas.append(nome)

    # coeficientes: JSON versionado vs bloco MODELO-IA
    modelo_js = json.loads(
        re.search(r"const MODELO_IA = (\{.*?\});",
                  re.search(r"MODELO-IA:INICIO.*?MODELO-IA:FIM", html, re.S).group(0),
                  re.S).group(1)
    )
    with open(os.path.join(BASE_DIR, "modelo_coeficientes.json"), encoding="utf-8") as f:
        modelo_json = json.load(f)
    coefs_iguais = (modelo_js["coeficientes"] == modelo_json["coeficientes"]
                    and modelo_js["intercepto"] == modelo_json["intercepto"])
    print(f"  {'coeficientes':22s} {'ok' if coefs_iguais else 'DIVERGE'}")
    if not coefs_iguais:
        problemas.append("coeficientes")

    print(f"\n[{'OK' if not problemas else 'FALHOU'}] Constantes sincronizadas\n")
    return "ok" if not problemas else "falhou"


def main():
    py = sys.executable
    etapas = []

    etapas.append(("Gerar dataset sintetico",
                   rodar("Gerar dataset sintetico", [py, "ia/gerar_dataset.py"])))
    etapas.append(("Treinar modelo e injetar no index.html",
                   rodar("Treinar modelo e injetar no index.html", [py, "ia/treinar_modelo.py"])))
    etapas.append(("AUC-ROC >= 0.90", conferir_auc()))
    etapas.append(("Paridade Python <-> JavaScript",
                   rodar("Paridade Python <-> JavaScript", ["node", "ia/verificar_paridade.js"])))
    etapas.append(("Score de base em animais saudaveis",
                   rodar("Score de base em animais saudaveis", [py, "ia/verificar_base_saudavel.py"])))
    etapas.append(("Calibracao da fragmentacao",
                   rodar("Calibracao da fragmentacao", [py, "ia/calibrar_fragmentacao.py"])))
    etapas.append(("Constantes sincronizadas", conferir_constantes()))
    etapas.append(("Modo Demonstracao (10 execucoes)",
                   rodar("Modo Demonstracao (10 execucoes)",
                         ["node", "ia/verificar_demo.js", "10"], aceita_pulo=True)))

    print("=" * 78)
    print("RESUMO DA REVALIDACAO")
    print("=" * 78)
    falhas = 0
    for nome, estado in etapas:
        marca = {"ok": "[OK]     ", "pulada": "[PULADA] ", "falhou": "[FALHOU] "}[estado]
        print(f"  {marca}{nome}")
        if estado == "falhou":
            falhas += 1
    print()
    if falhas:
        print(f"{falhas} etapa(s) falharam.")
        sys.exit(1)
    print("Todas as etapas obrigatorias passaram.")
    sys.exit(0)


if __name__ == "__main__":
    main()
