/*
 * Vetly Insights — Teste de paridade Python <-> JavaScript.
 *
 * Garante que o modelo que roda no navegador é exatamente o mesmo que foi
 * treinado e medido em Python. Extrai os blocos marcados de index.html,
 * avalia as funções em Node e compara os scores com casos_de_teste.json.
 *
 * Execução: node ia/verificar_paridade.js
 * Saída: código 0 se todos os casos passarem, 1 na primeira divergência.
 */

const fs = require('fs');
const path = require('path');
const Module = require('module');

const TOLERANCIA = 1e-6;

function extrairBlocoScript(html, marcadorInicio, marcadorFim) {
  const i = html.indexOf(marcadorInicio);
  if (i === -1) throw new Error(`Marcador não encontrado em index.html: ${marcadorInicio}`);
  const f = html.indexOf(marcadorFim, i);
  if (f === -1) throw new Error(`Marcador não encontrado em index.html: ${marcadorFim}`);

  const trecho = html.slice(i, f + marcadorFim.length);
  const script = trecho.match(/<script[^>]*>([\s\S]*?)<\/script>/);
  if (!script) throw new Error(`Nenhum bloco <script> entre ${marcadorInicio} e ${marcadorFim}`);
  return script[1];
}

function carregarImplementacaoJs(htmlPath) {
  const html = fs.readFileSync(htmlPath, 'utf8');

  const blocoModelo = extrairBlocoScript(html, 'MODELO-IA:INICIO', 'MODELO-IA:FIM');
  const blocoFuncoes = extrairBlocoScript(html, 'FUNCOES-IA:INICIO', 'FUNCOES-IA:FIM');

  const codigo = [
    blocoModelo,
    blocoFuncoes,
    'module.exports = { MODELO_IA, calcularScoreBruto, calcularIndiceDeterioracao, classificarIndice, explicarIndice, calcularFeatures };',
  ].join('\n');

  const modulo = new Module(htmlPath);
  modulo._compile(codigo, htmlPath);
  return modulo.exports;
}

function main() {
  const htmlPath = path.join(__dirname, '..', 'index.html');
  const casosPath = path.join(__dirname, 'casos_de_teste.json');

  const impl = carregarImplementacaoJs(htmlPath);
  const casos = JSON.parse(fs.readFileSync(casosPath, 'utf8'));

  if (!Array.isArray(casos) || casos.length === 0) {
    console.error('✗ casos_de_teste.json vazio ou inválido. Rode python ia/treinar_modelo.py primeiro.');
    process.exit(1);
  }

  // Confere que o modelo embutido no HTML é o mesmo do JSON versionado.
  const modeloJson = JSON.parse(
    fs.readFileSync(path.join(__dirname, 'modelo_coeficientes.json'), 'utf8')
  );
  const mesmoIntercepto = Math.abs(modeloJson.intercepto - impl.MODELO_IA.intercepto) < 1e-12;
  const mesmosCoefs = modeloJson.coeficientes.every(
    (c, i) => Math.abs(c - impl.MODELO_IA.coeficientes[i]) < 1e-12
  );
  if (!mesmoIntercepto || !mesmosCoefs) {
    console.error('✗ Os coeficientes embutidos em index.html divergem de modelo_coeficientes.json.');
    console.error('  Rode python ia/treinar_modelo.py para ressincronizar o bloco MODELO-IA.');
    process.exit(1);
  }

  let aprovados = 0;
  for (let i = 0; i < casos.length; i++) {
    const caso = casos[i];
    const scoreJs = impl.calcularScoreBruto(caso.features);
    const diferenca = Math.abs(scoreJs - caso.score_esperado);

    if (diferenca > TOLERANCIA) {
      console.error(`✗ Divergência no caso ${i + 1}/${casos.length}`);
      console.error('  features        :', JSON.stringify(caso.features));
      console.error('  score Python    :', caso.score_esperado);
      console.error('  score JavaScript:', scoreJs);
      console.error('  diferença       :', diferenca, `(tolerância ${TOLERANCIA})`);
      process.exit(1);
    }
    aprovados++;
  }

  console.log(`✓ Paridade Python ↔ JavaScript verificada: ${aprovados}/${casos.length} casos`);
  console.log(`  Tolerância aplicada: ${TOLERANCIA}`);
  console.log(`  Modelo v${impl.MODELO_IA.versao} gerado em ${impl.MODELO_IA.gerado_em}`);
  console.log(`  AUC-ROC no conjunto de teste: ${impl.MODELO_IA.metricas.auc_roc}`);
  process.exit(0);
}

main();
