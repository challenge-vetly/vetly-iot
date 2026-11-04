# Roteiro do vídeo pitch — Vetly Collar (~5 min)

Disciplina *Disruptive Architectures: IoT, IoB & Generative IA* · 4º Sprint

| Bloco | Tempo | Duração |
|---|---|---|
| 1. O problema | 0:00 – 0:30 | 30 s |
| 2. A coleira no Wokwi | 0:30 – 1:15 | 45 s |
| 3. O painel e "Simular deterioração" | 1:15 – 2:30 | 1 min 15 s |
| 4. Conversa com o Claude pelo MCP | 2:30 – 4:00 | 1 min 30 s |
| 5. Benefícios para tutor e clínica | 4:00 – 4:45 | 45 s |
| 6. Encerramento | 4:45 – 5:00 | 15 s |

## Antes de gravar

- [ ] Wokwi aberto com `sketch.ino` e `diagram.json`, pronto para dar Play.
- [ ] `index.html` aberto no navegador, com o `localStorage` limpo (F12 → Application → Local Storage).
- [ ] Claude Code aberto na raiz do repositório com `VETLY_SIMULADO=1`, servidor `vetly-collar` aprovado e conectado (`/mcp`). Veja o [Passo 5 do README](README.md#passo-5--conversar-com-a-coleira-pelo-claude-mcp).
- [ ] Faça uma pergunta de teste ao Claude antes de gravar, para o servidor já estar aquecido.
- [ ] Zoom da fonte do terminal/chat em 125% ou mais.

---

## 1. O problema (0:00 – 0:30)

**Tela:** slide com o título "Vetly Collar" e a frase "o cuidado veterinário funciona por eventos isolados".

**Fala:**
> "Hoje o tutor só leva o pet ao veterinário quando o problema já está visível. Entre uma consulta e outra passam meses sem nenhum dado sobre o animal, e é nesse vazio que as doenças silenciosas se instalam. A Vetly Collar transforma esse cuidado em uma jornada contínua: ela detecta a piora enquanto os sinais ainda são sutis."

## 2. A coleira no Wokwi (0:30 – 1:15)

**Tela:** Wokwi. Dar Play e mostrar o circuito (ESP32, DS18B20, potenciômetro e MPU6050) e depois o Serial Monitor com as linhas `[PUB] vetlycollar/pet001/...`.

**Fala:**
> "Esta é a coleira, um ESP32 com três sensores: temperatura, batimentos e um acelerômetro que mede o comportamento do animal. A cada 2 segundos ela publica os dados por MQTT no broker HiveMQ. O mesmo hardware serve para cão, gato, coelho, ave ou bovino. O que muda é a interpretação, não o sensor: 38,6 °C é normal num cão e é hipotermia numa ave."

## 3. O painel e "Simular deterioração" (1:15 – 2:30)

**Tela:** `index.html` com o Rex selecionado. Mostrar os cards ao vivo e o Índice de Deterioração. Clicar em **▶ Simular deterioração** e narrar enquanto o índice sobe. Ao final, clicar em **Gerar análise com IA**.

**Fala:**
> "O painel recebe os dados em tempo real e aplica três camadas de IA. A primeira é o motor de regras, que olha o instante: o valor está dentro da faixa da espécie? A segunda é um modelo preditivo de regressão logística, que olha a trajetória das últimas 30 leituras e dá uma nota de 0 a 100."
>
> *(clicar em Simular deterioração)*
>
> "Repare: a temperatura e os batimentos continuam normais, e a regra segue dizendo Normal. Mas o Rex está ficando mais parado e dormindo pior. Isso é comportamento, IoB. O índice já entrou em Vigilância… e agora em Deterioração. Só alguns passos depois a regra finalmente reage. O modelo avisa de 9 a 10 passos antes, em 10 de 10 execuções."
>
> *(clicar em Gerar análise com IA)*
>
> "A terceira camada, a IA generativa, traduz esse quadro: um briefing técnico para o veterinário, uma mensagem simples para o tutor e uma ação recomendada."

## 4. Conversa com o Claude pelo MCP (2:30 – 4:00)

**Tela:** Claude Code (terminal ou VS Code). Mostrar rapidamente o `/mcp` com o `vetly-collar` conectado e depois digitar as perguntas abaixo. Deixar as chamadas de tool visíveis.

**Fala de abertura:**
> "Na quarta sprint integramos uma quarta camada: um agente conversacional. Criamos um servidor MCP, o protocolo aberto que liga um LLM a ferramentas. Ele assina o mesmo MQTT da coleira e expõe as nossas regras e o nosso modelo como ferramentas para o Claude. O veterinário não precisa abrir painel nenhum: basta perguntar."

**Pergunta 1:** `Faça a análise clínica do Rex`
> "Veja que o Claude não inventa números: ele chama `ler_sinais`, depois `calcular_indice_deterioracao` e `faixas_da_especie`, que usam exatamente o mesmo modelo do painel, com paridade testada. A resposta vem em três partes: briefing técnico, mensagem para o tutor e ação recomendada. E sempre com o aviso RN-082: a IA sugere, o profissional valida."

**Pergunta 2:** `Qual pet eu devo olhar primeiro?`
> "Aqui ele compara o índice dos três pets e prioriza. É a fila de atendimento da clínica montada numa pergunta."

**Pergunta 3:** `Uma ave com 38,6 °C está bem? E se fosse um cão?`
> "E a personalização por espécie: o mesmo número, 38,6 °C, é Normal no cão e fora da faixa na ave."

**Pergunta 4 (se sobrar tempo):** `Monte a triagem do Rex`
> "Por fim, ele monta o payload para a API da Vetly com `validadoPorProfissional: false`. Nada é enviado sem o veterinário validar."

## 5. Benefícios para tutor e clínica (4:00 – 4:45)

**Tela:** slide com duas colunas, Tutor e Clínica.

**Fala:**
> "Para o tutor, é tranquilidade: um aviso claro, sem jargão e sem alarmismo, antes que o problema fique grave. Para a clínica, é priorização: cada animal tem uma nota de risco explicável, a equipe sabe quem atender primeiro, e o veterinário consulta tudo em linguagem natural. A integração usa os contratos que a plataforma Vetly já tem: triagem, orientações e lembretes. O backend não muda nada."

## 6. Encerramento (4:45 – 5:00)

**Tela:** slide final com o nome da equipe e o link do repositório.

**Fala:**
> "Vetly Collar: o sensor mede, as regras classificam, o modelo prevê, a IA explica e o veterinário decide. Obrigado!"
