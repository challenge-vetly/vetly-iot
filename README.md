# Vetly Collar — Coleira Inteligente com IA

**Disciplina:** Disruptive Architectures: IoT, IoB & Generative IA
**Entrega:** 4º Sprint

## Equipe

| Nome | RM |
|---|---|
| Anna Clara Russo Luca | 561928 |
| Gabriel Duarte Maciel | 565754 |
| Tiago Guedes da Costa | 564731 |
| Gustavo Tavares | 562827 |

---

## O que é este projeto

Uma coleira inteligente que monitora a saúde do pet 24 horas por dia e usa Inteligência Artificial para avisar quando algo começa a dar errado — antes que o tutor perceba.

O projeto tem quatro partes:

1. **Hardware** — um ESP32 com três sensores, simulado no Wokwi
2. **Comunicação** — os dados vão para a nuvem por MQTT
3. **Inteligência** — um painel web que recebe os dados e aplica três camadas de IA
4. **Agente conversacional** — um servidor MCP que deixa o veterinário perguntar ao Claude, em linguagem natural, como está cada pet

---

## 📍 Onde encontrar cada item da avaliação

Esta tabela existe para facilitar a correção. Cada exigência da disciplina está em um lugar específico.

| O que a disciplina pede | Onde está |
|---|---|
| Problema de negócio tratado pela IA | Seção 1 deste README |
| Abordagem de IA escolhida e justificada | Seção 3 deste README |
| Como a IA personaliza, prioriza e apoia decisões | Seção 4 deste README |
| Dados usados (origem, estrutura, utilização) | Seção 5 deste README e `DADOS-IA.md` |
| Fluxo de dados entre usuário, app, banco e IA | Seção 6 deste README |
| Diagrama arquitetural | Seção 2 e Seção 6 deste README |
| Resultados e métricas do modelo | Seção 7 deste README e `ia/METRICAS.md` |
| Instruções de uso (passo a passo) | Seção 8 deste README |
| Tecnologias utilizadas | Seção 10 deste README |
| **4º Sprint** — IA implementada e integrada à aplicação | Seção 3 (camada 4) e [`mcp/vetly_mcp_server.py`](mcp/vetly_mcp_server.py) |
| **4º Sprint** — Integração de interface, dados, APIs e serviços inteligentes | Diagrama da Seção 2, [`.mcp.json`](.mcp.json) e tool `montar_triagem` ([`mcp/README.md`](mcp/README.md)) |
| **4º Sprint** — Testes e validação em cenários de uso | Seção 7.4, [`mcp/test_vetly_mcp.py`](mcp/test_vetly_mcp.py) e [`ia/verificar_paridade.js`](ia/verificar_paridade.js) |
| **4º Sprint** — Evidências (fluxos conversacionais, demonstração) | [`mcp/README.md`](mcp/README.md#exemplos-de-conversa) (3 conversas) e Seção 7.4 |
| **4º Sprint** — Instruções de uso do agente | Seção 8, Passo 4 |

---

## 1. O problema de negócio

Hoje o cuidado veterinário funciona por **eventos isolados**: o tutor leva o animal à clínica quando o problema já está visível.

Entre uma consulta e a próxima passam meses sem nenhuma informação sobre o animal. É nesse vazio que doenças silenciosas se instalam.

O problema em números:

- O mercado pet brasileiro movimenta cerca de **R$ 75 bilhões por ano**
- Mesmo assim, o tutor só percebe mudanças sutis **tarde demais**
- A clínica perde a janela em que o tratamento seria mais simples e mais barato

**O que a IA resolve:** transformar o cuidado de eventos isolados em uma **jornada contínua**, detectando a deterioração da saúde enquanto os sinais ainda são sutis.

---

## 2. A solução e a arquitetura

O mesmo hardware serve cão, gato, ave, coelho ou bovino. **O que muda é a interpretação, não o sensor.**

> Uma temperatura de **38,6 °C é normal em um cão**, mas é **hipotermia grave em uma ave** — que opera entre 40 e 42 °C.

O sensor mede. O software decide o que aquilo significa para aquela espécie.

### Diagrama da arquitetura

```mermaid
flowchart TB
    subgraph DISPOSITIVO["🐕 DISPOSITIVO (IoT)"]
        S1[Sensor de temperatura<br/>DS18B20]
        S2[Sensor de batimentos<br/>Potenciômetro]
        S3[Acelerômetro<br/>MPU6050 - comportamento]
        ESP[ESP32<br/>Firmware da coleira]
        S1 --> ESP
        S2 --> ESP
        S3 --> ESP
    end

    subgraph NUVEM["☁️ TRANSPORTE"]
        MQTT[(Broker MQTT<br/>HiveMQ)]
    end

    subgraph APP["💻 APLICAÇÃO (Painel Web)"]
        REC[Recebe os dados]
        IA1[IA 1 - Motor de Regras<br/>classifica o instante]
        IA2[IA 2 - Modelo Preditivo<br/>Indice de Deterioracao]
        IA3[IA 3 - LLM Local<br/>Vetly Insights]
        REC --> IA1
        REC --> IA2
        IA1 --> IA3
        IA2 --> IA3
    end

    subgraph AGENTE["🤖 AGENTE CONVERSACIONAL (MCP)"]
        MCPS[Servidor MCP<br/>últimas 30 leituras por pet]
        IA4[IA 4 - Claude<br/>agente conversacional]
        MCPS <-->|tools MCP<br/>sinais, índice, faixas, triagem| IA4
    end

    subgraph BACKEND["🏥 PLATAFORMA VETLY (.NET)"]
        API[API REST]
        DB[(Banco de dados<br/>Oracle)]
        API <--> DB
    end

    ESP -->|publica a cada 2s| MQTT
    MQTT -->|WebSocket seguro| REC
    MQTT -->|TCP 1883| MCPS
    IA3 -->|POST /api/ia/triagem<br/>POST /api/ia/orientacoes<br/>POST /api/lembretes| API
    MCPS -.->|mesmos payloads,<br/>montados e não enviados| API

    VET[👨‍⚕️ Veterinário]
    TUT[👤 Tutor]
    IA3 --> VET
    IA4 <-->|pergunta em linguagem natural| VET
    API --> TUT
```

O caminho da camada 4 é **MQTT → Servidor MCP → Claude → Veterinário**. O servidor MCP reaproveita as regras da camada 1 e o modelo da camada 2, sem reescrever nada.

**Ponto importante da arquitetura:** a coleira conversa com a plataforma Vetly usando endpoints que **já existiam**. Nenhuma linha do backend precisou ser alterada para a coleira funcionar.

---

## 3. Abordagem de IA escolhida e justificativa

Não usamos uma única técnica. Usamos **quatro**, porque são quatro problemas diferentes.

| Camada | Técnica de IA | Qual problema resolve | Por que esta técnica |
|---|---|---|---|
| **1** | **Motor de regras inteligentes** | O valor de agora está fora da faixa da espécie? | As faixas fisiológicas são conhecimento veterinário consolidado. Um modelo aqui só traria complexidade sem ganho. Regra é rápida, auditável e nunca erra o óbvio. |
| **2** | **Modelo preditivo** (regressão logística) | O animal está piorando, mesmo com os valores ainda normais? | Aqui existe um padrão que envolve **seis variáveis ao mesmo tempo, ao longo do tempo**. Regra não dá conta disso. Escolhemos regressão logística porque os coeficientes são **interpretáveis** — em saúde, não podemos usar caixa-preta. |
| **3** | **IA Generativa (LLM local)** | Como explicar o mesmo quadro clínico para públicos diferentes? | O veterinário precisa de termo técnico, o tutor precisa de linguagem simples. Traduzir contexto para linguagem natural é exatamente o que um LLM faz melhor que qualquer template fixo. |
| **4** | **Agente conversacional (Claude via MCP)** | Como o veterinário consulta tudo isso sem abrir o painel, só perguntando? | O MCP é o protocolo aberto para ligar um LLM a ferramentas. O Claude conduz a conversa, mas **todo número vem das tools**, ou seja, das mesmas regras e do mesmo modelo das camadas 1 e 2. Assim a conversa fica flexível e o cálculo continua auditável. |

### 4 — Agente conversacional (Claude via MCP)

Implementado no 4º Sprint em [`mcp/vetly_mcp_server.py`](mcp/vetly_mcp_server.py), um único arquivo com o SDK oficial `mcp`:

- assina por MQTT os mesmos tópicos que o `sketch.ino` publica e guarda as últimas 30 leituras de cada pet;
- expõe 5 tools: `listar_pets`, `ler_sinais` (motor de regras), `calcular_indice_deterioracao` (modelo preditivo), `faixas_da_especie` e `montar_triagem` (payloads da API .NET, **sem enviar**);
- oferece o prompt `analise_clinica`, que gera briefing para o veterinário, mensagem para o tutor e ação recomendada;
- importa as funções de `ia/gerar_dataset.py` e os pesos de `ia/modelo_coeficientes.json`, então o índice do Claude é o mesmo do painel (paridade testada);
- leva o aviso **RN-082** em toda resposta clínica: o Claude sugere, o veterinário valida.

Exemplos de conversa e instruções de conexão (Claude Code e Claude Desktop) estão em [`mcp/README.md`](mcp/README.md).

### Por que descartamos outras opções

- **Rede neural:** seria caixa-preta e injustificável para apenas 6 variáveis.
- **Árvore de decisão / ensemble:** ganho marginal de precisão com perda grande de interpretabilidade.
- **Templates de texto fixos:** não se adaptam ao contexto clínico nem à espécie.

### A diferença entre a camada 1 e a camada 2

> **As regras olham o instante. O modelo olha a trajetória.**

É por isso que o modelo consegue avisar antes. Demonstramos isso funcionando na Seção 7.

---

## 4. Como a IA gera valor

### Personalização

Todo cálculo é **relativo à espécie do paciente**. O mesmo número gera resultados opostos:

| Valor medido | Em um cão | Em uma ave |
|---|---|---|
| 38,6 °C | Normal | Hipotermia crítica |
| 200 bpm | Crítico | Abaixo do normal |

O LLM também recebe as faixas da espécie antes de escrever qualquer coisa. Sem isso, ele avaliaria um coelho com referência de cachorro.

### Priorização de ações

O Índice de Deterioração dá uma nota de **0 a 100** para cada animal. A clínica sabe **quem atender primeiro** sem precisar abrir prontuário por prontuário.

| Faixa | Nota | O que significa |
|---|---|---|
| 🟢 Estável | 0 a 39 | Nada a fazer |
| 🟡 Vigilância | 40 a 69 | Acompanhar de perto |
| 🔴 Deterioração | 70 a 100 | Ação recomendada |

### Recomendação de serviço

O Vetly Insights sempre devolve uma ação concreta: **OBSERVAR**, **AGENDAR** ou **URGÊNCIA**. Quando a recomendação é agendar, isso vira uma sugestão de consulta dentro da plataforma Vetly.

### Apoio à tomada de decisão

O sistema **nunca dá um diagnóstico fechado**. Ele entrega hipóteses e contexto, e o veterinário decide. Isso segue a regra **RN-082** da plataforma Vetly: *a IA sugere, o profissional valida*.

Além disso, o painel **nunca mostra o número sozinho**. Junto com a nota, ele mostra as três informações que mais pesaram naquele resultado. O veterinário vê de onde veio a conclusão.

---

## 5. Dados usados pela IA

### 5.1 Dados que vêm da coleira (tempo real)

| Dado | Origem | Estrutura | Como é usado |
|---|---|---|---|
| Temperatura | Sensor DS18B20 | Número decimal, °C | Detecta febre e hipotermia |
| Batimentos | Sensor de pulso | Número inteiro, bpm | Detecta taquicardia e bradicardia |
| Atividade | Acelerômetro MPU6050 | Número de 0 a 1 | **Comportamento (IoB)**: letargia e agitação |

Os três chegam a cada 2 segundos, por MQTT.

### 5.2 Dados que vêm do cadastro do pet

| Dado | Origem | Como é usado |
|---|---|---|
| Espécie | Cadastro na plataforma Vetly | Define todas as faixas de referência |
| Nome e idade | Cadastro | Personaliza o texto gerado pelo LLM |
| Faixas fisiológicas | Base de conhecimento veterinário | Referência para classificar cada leitura |

### 5.3 Dados que a plataforma Vetly já possui (integração)

Estes não são gerados pela coleira, mas alimentam o contexto clínico quando a coleira se conecta ao backend:

| Dado | De onde vem |
|---|---|
| Histórico de consultas | Tabela `Consultas` |
| Prontuário | Tabela `Prontuarios` |
| Vacinas e obrigações | Tabela `ObrigacoesPet` |
| Exames | Tabela `Exames` |
| Peso registrado | Entidade `Animal` |

### 5.4 As seis variáveis que o modelo calcula

A partir dos dados brutos, o sistema calcula seis indicadores sobre as últimas 30 leituras:

| # | Indicador | O que detecta | Peso no modelo |
|---|---|---|---|
| 1 | Queda de atividade | O animal está mais parado que o normal — **comportamento (IoB)** | **40,3%** |
| 2 | Desvio de temperatura | Febre ou hipotermia para aquela espécie | 26,5% |
| 3 | Variabilidade dos batimentos | Ritmo cardíaco instável | 12,4% |
| 4 | Taquicardia em repouso | Coração acelerado sem esforço físico | 7,8% |
| 5 | Fragmentação do repouso | Sono agitado — **comportamento (IoB)** | 7,0% |
| 6 | Desvio de batimentos | Batimento fora da faixa da espécie | 6,0% |

> **Destaque:** a variável mais importante do modelo é **comportamental**, não fisiológica. É o acelerômetro, e não o termômetro, que dá o primeiro aviso. Isso é exatamente o conceito de **IoB (Internet of Behavior)**.

### 5.5 Faixas de referência por espécie

| Espécie | Temperatura | Batimentos em repouso |
|---|---|---|
| Cão | 37,5 – 39,2 °C | 60 – 140 bpm |
| Gato | 38,0 – 39,2 °C | 140 – 220 bpm |
| Bovino | 38,0 – 39,5 °C | 40 – 80 bpm |
| Ave | 40,0 – 42,0 °C | 250 – 400 bpm |
| Coelho | 38,5 – 40,0 °C | 130 – 325 bpm |

### 5.6 De onde veio o dataset de treino

Não existe base pública de telemetria contínua multi-espécie com rótulo clínico. Por isso geramos um **dataset sintético de 4.000 janelas**, que codifica conhecimento veterinário estabelecido em seis cenários clínicos.

O gerador está em `ia/gerar_dataset.py`, com semente fixa — qualquer pessoa reproduz exatamente o mesmo dataset.

---

## 6. Fluxo de dados

```mermaid
sequenceDiagram
    participant P as 🐕 Pet
    participant C as Coleira ESP32
    participant M as Broker MQTT
    participant D as Painel Web
    participant L as LLM Local (Ollama)
    participant A as API Vetly .NET
    participant B as Banco de Dados
    participant V as 👨‍⚕️ Veterinário

    P->>C: sinais vitais e movimento
    C->>M: publica a cada 2 segundos
    M->>D: entrega em tempo real
    D->>D: 1 - Motor de regras classifica o instante
    D->>D: 2 - Modelo calcula o Índice de Deterioração
    V->>D: solicita análise
    D->>L: envia contexto clínico + índice
    L->>D: devolve 3 textos + ação recomendada
    D->>V: exibe briefing técnico e explicação
    D->>A: envia triagem e orientações
    A->>B: grava no histórico do pet
    A->>P: gera lembrete para o tutor
```

**Resumo em uma frase:** o sensor mede, o MQTT transporta, as regras classificam, o modelo prevê, o LLM explica, a API registra e o veterinário decide.

---

## 7. Resultados

### 7.1 Desempenho do modelo preditivo

Medido em 800 janelas de teste que o modelo nunca viu durante o treino:

| Métrica | Resultado | O que significa |
|---|---|---|
| **AUC-ROC** | **0,9997** | Capacidade de separar animal saudável de animal em risco |
| Acurácia | 0,9862 | Acertou 98,6% dos casos |
| Precisão | 1,0000 | Quando disse "risco", estava certo em 100% das vezes |
| Recall | 0,9725 | Encontrou 97,25% dos animais realmente em risco |

**Matriz de confusão:** 400 acertos em saudáveis · 389 acertos em risco · 0 falsos alarmes · 11 casos de risco não detectados.

> ⚠️ **Como ler esse AUC.** Um resultado de 0,9997 **não** significa que o modelo é quase perfeito na vida real. Significa que os cenários do nosso dataset sintético são bem separáveis. Ele mede a qualidade da simulação, não acurácia clínica. Com telemetria real de animais, o número seria mais baixo.

### 7.2 A prova de que o modelo antecipa a regra

Este é o resultado mais importante do projeto. O painel tem um botão **"Simular deterioração"** que injeta uma piora gradual no animal.

Medimos 10 execuções seguidas:

| Momento | Passo | O que o motor de regras dizia |
|---|---|---|
| Índice entra em **Vigilância** (40) | 10 | Normal |
| Índice entra em **Deterioração** (70) | 14 | **Normal** |
| Regras finalmente saem de Normal | 23 a 24 | Atenção |
| Regras chegam em Crítico | 25 a 26 | Crítico |

**O modelo aponta deterioração 9 a 10 passos antes de a regra reagir — cerca de 7 segundos de antecedência na simulação, em 10 de 10 execuções.**

Por que isso acontece: durante toda a primeira fase, a temperatura e os batimentos continuam **dentro da faixa normal**. O que muda primeiro é o **comportamento** — o animal fica mais parado e dorme pior. A regra não consegue ver isso. O modelo vê.

### 7.3 Garantia de que o modelo do navegador é o mesmo que foi treinado

O modelo é treinado em Python e roda em JavaScript. Existe um teste automático que compara os dois:

```
✓ Paridade Python ↔ JavaScript verificada: 20/20 casos
  Tolerância aplicada: 0.000001
```

Rode com: `node ia/verificar_paridade.js`

### 7.4 Testes do agente conversacional (4º Sprint)

O servidor MCP tem uma suíte própria, que roda sem rede em modo simulado:

```
pytest mcp/
.......                                                       [100%]
7 passed
```

| Cenário de uso testado | Resultado |
|---|---|
| Índice do servidor × `ia/casos_de_teste.json` | 20/20 casos iguais (tolerância 1e-6): o Claude usa o mesmo modelo do painel |
| 38,6 °C e 100 bpm em cão × ave | **Normal** no cão, **Crítico** na ave |
| Menos de 30 leituras | Responde "coletando dados (N/30)" em vez de inventar número |
| Triagem para a API | Chaves idênticas às de `montarPayloadsVetly()` no `index.html`, com `validadoPorProfissional: false` |
| Mensagens MQTT do firmware | Viram leituras; pet desconhecido e payload inválido são ignorados |
| Ponta a ponta por stdio | O servidor sobe, expõe 5 tools e o prompt `analise_clinica` e responde como no Claude Code |

Os fluxos conversacionais (pergunta → tools chamadas → resposta) estão em [`mcp/README.md`](mcp/README.md#exemplos-de-conversa).

---

## 8. Como executar

Siga os passos na ordem. Cada passo termina com um **✅ Confira**, para você saber se deu certo antes de seguir.

| Passo | O que você vai ver | Precisa instalar | |
|---|---|---|---|
| 0 | O projeto na sua máquina | Git | obrigatório |
| 1 | A coleira publicando dados no Wokwi | nada (navegador) | obrigatório |
| 2 | O painel com as 3 camadas de IA | nada | obrigatório |
| 3 | Os textos do Vetly Insights gerados por LLM local | Ollama | opcional |
| 4 | A conversa com a coleira pelo Claude (MCP) | Python e Claude Code | obrigatório (4º Sprint) |
| 5 | Os testes automáticos passando | Python; Node.js para a paridade | recomendado |
| 6 | O modelo retreinado do zero | Python 3.9 a 3.12 | opcional |

**Pré-requisitos:**
- navegador atualizado com acesso à internet (o Wokwi e o painel usam o broker público HiveMQ);
- **Python 3.10 ou mais recente** (recomendamos o 3.12, que também serve para o Passo 6);
- **Claude Code** com uma conta Claude, por exemplo `npm install -g @anthropic-ai/claude-code`;
- Node.js 18 ou mais recente, só para o teste de paridade do Passo 5.

### Passo 0 — Baixar o projeto

```bash
git clone https://github.com/challenge-vetly/vetly-iot.git
cd vetly-iot
```

Todos os comandos a seguir rodam nesta pasta, a raiz do repositório.

### Passo 1 — Rodar a coleira no Wokwi

1. Acesse [wokwi.com](https://wokwi.com) e crie um projeto **ESP32** (Arduino). Não é preciso fazer login para rodar.
2. Na aba `sketch.ino`, apague o conteúdo e cole o [`sketch.ino`](sketch.ino) deste repositório. Faça o mesmo na aba `diagram.json` com o [`diagram.json`](diagram.json).
3. Na aba `libraries.txt` (ou pelo **Library Manager**), adicione as bibliotecas, uma por linha:
   ```
   PubSubClient
   OneWire
   DallasTemperature
   Adafruit MPU6050
   Adafruit Unified Sensor
   ```
4. Clique em **Play ▶** e espere o Wi-Fi e o MQTT conectarem.
5. **Ajuste o acelerômetro.** Clique no **MPU6050** no circuito e arraste **Acceleration Z** de `1 g` para **cerca de 1,2 g**. Os outros controles desse painel não são usados.
   > **Por quê:** em 1 g o sensor mede só a gravidade, como se o Rex estivesse imóvel, e a atividade dá zero. O modelo interpreta isso como um animal prostrado e o índice vai a 100. Com 1,2 g, o Rex fica "Ativo", como um cão saudável.

**✅ Confira no Serial Monitor** (o IP e os contadores variam):

```
[WiFi] Conectado | IP: 10.0.0.2
[MQTT] Conectado ao broker.hivemq.com
[PUB] vetlycollar/pet001/temperatura 38.6
[PUB] vetlycollar/pet001/bpm 135
[PUB] vetlycollar/pet001/atividade {"level":1,"steps":3,"mov_ms":2000,"idx":0.39}
```

A linha de `atividade` precisa vir em JSON (`{"level":...}`). Se aparecer só um número (`0.39`), o projeto do Wokwi está com uma versão antiga do sketch. Cole o `sketch.ino` atual de novo e salve.

Deixe a simulação **rodando** durante os próximos passos. Para mudar os sinais do Rex, clique no **DS18B20** (temperatura) ou gire o **potenciômetro** (batimentos, de 50 a 220 bpm). A Mimi e o Tobi são pets virtuais gerados pelo próprio firmware.

### Passo 2 — Abrir o painel

1. Dê **duplo clique** em `index.html`. Não é preciso instalar nada nem subir servidor.
2. Espere cerca de 20 segundos para o Índice de Deterioração sair de "Coletando dados".

**✅ Confira:**
- no canto superior direito aparece **Conectado · broker.hivemq.com**;
- o Rex (marcado como SENSOR) mostra **38,6 °C**, **135 bpm** e Atividade **Ativo**;
- o Índice de Deterioração fica em **Estável** (perto de 3) e o Status clínico em **Normal**.

**Demonstração do modelo antecipando a regra:**
1. Ligue a chave **🎮 Controle de Simulação**.
2. Em "Modo demonstração", clique em **▶ Simular deterioração**.
3. O índice passa de Estável para Vigilância e depois Deterioração, enquanto o Status clínico continua **Normal**. Só bem depois a regra chega em Crítico (resultado na Seção 7.2).
4. **↺ Restaurar** desfaz a demonstração e volta aos dados do Wokwi.

> Se aparecerem valores de uma sessão antiga, limpe o `localStorage` (F12 → Application → Local Storage) e recarregue a página.

### Passo 3 — Ligar a IA generativa local (opcional)

O Índice de Deterioração funciona sem isso. O Ollama só é necessário para o Vetly Insights.

```bash
# 1. Instale o Ollama em ollama.com
# 2. Baixe o modelo
ollama pull llama3.2
```

Depois libere o acesso do navegador:

| Sistema | Comando |
|---|---|
| Windows | `setx OLLAMA_ORIGINS "*"` |
| macOS | `launchctl setenv OLLAMA_ORIGINS "*"` |
| Linux | `OLLAMA_ORIGINS="*" ollama serve` |

**Reinicie o Ollama** depois do comando e clique em **Gerar análise com IA** no painel.

> Se o Ollama não estiver rodando, o painel gera os textos por um método alternativo e avisa na tela. A demonstração não quebra.

### Passo 4 — Conversar com a coleira pelo Claude (MCP)

**4.1 Instalar as dependências (uma vez só)**

Windows (Prompt de Comando):
```bat
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r mcp/requirements.txt
```

No PowerShell, troque a segunda linha por `.venv\Scripts\Activate.ps1`.

macOS / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r mcp/requirements.txt
```

**4.2 Escolher de onde vêm os dados** (no mesmo terminal, com o venv ativado)

| Situação | O que fazer |
|---|---|
| Wokwi rodando (Passo 1) | Nada. O servidor lê os dados reais por MQTT. |
| Sem o Wokwi | Ligue o modo simulado. No Prompt de Comando, `set VETLY_SIMULADO=1`; no PowerShell, `$env:VETLY_SIMULADO="1"`; no macOS/Linux, `export VETLY_SIMULADO=1` |

**4.3 Abrir o Claude Code no mesmo terminal**

```bash
claude
```

1. Na primeira vez, o Claude Code avisa que encontrou o servidor `vetly-collar` no arquivo `.mcp.json`. **Aprove.**
2. Digite `/mcp`.

**✅ Confira:** o `vetly-collar` aparece como **connected**, com 5 tools.

> **Por que precisa ser no mesmo terminal:** o `.mcp.json` manda o Claude Code rodar `python mcp/vetly_mcp_server.py`. Com o venv ativado, esse `python` é o do venv, que tem as dependências, e a variável `VETLY_SIMULADO` também chega ao servidor. No VS Code, rode o `claude` no **terminal integrado**. Para usar o painel da extensão do VS Code ou o Claude Desktop, veja [`mcp/README.md`](mcp/README.md#outras-formas-de-conectar).

**4.4 Conversar**

| Pergunte | O Claude chama | Você deve ver |
|---|---|---|
| `Faça a análise clínica do Rex` | `ler_sinais`, `calcular_indice_deterioracao`, `faixas_da_especie` | (a) briefing para o veterinário, (b) mensagem para o tutor, (c) ação **OBSERVAR**, **AGENDAR** ou **URGENCIA** e o aviso RN-082 |
| `Qual pet eu devo olhar primeiro?` | `listar_pets` e o índice de cada pet | os pets ordenados pelo Índice de Deterioração |
| `Uma ave com 38,6 °C está bem? E se fosse um cão?` | `faixas_da_especie` | fora da faixa na ave (40–42 °C) e Normal no cão |
| `Monte a triagem do Rex` | `montar_triagem` | os payloads da API Vetly com `validadoPorProfissional: false`. Nada é enviado |

Na primeira vez que cada tool for chamada, o Claude Code pede permissão; aceite. O roteiro de análise também existe como prompt pronto: `/mcp__vetly-collar__analise_clinica Rex`.

**✅ Confira de onde vieram os dados:**
- **Modo simulado:** o Claude avisa que os dados são de simulação.
- **Wokwi:** a fonte é `mqtt (broker.hivemq.com)` e os valores do Rex batem com o Wokwi (38,6 °C e 135 bpm). O índice precisa de 30 leituras, cerca de 60 s; antes disso, a resposta diz "coletando dados (N/30)".

**Teste extra, com o Wokwi:** volte o Z do MPU6050 para `1 g`, espere uns 30 segundos e peça a análise de novo. A temperatura e os batimentos continuam normais e a regra diz Normal, mas o índice sobe para **Deterioração** por queda de atividade. É a IA detectando a piora pelo comportamento (IoB) antes dos sinais vitais.

### Passo 5 — Rodar os testes automáticos

Com o venv ativado:

```bash
pip install pytest
pytest mcp/
node ia/verificar_paridade.js
```

**✅ Confira:** `7 passed` no primeiro e `✓ Paridade Python ↔ JavaScript verificada: 20/20 casos` no segundo. O que cada teste garante está nas Seções 7.3 e 7.4.

### Passo 6 — Retreinar o modelo (opcional)

```bash
pip install -r ia/requirements.txt
python ia/revalidar.py
```

Esse comando refaz tudo do zero: gera o dataset, treina o modelo, atualiza o painel e roda todas as verificações.

> As versões fixadas em `ia/requirements.txt` só instalam em Python 3.9 a 3.12.

### 8.1 Problemas comuns

| Sintoma | Causa | Solução |
|---|---|---|
| No Serial Monitor, a `atividade` é só um número (`0.39`); no painel, Atividade fica em "Aguardando" | O Wokwi está com uma versão antiga do `sketch.ino` | Cole o `sketch.ino` atual do repositório e salve (Passo 1) |
| O índice do Rex vai a ~100 (Deterioração) com o Status clínico Normal | O MPU6050 está parado em 1 g, então a atividade é zero | Ajuste o Acceleration Z para ~1,2 g (Passo 1, item 5) |
| O painel não mostra "Conectado" | A rede bloqueia WebSocket na porta 8884 | Use outra rede (por exemplo, o roteador do celular) |
| O painel mostra valores antigos ou estranhos | Há histórico salvo de uma sessão anterior | Limpe o `localStorage` e recarregue |
| No `/mcp`, o `vetly-collar` aparece como **Failed** / "Connection closed" | O `python` que o Claude Code chamou não tem as dependências. No Windows, pode ser o atalho da Microsoft Store | Abra o `claude` no terminal com o venv ativado (Passo 4.3). Na extensão do VS Code, veja [`mcp/README.md`](mcp/README.md#outras-formas-de-conectar) |
| `ModuleNotFoundError: No module named 'mcp.server.fastmcp'` | Foi instalado o `mcp` 2.x, que renomeou o FastMCP | `pip install -r mcp/requirements.txt` (fixa `mcp<2`) |
| O PowerShell diz que `Activate.ps1` não pode ser carregado | Política de execução de scripts | Use o Prompt de Comando com `.venv\Scripts\activate.bat`, ou rode `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| O Claude responde "aguardando dados" | O MQTT conectou, mas o Wokwi está parado | Dê Play no Wokwi ou use o modo simulado (Passo 4.2) |
| O Claude responde "coletando dados (N/30)" | Ainda não há 30 leituras | Espere cerca de 60 s com o Wokwi rodando |
| As respostas dizem "simulado" sem você ter pedido | O MQTT não conectou em 5 s (rede bloqueando a porta 1883) | Libere a porta 1883 ou siga no modo simulado |

---

## 9. Estrutura do repositório

```
vetly-iot/
├── sketch.ino                   # Firmware da coleira (ESP32)
├── diagram.json                 # Circuito do Wokwi
├── index.html                   # Painel web com as 3 camadas de IA
├── .mcp.json                    # Registra o servidor MCP no Claude Code
│
├── README.md                    # Este arquivo
├── ARQUITETURA-IA.md            # Detalhamento técnico da arquitetura
├── DADOS-IA.md                  # Dicionário de dados completo
│
├── ia/
│   ├── gerar_dataset.py         # Gera as 4.000 janelas de treino
│   ├── treinar_modelo.py        # Treina e avalia o modelo
│   ├── revalidar.py             # Refaz tudo e valida
│   ├── verificar_paridade.js    # Teste Python ↔ JavaScript
│   ├── modelo_coeficientes.json # O modelo treinado
│   ├── METRICAS.md              # Métricas detalhadas
│   ├── curva_roc.png            # Gráfico de desempenho
│   └── matriz_confusao.png      # Gráfico de acertos e erros
│
└── mcp/                         # 4º Sprint — agente conversacional
    ├── vetly_mcp_server.py      # Servidor MCP (MQTT → tools para o Claude)
    ├── test_vetly_mcp.py        # Testes (pytest mcp/)
    ├── requirements.txt         # mcp, paho-mqtt e numpy
    └── README.md                # Instalação, conexão e exemplos de conversa
```

---

## 10. Tecnologias utilizadas

| Camada | Tecnologia | Para quê |
|---|---|---|
| Hardware | ESP32 DevKit-C v4 | Microcontrolador (simulado no Wokwi) |
| Sensores | DS18B20, MPU6050 | Temperatura e movimento |
| Comunicação | MQTT + HiveMQ | Transporte dos dados |
| Painel | HTML, CSS e JavaScript | Interface, sem framework e sem build |
| Gráficos | Chart.js 4.4.0 | Séries temporais |
| Treino do modelo | Python, scikit-learn, pandas | Regressão logística |
| IA Generativa | Ollama + llama3.2 | LLM rodando localmente |
| Agente conversacional | Claude + MCP (SDK Python `mcp`, FastMCP, stdio) | Consulta da coleira em linguagem natural |
| MQTT no servidor MCP | paho-mqtt | Assinatura dos tópicos da coleira |
| Testes | pytest, Node.js | Suíte do servidor MCP e paridade Python ↔ JavaScript |
| Integração | API REST da plataforma Vetly (.NET) | Registro no prontuário |

---

## 11. Limitações conhecidas

Preferimos declarar em vez de omitir:

1. **O modelo foi treinado com dados sintéticos.** As métricas medem a qualidade da simulação, não desempenho clínico real.
2. **11 casos de risco não foram detectados** (recall 0,9725), contra zero falsos alarmes. Para triagem real, o ideal seria o contrário — é preferível um alarme falso a deixar passar um animal doente.
3. **O tempo está comprimido.** Na simulação, 30 leituras são 60 segundos. Em produção seriam 24 horas. A matemática é idêntica; só a escala muda.
4. **O broker MQTT é público.** Serve para demonstração, mas em produção exigiria autenticação.
5. **O LLM do painel roda localmente**, o que é ótimo para privacidade (nenhum dado clínico sai da máquina), mas depende do computador do usuário.
6. **O agente da camada 4 usa o Claude, que roda na nuvem.** Veja a Seção 12.
7. **O servidor MCP guarda só as últimas 30 leituras, em memória**, e as perde ao reiniciar. A tool `montar_triagem` monta os payloads, mas não chama o backend .NET.

---

## 12. Privacidade

O LLM do painel (camada 3) roda **inteiramente na máquina local**. Nesse caminho, nenhum dado de saúde do animal sai do computador. Isso é privacidade por design, e não um recurso adicional.

A camada 4 é **opcional** e usa o Claude, um serviço em nuvem. Quando ela está em uso, o que as tools devolvem (nome e espécie do pet, sinais vitais, índice) passa pelos servidores da Anthropic. Nenhum dado do tutor é enviado. Em produção, isso exigiria base legal e acordo de tratamento de dados (LGPD). Quem precisar de privacidade total pode usar só o painel com o Ollama.

---

## 13. Documentação complementar

| Documento | Conteúdo |
|---|---|
| [`ARQUITETURA-IA.md`](ARQUITETURA-IA.md) | Detalhamento técnico, prompt engineering e integração com o backend |
| [`DADOS-IA.md`](DADOS-IA.md) | Dicionário de dados completo e pipeline de transformação |
| [`ia/METRICAS.md`](ia/METRICAS.md) | Métricas detalhadas com gráficos |
| [`mcp/README.md`](mcp/README.md) | Servidor MCP: instalação, conexão no Claude Code/Desktop e exemplos de conversa |