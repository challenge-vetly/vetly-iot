"""
Vetly Collar — servidor MCP (Sprint 4).

Deixa o Claude agir como agente conversacional sobre os dados da coleira.
Assina o MQTT do ESP32, guarda as últimas 30 leituras por pet e expõe as
camadas de IA do painel (regras por espécie, Índice de Deterioração e triagem)
como tools MCP. Transporte stdio: logs vão para stderr, nunca para stdout.

Execução:  python mcp/vetly_mcp_server.py
Demo:      VETLY_SIMULADO=1 (leituras saudáveis locais, sem Wokwi e sem rede)
API .NET:  VETLY_API_URL (padrão http://localhost:5140), usada só por enviar_triagem
"""

import json
import logging
import math
import os
import socket
import sys
import threading
import time
import types
import unicodedata
import urllib.error
import urllib.request
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import paho.mqtt.client as mqtt
from mcp.server.fastmcp import FastMCP

IA_DIR = Path(__file__).resolve().parent.parent / "ia"
sys.path.insert(0, str(IA_DIR))

# gerar_dataset.py importa pandas no topo, mas só o usa em main() (geração do CSV).
# O servidor não precisa dele: um módulo vazio basta para o import funcionar.
try:
    import pandas  # noqa: F401
except ImportError:
    sys.modules["pandas"] = types.ModuleType("pandas")

from gerar_dataset import (  # noqa: E402
    ATIVIDADE_BASAL,
    FRAGMENTACAO_REF,
    PERFIS,
    calcular_features,
    nivel_de_indice,
)

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="[vetly-mcp] %(message)s")
log = logging.getLogger("vetly-mcp")

with open(IA_DIR / "modelo_coeficientes.json", encoding="utf-8") as f:
    MODELO = json.load(f)

# ---------------- Configuração ----------------
BROKER, PORTA = "broker.hivemq.com", 1883
TOPICOS = ["vetlycollar/+/temperatura", "vetlycollar/+/bpm", "vetlycollar/+/atividade"]
TIMEOUT_MQTT_S = 5
INTERVALO_S = 2  # mesmo PUBLISH_INTERVAL_MS do sketch.ino
JANELA = 30      # mesmo HISTORICO_MAX do painel e N_JANELA do treino

# Iguais ao array PETS de index.html
PETS = {
    "pet001": {"nome": "Rex", "especie": "cao", "idade": "5 anos", "sensor": "sensores reais (Wokwi)"},
    "pet002": {"nome": "Mimi", "especie": "gato", "idade": "3 anos", "sensor": "pet virtual"},
    "pet003": {"nome": "Tobi", "especie": "coelho", "idade": "2 anos", "sensor": "pet virtual"},
}

ROTULOS_ATIVIDADE = ["Repouso", "Ativo", "Intenso"]
NIVEL_IDX_REPRESENTATIVO = [0.10, 0.45, 0.85]  # idem index.html
ROTULOS_FEATURES = {
    "desvio_termico": "Desvio térmico",
    "desvio_bpm": "Desvio de BPM",
    "variabilidade_bpm": "Variabilidade de BPM",
    "queda_atividade": "Queda de atividade",
    "fragmentacao_repouso": "Fragmentação do repouso",
    "taquicardia_repouso": "Taquicardia em repouso",
}
PRAZO_DIAS = {"URGENCIA": 0, "AGENDAR": 3, "OBSERVAR": 30}  # idem montarPayloadsVetly()
SINONIMOS_ESPECIE = {"cachorro": "cao", "passaro": "ave", "vaca": "bovino", "boi": "bovino"}

# API Vetly .NET (vetly-.net). Rodando em Development, ela grava no Oracle da plataforma.
API_URL = os.environ.get("VETLY_API_URL", "http://localhost:5140").rstrip("/")
TIMEOUT_API_S = 20
TIMEOUT_TRIAGEM_S = 150  # a triagem passa pelo LLM do backend (Ollama:TimeoutSeconds = 120)
TIPO_LEMBRETE = {"URGENCIA": "Retorno", "AGENDAR": "Retorno", "OBSERVAR": "CheckUp"}  # enum TipoLembrete
# Cadastro dos pets da coleira na plataforma (a API exige espécie, raça e peso)
CADASTRO_API = {
    "pet001": {"especie": "Canino", "raca": "SRD", "pesoKg": 20.0},
    "pet002": {"especie": "Felino", "raca": "SRD", "pesoKg": 4.0},
    "pet003": {"especie": "Coelho", "raca": "SRD", "pesoKg": 2.0},
}
TUTOR_API = {"nome": "Tutor Vetly Collar (demo IoT)", "email": "vetly-collar-demo@exemplo.com",
             "telefone": "11999990000"}

