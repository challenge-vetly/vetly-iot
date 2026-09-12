/*
 * Vetly Insights — Verificação do Modo Demonstração.
 *
 * Roda a demo N vezes sobre o index.html real (DOM completo via jsdom) e checa os
 * critérios que sustentam o argumento central do pitch:
 *
 *   a) o índice atinge DETERIORAÇÃO (>= 70) antes de o motor de regras sair de
 *      "Normal" — antes de Atenção, não só antes de Crítico;
 *   b) essa separação é de no mínimo 5 passos em todas as execuções;
 *   c) convertida pelo intervalo real da demo, equivale a >= 3,5 s de tela;
 *   d) durante toda a fase 1, classificarStatus() devolve "Normal".
 *
 * Requer jsdom (só para teste; o dashboard em si não tem dependência nenhuma):
 *     npm install jsdom
 * Execução: node ia/verificar_demo.js [numero_de_execucoes]
 */

const fs = require('fs');
const path = require('path');

const EXECUCOES = parseInt(process.argv[2], 10) || 10;
const MARGEM_MIN_PASSOS = 5;
const MARGEM_MIN_SEGUNDOS = 3.5;

let JSDOM;
try {
  ({ JSDOM } = require('jsdom'));
} catch (e) {
  console.error('✗ jsdom não encontrado. Instale com: npm install jsdom');
  console.error('  (dependência apenas de teste — o dashboard não precisa dela)');
  process.exit(2);
}

const HTML_PATH = path.join(__dirname, '..', 'index.html');

function lerConstante(html, nome) {
  const m = html.match(new RegExp('const\\s+' + nome + '\\s*=\\s*(\\d+)'));
  if (!m) throw new Error(`constante ${nome} não encontrada em index.html`);
  return parseInt(m[1], 10);
}

function montarPagina() {
  let html = fs.readFileSync(HTML_PATH, 'utf8');
  html = html.replace(/<script src="https:\/\/[^"]+"><\/script>/g, '');
  const stubs = `<script>
    window.__h = {};
    window.mqtt = { connect: () => ({ on: (e, c) => { window.__h[e] = c; }, subscribe: () => {} }) };
    window.Chart = function(){ this.data={labels:[],datasets:[{},{}]}; this.update=function(){}; };
    HTMLCanvasElement.prototype.getContext = function(){ return {}; };
    window.alert = () => {}; window.confirm = () => true;
  <\/script>`;
  return html.replace('</head>', stubs + '</head>');
}

async function umaExecucao(paginaHtml, passosFase1, passos, intervalo) {
  const dom = new JSDOM(paginaHtml, {
    runScripts: 'dangerously',
    url: 'http://localhost/',
    pretendToBeVisual: true,
    virtualConsole: new (require('jsdom').VirtualConsole)(),
  });
  const w = dom.window;
  const $ = id => w.document.getElementById(id);

  // Baseline: 30 leituras perfeitamente saudáveis de cão, janela limpa.
  let t = w.Date.now();
  w.Date.now = () => t;
  const onMsg = w.__h['message'];
  for (let i = 0; i < 30; i++) {
    t += 2000;
    onMsg('vetlycollar/pet001/temperatura', { toString: () => '38.3' });
    onMsg('vetlycollar/pet001/bpm', { toString: () => '95' });
    onMsg('vetlycollar/pet001/atividade', {
      toString: () => JSON.stringify({ level: 1, steps: 5, mov_ms: 2000, idx: 0.30 }),
    });
  }
  const dateNowReal = Date.now;
  w.Date.now = () => dateNowReal();

  const baseline = parseFloat($('indiceScore').textContent);
  const regraBaseline = $('statusValue').textContent;

  $('btnSimularDeterioracao').click();

  const trilha = [];
  for (let i = 0; i < passos; i++) {
    await new Promise(r => setTimeout(r, intervalo + 15));
    trilha.push({
      passo: i + 1,
      score: parseFloat($('indiceScore').textContent),
      faixa: $('indiceRotulo').textContent,
      regra: $('statusValue').textContent,
    });
  }
  dom.window.close();

  const deterioracao = trilha.find(p => p.score >= 70);
  const vigilancia = trilha.find(p => p.score >= 40);
  const saiNormal = trilha.find(p => p.regra !== 'Normal');
  const critico = trilha.find(p => p.regra === 'Crítico');
  const fase1Normal = trilha
    .filter(p => p.passo <= passosFase1)
    .every(p => p.regra === 'Normal');

  return {
    baseline, regraBaseline,
    vigilancia: vigilancia ? vigilancia.passo : null,
    deterioracao: deterioracao ? deterioracao.passo : null,
    saiNormal: saiNormal ? saiNormal.passo : null,
    critico: critico ? critico.passo : null,
    margem: (deterioracao && saiNormal) ? saiNormal.passo - deterioracao.passo : null,
    fase1Normal,
  };
}

