# Roteiro do vídeo — Vetly Collar · Sprint 3

**Duração alvo: 5 minutos.** Pitch técnico da camada de Inteligência Artificial.

| Equipe | RM |
|---|---|
| Anna Clara Russo Luca | 561928 |
| Gabriel Duarte Maciel | 565754 |
| Tiago Guedes da Costa | 564731 |
| Gustavo Tavares | 562827 |

---

## Checklist pré-gravação

Faça **todos** os itens antes de apertar o REC. O bloco de 2:10–3:10 é o mais
importante do vídeo e depende de estado limpo.

- [ ] **Ollama rodando com CORS liberado.** Sem `OLLAMA_ORIGINS`, o `fetch` a
      partir de `file://` (origem `null`) é bloqueado e o painel cai em modo
      offline.
  - Windows (PowerShell): `setx OLLAMA_ORIGINS "*"` → **feche e reabra** o Ollama
  - macOS: `launchctl setenv OLLAMA_ORIGINS "*"` → reinicie o Ollama
  - Linux: `OLLAMA_ORIGINS="*" ollama serve`
- [ ] Modelo baixado: `ollama pull llama3.2`
- [ ] Teste rápido: `ollama run llama3.2 "responda ok"` responde em poucos segundos
- [ ] **Wokwi rodando** e publicando (Serial Monitor mostrando linhas `[PUB]`)
- [ ] **`localStorage` limpo** — abra o DevTools (F12) → Application → Local Storage
      → remova `vetlycollar_histories_v2` e `vetlycollar_insights_v1`.
      *Por quê:* o Índice precisa partir de uma janela limpa para a demonstração
      de deterioração ficar convincente.
- [ ] Dashboard aberto e **conectado** (indicador "Conectado · broker.hivemq.com")
- [ ] Aguarde ~1 minuto com o dashboard aberto para a janela encher
      (o card do Índice precisa sair de "Coletando dados" e mostrar faixa Estável)
- [ ] Janela do navegador em **1920×1080**, zoom em 100%, DevTools fechado
- [ ] Notificações do sistema silenciadas
- [ ] **Ensaie o bloco 2:10–3:10 uma vez.** A simulação dura **~24 segundos**
      (34 passos a 700 ms) e cabe folgada no minuto do bloco, mas a narração precisa
      acompanhar os marcos: Vigilância por volta dos 7 s, Deterioração por volta dos
      10 s, e o motor de regras só reagindo aos ~16 s. Clique em **"↺ Restaurar"**
      depois do ensaio para voltar ao estado inicial.

---

## Blocos cronometrados

### 0:00 – 0:40 · O problema

**Mostrar:** slide simples ou o README aberto na seção "O problema".

**Dizer:**
> O mercado pet brasileiro movimenta cerca de 75 bilhões de reais por ano, mas o
> cuidado clínico ainda é estruturado em eventos pontuais: o tutor leva o animal à
> clínica quando algo já está visivelmente errado. Entre uma consulta e a próxima
> existe um vácuo de meses sem nenhum dado fisiológico — e é exatamente nesse
> intervalo que as doenças silenciosas se instalam.
>
> No Sprint 1 nós fechamos esse vácuo de dados com a coleira. Mas dado contínuo
> não é cuidado contínuo. O que entregamos no Sprint 1 foi um motor de regras: ele
> responde "este animal está mal agora?". Ele não responde "este animal está
> ficando pior?" — e é essa a pergunta que abre a janela de intervenção precoce.

---

### 0:40 – 1:20 · A solução e a arquitetura em uma frase

**Mostrar:** o diagrama Mermaid de `ARQUITETURA-IA.md` (seção 3).

**Dizer:**
> O Vetly Collar é uma coleira multi-espécie: o mesmo hardware mede cão, gato, ave
> ou coelho, e o software é que muda a interpretação. 38,6 °C é normal num cão e é
> hipotermia grave numa ave.
>
> A arquitetura em uma frase: **o ESP32 publica por MQTT, o dashboard consome por
> WebSocket, e sobre esse fluxo rodam três camadas de inteligência** — um motor de
> regras para o instante, um modelo de regressão logística para a trajetória, e um
> LLM local para traduzir o resultado em linguagem humana. Nada disso exigiu
> qualquer alteração no backend .NET da plataforma.

---

### 1:20 – 2:10 · Demonstração ao vivo

**Mostrar:** dashboard recebendo os três pets. Clicar entre Rex, Mimi e Tobi.