AVISO = ("⚠️ Sugestão gerada por IA, sujeita à validação de um médico veterinário (RN-082). "
         "Não é diagnóstico.")

# ---------------- Estado em memória ----------------
leituras = {pid: deque(maxlen=JANELA) for pid in PETS}
recebidas = {pid: 0 for pid in PETS}
_parcial = {pid: {} for pid in PETS}
_trava = threading.Lock()
estado = {"fonte": "conectando ao MQTT"}


def _normalizar(texto):
    sem_acento = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return sem_acento.strip().lower()


def _resolver_pet(pet_id):
    chave = _normalizar(pet_id)
    for pid, pet in PETS.items():
        if chave in (pid, _normalizar(pet["nome"])):
            return pid
    validos = ", ".join(f"{pid} ({p['nome']})" for pid, p in PETS.items())
    raise ValueError(f"Pet '{pet_id}' não encontrado. Use um destes: {validos}.")


def registrar_leitura(pet_id, temperatura, bpm, idx, nivel=None):
    with _trava:
        leituras[pet_id].append({
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "temperatura": float(temperatura),
            "bpm": int(bpm),
            "idx": float(idx),
            "nivel": nivel_de_indice(idx) if nivel is None else int(nivel),
        })
        recebidas[pet_id] += 1


def _janela(pet_id):
    with _trava:
        return list(leituras[pet_id])


# ---------------- Camada 1: motor de regras (igual a index.html) ----------------
def _classificar_valor(valor, vmin, vmax):
    if vmin <= valor <= vmax:
        return "Normal", 0.0
    limite = vmin if valor < vmin else vmax
    desvio = abs(valor - limite) / limite * 100
    return ("Atenção" if desvio <= 5 else "Crítico"), desvio


def classificar_sinais(temperatura, bpm, especie):
    """Porta de classificarStatus(): o pior entre temperatura e bpm, pela faixa da espécie."""
    perfil = PERFIS[especie]
    nt, dt = _classificar_valor(temperatura, perfil["temp_min"], perfil["temp_max"])
    nb, db = _classificar_valor(bpm, perfil["bpm_min"], perfil["bpm_max"])
    ordem = {"Normal": 0, "Atenção": 1, "Crítico": 2}
    nivel, desvio, metrica = (nt, dt, "temperatura") if ordem[nt] > ordem[nb] else (nb, db, "batimentos")
    if nivel == "Normal":
        msg = f"Sinais vitais dentro do esperado para {perfil['nome'].lower()}."
    elif nivel == "Atenção":
        msg = f"Leve desvio em {metrica} ({desvio:.1f}% do limite)."
    else:
        msg = f"Desvio relevante em {metrica} ({desvio:.1f}%). Atendimento recomendado."
    return {
        "classificacao": nivel,
        "mensagem": msg,
        "detalhe": {
            "temperatura": {"nivel": nt, "desvio_pct": round(dt, 1)},
            "bpm": {"nivel": nb, "desvio_pct": round(db, 1)},
        },
    }


def _alerta_cruzado(bpm, nivel, perfil):
    """Porta de detectarCrossAlert(): BPM x atividade."""
    alto, baixo = bpm > perfil["bpm_max"], bpm < perfil["bpm_min"]
    if alto and nivel == 0:
        return "Taquicardia em repouso — sinal clínico relevante"
    if baixo and nivel == 2:
        return "BPM abaixo da faixa durante esforço intenso — investigar"
    if alto and nivel == 2:
        return "BPM elevado durante esforço — esperado, monitorar recuperação"
    return None


def _tendencia(serie, limiar):
    """Porta de calcularTendencia(): variação nas últimas 5 leituras."""
    if len(serie) < 5:
        return "sem dados suficientes"
    delta = serie[-1] - serie[-5]
    if abs(delta) < limiar:
        return "estável"
    return "subindo" if delta > 0 else "caindo"


