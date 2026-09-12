# `ia/` — Pipeline do modelo preditivo

Esta pasta contém tudo que produz o **Índice de Deterioração** consumido pelo
dashboard: geração do dataset, treino, avaliação e verificação de paridade.

> ⚠️ **Aviso importante:** `treinar_modelo.py` **reescreve automaticamente** o
> bloco delimitado por `<!-- MODELO-IA:INICIO -->` e `<!-- MODELO-IA:FIM -->`
> dentro de `../index.html`. Não edite aquele bloco à mão — qualquer alteração
> manual é perdida no próximo treino. Se os marcadores não forem encontrados, o
> script **falha com erro explícito** em vez de escrever no lugar errado.

---

## Arquivos

| Arquivo | Tipo | O que faz |
|---|---|---|
| `requirements.txt` | fonte | Versões exatas das dependências Python |
| `gerar_dataset.py` | fonte | Simula 4.000 janelas clínicas e calcula as 6 features |
| `calibrar_fragmentacao.py` | fonte | Mede a fragmentação de animais saudáveis e deriva `FRAGMENTACAO_REF` por espécie |
| `treinar_modelo.py` | fonte | Treina, avalia, exporta artefatos e injeta o modelo no `index.html` |
| `verificar_base_saudavel.py` | fonte | Teste de regressão: animal saudável não pode entrar sozinho em faixa de alerta |
| `verificar_paridade.js` | fonte | Confere que o JS do navegador calcula o mesmo score que o Python |
| `verificar_demo.js` | fonte | Roda o Modo Demonstração 10× e checa que o índice antecipa o motor de regras |
| `revalidar.py` | fonte | **Comando único**: roda todo o pipeline e todas as verificações, do zero |
| `dataset_sintetico.csv` | gerado | 4.000 linhas: espécie, cenário, 6 features, rótulo `risco` |
| `modelo_coeficientes.json` | gerado | **Fonte da verdade versionada** do modelo (coeficientes, limiares, métricas) |
| `casos_de_teste.json` | gerado | 20 vetores do conjunto de teste com score Python em 8 casas decimais |
| `curva_roc.png` | gerado | Curva ROC do conjunto de teste |
| `matriz_confusao.png` | gerado | Matriz de confusão do conjunto de teste |
| `METRICAS.md` | gerado | Relatório de métricas reais, importância das features e limitações |

## Ordem de execução

**Atalho — revalidar tudo de uma vez:**

```bash
pip install -r ia/requirements.txt
python ia/revalidar.py
```

`revalidar.py` executa todas as etapas abaixo em ordem e imprime um resumo com
OK/FALHOU por etapa, saindo com código 1 se qualquer uma falhar.

**Ou passo a passo:**

```bash
pip install -r ia/requirements.txt      # 1. dependências
python ia/gerar_dataset.py              # 2. gera o CSV (4.000 amostras)
python ia/treinar_modelo.py             # 3. treina, avalia e injeta no index.html
node ia/verificar_paridade.js           # 4. valida a paridade Python <-> JavaScript
python ia/verificar_base_saudavel.py    # 5. valida o score de base em animais saudáveis
node ia/verificar_demo.js 10            # 6. valida o Modo Demonstração (precisa de jsdom)
```

O passo 6 é o único que tem dependência externa (`npm install jsdom`). Ele é de
teste apenas — o dashboard não depende de nada disso. Se o jsdom não estiver
instalado, `revalidar.py` reporta a etapa como PULADA em vez de falhar.

Os passos 2 e 3 são determinísticos (`random_state=42`): rodar de novo produz
exatamente os mesmos números. Os passos 4 e 5 **precisam passar** — são as duas
garantias automatizadas do pipeline.

`calibrar_fragmentacao.py` é executado sob demanda, não a cada treino: ele só
precisa rodar de novo se as atividades basais, o limiar de atividade ou o gerador de
janelas saudáveis mudarem. Ele apenas reporta os valores medidos e avisa se os
valores em uso divergirem — não escreve em nenhum arquivo.

## Como interpretar as saídas