**Dizer:**
> Aqui está o dashboard ao vivo, recebendo três pacientes simultâneos do Wokwi:
> Rex, um cão com sensores físicos; Mimi, uma gata; e Tobi, um coelho — esses dois
> simulados no firmware com ruído gaussiano e drift biológico.
>
> [*clicar em Tobi*] Repare que ao trocar de paciente as faixas de referência
> mudam: o coelho opera entre 38,5 e 40 graus e entre 130 e 325 batimentos. A
> mesma leitura teria classificação completamente diferente em outra espécie.

**Mostrar:** o card do Índice de Deterioração, com as 3 contribuições.

> E esta é a primeira camada nova: o **Índice de Deterioração**, de 0 a 100. Não é
> um limiar — é a saída de uma regressão logística que olha os últimos 30 pontos e
> estima a probabilidade de o animal estar em processo de deterioração.
>
> Repare que ele **nunca aparece sozinho**: logo abaixo estão as três maiores
> contribuições para esse número. IA em saúde não pode ser caixa-preta.

---

### 2:10 – 3:10 · **O momento-chave — o modelo antecipa a regra**

**Mostrar:** abrir o painel de simulação → **"▶ Simular deterioração"**.
A animação dura **cerca de 24 segundos** (34 passos a 700 ms). Deixe o card do
Índice e o card de Status clínico visíveis ao mesmo tempo na tela — o contraste
entre os dois é o argumento inteiro.

**Dizer:**
> Agora o ponto central da entrega. Vou injetar uma deterioração em duas fases,
> igual à progressão clínica real. Primeiro um **pródromo comportamental**: a
> atividade afunda e o repouso fica fragmentado — mas a temperatura e os
> batimentos continuam **dentro da faixa normal** do cão.
>
> [*por volta do passo 10, ~7 s*] Olhem: o **Índice** já está em **Vigilância**… e o
> status por regras, embaixo, continua dizendo **Normal**. Porque não há o que elas
> possam ver: todos os valores estão dentro do limite da espécie. O que mudou foi o
> **comportamento**.
>
> [*por volta do passo 14, ~10 s*] Agora o índice entra em **Deterioração** — o
> vermelho — e as regras **continuam dizendo Normal**. Esse é o ponto. Temos aqui
> quase sete segundos de tela em que o modelo está gritando e o motor de regras não
> tem absolutamente nada a relatar.
>
> [*a partir do passo 23, ~16 s*] Só agora, na segunda fase, a temperatura e os
> batimentos cruzam de fato os limiares — e o motor de regras finalmente acorda:
> Atenção… e depois Crítico.
>
> Medimos isso em **dez execuções**, sempre com o mesmo resultado: índice em
> **Vigilância no passo 10**, **Deterioração no passo 14**, e a regra só saindo de
> Normal no **passo 23**. São **nove a dez passos de antecipação** — entre seis e
> sete segundos.
>
> E essa antecipação é **estrutural, não sorte**: as duas features de maior peso
> do modelo são justamente as de comportamento — queda de atividade e fragmentação
> do repouso. É aqui que o **IoB** deixa de ser sigla e vira diagnóstico precoce.
>
> **As regras olham o instante; o modelo olha a trajetória.** Quando a regra
> dispara, o quadro já se instalou. Quando o modelo alerta, ainda há janela de
> intervenção.

> 💡 *Se precisar repetir a demonstração, clique em "↺ Restaurar" antes.*

---

### 3:10 – 4:00 · Vetly Insights — três linguagens, um dado

**Mostrar:** clicar em **"Gerar análise com IA"**. Aguardar o spinner e o resultado.

**Dizer:**
> Com o quadro deteriorado, aciono a camada generativa: o **Vetly Insights**. Ele
> roda num LLM **local**, via Ollama — nenhum dado clínico sai da máquina.
>
> [*resultado aparece*] E aqui está o argumento técnico da camada: o mesmo estado
> clínico precisa virar **três linguagens diferentes**.
>
> Para o **veterinário**, linguagem técnica, pronta para o prontuário. Para o
> **tutor**, linguagem simples e acolhedora, sem jargão e sem alarmismo. E para o
> **sistema**, um veredito operacional — OBSERVAR, AGENDAR ou URGÊNCIA.
>
> Tradução contextual de linguagem é exatamente o que um LLM faz melhor que
> qualquer regra. E repare no rodapé: origem da geração, timestamp e nível de
> confiança. Cada geração fica registrada num log de auditoria — rastreabilidade
> de decisão de IA em saúde não é opcional.
>
> Um detalhe de engenharia que vale citar: o prompt **sempre** injeta as faixas
> fisiológicas da espécie. Sem isso o modelo avaliaria um coelho com régua de
> cachorro e erraria com confiança.