# ---------------- Camada 2: Índice de Deterioração ----------------
def score_bruto(features):
    """Regressão logística com os coeficientes de ia/modelo_coeficientes.json (0-100)."""
    z = MODELO["intercepto"]
    for coef, nome in zip(MODELO["coeficientes"], MODELO["features"]):
        z += coef * features[nome]
    return 1.0 / (1.0 + math.exp(-z)) * 100.0


def classificar_indice(indice):
    lim = MODELO["limiares"]
    if indice >= lim["deterioracao"]:
        return "Deterioração"
    if indice >= lim["vigilancia"]:
        return "Vigilância"
    return "Estável"


def indice_da_janela(janela, especie):
    """Índice sobre as 30 leituras; None enquanto a janela não estiver cheia."""
    if len(janela) < JANELA:
        return None
    feats = calcular_features(
        [l["temperatura"] for l in janela], [l["bpm"] for l in janela],
        [l["idx"] for l in janela], PERFIS[especie], especie,
    )
    feats = {k: float(v) for k, v in feats.items()}
    bruto = score_bruto(feats)
    indice = math.floor(bruto * 10 + 0.5) / 10  # mesmo arredondamento do Math.round do painel
    fatores = sorted(
        ({"feature": n, "fator": ROTULOS_FEATURES[n], "valor": round(feats[n], 4),
          "coeficiente": round(c, 3), "contribuicao": round(c * feats[n], 3)}
         for c, n in zip(MODELO["coeficientes"], MODELO["features"])),
        key=lambda f: abs(f["contribuicao"]), reverse=True,
    )
    return {"bruto": bruto, "indice": indice, "faixa": classificar_indice(indice),
            "features": feats, "fatores": fatores[:3]}


# ---------------- Coleta: MQTT ou simulação ----------------
def _ao_receber(cliente, userdata, msg):
    partes = msg.topic.split("/")
    if len(partes) != 3 or partes[1] not in PETS:
        return
    pet_id, tipo = partes[1], partes[2]
    bruto = msg.payload.decode("utf-8", "replace").strip()
    try:
        p = _parcial[pet_id]
        if tipo == "temperatura":
            p["temperatura"] = float(bruto)
        elif tipo == "bpm":
            p["bpm"] = int(float(bruto))
        elif tipo == "atividade":
            obj = json.loads(bruto)
            if isinstance(obj, (int, float)):  # firmware antigo publica só o índice, sem JSON
                p["idx"] = float(obj)
                p["nivel"] = nivel_de_indice(p["idx"])
            else:
                p["nivel"] = int(obj["level"])
                p["idx"] = float(obj.get("idx", NIVEL_IDX_REPRESENTATIVO[p["nivel"]]))
            # atividade é o último tópico de cada ciclo do sketch.ino: fecha uma leitura
            if "temperatura" in p and "bpm" in p:
                registrar_leitura(pet_id, p["temperatura"], p["bpm"], p["idx"], p["nivel"])
    except (ValueError, KeyError, TypeError, IndexError):
        log.warning("payload inválido em %s: %r", msg.topic, bruto)


def _endereco_broker():
    # Prefere IPv4: com IPv6 quebrado na rede, o connect gasta o timeout no IPv6 antes do IPv4.
    try:
        return socket.getaddrinfo(BROKER, PORTA, socket.AF_INET, socket.SOCK_STREAM)[0][4][0]
    except OSError:
        return BROKER


def _conectar_mqtt():
    conectou = threading.Event()

    def ao_conectar(cliente, userdata, flags, reason_code, properties):
        if not reason_code.is_failure:
            cliente.subscribe([(t, 0) for t in TOPICOS])
            conectou.set()

    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"vetly-mcp-{uuid.uuid4().hex[:8]}")
    cliente.on_connect = ao_conectar
    cliente.on_message = _ao_receber
    try:
        cliente.connect_async(_endereco_broker(), PORTA, keepalive=30)
        cliente.loop_start()
    except OSError:
        return False
    if conectou.wait(TIMEOUT_MQTT_S):
        return True
    cliente.loop_stop()
    return False