### `python ia/gerar_dataset.py`
Imprime a distribuição por cenário, por espécie e por rótulo, além das
estatísticas descritivas das 6 features. Espere **4.000 amostras**, balanceadas
em 2.000 de risco e 2.000 sem risco.

### `python ia/treinar_modelo.py`
Imprime as 5 métricas do conjunto de teste, a matriz de confusão e os 6
coeficientes com o intercepto.

- **AUC-ROC** é a métrica principal. **Alvo: ≥ 0,90.** Se cair abaixo, o problema
  está na geração do dataset (cenários pouco separáveis ou ruído excessivo) —
  ajuste `gerar_dataset.py` e treine de novo. Nunca force o resultado com
  vazamento de dados entre treino e teste.
- **Coeficiente positivo** = a feature empurra o score para cima (mais risco).
  **Negativo** = empurra para baixo. Como todas as features vivem em [0,1], os
  coeficientes são diretamente comparáveis entre si — é isso que torna a
  explicabilidade da interface honesta.

### `node ia/verificar_paridade.js`
Saída esperada:

```
✓ Paridade Python ↔ JavaScript verificada: 20/20 casos
```

Antes de comparar os casos, o script confere que os coeficientes embutidos no
`index.html` são idênticos aos de `modelo_coeficientes.json`. Se divergirem, ele
avisa que falta rodar o treino. Qualquer diferença de score acima de **1e-6**
imprime o caso divergente e encerra com código de saída 1.

## Por que existe um teste de paridade

O modelo é treinado em Python e executado em JavaScript, em duas implementações
independentes das mesmas fórmulas. Sem uma verificação automática, uma divergência
sutil — ordem das features, desvio padrão populacional vs. amostral, truncamento
em ponto diferente — passaria despercebida e o dashboard exibiria um score que
**não corresponde ao modelo que foi medido**. As métricas de `METRICAS.md`
descreveriam um modelo que não é o que está rodando.

O teste elimina essa classe de erro: 20 vetores reais do conjunto de teste,
pontuados nas duas linguagens, comparados com tolerância de 1e-6.

## Detalhe de arquitetura: por que os coeficientes ficam inline no HTML

O dashboard precisa funcionar aberto por duplo clique, via `file://`. Nesse
contexto o navegador **bloqueia `fetch()` de arquivos locais**, então carregar
`modelo_coeficientes.json` em tempo de execução não é possível.

A solução é injetar os coeficientes diretamente no HTML no fim do treino. Para que
as duas cópias nunca fiquem dessincronizadas:

1. `modelo_coeficientes.json` permanece como fonte da verdade versionada no Git.
2. `treinar_modelo.py` reescreve o bloco marcado do `index.html` a cada execução.
3. `verificar_paridade.js` falha se os dois divergirem.

## Dependência entre este pipeline e o dashboard

Três constantes precisam permanecer **idênticas** entre `gerar_dataset.py` e o
bloco `FUNCOES-IA` do `index.html`, sob pena de o modelo receber features com
significado diferente do que foi treinado:

| Constante | Valor |
|---|---|
| `PERFIS` (faixas por espécie) | ver `DADOS-IA.md`, seção 1.3 |
| `ATIVIDADE_BASAL` | cao 0,30 · gato 0,35 · bovino 0,25 · ave 0,45 · coelho 0,40 |
| `PERSISTENCIA_MIN` | 2 leituras |
| `FRAGMENTACAO_REF` | cao 0,4924 · gato 0,15 · bovino 0,8134 · coelho 0,15 · ave 0,15 |
| Limiares de nível | `> 0,65` → intenso; `> 0,25` → ativo; senão repouso |

Os limiares de nível vêm de `publicaAtividade()` em `sketch.ino` e não devem ser
alterados sem revalidar a simulação no Wokwi.

Além das constantes, a **função de contagem de transições com histerese** precisa ser
idêntica nos dois lados: `contar_transicoes_com_histerese()` em `gerar_dataset.py` e
`contarTransicoesComHisterese()` no bloco `FUNCOES-IA`. Uma divergência aqui não
quebra nada visivelmente — apenas faz o navegador calcular um score diferente do
modelo treinado, silenciosamente. É exatamente o tipo de erro que o teste de paridade
existe para pegar.
