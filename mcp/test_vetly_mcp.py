"""
Testes do servidor MCP da Vetly Collar. Rodam em modo simulado, sem rede.

Execução: pytest mcp/
"""

import asyncio
import json
import math
import os
import re
import sys
from pathlib import Path

import numpy as np
import pytest

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(AQUI))
os.environ["VETLY_SIMULADO"] = "1"

import vetly_mcp_server as srv  # noqa: E402
from gerar_dataset import PERFIS, calcular_features  # noqa: E402  (ia/ entra no path via servidor)


@pytest.fixture(autouse=True)
def janelas_vazias():
    for pid in srv.PETS:
        srv.leituras[pid].clear()
        srv._parcial[pid].clear()


def encher(pet_id, n, semente=7):
    rng = np.random.default_rng(semente)
    especie = srv.PETS[pet_id]["especie"]
    for _ in range(n):
        srv.registrar_leitura(pet_id, *srv.leitura_saudavel(rng, especie))


def test_paridade_com_casos_de_teste_do_modelo():
    casos = json.loads((RAIZ / "ia" / "casos_de_teste.json").read_text(encoding="utf-8"))
    assert len(casos) == 20
    for caso in casos:
        assert abs(srv.score_bruto(caso["features"]) - caso["score_esperado"]) <= 1e-6


def test_tool_do_indice_igual_ao_calculo_direto():
    encher("pet001", 30)
    janela = list(srv.leituras["pet001"])
    feats = calcular_features([l["temperatura"] for l in janela], [l["bpm"] for l in janela],
                              [l["idx"] for l in janela], PERFIS["cao"], "cao")
    modelo = json.loads((RAIZ / "ia" / "modelo_coeficientes.json").read_text(encoding="utf-8"))
    z = modelo["intercepto"] + sum(c * feats[n] for c, n in zip(modelo["coeficientes"], modelo["features"]))
    esperado = 1 / (1 + math.exp(-z)) * 100

    assert abs(srv.indice_da_janela(janela, "cao")["bruto"] - esperado) <= 1e-6
    r = srv.calcular_indice_deterioracao("Rex")
    assert abs(r["indice"] - esperado) <= 0.05 + 1e-9  # a tool arredonda para 1 casa, como o painel
    assert r["faixa"] == srv.classificar_indice(r["indice"])
    assert len(r["principais_fatores"]) == 3
    assert "RN-082" in r["aviso"]


def test_mesma_leitura_normal_no_cao_e_critica_na_ave():
    # 38,6 °C e 100 bpm: leitura saudável de cão
    cao = srv.classificar_sinais(38.6, 100, "cao")
    ave = srv.classificar_sinais(38.6, 100, "ave")
    assert cao["classificacao"] == "Normal"
    assert ave["classificacao"] == "Crítico"
    # Sozinha, a temperatura fica 3,5% abaixo de 40 °C: Atenção pela regra de 5% do painel
    assert ave["detalhe"]["temperatura"]["nivel"] == "Atenção"

    srv.registrar_leitura("pet001", 38.6, 100, 0.30)
    assert srv.ler_sinais("pet001")["classificacao"] == "Normal"


def test_mensagens_mqtt_do_firmware_viram_uma_leitura():
    class Msg:  # imita paho.mqtt.client.MQTTMessage
        def __init__(self, topic, payload):
            self.topic, self.payload = topic, payload.encode()

    # mesmo formato e ordem que o sketch.ino publica a cada ciclo
    for topico, payload in [
        ("vetlycollar/pet001/temperatura", "38.4"),
        ("vetlycollar/pet001/bpm", "102"),
        ("vetlycollar/pet001/atividade", '{"level":1,"steps":3,"mov_ms":2000,"idx":0.31}'),
        # firmware antigo (commit 5ece021): atividade é só o número, sem JSON
        ("vetlycollar/pet003/temperatura", "39.2"),
        ("vetlycollar/pet003/bpm", "226"),
        ("vetlycollar/pet003/atividade", "0.44"),
        ("vetlycollar/pet999/bpm", "80"),        # pet desconhecido: ignorado
        ("vetlycollar/pet002/bpm", "abc"),       # payload inválido: ignorado
    ]:
        srv._ao_receber(None, None, Msg(topico, payload))

    assert len(srv.leituras["pet001"]) == 1
    ultima = srv.leituras["pet001"][-1]
    assert (ultima["temperatura"], ultima["bpm"], ultima["nivel"], ultima["idx"]) == (38.4, 102, 1, 0.31)
    antigo = srv.leituras["pet003"][-1]
    assert (antigo["temperatura"], antigo["bpm"], antigo["nivel"], antigo["idx"]) == (39.2, 226, 1, 0.44)
    assert len(srv.leituras["pet002"]) == 0


def test_menos_de_30_leituras_responde_coletando_dados():
    encher("pet002", 12)
    r = srv.calcular_indice_deterioracao("Mimi")
    assert r["status"] == "coletando dados (12/30)"
    assert "indice" not in r


def chaves_do_painel():
    """Lê as chaves de cada payload direto de montarPayloadsVetly() em index.html."""
    html = (RAIZ / "index.html").read_text(encoding="utf-8")
    corpo = html[html.index("function montarPayloadsVetly"):]
    corpo = corpo[corpo.index("return {"):corpo.index("};")]
    blocos = re.findall(r"'(POST [^']+)': \{(.*?)\}", corpo, re.S)
    return {rota: set(re.findall(r"(\w+):", campos)) for rota, campos in blocos}


def test_montar_triagem_no_formato_do_painel():
    encher("pet001", 30)
    r = srv.montar_triagem("pet001", "agendar", "Tendência térmica de alta.", "Briefing.", "Mensagem.")
    payloads = r["payloads"]

    assert {rota: set(campos) for rota, campos in payloads.items()} == chaves_do_painel()
    assert payloads["POST /api/ia/orientacoes"]["validadoPorProfissional"] is False
    assert payloads["POST /api/lembretes"]["tipo"] == "AGENDAR"
    assert payloads["POST /api/ia/triagem"]["indiceDeterioracao"] is not None
    assert r["enviado"] is False
    assert "RN-082" in r["aviso"]

    with pytest.raises(ValueError):
        srv.montar_triagem("pet001", "INTERNAR", "x")


def test_servidor_mcp_de_ponta_a_ponta():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def conversa():
        params = StdioServerParameters(
            command=sys.executable, args=[str(AQUI / "vetly_mcp_server.py")],
            env={**os.environ, "VETLY_SIMULADO": "1"},
        )
        async with stdio_client(params) as (leitura, escrita):
            async with ClientSession(leitura, escrita) as sessao:
                init = await sessao.initialize()
                tools = {t.name for t in (await sessao.list_tools()).tools}
                prompts = {p.name for p in (await sessao.list_prompts()).prompts}
                indice = await sessao.call_tool("calcular_indice_deterioracao", {"pet_id": "Rex"})
                prompt = await sessao.get_prompt("analise_clinica", {"pet_id": "Rex"})
                return init, tools, prompts, indice, prompt

    init, tools, prompts, indice, prompt = asyncio.run(conversa())
    assert tools == {"listar_pets", "ler_sinais", "calcular_indice_deterioracao",
                     "faixas_da_especie", "montar_triagem"}
    assert prompts == {"analise_clinica"}
    assert "RN-082" in init.instructions
    dados = json.loads(indice.content[0].text)
    assert dados["faixa"] in ("Estável", "Vigilância", "Deterioração")
    assert "simulado" in dados["fonte"]
    assert "RN-082" in prompt.messages[0].content.text