def leitura_saudavel(rng, especie):
    """Uma leitura saudável, com a mesma distribuição de gerar_janela_saudavel()."""
    p = PERFIS[especie]
    temp = rng.normal((p["temp_min"] + p["temp_max"]) / 2, (p["temp_max"] - p["temp_min"]) / 2 * 0.12)
    bpm = rng.normal((p["bpm_min"] + p["bpm_max"]) / 2, (p["bpm_max"] - p["bpm_min"]) / 2 * 0.10)
    idx = float(np.clip(rng.normal(ATIVIDADE_BASAL[especie], 0.08), 0, 1))
    return round(float(temp), 1), int(round(float(bpm))), round(idx, 2)  # mesmas casas do firmware


def _iniciar_simulador(motivo):
    estado["fonte"] = f"simulado ({motivo})"
    log.info("modo simulado: %s", motivo)
    rng = np.random.default_rng(42)
    # Já começa com a janela cheia, para o índice existir desde a primeira pergunta.
    for pet_id, pet in PETS.items():
        for _ in range(JANELA):
            registrar_leitura(pet_id, *leitura_saudavel(rng, pet["especie"]))

    def laco():
        while True:
            time.sleep(INTERVALO_S)
            for pet_id, pet in PETS.items():
                registrar_leitura(pet_id, *leitura_saudavel(rng, pet["especie"]))

    threading.Thread(target=laco, daemon=True).start()


def iniciar_coleta():
    if os.environ.get("VETLY_SIMULADO") == "1":
        _iniciar_simulador("VETLY_SIMULADO=1")
        return

    def tentar():
        if _conectar_mqtt():
            estado["fonte"] = f"mqtt ({BROKER})"
            log.info("conectado ao %s, assinando %s", BROKER, TOPICOS)
        else:
            _iniciar_simulador(f"MQTT não conectou em {TIMEOUT_MQTT_S} s")

    threading.Thread(target=tentar, daemon=True).start()


# ---------------- Servidor MCP ----------------
mcp = FastMCP(
    "vetly-collar",
    instructions=(
        "Dados ao vivo da coleira Vetly Collar (Rex/cão, Mimi/gato, Tobi/coelho). "
        "Para analisar um pet: chame ler_sinais, depois calcular_indice_deterioracao e "
        "faixas_da_especie, e responda com (a) briefing técnico para o veterinário, "
        "(b) mensagem simples para o tutor e (c) ação recomendada (OBSERVAR, AGENDAR ou "
        "URGENCIA) com justificativa. Nunca dê diagnóstico fechado nem prescreva medicamento "
        f"ou dose. Termine sempre com o aviso: {AVISO} "
        "Se a fonte for 'simulado', diga que os dados são de simulação. "
        "montar_triagem só monta o JSON da API; nada é enviado. enviar_triagem grava na "
        "plataforma Vetly (lembrete do tutor no banco): chame-a só quando o veterinário "
        "confirmar a ação explicitamente."
    ),
)


@mcp.tool()
def listar_pets() -> dict:
    """Lista os pets monitorados pela coleira e quantas leituras cada um já recebeu."""
    pets = []
    for pid, pet in PETS.items():
        pets.append({
            "id": pid, "nome": pet["nome"], "especie": PERFIS[pet["especie"]]["nome"],
            "idade": pet["idade"], "origem": pet["sensor"],
            "leituras_recebidas": recebidas[pid], "leituras_na_janela": len(leituras[pid]),
        })
    return {"fonte": estado["fonte"], "janela_maxima": JANELA, "pets": pets}


@mcp.tool()
def ler_sinais(pet_id: str) -> dict:
    """Última temperatura, bpm e atividade do pet, com a classificação do motor de regras
    (Normal / Atenção / Crítico) pela faixa da espécie. Aceita o id (pet001) ou o nome (Rex)."""
    pid = _resolver_pet(pet_id)
    pet, janela = PETS[pid], _janela(pid)
    perfil = PERFIS[pet["especie"]]
    base = {"pet_id": pid, "nome": pet["nome"], "especie": perfil["nome"], "fonte": estado["fonte"]}
    if not janela:
        return {**base, "status": "aguardando dados", "aviso": AVISO}
    ultima = janela[-1]
    regras = classificar_sinais(ultima["temperatura"], ultima["bpm"], pet["especie"])
    return {
        **base,
        "leitura_em": ultima["ts"],
        "temperatura_c": ultima["temperatura"],
        "bpm": ultima["bpm"],
        "atividade": {"nivel": ROTULOS_ATIVIDADE[ultima["nivel"]], "indice": ultima["idx"]},
        **regras,
        "alerta_cruzado": _alerta_cruzado(ultima["bpm"], ultima["nivel"], perfil),
        "tendencia_5_leituras": {
            "temperatura": _tendencia([l["temperatura"] for l in janela], 0.15),
            "bpm": _tendencia([l["bpm"] for l in janela], 4),
        },
        "faixa_especie": {"temperatura_c": [perfil["temp_min"], perfil["temp_max"]],
                          "bpm": [perfil["bpm_min"], perfil["bpm_max"]]},
        "leituras_na_janela": len(janela),
        "aviso": AVISO,
    }