---

### 4:00 – 4:35 · Integração com o core .NET

**Mostrar:** clicar em **"Ver payload de integração"**, rolar o JSON.

**Dizer:**
> A coleira não é um produto isolado — ela alimenta a plataforma Vetly. Este botão
> mostra os payloads prontos, exatamente nos contratos que o backend .NET **já
> expõe**: `/api/ia/triagem`, `/api/ia/orientacoes` e `/api/lembretes`.
>
> E aqui está o argumento arquitetural: **nós não alteramos uma linha do backend.**
> A coleira fala os contratos que já existiam. Isso é integração por contrato e
> baixo acoplamento — a camada de IoT evolui sem arrastar o core junto.
>
> Inclusive o motor de IA é o mesmo: o backend já usa Ollama através do
> `IOllamaService`. Ao promover isso para produção, a inferência sai do navegador e
> passa para o backend reutilizando o serviço que já existe.

---

### 4:35 – 5:00 · Por que cada abordagem · encerramento

**Mostrar:** a tabela de justificativa técnica de `ARQUITETURA-IA.md` (seção 2).

**Dizer:**
> Fechando com a justificativa de cada escolha. **Regras** para a classificação
> instantânea, porque faixas fisiológicas são conhecimento consolidado — um modelo
> ali seria complexidade sem ganho. **Regressão logística** para a deterioração,
> porque precisávamos de coeficientes interpretáveis e de algo leve o bastante para
> rodar no navegador — uma rede neural seria caixa-preta injustificável para seis
> features. E **LLM** para a comunicação, porque regras não escalam para linguagem
> natural.
>
> O modelo atingiu **AUC de 0,9997** no conjunto de teste — e aqui cabe uma
> ressalva honesta: isso mede o quão bem o modelo separa os *cenários simulados*,
> não acurácia clínica. Com dados reais, o número seria bem menor. E há um teste
> automatizado que garante que o modelo rodando no navegador é o mesmo que foi
> medido em Python.
>
> Isso é o Vetly Collar: da telemetria bruta à decisão clínica, com o humano sempre
> no centro. A IA sugere; o veterinário valida.

---

## Falas de reserva (se sobrar tempo ou vier pergunta)

| Pergunta provável | Resposta curta |
|---|---|
| "Os dados são reais?" | Não — são sintéticos, e isso está documentado. Não existe base pública de telemetria contínua multi-espécie rotulada. O dataset codifica conhecimento veterinário estabelecido, e o pipeline é idêntico quando a fonte virar dado real. |
| "30 leituras é 1 minuto, não 24 horas." | Correto, e está documentado em `DADOS-IA.md`. O tempo está comprimido para caber na demo; a matemática é idêntica, muda só a taxa de agregação na entrada. |
| "O AUC de 0,9997 não é bom demais?" | É, e é justamente por serem dados sintéticos: mede separabilidade dos cenários simulados, não acurácia clínica. Testamos `class_weight='balanced'` e não muda nada, porque o dataset é balanceado por construção. |
| "Por que 11 falsos negativos e zero falsos positivos?" | O modelo prioriza precisão. Em triagem o trade-off correto é o inverso — falso negativo custa mais. A alavanca é o limiar de decisão, e o produto já opera abaixo dele: alerta a partir de score 40, não de 50. |
| "Vocês encontraram algum bug sério?" | Sim, e está documentado. A `fragmentacao_repouso` saturava em animais saudáveis porque o limiar de atividade fica em cima da basal de cão e bovino — 19,7% dos bovinos saudáveis entravam em Vigilância sozinhos. Corrigido com histerese e referência por espécie; há um teste de regressão que falha se voltar a acontecer. |
| "E se o Ollama cair no meio da apresentação?" | O painel entra em modo offline automaticamente, com fallback determinístico e selo visível. A demonstração não quebra. |
| "O que é IoB aqui?" | As features 4 e 5: queda de atividade e fragmentação do repouso. Não medimos só fisiologia, medimos comportamento — e `queda_atividade` é a feature de maior peso do modelo. |