(async () => {
  const html = fs.readFileSync(HTML_PATH, 'utf8');
  const passosFase1 = lerConstante(html, 'DEMO_PASSOS_FASE1');
  const passosFase2 = lerConstante(html, 'DEMO_PASSOS_FASE2');
  const intervalo = lerConstante(html, 'DEMO_INTERVALO_MS');
  const passos = passosFase1 + passosFase2;
  const pagina = montarPagina();

  console.log('='.repeat(96));
  console.log(`Verificação do Modo Demonstração — ${EXECUCOES} execuções`);
  console.log(`fase 1 = ${passosFase1} passos · fase 2 = ${passosFase2} passos · `
    + `intervalo = ${intervalo} ms · duração ≈ ${((passos * intervalo) / 1000).toFixed(1)} s`);
  console.log('='.repeat(96));
  console.log();
  console.log('exec | base | Vigilância | Deterioração | regra sai de Normal | Crítico | margem | margem(s) | fase1 Normal');
  console.log('-'.repeat(96));

  const resultados = [];
  for (let i = 1; i <= EXECUCOES; i++) {
    const r = await umaExecucao(pagina, passosFase1, passos, intervalo);
    resultados.push(r);
    const margemSeg = r.margem === null ? null : (r.margem * intervalo) / 1000;
    console.log(
      `${String(i).padStart(4)} | ${String(r.baseline).padStart(4)} | `
      + `${String(r.vigilancia).padStart(10)} | ${String(r.deterioracao).padStart(12)} | `
      + `${String(r.saiNormal).padStart(19)} | ${String(r.critico).padStart(7)} | `
      + `${String(r.margem).padStart(6)} | ${String(margemSeg === null ? '-' : margemSeg.toFixed(1) + 's').padStart(9)} | `
      + `${r.fase1Normal ? 'sim' : 'NÃO'}`
    );
  }

  const margens = resultados.map(r => r.margem);
  const margemMin = Math.min(...margens);
  const margemMinSeg = (margemMin * intervalo) / 1000;

  const a = resultados.every(r => r.deterioracao !== null && r.saiNormal !== null
    && r.deterioracao < r.saiNormal);
  const b = margens.every(m => m !== null && m >= MARGEM_MIN_PASSOS);
  const c = margemMinSeg >= MARGEM_MIN_SEGUNDOS;
  const d = resultados.every(r => r.fase1Normal);

  const ok = s => s ? 'OK' : 'FALHOU';
  console.log();
  console.log('Critérios de aceite:');
  console.log(`  a) Deterioração antes de a regra sair de Normal, em ${EXECUCOES}/${EXECUCOES}: `
    + `${ok(a)} (${resultados.filter(r => r.deterioracao < r.saiNormal).length}/${EXECUCOES})`);
  console.log(`  b) margem >= ${MARGEM_MIN_PASSOS} passos em ${EXECUCOES}/${EXECUCOES}: `
    + `${ok(b)} (mínima medida: ${margemMin} passos)`);
  console.log(`  c) margem >= ${MARGEM_MIN_SEGUNDOS} s de tela: `
    + `${ok(c)} (mínima medida: ${margemMinSeg.toFixed(1)} s com intervalo de ${intervalo} ms)`);
  console.log(`  d) fase 1 inteira com regra "Normal" em ${EXECUCOES}/${EXECUCOES}: `
    + `${ok(d)} (${resultados.filter(r => r.fase1Normal).length}/${EXECUCOES})`);
  console.log();

  if (a && b && c && d) {
    console.log('OK - Todos os criterios de aceite do Modo Demonstracao foram atendidos.');
    process.exit(0);
  }
  console.log('FALHOU - Ha criterio de aceite violado.');
  process.exit(1);
})();
