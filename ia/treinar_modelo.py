"""
Vetly Insights — Treino do modelo de Índice de Deterioração.

Lê dataset_sintetico.csv, treina uma regressão logística sobre as 6 features
brutas (sem normalização/scaler — elas já estão em faixas [0,1] por construção),
avalia no conjunto de teste, exporta os artefatos de avaliação e injeta os
coeficientes finais no bloco marcado dentro de index.html.

Execução: python treinar_modelo.py
"""

import json
import os
import re
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, roc_curve, confusion_matrix,
)
from sklearn.model_selection import train_test_split

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)
INDEX_HTML = os.path.join(REPO_DIR, "index.html")

FEATURE_NAMES = [
    "desvio_termico",
    "desvio_bpm",
    "variabilidade_bpm",
    "queda_atividade",
    "fragmentacao_repouso",
    "taquicardia_repouso",
]

FEATURE_LABELS = {
    "desvio_termico": "Desvio térmico",
    "desvio_bpm": "Desvio de BPM",
    "variabilidade_bpm": "Variabilidade de BPM",
    "queda_atividade": "Queda de atividade (IoB)",
    "fragmentacao_repouso": "Fragmentação do repouso (IoB)",
    "taquicardia_repouso": "Taquicardia em repouso",
}

LIMIARES = {"vigilancia": 40, "deterioracao": 70}
RANDOM_STATE = 42
N_CASOS_TESTE = 20


def carregar_dataset():
    caminho = os.path.join(BASE_DIR, "dataset_sintetico.csv")
    return pd.read_csv(caminho)


def treinar(df):
    X = df[FEATURE_NAMES].values
    y = df["risco"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )

    modelo = LogisticRegression(random_state=RANDOM_STATE, max_iter=1000)
    modelo.fit(X_train, y_train)

    y_pred = modelo.predict(X_test)
    y_proba = modelo.predict_proba(X_test)[:, 1]

    metricas = {
        "acuracia": float(accuracy_score(y_test, y_pred)),
        "precisao": float(precision_score(y_test, y_pred)),
        "recall": float(recall_score(y_test, y_pred)),
        "f1": float(f1_score(y_test, y_pred)),
        "auc_roc": float(roc_auc_score(y_test, y_proba)),
    }
    matriz = confusion_matrix(y_test, y_pred)

    return modelo, X_test, y_test, y_pred, y_proba, metricas, matriz


def gerar_graficos(y_test, y_proba, matriz):
    # Curva ROC
    fpr, tpr, _ = roc_curve(y_test, y_proba)
    auc = roc_auc_score(y_test, y_proba)
    plt.figure(figsize=(6, 6))
    plt.plot(fpr, tpr, color="#2BB3C0", linewidth=2.5, label=f"Regressão Logística (AUC = {auc:.4f})")
    plt.plot([0, 1], [0, 1], color="#9aa3b2", linestyle="--", linewidth=1, label="Classificador aleatório")
    plt.xlabel("Taxa de Falsos Positivos")
    plt.ylabel("Taxa de Verdadeiros Positivos")
    plt.title("Curva ROC — Índice de Deterioração")
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(os.path.join(BASE_DIR, "curva_roc.png"), dpi=150)
    plt.close()

    # Matriz de confusão
    plt.figure(figsize=(5.5, 5))
    plt.imshow(matriz, cmap="Blues")
    plt.title("Matriz de Confusão")
    plt.colorbar()
    classes = ["Saudável (0)", "Risco (1)"]
    plt.xticks([0, 1], classes)
    plt.yticks([0, 1], classes)
    plt.xlabel("Predito")
    plt.ylabel("Real")
    for i in range(matriz.shape[0]):
        for j in range(matriz.shape[1]):
            cor = "white" if matriz[i, j] > matriz.max() / 2 else "black"
            plt.text(j, i, str(matriz[i, j]), ha="center", va="center", color=cor, fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(BASE_DIR, "matriz_confusao.png"), dpi=150)
    plt.close()