@mcp.tool()
def calcular_indice_deterioracao(pet_id: str) -> dict:
    """Índice de Deterioração 0-100 (regressão logística treinada em ia/) sobre as últimas
    30 leituras, com a faixa (Estável / Vigilância / Deterioração) e os 3 fatores que mais pesaram."""
    pid = _resolver_pet(pet_id)
    pet, janela = PETS[pid], _janela(pid)
    base = {"pet_id": pid, "nome": pet["nome"], "especie": PERFIS[pet["especie"]]["nome"],
            "fonte": estado["fonte"]}
    r = indice_da_janela(janela, pet["especie"])
    if r is None:
        return {**base, "status": f"coletando dados ({len(janela)}/{JANELA})", "aviso": AVISO}
    return {
        **base,
        "indice": r["indice"],
        "faixa": r["faixa"],
        "principais_fatores": r["fatores"],
        "features": {k: round(v, 4) for k, v in r["features"].items()},
        "limiares": MODELO["limiares"],
        "modelo": f"regressão logística v{MODELO['versao']} · AUC-ROC {MODELO['metricas']['auc_roc']} "
                  "(dados sintéticos)",
        "aviso": AVISO,
    }


@mcp.tool()
def faixas_da_especie(especie: str) -> dict:
    """Faixas fisiológicas de temperatura e bpm da espécie (cao, gato, bovino, ave, coelho)."""
    chave = _normalizar(especie)
    chave = SINONIMOS_ESPECIE.get(chave, chave)
    if chave not in PERFIS:
        chave = next((k for k, p in PERFIS.items() if _normalizar(p["nome"]) == chave), None)
    if chave is None:
        raise ValueError(f"Espécie '{especie}' não suportada. Use: {', '.join(PERFIS)}.")
    p = PERFIS[chave]
    return {
        "especie": chave,
        "nome": p["nome"],
        "temperatura_c": {"min": p["temp_min"], "max": p["temp_max"]},
        "bpm": {"min": p["bpm_min"], "max": p["bpm_max"]},
        "atividade_basal": ATIVIDADE_BASAL[chave],
        "fragmentacao_referencia": FRAGMENTACAO_REF[chave],
        "regra": "Dentro da faixa = Normal; fora até 5% do limite = Atenção; acima de 5% = Crítico.",
    }


@mcp.tool()
def montar_triagem(pet_id: str, acao: str, justificativa: str,
                   briefing_veterinario: str = "", mensagem_tutor: str = "") -> dict:
    """Monta (sem enviar) os payloads da API Vetly .NET no formato de montarPayloadsVetly()
    do painel. acao: OBSERVAR, AGENDAR ou URGENCIA. briefing e mensagem ao tutor são opcionais."""
    pid = _resolver_pet(pet_id)
    acao = _normalizar(acao).upper()
    if acao not in PRAZO_DIAS:
        raise ValueError("acao deve ser OBSERVAR, AGENDAR ou URGENCIA.")
    pet, janela = PETS[pid], _janela(pid)
    ultima = janela[-1] if janela else {}
    indice = indice_da_janela(janela, pet["especie"])
    agora = datetime.now(timezone.utc)

    def iso(dt):  # mesmo formato do toISOString() do JavaScript
        return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    payloads = {
        "POST /api/ia/triagem": {
            "petId": pid,
            "especie": PERFIS[pet["especie"]]["nome"],
            "sintomasRelatados": [justificativa],
            "temperaturaC": ultima.get("temperatura"),
            "frequenciaCardiaca": ultima.get("bpm"),
            "nivelAtividade": ultima.get("nivel"),
            "indiceDeterioracao": indice["indice"] if indice else None,
            "origemDados": "vetly-collar",
        },
        "POST /api/ia/orientacoes": {
            "petId": pid,
            "resumoConsulta": briefing_veterinario,
            "orientacoesTutor": mensagem_tutor,
            "geradoEm": iso(agora),
            "validadoPorProfissional": False,
        },
        "POST /api/lembretes": {
            "petId": pid,
            "tipo": acao,
            "descricao": justificativa,
            "dataSugerida": iso(agora + timedelta(days=PRAZO_DIAS[acao])),
            "origem": "vetly-collar/insights",
        },
    }
    return {
        "payloads": payloads,
        "enviado": False,
        "observacao": "Payloads só montados, nada foi enviado. Depois que o veterinário validar, "
                      "enviar_triagem grava a triagem na API Vetly .NET.",
        "aviso": AVISO,
    }


