# Métricas do Modelo — Índice de Deterioração

Resultados reais da execução de `treinar_modelo.py` sobre `dataset_sintetico.csv`
(4.000 amostras, split estratificado 80/20, `random_state=42`). Nenhum número
nesta página foi editado manualmente — todos vêm da saída do script de treino.

## Métricas no conjunto de teste (800 amostras)

| Métrica | Valor | Interpretação |
|---|---|---|
| Acurácia | 0.9862 | Fração total de janelas classificadas corretamente (saudável vs. risco) |
| Precisão | 1.0000 | Das janelas que o modelo marcou como risco, esta fração realmente era risco — mede o custo de falsos alarmes |
| Recall (sensibilidade) | 0.9725 | Das janelas que realmente eram de risco, esta fração foi detectada — mede o custo de deteriorações não percebidas |
| F1-score | 0.9861 | Média harmônica entre precisão e recall — resume o equilíbrio entre os dois erros |
| AUC-ROC | 0.9997 | Capacidade do modelo de separar as duas classes em todos os limiares possíveis; 1.0 é separação perfeita, 0.5 é aleatório |

## Matriz de confusão

|  | Predito: Saudável | Predito: Risco |
|---|---|---|
| **Real: Saudável** | 400 (verdadeiro negativo) | 0 (falso positivo) |
| **Real: Risco** | 11 (falso negativo) | 389 (verdadeiro positivo) |

![Matriz de confusão](matriz_confusao.png)

## Curva ROC

![Curva ROC](curva_roc.png)

## Importância relativa das features

Ordenadas pelo valor absoluto do coeficiente da regressão logística (features
estão todas em faixas comparáveis [0,1], então os coeficientes são diretamente
comparáveis entre si sem necessidade de normalização adicional).

| Feature | Coeficiente | Importância relativa | Efeito |
|---|---|---|---|
| Queda de atividade (IoB) | +13.3322 | 40.3% | aumenta o risco |
| Desvio térmico | +8.7709 | 26.5% | aumenta o risco |
| Variabilidade de BPM | +4.0994 | 12.4% | aumenta o risco |
| Taquicardia em repouso | +2.5949 | 7.8% | aumenta o risco |
| Fragmentação do repouso (IoB) | +2.3093 | 7.0% | aumenta o risco |
| Desvio de BPM | -2.0020 | 6.0% | reduz o risco |

Intercepto do modelo: `-3.3676`

## Comparação: `class_weight='balanced'`

Em triagem clínica o falso negativo custa mais que o falso positivo, então
testamos explicitamente se o balanceamento de classes elevaria o recall.

| Métrica | Padrão | `class_weight='balanced'` |
|---|---|---|
| Acurácia | 0.9862 | 0.9862 |
| Precisão | 1.0000 | 1.0000 |
| Recall | 0.9725 | 0.9725 |
| F1-score | 0.9861 | 0.9861 |
| AUC-ROC | 0.9997 | 0.9997 |

**Resultado: as duas variantes são idênticas, e isso era esperado.** O
dataset é balanceado por construção (2.000 amostras de risco e 2.000 sem
risco), então `class_weight='balanced'` atribui peso 1.0 às duas classes —
exatamente o que o modelo padrão já faz. Não há ganho de recall a capturar
por esse caminho, e por isso **mantivemos a variante padrão**: adotar o
parâmetro sugeriria um efeito que ele não tem neste dataset.

O parâmetro passaria a importar se a proporção entre as classes mudasse —
por exemplo, ao treinar com telemetria real, onde janelas de risco são
muito mais raras que janelas saudáveis. O script reavalia as duas variantes
a cada execução e adota `balanced` automaticamente se ela elevar o recall
sem derrubar o AUC abaixo de 0,90.

**A alavanca que de fato troca falso positivo por falso negativo aqui é o
limiar de decisão, não o peso de classe.** O modelo classifica em 0,5, mas
o dashboard alerta a partir de um score de 40 (probabilidade 0,40) e marca
deterioração em 70. Ou seja: o produto já opera num ponto mais sensível que
o classificador, favorecendo a detecção precoce.

## Calibração da fragmentação do repouso

A feature `fragmentacao_repouso` passou por uma correção de calibração. O limiar de
atividade (`LIMIAR_ATIVO = 0.25`, herdado do firmware) fica colado na atividade
basal do cão (0,30) e **exatamente em cima** da do bovino (0,25). Com o ruído normal
do sensor, um animal saudável cruzava a fronteira repouso/ativo a cada leitura e a
feature saturava em 1,0 — medido em 300 janelas saudáveis por espécie:

| Espécie | Basal | Saturava em 1,0 | Score de base | Entrava em Vigilância |
|---|---|---|---|---|
| Bovino | 0,25 | 100,0% | 35,0 | 19,7% |
| Cão | 0,30 | 98,0% | 34,6 | 16,3% |
| Gato | 0,35 | 56,0% | 24,5 | 7,0% |
| Coelho | 0,40 | 3,3% | 9,1 | 1,0% |
| Ave | 0,45 | 0,3% | 3,8 | 0,0% |

Ou seja: quase um em cada cinco bovinos saudáveis entrava espontaneamente em
Vigilância, sem nada de errado acontecer. O defeito estava também no gerador do
dataset, então contaminou o treino.

**Correção aplicada nos dois lados (Python e JavaScript), de forma idêntica:**

1. **Histerese** — uma mudança de estado só é contada se o novo estado persistir por
   pelo menos 2 leituras consecutivas. Chaveamento de uma única leitura é ruído de
   sensor; fragmentação real de repouso é um episódio e dura várias leituras.
2. **Referência por espécie** — `FRAGMENTACAO_REF` deixou de ser um valor global
   (0,20) e passou a ser calibrado por espécie por `calibrar_fragmentacao.py`, de
   modo que um animal saudável fique em torno de 0,2 na feature em vez de 1,0.

Como consequência, o cenário `letargia` do gerador também foi corrigido: ele produzia
picos de **uma única leitura**, que são exatamente o que a histerese descarta (e
descarta com razão, por serem indistinguíveis de ruído). Passou a gerar episódios
reais de 2 a 4 leituras alternando repouso e atividade.

## Limitações

- **Dados sintéticos, e métricas altas por causa disso.** O modelo foi treinado
  inteiramente sobre janelas geradas por simulação estatística de cenários clínicos
  (`gerar_dataset.py`), não sobre telemetria real. Um AUC próximo de 1,0 **não
  significa que o modelo é quase perfeito clinicamente** — significa que os cenários
  simulados são bem separáveis pelas features projetadas para separá-los. Em dados
  reais, com comorbidades, variação individual e rótulos ambíguos, o desempenho seria
  substancialmente menor. Leia estas métricas como validação de que o *pipeline*
  funciona, não como estimativa de acurácia clínica.
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