def exportar_coeficientes(modelo, metricas):
    dados = {
        "versao": "1.0.0",
        "tipo": "regressao_logistica",
        "gerado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "features": FEATURE_NAMES,
        "coeficientes": [float(c) for c in modelo.coef_[0]],
        "intercepto": float(modelo.intercept_[0]),
        "limiares": LIMIARES,
        "metricas": {k: round(v, 6) for k, v in metricas.items()},
    }
    caminho = os.path.join(BASE_DIR, "modelo_coeficientes.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    return dados


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def exportar_casos_de_teste(modelo, X_test, y_test):
    rng = np.random.default_rng(RANDOM_STATE)
    idx = rng.choice(len(X_test), size=N_CASOS_TESTE, replace=False)
    casos = []
    coef = modelo.coef_[0]
    intercepto = modelo.intercept_[0]
    for i in idx:
        features = X_test[i]
        z = intercepto + float(np.dot(coef, features))
        score = round(float(sigmoid(z) * 100), 8)
        caso = {
            "features": {name: round(float(v), 8) for name, v in zip(FEATURE_NAMES, features)},
            "risco_real": int(y_test[i]),
            "score_esperado": score,
        }
        casos.append(caso)
    caminho = os.path.join(BASE_DIR, "casos_de_teste.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(casos, f, ensure_ascii=False, indent=2)
    return casos


def injetar_no_index_html(modelo_json, casos):
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        conteudo = f.read()

    inicio_marcador = "<!-- MODELO-IA:INICIO — bloco gerado automaticamente por ia/treinar_modelo.py. NÃO EDITE À MÃO. -->"
    fim_marcador = "<!-- MODELO-IA:FIM -->"

    if inicio_marcador not in conteudo or fim_marcador not in conteudo:
        raise RuntimeError(
            "Marcadores MODELO-IA:INICIO / MODELO-IA:FIM não encontrados em index.html. "
            "Abortando para não corromper o arquivo."
        )

    modelo_js = json.dumps(modelo_json, ensure_ascii=False, indent=2)
    casos_js = json.dumps(casos, ensure_ascii=False, indent=2)

    bloco_novo = (
        f"{inicio_marcador}\n"
        f'    <script id="modelo-ia">\n'
        f"      const MODELO_IA = {modelo_js};\n"
        f"      const CASOS_DE_TESTE_IA = {casos_js};\n"
        f"    </script>\n"
        f"    {fim_marcador}"
    )

    padrao = re.compile(
        re.escape(inicio_marcador) + r".*?" + re.escape(fim_marcador),
        re.DOTALL,
    )
    novo_conteudo, n = padrao.subn(bloco_novo, conteudo)
    if n != 1:
        raise RuntimeError(f"Esperava substituir exatamente 1 bloco MODELO-IA, encontrou {n}.")

    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(novo_conteudo)


def escrever_metricas_md(metricas, matriz, modelo, df):
    tn, fp, fn, tp = matriz.ravel()
    coefs = modelo.coef_[0]
    importancias = sorted(zip(FEATURE_NAMES, coefs), key=lambda x: abs(x[1]), reverse=True)
    soma_abs = sum(abs(c) for _, c in importancias)

    linhas_importancia = []
    for nome, coef in importancias:
        pct = (abs(coef) / soma_abs) * 100 if soma_abs > 0 else 0
        direcao = "aumenta o risco" if coef > 0 else "reduz o risco"
        linhas_importancia.append(
            f"| {FEATURE_LABELS[nome]} | {coef:+.4f} | {pct:.1f}% | {direcao} |"
        )

    conteudo = f"""# Métricas do Modelo — Índice de Deterioração

Resultados reais da execução de `treinar_modelo.py` sobre `dataset_sintetico.csv`
(4.000 amostras, split estratificado 80/20, `random_state=42`). Nenhum número
nesta página foi editado manualmente — todos vêm da saída do script de treino.

## Métricas no conjunto de teste (800 amostras)

| Métrica | Valor | Interpretação |
|---|---|---|
| Acurácia | {metricas['acuracia']:.4f} | Fração total de janelas classificadas corretamente (saudável vs. risco) |
| Precisão | {metricas['precisao']:.4f} | Das janelas que o modelo marcou como risco, esta fração realmente era risco — mede o custo de falsos alarmes |
| Recall (sensibilidade) | {metricas['recall']:.4f} | Das janelas que realmente eram de risco, esta fração foi detectada — mede o custo de deteriorações não percebidas |
| F1-score | {metricas['f1']:.4f} | Média harmônica entre precisão e recall — resume o equilíbrio entre os dois erros |
| AUC-ROC | {metricas['auc_roc']:.4f} | Capacidade do modelo de separar as duas classes em todos os limiares possíveis; 1.0 é separação perfeita, 0.5 é aleatório |

## Matriz de confusão

|  | Predito: Saudável | Predito: Risco |
|---|---|---|
| **Real: Saudável** | {tn} (verdadeiro negativo) | {fp} (falso positivo) |
| **Real: Risco** | {fn} (falso negativo) | {tp} (verdadeiro positivo) |

![Matriz de confusão](matriz_confusao.png)

## Curva ROC

![Curva ROC](curva_roc.png)

## Importância relativa das features

Ordenadas pelo valor absoluto do coeficiente da regressão logística (features
estão todas em faixas comparáveis [0,1], então os coeficientes são diretamente
comparáveis entre si sem necessidade de normalização adicional).

| Feature | Coeficiente | Importância relativa | Efeito |
|---|---|---|---|
{chr(10).join(linhas_importancia)}

Intercepto do modelo: `{modelo.intercept_[0]:+.4f}`

## Limitações

- **Dados sintéticos.** O modelo foi treinado inteiramente sobre janelas geradas
  por simulação estatística de cenários clínicos (`gerar_dataset.py`), não sobre
  telemetria real de animais. A separabilidade das classes reflete o desenho dos
  cenários, não necessariamente a variabilidade biológica real de uma população
  de pacientes.
- **Não substitui avaliação veterinária.** Conforme a RN-082 do backend Vetly,
  este índice é uma sugestão de apoio à decisão. Nenhuma ação clínica deve ser
  tomada com base apenas no score — o veterinário valida.
- **Escala temporal comprimida na demo.** A janela de 30 leituras representa
  ~60 segundos na simulação do Wokwi (publicação a cada 2s), enquanto em produção
  representaria uma janela comportamental de ~24h. Ver `DADOS-IA.md`, seção
  "Escala temporal: simulação vs. produção".
- **5 espécies, faixas fixas.** O modelo não generaliza para espécies fora do
  objeto `PERFIS`; qualquer nova espécie exige novas faixas fisiológicas e,
  idealmente, retreino com cenários específicos.
- **Basais de atividade estimadas.** Os valores de `ATIVIDADE_BASAL` por espécie
  (usados na feature `queda_atividade`) são estimativas documentadas, não medições
  de campo — ver `DADOS-IA.md`.
"""
    caminho = os.path.join(BASE_DIR, "METRICAS.md")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo)


def main():
    df = carregar_dataset()
    modelo, X_test, y_test, y_pred, y_proba, metricas, matriz = treinar(df)

    gerar_graficos(y_test, y_proba, matriz)
    modelo_json = exportar_coeficientes(modelo, metricas)
    casos = exportar_casos_de_teste(modelo, X_test, y_test)
    injetar_no_index_html(modelo_json, casos)
    escrever_metricas_md(metricas, matriz, modelo, df)

    print("=" * 60)
    print("Treino concluído — Índice de Deterioração (regressão logística)")
    print("=" * 60)
    print(f"Amostras totais: {len(df)}  |  treino: {len(df) - len(X_test)}  |  teste: {len(X_test)}")
    print()
    print(f"Acurácia : {metricas['acuracia']:.4f}")
    print(f"Precisão : {metricas['precisao']:.4f}")
    print(f"Recall   : {metricas['recall']:.4f}")
    print(f"F1-score : {metricas['f1']:.4f}")
    print(f"AUC-ROC  : {metricas['auc_roc']:.4f}")
    print()
    print("Matriz de confusão:")
    print(matriz)
    print()
    print("Coeficientes:")
    for nome, coef in zip(FEATURE_NAMES, modelo.coef_[0]):
        print(f"  {nome:24s} {coef:+.4f}")
    print(f"  {'intercepto':24s} {modelo.intercept_[0]:+.4f}")
    print()
    print("Artefatos gerados:")
    print("  - dataset_sintetico.csv (já existente)")
    print("  - modelo_coeficientes.json")
    print("  - casos_de_teste.json")
    print("  - curva_roc.png")
    print("  - matriz_confusao.png")
    print("  - METRICAS.md")
    print("  - index.html (bloco MODELO-IA atualizado)")


if __name__ == "__main__":
    main()