# ---------------- Integração com a API Vetly .NET ----------------
_ids_api = {"animais": {}}  # tutorId e animalId já cadastrados na plataforma


def _api(metodo, caminho, corpo=None, token=None, timeout=TIMEOUT_API_S):
    """Chamada JSON à API. Devolve (status, corpo); erro de rede vira ValueError legível."""
    cabecalhos = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        cabecalhos["Authorization"] = f"Bearer {token}"
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    req = urllib.request.Request(API_URL + caminho, data=dados, headers=cabecalhos, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, texto = resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as erro:
        status, texto = erro.code, erro.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        raise ValueError(f"API Vetly indisponível em {API_URL} ({erro}). "
                         "Suba o vetly-.net com: dotnet run --project src/Vetly.API --launch-profile http")
    try:
        return status, json.loads(texto) if texto else None
    except ValueError:
        return status, texto


def _exigir(status, esperado, passo, corpo):
    if status != esperado:
        raise ValueError(f"A API respondeu HTTP {status} ao {passo}: {str(corpo)[:300]}")


def _itens(corpo):
    """Lista de uma resposta crua ou paginada ({itens: [...]}), como no validador do vetly-.net."""
    return corpo if isinstance(corpo, list) else (corpo or {}).get("itens", [])


def _cadastro_na_api(pet_id, token):
    """Acha ou cria o tutor de demonstração e o animal do pet. Devolve (tutorId, animalId)."""
    if "tutorId" not in _ids_api:
        status, tutores = _api("GET", "/api/tutores", token=token)
        _exigir(status, 200, "listar tutores", tutores)
        tutor = next((t for t in _itens(tutores)
                      if str(t.get("email", "")).lower() == TUTOR_API["email"]), None)
        if tutor is None:
            status, tutor = _api("POST", "/api/tutores", TUTOR_API, token)
            _exigir(status, 201, "cadastrar o tutor", tutor)
        _ids_api["tutorId"] = tutor["id"]
    tutor_id = _ids_api["tutorId"]

    if pet_id not in _ids_api["animais"]:
        pet = PETS[pet_id]
        status, animais = _api("GET", f"/api/tutores/{tutor_id}/animais", token=token)
        _exigir(status, 200, "listar os animais do tutor", animais)
        animal = next((a for a in _itens(animais) if a.get("nome") == pet["nome"]), None)
        if animal is None:
            hoje = datetime.now(timezone.utc)
            nascimento = datetime(hoje.year - int(pet["idade"].split()[0]), hoje.month, 1, tzinfo=timezone.utc)
            corpo = {"nome": pet["nome"], **CADASTRO_API[pet_id], "tutorId": tutor_id,
                     "dataNascimento": nascimento.isoformat().replace("+00:00", "Z")}
            status, animal = _api("POST", "/api/animais", corpo, token)
            _exigir(status, 201, "cadastrar o animal", animal)
        _ids_api["animais"][pet_id] = animal["id"]
    return tutor_id, _ids_api["animais"][pet_id]


@mcp.tool()
def enviar_triagem(pet_id: str, acao: str, justificativa: str,
                   briefing_veterinario: str = "", mensagem_tutor: str = "") -> dict:
    """Grava a triagem na plataforma Vetly (API .NET + Oracle). Use SÓ depois que o veterinário
    confirmar a ação (RN-082). Agenda o lembrete do tutor (POST /api/lembretes) e pede a
    segunda opinião do LLM do backend (POST /api/ia/triagem). acao: OBSERVAR, AGENDAR ou URGENCIA."""
    montado = montar_triagem(pet_id, acao, justificativa, briefing_veterinario, mensagem_tutor)
    pid = _resolver_pet(pet_id)
    lembrete_local = montado["payloads"]["POST /api/lembretes"]
    triagem_local = montado["payloads"]["POST /api/ia/triagem"]

    # Token de Admin da rota de desenvolvimento (só existe com a API em Development).
    status, sessao = _api("POST", "/api/auth/token", {"usuario": "vetly-collar-mcp", "role": "Admin"})
    _exigir(status, 200, "emitir o token de desenvolvimento (a API precisa rodar em Development)", sessao)
    token = sessao["token"]
    tutor_id, animal_id = _cadastro_na_api(pid, token)

    # 1) Lembrete para o tutor: é o registro que fica gravado no banco.
    status, lembrete = _api("POST", "/api/lembretes", {
        "animalId": animal_id, "tutorId": tutor_id,
        "tipo": TIPO_LEMBRETE[lembrete_local["tipo"]], "dataEvento": lembrete_local["dataSugerida"],
    }, token)
    _exigir(status, 201, "gravar o lembrete", lembrete)

    # 2) Segunda opinião do LLM do backend. Se o Ollama estiver fora, o lembrete continua gravado.
    sintomas = [justificativa]
    if triagem_local["temperaturaC"] is not None:
        sintomas.append(f"Temperatura {triagem_local['temperaturaC']} °C e frequência cardíaca "
                        f"{triagem_local['frequenciaCardiaca']} bpm, medidas pela coleira")
    if triagem_local["indiceDeterioracao"] is not None:
        sintomas.append(f"Índice de Deterioração da coleira: {triagem_local['indiceDeterioracao']}/100")
    try:
        status, triagem = _api("POST", "/api/ia/triagem", {
            "especie": CADASTRO_API[pid]["especie"], "sintomas": sintomas,
            "idadeAnos": int(PETS[pid]["idade"].split()[0]), "pesoKg": CADASTRO_API[pid]["pesoKg"],
        }, token, timeout=TIMEOUT_TRIAGEM_S)
        triagem_backend = triagem if status == 200 else {"indisponivel": f"HTTP {status}", "detalhe": triagem}
    except ValueError as erro:
        triagem_backend = {"indisponivel": str(erro)}

    return {
        "enviado": True,
        "api": API_URL,
        "tutorId": tutor_id,
        "animalId": animal_id,
        "lembrete_gravado": lembrete,
        "triagem_do_backend": triagem_backend,
        "aviso": AVISO,
    }


@mcp.prompt()
def analise_clinica(pet_id: str) -> str:
    """Análise clínica completa de um pet: briefing ao veterinário, mensagem ao tutor e ação."""
    return f"""Faça a análise clínica do pet "{pet_id}" monitorado pela coleira Vetly Collar.

1. Chame `ler_sinais` com pet_id="{pet_id}".
2. Chame `calcular_indice_deterioracao` com pet_id="{pet_id}".
3. Chame `faixas_da_especie` com a espécie do pet.

Depois responda em português do Brasil, em três partes:

**(a) Briefing para o veterinário** — 2 a 4 frases técnicas: sinais atuais frente à faixa da espécie, classificação do motor de regras, tendência, índice com a faixa e os 3 fatores que mais pesaram.
**(b) Mensagem para o tutor** — 2 a 3 frases simples e acolhedoras, sem jargão e sem alarmismo.
**(c) Ação recomendada** — OBSERVAR, AGENDAR ou URGENCIA, com 1 frase de justificativa.
Referência: Estável → OBSERVAR; Vigilância → AGENDAR; Deterioração ou regra Crítico → URGENCIA.

Regras:
- Nunca dê diagnóstico fechado; trabalhe com hipóteses e conduta.
- Nunca prescreva medicamento, princípio ativo ou dose.
- Se o índice estiver "coletando dados", diga isso e use só o motor de regras.
- Se a fonte for "simulado", deixe claro que os dados vêm de simulação.
- Termine com o aviso: {AVISO}

Se o veterinário pedir, use `montar_triagem` para mostrar o payload da API (nada é enviado).
Só quando o veterinário confirmar a ação, use `enviar_triagem` para gravá-la na plataforma Vetly."""


if __name__ == "__main__":
    iniciar_coleta()
    mcp.run()
