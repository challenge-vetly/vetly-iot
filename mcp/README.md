# Vetly Collar — servidor MCP (camada 4: agente conversacional)

Servidor [MCP](https://modelcontextprotocol.io) que liga o **Claude** aos dados da coleira. O veterinário pergunta em linguagem natural ("como está o Rex?"), e o Claude responde chamando as mesmas regras e o mesmo modelo do painel. O Claude não recalcula nada por conta própria.

```
ESP32 (Wokwi) ──MQTT──► vetly_mcp_server.py ──tools MCP──► Claude ──► Veterinário
                         (últimas 30 leituras por pet)
```

- **Um arquivo:** [`vetly_mcp_server.py`](vetly_mcp_server.py), SDK oficial `mcp` (FastMCP) e transporte stdio.
- **Dados:** assina `vetlycollar/+/temperatura`, `/bpm` e `/atividade` em `broker.hivemq.com:1883` e guarda as últimas 30 leituras por pet em memória.
- **Mesmo modelo:** importa `PERFIS`, `ATIVIDADE_BASAL`, `FRAGMENTACAO_REF` e `calcular_features` de [`ia/gerar_dataset.py`](../ia/gerar_dataset.py) e lê os pesos de [`ia/modelo_coeficientes.json`](../ia/modelo_coeficientes.json).
- **Pets:** os mesmos do painel. `pet001` Rex (cão, sensores reais), `pet002` Mimi (gato) e `pet003` Tobi (coelho). As tools aceitam o id ou o nome.
- **RN-082:** toda resposta clínica traz o aviso *"a IA sugere, o profissional valida"*. A IA nunca dá diagnóstico fechado.

## Tools e prompt

| Tool | Entrada | O que devolve |
|---|---|---|
| `listar_pets` | — | id, nome, espécie e nº de leituras de cada pet |
| `ler_sinais` | `pet_id` | última temperatura, bpm e atividade + classificação do motor de regras (Normal / Atenção / Crítico) pela faixa da espécie |
| `calcular_indice_deterioracao` | `pet_id` | índice 0–100, faixa (Estável / Vigilância / Deterioração) e os 3 fatores que mais pesaram. Com menos de 30 leituras, responde `coletando dados (N/30)` |
| `faixas_da_especie` | `especie` | faixas de temperatura e bpm de `PERFIS` |
| `montar_triagem` | `pet_id`, `acao`, `justificativa` (+ `briefing_veterinario`, `mensagem_tutor` opcionais) | payloads `POST /api/ia/triagem`, `/api/ia/orientacoes` e `/api/lembretes` no formato de `montarPayloadsVetly()`, com `validadoPorProfissional: false`. **Não envia** nada |

**Prompt MCP `analise_clinica(pet_id)`:** guia o Claude por `ler_sinais` → `calcular_indice_deterioracao` → `faixas_da_especie` e pede (a) briefing técnico, (b) mensagem ao tutor e (c) ação recomendada, sempre com o aviso RN-082. As mesmas regras vão nas *instructions* do servidor. Por isso, pedir em texto livre ("faça a análise clínica do Rex") produz o mesmo formato.

## Instalação

Precisa de Python 3.10 ou mais recente.

```bash
pip install -r mcp/requirements.txt pytest
pytest mcp/            # 7 testes, sem rede
```

> O `requirements.txt` fixa `mcp<2`. No `mcp` 2.x, o `FastMCP` foi renomeado para `MCPServer`.

### Modo simulado

Com `VETLY_SIMULADO=1`, ou se o MQTT não conectar em 5 s, o servidor gera leituras saudáveis dentro da faixa de cada espécie (mesma distribuição de `gerar_janela_saudavel()`). Ele já começa com a janela de 30 leituras cheia e acrescenta uma leitura a cada 2 s. Todas as respostas trazem `"fonte": "simulado (...)"`, e o Claude avisa que os dados são de simulação.

Sem `VETLY_SIMULADO` e com o Wokwi rodando, os dados vêm do ESP32 por MQTT.

## Conectar no Claude Code

O [`.mcp.json`](../.mcp.json) na raiz já registra o servidor `vetly-collar`. Abra o Claude Code na raiz do repositório, aprove o servidor quando ele pedir e confira com `/mcp`.

```powershell
# PowerShell, demo sem Wokwi
$env:VETLY_SIMULADO = "1"; claude
```

```bash
# bash/zsh
VETLY_SIMULADO=1 claude
```

O prompt MCP fica disponível como comando: `/mcp__vetly-collar__analise_clinica Rex`.

**Se o `python` do PATH não for o que tem as dependências** (no Windows, às vezes `python` abre a Microsoft Store), registre o servidor no escopo local com o caminho completo. O registro local tem prioridade sobre o `.mcp.json` e não altera o repositório:

```powershell
claude mcp add vetly-collar -s local -e VETLY_SIMULADO=1 -- C:\caminho\para\vetly-iot\.venv\Scripts\python.exe C:\caminho\para\vetly-iot\mcp\vetly_mcp_server.py
```

## Conectar no Claude Desktop

Edite o `claude_desktop_config.json` (Windows: `%APPDATA%\Claude\`; macOS: `~/Library/Application Support/Claude/`) com **caminhos absolutos** e reinicie o Claude Desktop:

```json
{
  "mcpServers": {
    "vetly-collar": {
      "command": "C:\\caminho\\para\\vetly-iot\\.venv\\Scripts\\python.exe",
      "args": ["C:\\caminho\\para\\vetly-iot\\mcp\\vetly_mcp_server.py"],
      "env": { "VETLY_SIMULADO": "1" }
    }
  }
}
```

No macOS/Linux, use caminhos como `/Users/voce/vetly-iot/.venv/bin/python`. Remova o bloco `env` para usar os dados reais do MQTT.

## Exemplos de conversa

Os números abaixo são saídas reais das tools no modo simulado (janela inicial). Eles mudam a cada execução, porque o simulador gera uma leitura nova a cada 2 s. As respostas do Claude estão resumidas.

### 1. "Faça a análise clínica do Rex"

**Tools chamadas:** `ler_sinais("Rex")` → `calcular_indice_deterioracao("Rex")` → `faixas_da_especie("cao")`

**Resposta (resumo):**
- **(a) Briefing ao veterinário:** paciente canino com 38,4 °C e 102 bpm, dentro das faixas da espécie (37,5–39,2 °C; 60–140 bpm). O motor de regras classifica Normal, e o BPM teve leve subida nas últimas 5 leituras, sem cruzar o limiar. Índice de Deterioração 3,8/100 (Estável). O maior fator foi variabilidade de BPM (3%); queda de atividade e fragmentação do repouso estão zeradas.
- **(b) Mensagem ao tutor:** "O Rex está bem! A temperatura, os batimentos e o nível de atividade estão dentro do esperado para um cão. Continue com a rotina normal."
- **(c) Ação:** **OBSERVAR**. Índice estável e sinais na faixa da espécie.
- *Dados de simulação (VETLY_SIMULADO=1).* ⚠️ Sugestão gerada por IA, sujeita à validação de um médico veterinário (RN-082). Não é diagnóstico.

*Continuação: "gera o payload para a API".* `montar_triagem("Rex", "OBSERVAR", ...)` devolve os 3 payloads (`indiceDeterioracao: 3.8`, `tipo: "OBSERVAR"`, lembrete em 30 dias, `validadoPorProfissional: false`, `enviado: false`).

### 2. "Qual pet eu devo olhar primeiro?"

**Tools chamadas:** `listar_pets()` → `calcular_indice_deterioracao` para Rex, Mimi e Tobi

**Resposta (resumo):** os três estão na faixa Estável, então nada é urgente. Pela prioridade, a **Mimi** vem primeiro (índice 14,6), puxada pela fragmentação do repouso (46% do máximo): ela trocou mais vezes entre repouso e atividade do que o esperado para um gato. Depois vêm o Tobi (5,1) e o Rex (3,8). Sugestão: manter a Mimi em observação e reavaliar se o índice passar de 40 (Vigilância). Aviso RN-082.

### 3. "Uma ave com 38,6 °C está bem? E se fosse um cão?"

**Tools chamadas:** `faixas_da_especie("ave")` → `faixas_da_especie("cao")`

**Resposta (resumo):** para uma ave, a faixa é 40,0–42,0 °C. Então 38,6 °C está 1,4 °C abaixo do limite, um quadro compatível com hipotermia que merece avaliação. O motor de regras marca **Atenção** (3,5% abaixo do limite; Crítico só acima de 5%). Se o bpm também estiver fora da faixa (250–400), a classificação sobe para **Crítico**. Para um cão (37,5–39,2 °C), a mesma leitura é **Normal**. O sensor mede; a espécie define o significado. Aviso RN-082.

## Testes

[`test_vetly_mcp.py`](test_vetly_mcp.py), executado com `pytest mcp/`:

| Teste | O que garante |
|---|---|
| paridade com `ia/casos_de_teste.json` | o índice do servidor bate com o modelo treinado nos 20 casos (tolerância 1e-6) |
| tool do índice = cálculo direto | `calcular_features` + coeficientes do JSON dão o mesmo número da tool |
| 38,6 °C e 100 bpm: cão × ave | Normal no cão e Crítico na ave (só a temperatura dá Atenção na ave) |
| mensagens MQTT do firmware | os payloads do `sketch.ino` viram uma leitura; pet desconhecido ou payload inválido são ignorados |
| menos de 30 leituras | responde `coletando dados (12/30)` em vez de inventar número |
| formato da triagem | as chaves são lidas de `montarPayloadsVetly()` no `index.html`; `validadoPorProfissional == false` |
| ponta a ponta | sobe o servidor por stdio, lista as 5 tools e o prompt e chama o índice como o Claude faria |
