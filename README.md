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
| Instruções de uso | Seção 8 deste README |
| Tecnologias utilizadas | Seção 10 deste README |
| **4º Sprint** — IA implementada e integrada à aplicação | Seção 3 (camada 4) e [`mcp/vetly_mcp_server.py`](mcp/vetly_mcp_server.py) |
| **4º Sprint** — Integração de interface, dados, APIs e serviços inteligentes | Diagrama da Seção 2, [`.mcp.json`](.mcp.json) e tool `montar_triagem` ([`mcp/README.md`](mcp/README.md)) |
| **4º Sprint** — Testes e validação em cenários de uso | Seção 7.4, [`mcp/test_vetly_mcp.py`](mcp/test_vetly_mcp.py) e [`ia/verificar_paridade.js`](ia/verificar_paridade.js) |
| **4º Sprint** — Evidências (fluxos conversacionais, demonstração) | [`mcp/README.md`](mcp/README.md#exemplos-de-conversa) (3 conversas) e Seção 7.4 |
| **4º Sprint** — Instruções de uso do agente | Seção 8, Passo 5 |

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

### Passo 1 — Rodar a coleira no Wokwi

1. Acesse [wokwi.com](https://wokwi.com) e crie um projeto **ESP32**
2. Cole o conteúdo de `sketch.ino` e `diagram.json` nas abas correspondentes
3. No gerenciador de bibliotecas, adicione: `PubSubClient`, `OneWire`, `DallasTemperature`, `Adafruit MPU6050`, `Adafruit Unified Sensor`
4. Clique em **Play ▶**

Você deve ver no Serial Monitor:

```
[WiFi] Conectado | IP: 10.0.0.2
[MQTT] Conectado ao broker.hivemq.com
[PUB] vetlycollar/pet001/temperatura 38.4
```

### Passo 2 — Abrir o painel

Dê **duplo clique** em `index.html`. Não precisa instalar nada, não precisa de servidor.

Aguarde cerca de 20 segundos para o Índice de Deterioração sair do estado "coletando dados".

> Se aparecerem valores estranhos, limpe o `localStorage` do navegador (F12 → Application → Local Storage) e recarregue a página.

### Passo 3 — Ligar a IA generativa (opcional)

O Índice de Deterioração já funciona sem isso. O Ollama é necessário só para o Vetly Insights.

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

**Reinicie o Ollama depois de rodar o comando.**

> Se o Ollama não estiver rodando, o painel gera os textos por um método alternativo e avisa na tela. A demonstração nunca quebra.

### Passo 4 — Retreinar o modelo (opcional)

```bash
pip install -r ia/requirements.txt
python ia/revalidar.py
```

Este comando refaz tudo do zero: gera o dataset, treina o modelo, atualiza o painel e roda todas as verificações.

### Passo 5 — Conversar com a coleira pelo Claude (MCP)

```bash
pip install -r mcp/requirements.txt
```

1. Abra o **Claude Code** na raiz do repositório. O arquivo `.mcp.json` registra o servidor `vetly-collar` automaticamente. Aprove o servidor quando o Claude Code pedir e confira com `/mcp`.
2. Se o Wokwi não estiver rodando, ative o modo simulado **antes** de abrir o Claude Code:

| Sistema | Comando |
|---|---|
| Windows (PowerShell) | `$env:VETLY_SIMULADO="1"; claude` |
| macOS / Linux | `VETLY_SIMULADO=1 claude` |

3. Pergunte: **"Faça a análise clínica do Rex"**. O Claude chama `ler_sinais`, `calcular_indice_deterioracao` e `faixas_da_especie` e responde com briefing para o veterinário, mensagem para o tutor e ação recomendada, sempre com o aviso RN-082.

> Com o Wokwi rodando e sem `VETLY_SIMULADO`, o servidor usa os dados reais do ESP32. Se o MQTT não conectar em 5 s, ele entra sozinho no modo simulado e avisa isso nas respostas.
>
> Se o `python` do PATH não tiver as dependências, ou para usar o Claude Desktop, veja [`mcp/README.md`](mcp/README.md#conectar-no-claude-code).

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