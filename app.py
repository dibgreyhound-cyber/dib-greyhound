# -*- coding: utf-8 -*-
"""
app.py - Lista de corridas / Resultados na barra lateral + analise e Form na pagina principal.
Usa o dib_core.py (v3) para calculo e tabelas.
Novidades desta versao:
  - Busca do resultado com track_id/r_time e varredura automatica de enderecos (o que funcionar fica salvo em endereco_resultado.json)
  - Resultado lido pelo site fecha sozinho os confrontos de AvB (sem digitar a ordem de chegada)
  - Botao "Fechar resultados pendentes" na barra lateral
  - Correcoes no texto exportado (Grades das corridas validas, Recup. sem dado, alerta de split)
"""
import re
import time
import json
import os
import csv
from urllib.parse import quote
from datetime import datetime, timedelta

import pandas as pd
from curl_cffi import requests as curl_requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="DIB GREYHOUND", layout="wide", initial_sidebar_state="auto")

# --- BLOCO PARA O GALGO CORRENDO NO STATUS DO STREAMLIT ---
st.markdown(
    """
    <style>
    /* 1. Força a esconder qualquer ícone de esporte original */
    [data-testid="stStatusWidget"] svg {
        display: none !important;
    }

    /* 2. Adiciona o Galgo no lugar */
    [data-testid="stStatusWidget"] > div::before {
        content: "";
        display: inline-block;
        width: 32px;
        height: 32px;
        /* Silhueta de Galgo em SVG na cor cinza escuro (#31333F) */
        background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 104 42"><g fill="%2331333F" stroke="%2331333F" stroke-linecap="round" stroke-linejoin="round"><path stroke-width="0.4" d="M24 13 C32 9.6 44 8.8 54 8.6 C62 8.4 68 7.2 74 6 C78 5 81 4.2 84 3.8 C87 3.4 89 4 91 5 L99 9 C100.4 9.8 100.4 11 99 11.6 L94 12.4 C91 12.6 89.4 11.4 87 11.2 C83 11.6 80 13 78.4 15.6 C77.4 19.2 75 22.6 70 22.6 C65 22.6 60 20 55 18.4 C50 16.8 44 15.8 38 16 C32 16 27 16.6 24 14.8 Z"/><path stroke-width="0.3" d="M85.4 3.8 L86.4 0.6 L88.8 3.4 Z"/><path fill="none" stroke-width="2.6" d="M77 15.4 L88 18"/><path fill="none" stroke-width="1.6" d="M88 18 L98 18.6"/><path fill="none" stroke-width="2.4" d="M76 17 L85 21.6"/><path fill="none" stroke-width="1.6" d="M85 21.6 L94 22.4"/><path fill="none" stroke-width="5" d="M29 13.6 L19 19.4"/><path fill="none" stroke-width="2.4" d="M19 19.4 L10 24.6"/><path fill="none" stroke-width="1.7" d="M10 24.6 L4 26.4"/><path fill="none" stroke-width="3.8" d="M30 15.6 L23 24"/><path fill="none" stroke-width="2.2" d="M23 24 L15 30.4"/><path fill="none" stroke-width="1.7" d="M15 30.4 L8.4 32.6"/><path fill="none" stroke-width="1.2" d="M24 12.6 C18 14.2 12 15 5 13.4"/></g></svg>');
        background-size: contain;
        background-repeat: no-repeat;
        background-position: center;
        margin-right: 8px;
        vertical-align: middle;
        
        /* Animação do galgo correndo */
        animation: runDog 0.4s infinite alternate;
    }

    @keyframes runDog {
        from { transform: translateX(-3px); }
        to { transform: translateX(3px); }
    }
    </style>
    """,
    unsafe_allow_html=True
)
# --- FIM DO BLOCO DO GALGO ---

import dib_core as dib
import dib_ui

BASE = "https://greyhoundbet.racingpost.com"
LISTA_CANDIDATOS = [
    BASE + "/meeting/blocks.sd?r_date={d}&blocks=header%2Clist",
    BASE + "/meeting/blocks.sd?r_date={d}&blocks=list",
    BASE + "/meeting-list/blocks.sd?r_date={d}&blocks=list",
    BASE + "/meeting/list.sd?r_date={d}",
]

# [NOVO] Resultado: o site tem /results/blocks.sd e /card/blocks.sd. A pagina de resultado usa race_id + track_id + r_date + r_time.
CTRLS_RES = ("results", "card")
CONJ_PARAMS = (
    ("race_id", "track_id", "r_date", "r_time"),
    ("race_id", "track_id", "r_date"),
    ("race_id", "r_date"),
    ("track_id", "r_date", "r_time"),
)
BLOCOS_RES = (
    "result", "results", "meeting-result", "result-meeting-result", "race-result", "result-details", "result-list",
    "list", "header%2Clist", "header%2Cresult", "result-header%2Cresult",
    "result-pager%2Cresult-header%2Cresult-tabs%2Cresult-title%2Cresult",
    "card-pager%2Ccard-header%2Ccard-tabs%2Ccard-title%2Cresult",
)
RES_PADRAO_ARQ = "endereco_resultado.json"

KEYS = {
    "id": ["raceId", "race_id", "rid"],
    "tid": ["trackId", "track_id", "trackID"],
    "hora": ["raceDate", "offTime", "scheduledTime", "displayTime", "raceTime", "time", "startTime"],
    "pista": ["trackName", "track", "meetingName", "courseName", "venue"],
    "num": ["raceTitle", "raceNum", "raceNumber", "rNum", "number", "raceNo"],
    "grade": ["raceClass", "raceGrade", "grade", "class", "raceClassDesc"],
    "dist": ["distMetres", "distMeters", "distance", "dist", "raceDistance"],
    "clip": ["clipId", "clip_id", "videoId", "replayId"],
}
RES = {
    "nome": ["dogName", "dog_name", "name"],
    "pos": ["finishPos", "finPos", "outcomeDesc", "position", "pos", "fin", "outcome", "result",
            "finishPosition", "place", "placing", "finish", "resultPos"],
    "trap": ["trapNum", "trap", "dogTrap"],
    "sp": ["SP", "sp", "startingPrice", "price", "odds"],
    "tempo": ["calcRTimes", "calTm", "finishTime", "winTime", "time"],
    "margem": ["distBtn", "by", "beatenDistance"],
    "coment": ["closeUpCmnt", "comment", "cmnt", "commentary", "description"],
}
EXTRA = {"winsec": ["winnerOrSecond", "winSec", "wnSec", "winnerName", "secondName"],
         "sp": ["SP", "sp", "startingPrice", "price"],
         "trainer": ["trainerName", "trainer", "trainer_name"]}


# ---------------------------------------------------------------- conexao com o site (CURL_CFFI LIMPO)
class _Http:
    def __init__(self):
        # O impersonate="chrome120" já cuida de todo o disfarce de TLS e User-Agent perfeitamente
        self.s = curl_requests.Session(impersonate="chrome120")
        self.s.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            "Referer": BASE + "/",
            "Origin": BASE,
        })
        self.pronto = False

    def get(self, url, headers=None, timeout=15):
        if not self.pronto:
            try: 
                # Visita a home page primeiro para capturar os cookies de sessão do WAF
                self.s.get(BASE + "/", timeout=10)
                time.sleep(1)
            except Exception: 
                pass
            self.pronto = True

        try:
            r = self.s.get(url, headers=headers, timeout=timeout)
        except Exception:
            return None

        if r.status_code in (403, 406, 429):
            time.sleep(2)
            url_retry = url + ("&" if "?" in url else "?") + f"_={int(time.time()*1000)}"
            try:
                r = self.s.get(url_retry, headers=headers, timeout=timeout)
            except Exception:
                pass
        
        return r


@st.cache_resource
def http():
    return _Http()


dib.requests = http()

# ---------------------------------------------------------------- numeros dos galgos
BADGE_STYLE = {
    1: "background:#d62828;color:#fff;",
    2: "background:#1d4ed8;color:#fff;",
    3: "background:#fff;color:#000;border:1px solid #000;",
    4: "background:#111;color:#fff;border:1px solid #444;",
    5: "background:#f97316;color:#fff;",
    6: "background:repeating-linear-gradient(90deg,#111 0 4px,#fff 4px 8px);color:#e11;"
       "text-shadow:0 0 2px #fff,0 0 2px #fff,0 0 2px #fff;",
}


def badge(t):
    try: t = int(t)
    except Exception: return ""
    return (f"<span style='display:inline-block;min-width:24px;height:24px;line-height:24px;text-align:center;"
            f"border-radius:4px;font-weight:700;font-size:14px;vertical-align:middle;{BADGE_STYLE.get(t, '')}'>{t}</span>")


class _St:
    def __getattr__(self, n): return getattr(st, n)
    def markdown(self, body, *a, **k):
        k.setdefault("unsafe_allow_html", True)
        return st.markdown(body, *a, **k)


dib.st = _St()
dib.TRAP_EMOJI = {t: badge(t) for t in range(1, 7)}
dib.trap_label = lambda d: badge(d["trap"])


# ---------------------------------------------------------------- botao copiar (JavaScript)
def botao_copiar(texto):
    texto_js = json.dumps(texto)

    html = f"""
    <html>
    <head>
    <style>
    .copy-btn {{
        background-color: #ff4b4b;
        color: white;
        border: none;
        padding: 12px 20px;
        border-radius: 8px;
        cursor: pointer;
        font-size: 16px;
        font-weight: bold;
        width: 100%;
        transition: 0.2s;
    }}
    .copy-btn:active {{ background-color: #cc0000; }}
    </style>
    </head>
    <body>
    <button class="copy-btn" id="copyBtn">📋 Copiar Análise para o Chat</button>
    <script>
    const textToCopy = {texto_js};
    document.getElementById("copyBtn").addEventListener("click", async () => {{
        try {{
            await navigator.clipboard.writeText(textToCopy);
            document.getElementById("copyBtn").innerText = "✅ Texto Copiado! Cole no Chat.";
            document.getElementById("copyBtn").style.backgroundColor = "#28a745";
            setTimeout(() => {{
                document.getElementById("copyBtn").innerText = "📋 Copiar Análise para o Chat";
                document.getElementById("copyBtn").style.backgroundColor = "#ff4b4b";
            }}, 4000);
        }} catch (err) {{
            document.getElementById("copyBtn").innerText = "❌ Erro (Copie manualmente abaixo)";
            document.getElementById("copyBtn").style.backgroundColor = "#ff9800";
        }}
    }});
    </script>
    </body>
    </html>
    """
    components.html(html, height=65)


# ---------------------------------------------------------------- leitura de JSON
def _get(d, k, tabela=KEYS):
    for key in tabela[k]:
        if key in d and d[key] not in (None, "", {}, []):
            return d[key]
    return None


def _hhmm(v):
    m = re.search(r"(\d{1,2}):(\d{2})", str(v or ""))
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else None


def achar_corridas(obj):
    achados = {}

    def walk(o, pista_ctx, tid_ctx):
        if isinstance(o, dict):
            p = _get(o, "pista")
            if isinstance(p, str): pista_ctx = p
            t = _get(o, "tid")  # [NOVO] id da pista (track_id), herdado do encontro
            if t is not None and re.fullmatch(r"\d{1,6}", str(t).strip()): tid_ctx = str(t).strip()
            rid = _get(o, "id")
            hora = _hhmm(_get(o, "hora"))
            if rid is not None and re.fullmatch(r"\d{5,9}", str(rid)) and hora:
                g, d = _get(o, "grade"), _get(o, "dist")
                achados[str(rid)] = {
                    "id": str(rid), "hora": hora, "pista": (pista_ctx or "?").title(),
                    "num": str(_get(o, "num") or "").replace("Race", "").strip(),
                    "grade": re.sub(r"[()\s]", "", str(g or "")).upper(),
                    "dist": int(re.sub(r"\D", "", str(d))) if d and re.search(r"\d", str(d)) else 0,
                    "clip": str(_get(o, "clip") or ""),
                    "tid": tid_ctx,
                }
            for v in o.values(): walk(v, pista_ctx, tid_ctx)
        elif isinstance(o, list):
            for v in o: walk(v, pista_ctx, tid_ctx)

    walk(obj, "", "")
    return sorted(achados.values(), key=lambda c: (c["hora"], c["pista"]))


def achar_resultados(obj):
    achados = {}

    def walk(o):
        if isinstance(o, dict):
            nome = _get(o, "nome", RES)
            m = re.search(r"\d+", str(_get(o, "pos", RES) or ""))
            if isinstance(nome, str) and m and 1 <= int(m.group()) <= 8:
                t = re.search(r"\d+", str(_get(o, "trap", RES) or ""))
                achados[nome] = {
                    "pos": int(m.group()), "trap": int(t.group()) if t else None, "nome": nome,
                    "sp": str(_get(o, "sp", RES) or ""), "tempo": str(_get(o, "tempo", RES) or ""),
                    "margem": str(_get(o, "margem", RES) or ""), "coment": str(_get(o, "coment", RES) or ""),
                }
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)

    walk(obj)
    return sorted(achados.values(), key=lambda x: x["pos"])


def _chaves(js):
    if not isinstance(js, dict): return f"({type(js).__name__} com {len(js) if hasattr(js, '__len__') else '?'} itens)"
    return ", ".join(f"{k}{'(erro)' if isinstance(v, dict) and 'errorCode' in v else ''}" for k, v in js.items())[:90]


def tentar(urls, parser):
    tentativas, achado, primeira = [], [], None
    for u in urls:
        curto = u.replace(BASE, "")
        time.sleep(0.5)
        r = http().get(u, timeout=10)
        js, resposta = None, ""
        if r is not None and r.status_code == 200:
            try:
                js = r.json()
            except Exception:
                resposta = r.text[:90].replace("\n", " ")
        status = r.status_code if r is not None else "Erro"
        res = parser(js) if js is not None else []
        tentativas.append({"Status": status, "Achados": len(res),
                           "Chaves": _chaves(js) if js is not None else "", "Resposta": resposta,
                           "Endereço": curto})
        if primeira is None and js is not None and not res: primeira = js
        if res:
            achado = res
            break
    return achado, tentativas, primeira


@st.cache_data(ttl=120, show_spinner=False)
def buscar_lista(data_str, url_custom):
    urls = ([url_custom.replace("{data}", data_str)] if url_custom.strip() else []) \
        + [u.format(d=data_str) for u in LISTA_CANDIDATOS]
    return tentar(urls, achar_corridas)


# ---------------------------------------------------------------- [NOVO] resultado da corrida
def _ler_padrao():
    try:
        with open(RES_PADRAO_ARQ, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _gravar_padrao(p):
    try:
        with open(RES_PADRAO_ARQ, "w", encoding="utf-8") as f:
            json.dump(p, f)
    except Exception:
        pass


def _url_res(ctrl, params, blocos, race_id, data_str, track_id, r_time):
    vals = {"race_id": race_id, "track_id": track_id, "r_date": data_str, "r_time": r_time}
    if any(not vals.get(k) for k in params):
        return None
    q = "&".join(f"{k}={quote(str(vals[k]), safe='')}" for k in params)
    return f"{BASE}/{ctrl}/blocks.sd?{q}&blocks={blocos}"


def _testar_url(u):
    time.sleep(0.2)
    r = http().get(u, timeout=10)
    js, resposta = None, ""
    if r is not None and r.status_code == 200:
        try:
            js = r.json()
        except Exception:
            resposta = r.text[:90].replace("\n", " ")
    return (r.status_code if r is not None else "Erro"), js, resposta


def _linhas_da_corrida(js, race_id):
    """Lê as posições; se o JSON trouxer o encontro inteiro, tenta isolar só a corrida pedida."""
    alvo = _corrida_no_json(js, race_id)
    linhas = achar_resultados(alvo) if alvo is not None else []
    return linhas if len(linhas) >= 2 else achar_resultados(js)


def varredura_resultado(race_id, data_str, track_id, r_time, completo=False, extras=(), limite_s=120):
    """Testa combinações de endereço/bloco até achar um que devolva a ordem de chegada.
    Retorna (testes, padrao, linhas). padrao = {'ctrl','params','blocks'} do endereço que funcionou."""
    blocos = list(BLOCOS_RES) + [b for b in extras if b not in BLOCOS_RES]
    if completo:
        combos = [(ctrl, ps) for ctrl in CTRLS_RES for ps in CONJ_PARAMS]
    else:
        combos = [("results", CONJ_PARAMS[0]), ("results", CONJ_PARAMS[2])]
    testes, t0 = [], time.time()
    for ctrl, ps in combos:
        for b in blocos:
            if time.time() - t0 > limite_s:
                return testes, None, []
            u = _url_res(ctrl, ps, b, race_id, data_str, track_id, r_time)
            if not u:
                continue
            status, js, resposta = _testar_url(u)
            linhas = _linhas_da_corrida(js, race_id) if js is not None else []
            testes.append({"Status": status, "Galgos": len(linhas),
                           "Chaves": _chaves(js) if js is not None else "",
                           "Amostra": (str(js)[:140] if js not in (None, [], {}) else resposta),
                           "Endereço": u.replace(BASE, "")})
            if len(linhas) >= 2:
                return testes, {"ctrl": ctrl, "params": list(ps), "blocks": b}, linhas
    return testes, None, []


_GRID_TS = {"t": 0.0}


@st.cache_data(ttl=60, show_spinner=False)
def buscar_resultado(race_id, data_str, track_id="", r_time=""):
    """Devolve (linhas, tentativas, primeira). Usa o endereço salvo em endereco_resultado.json; se ainda não existir,
    faz uma varredura curta (no máximo uma a cada 10 minutos)."""
    padrao = _ler_padrao()
    if padrao:
        u = _url_res(padrao["ctrl"], tuple(padrao["params"]), padrao["blocks"], race_id, data_str, track_id, r_time)
        if u:
            status, js, resposta = _testar_url(u)
            linhas = _linhas_da_corrida(js, race_id) if js is not None else []
            tent = [{"Status": status, "Achados": len(linhas), "Chaves": _chaves(js) if js is not None else "",
                     "Resposta": resposta, "Endereço": u.replace(BASE, "")}]
            return linhas, tent, (js if (js is not None and not linhas) else None)
    if time.time() - _GRID_TS["t"] < 600:
        return [], [{"Status": "-", "Achados": 0, "Chaves": "", "Resposta": "Varredura recente sem sucesso; use o botão de descoberta abaixo.",
                     "Endereço": ""}], None
    _GRID_TS["t"] = time.time()
    testes, padrao, linhas = varredura_resultado(race_id, data_str, track_id, r_time, completo=False)
    if padrao:
        _gravar_padrao(padrao)
    tent = [{"Status": t["Status"], "Achados": t["Galgos"], "Chaves": t["Chaves"], "Resposta": t["Amostra"][:60],
             "Endereço": t["Endereço"]} for t in testes[-12:]]
    return linhas, tent, None


@st.cache_data(ttl=300, show_spinner=False)
def buscar_form_raw(race_id, data_str):
    try:
        r = http().get(f"{BASE}/card/blocks.sd?race_id={race_id}&r_date={data_str}&blocks=form", timeout=15)
        if r is not None:
            r.raise_for_status()
            return r.json().get("form", {}).get("dogs", [])
    except Exception:
        pass
    return []


def _fechar_confrontos(data_str, linhas):
    """Usa a ordem de chegada lida do site para fechar, no log de AvBs, os confrontos dessa corrida."""
    if not linhas:
        return 0
    n = 0
    if hasattr(dib, "resolver_por_resultado"):
        try:
            n = int(dib.resolver_por_resultado(data_str, linhas) or 0)
        except Exception:
            n = 0
    if hasattr(dib, "resolver_overall_por_resultado"):  # posicao real e margem para calibrar o Overall
        try:
            dib.resolver_overall_por_resultado(data_str, linhas)
        except Exception:
            pass
    return n


# ---------------------------------------------------------------- [NOVO] coleta historica (validar o modelo com dados reais)
COLETA_ARQ = "historico_corridas.csv"
_COLS_COLETA = ["race_id", "data", "pista", "tid", "hora", "num", "grade", "dist", "trap", "galgo", "peso_atual",
                "brt", "brt_txt", "runs_json", "res_pos", "res_by", "res_tempo", "res_origem", "coletado_em"]
_RUN_KEYS = ["date_str", "track", "dist", "grade", "trap", "split", "bends", "fin", "by", "wntm", "gng", "weight", "remarks", "caltm"]


def _ids_coletados():
    if not os.path.exists(COLETA_ARQ):
        return set()
    try:
        with open(COLETA_ARQ, newline="", encoding="utf-8") as f:
            return {r["race_id"] for r in csv.DictReader(f)}
    except Exception:
        return set()


def coletar_corrida(c, data_str):
    """Baixa o Form de uma corrida e grava UMA LINHA POR GALGO em historico_corridas.csv:
    o historico completo que o site devolveu (runs_json) + o resultado real dessa corrida (res_*).
    O resultado vem do proprio Form (a corrida aparece nas corridas do galgo, com a data dela) e, se faltar,
    do endereco de resultado ja descoberto. Retorna (galgos gravados, galgos com resultado)."""
    raw = buscar_form_raw(c["id"], data_str)
    if not raw:
        return 0, 0
    resultado = {}
    if _ler_padrao():
        try:
            linhas, _, _ = buscar_resultado(c["id"], data_str, c.get("tid", ""), c.get("hora", ""))
            resultado = {str(l["nome"]).strip().lower(): l for l in linhas}
        except Exception:
            resultado = {}
    dist_c = float(c.get("dist") or 0)
    novas, com_res = [], 0
    for dog in raw:
        nome = dog.get("dogName", "?")
        runs = [dib.norm_run(f) for f in dog.get("forms", [])]
        res = None
        for r in runs:
            if r["date_str"] == data_str and r["fin"] and (not dist_c or (r["dist"] and abs(r["dist"] - dist_c) < 1)):
                res = r
                break
        pos = by = tempo = origem = ""
        if res:
            pos, by, tempo, origem = res["fin"], ("" if res["by"] is None else res["by"]), (res["caltm"] or ""), "form"
        else:
            l = resultado.get(str(nome).strip().lower())
            if l:
                pos, by, tempo, origem = l["pos"], l["margem"], l["tempo"], "resultado"
        if pos != "":
            com_res += 1
        runs_json = json.dumps([{k: r.get(k) for k in _RUN_KEYS} for r in runs], ensure_ascii=False)
        novas.append([c["id"], data_str, c.get("pista", ""), c.get("tid", ""), c.get("hora", ""), c.get("num", ""),
                      c.get("grade", ""), c.get("dist", ""), dib.fin_num(dog.get("trapNum")) or "", nome,
                      dib.to_float(dog.get("weight")) or "", dib.extrair_brt(dog) or "", dib.extrair_brt_txt(dog),
                      runs_json, pos, by, tempo, origem, datetime.now().strftime("%Y-%m-%d %H:%M")])
    novo = not os.path.exists(COLETA_ARQ)
    with open(COLETA_ARQ, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if novo:
            w.writerow(_COLS_COLETA)
        w.writerows(novas)
    return len(novas), com_res


def completar_resultados_coleta():
    """Preenche res_pos/res_by/res_tempo das corridas coletadas SEM precisar do endereço de resultado:
    o histórico (runs_json) de qualquer galgo coletado depois traz as corridas anteriores dele com posição, margem e tempo.
    Casa por nome do galgo + data + distância. Retorna (preenchidos_agora, total_de_linhas, com_resultado)."""
    if not os.path.exists(COLETA_ARQ):
        return 0, 0, 0
    df = pd.read_csv(COLETA_ARQ, dtype=str).fillna("")
    idx = {}
    for _, r in df.iterrows():
        try:
            runs = json.loads(r["runs_json"])
        except Exception:
            continue
        for x in runs:
            try:
                if x.get("fin") and x.get("date_str") and x.get("dist"):
                    idx[(r["galgo"].strip().lower(), x["date_str"], int(round(float(x["dist"]))))] = x
            except Exception:
                continue
    n = 0
    for i, r in df.iterrows():
        if r["res_pos"] != "":
            continue
        try:
            chave = (r["galgo"].strip().lower(), r["data"], int(round(float(r["dist"]))))
        except Exception:
            continue
        x = idx.get(chave)
        if x:
            df.at[i, "res_pos"] = str(x["fin"])
            df.at[i, "res_by"] = "" if x.get("by") is None else str(x["by"])
            df.at[i, "res_tempo"] = "" if not x.get("caltm") else str(x["caltm"])
            df.at[i, "res_origem"] = "historico"
            n += 1
    if n:
        df.to_csv(COLETA_ARQ, index=False, encoding="utf-8")
    return n, len(df), int((df["res_pos"] != "").sum())


def painel_coleta(url_custom):
    st.markdown("### 🧪 Coleta histórica (validar o modelo com dados reais)")
    st.caption("Baixa corridas de dias anteriores com o histórico de cada galgo e o resultado real. Não precisa ficar aberto: "
               "cada toque coleta um lote e continua de onde parou. Depois baixe o CSV e envie no chat para avaliarmos o modelo.")
    hoje = agora_uk().date()
    c1, c2 = st.columns(2)
    ini = c1.date_input("De", value=hoje - timedelta(days=7), key="col_ini")
    fim = c2.date_input("Até", value=hoje - timedelta(days=1), key="col_fim")
    limite = int(st.number_input("Corridas por toque", min_value=10, max_value=300, value=60, step=10))
    pistas_txt = st.text_input("Só estas pistas (opcional, separadas por vírgula)", value="")
    pistas = [p.strip().lower() for p in pistas_txt.split(",") if p.strip()]
    st.caption("O resultado costuma vir do próprio Form (a corrida aparece no histórico do galgo). "
               "Corridas muito antigas podem sair do Form e ficar sem resultado.")
    if st.button("▶ Coletar próximo lote"):
        ja = _ids_coletados()
        alvo = []
        dia = fim
        with st.spinner("Listando corridas..."):
            while dia >= ini:
                ds_ = dia.strftime("%Y-%m-%d")
                try:
                    corridas = buscar_lista(ds_, url_custom)[0]
                except Exception:
                    corridas = []
                for c in corridas:
                    if c["id"] in ja:
                        continue
                    if pistas and not any(p in c["pista"].lower() for p in pistas):
                        continue
                    if dia == hoje and c["hora"] >= agora_uk().strftime("%H:%M"):
                        continue  # ainda nao correu
                    alvo.append((c, ds_))
                dia -= timedelta(days=1)
        total = len(alvo)
        alvo = alvo[:limite]
        if not alvo:
            st.info("Nada novo para coletar neste período (ou a lista do site não respondeu).")
        else:
            barra = st.progress(0.0)
            gal = res = 0
            for i, (c, ds_) in enumerate(alvo, 1):
                try:
                    g_, r_ = coletar_corrida(c, ds_)
                except Exception:
                    g_, r_ = 0, 0
                gal += g_
                res += r_
                barra.progress(i / len(alvo))
                time.sleep(0.2)
            try:
                completar_resultados_coleta()  # resultados vindos do histórico dos galgos coletados depois
            except Exception:
                pass
            st.success(f"{len(alvo)} corridas coletadas ({gal} galgos) · "
                       f"restam {max(0, total - len(alvo))} no período. Toque de novo para continuar.")
    if os.path.exists(COLETA_ARQ):
        if st.button("🧩 Completar resultados pelo histórico dos galgos"):
            n_, tot_, com_ = completar_resultados_coleta()
            st.success(f"{n_} galgos preenchidos agora · {com_} de {tot_} com resultado.")
        st.caption("Os resultados são preenchidos pelo histórico dos galgos que correram de novo depois: "
                   "colete também os dias seguintes (até hoje) e toque no botão acima. Não depende do endereço de resultado.")
        try:
            df = pd.read_csv(COLETA_ARQ, dtype=str)
            n_c = df["race_id"].nunique()
            pct = 100.0 * (df["res_pos"].fillna("") != "").mean() if len(df) else 0.0
            st.markdown(f"**Já coletado:** {n_c} corridas · {len(df)} galgos · {pct:.0f}% com resultado · "
                        f"de {df['data'].min()} a {df['data'].max()}")
            if pct < 50:
                st.warning("Poucos galgos com resultado. Descubra o endereço do resultado (aba 📊 Resultados) "
                           "ou colete dias mais recentes.")
            with open(COLETA_ARQ, "rb") as f:
                st.download_button("⬇️ Baixar historico_corridas.csv", f.read(), file_name="historico_corridas.csv", mime="text/csv")
        except Exception as e:
            st.caption(f"Não consegui ler o arquivo de coleta: {e}")


# ---------------------------------------------------------------- utilidades
def hora_br(hhmm, h24=False):
    h, m = [int(x) for x in hhmm.split(":")]
    t = datetime(2000, 1, 1, h, m) - timedelta(hours=3)
    if h24:
        return f"{t.hour:02d}:{t.minute:02d}"
    return f"{t.hour % 12 or 12}:{t.minute:02d}"


def agora_uk():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/London"))
    except Exception:
        return datetime.utcnow()


def escolher(c, data_str, modo):
    st.session_state["sel"] = dict(c, data=data_str, modo=modo)
    st.session_state["fechar"] = True


def fechar_sidebar():
    components.html(
        """<script>
        try {
          const d = window.parent.document;
          if (window.parent.innerWidth < 900) {
            const b = d.querySelector('[data-testid="stSidebarCollapseButton"] button')
                   || d.querySelector('[data-testid="stSidebarCollapseButton"]')
                   || d.querySelector('button[kind="header"]');
            if (b) b.click();
          }
        } catch (e) {}
        </script>""", height=0)


def tabela_html(headers, rows):
    st.markdown(dib.tbl(headers, rows), unsafe_allow_html=True)


def _link(url, rotulo):
    try:
        st.link_button(rotulo, url)
    except Exception:
        st.markdown(f"[{rotulo}]({url})")


# ---------------------------------------------------------------- replay
def mostrar_replay(c):
    clip = str(c.get("clip") or "").strip()
    if clip:
        url = f"https://www.youtube.com/watch?v={clip}"
        with st.expander("▶ Replay da corrida (tentativa)", expanded=False):
            try:
                st.video(url)
            except Exception:
                st.write("Não consegui incorporar o vídeo aqui.")
            _link(url, "Abrir o vídeo em outra aba")
            st.caption(f"Código do replay recebido da lista: {clip}")
    else:
        st.caption("▶ Replay: esta corrida ainda não trouxe o código do vídeo (clipId vazio na lista). "
                   "Ele costuma aparecer depois que a corrida termina; toque em 🔄 para recarregar a lista.")
    _link(f"{BASE}/#card/race_id={c['id']}&r_date={c['data']}", "Abrir esta corrida no site")


# ---------------------------------------------------------------- descobrir enderecos
_RE_SD = re.compile(r"""["']((?:/?[\w\-]+/)*[\w\-]*\.sd)(?:\?[^"']*)?["']""")
_RE_BLOCKS = re.compile(r"""blocks\s*[:=]\s*["']([\w,%\-]+)["']""")


def _baixar(url, tam=3_000_000):
    r = http().get(url, timeout=15)
    if r is not None and r.status_code == 200:
        return r.text[:tam]
    return ""


def _contextos(texto, padrao, n=70, limite=20):
    vistos, res = set(), []
    for m in re.finditer(padrao, texto, flags=re.I):
        ini, fim = max(0, m.start() - n), min(len(texto), m.end() + n)
        trecho = texto[ini:fim].replace("\n", " ")
        chave = trecho[n - 10:n + 20]
        if chave not in vistos:
            vistos.add(chave)
            res.append(trecho)
        if len(res) >= limite:
            break
    return res


def _extrair_blocos_ctrl(txt):
    """Procura nomes de blocos declarados no arquivo de controladores (ex.: 'card-pager,card-header,...')."""
    achados = []
    for m in re.finditer(r"blocks[^;\n]{0,200}", txt, flags=re.I):
        for s in re.findall(r"""['"]([a-z][\w\-]*(?:\s*,\s*[a-z][\w\-]*)*)['"]""", m.group(0), flags=re.I):
            s = re.sub(r"\s+", "", s)
            if len(s) < 120 and any(x in s.lower() for x in ("result", "card", "header", "list")):
                enc = s.replace(",", "%2C")
                if enc not in achados:
                    achados.append(enc)
    return achados[:12]


@st.cache_data(ttl=3600, show_spinner=False)
def varrer_site():
    html = _baixar(BASE + "/")
    scripts = []
    for u in re.findall(r"""<script[^>]+src=["']([^"']+)["']""", html):
        u = "https:" + u if u.startswith("//") else (BASE + u if u.startswith("/") else
                                                      (u if u.startswith("http") else BASE + "/" + u))
        if "racingpost" in u and u not in scripts:
            scripts.append(u)
    scripts = scripts[:8]
    textos = {u: _baixar(u) for u in scripts}
    tudo = "\n".join(textos.values())
    ctrl = "\n".join(t for u, t in textos.items() if "controllers" in u)
    return {
        "html": len(html), "scripts": [u.replace(BASE, "") for u in scripts], "chars": len(tudo),
        "caminhos": sorted({m.group(1) for m in _RE_SD.finditer(tudo)})[:120],
        "blocos": sorted({m.group(1) for m in _RE_BLOCKS.finditer(tudo)})[:120],
        "rotas": _contextos(ctrl, r"result-meeting|results-dog|results/blocks|card-meeting-result", 140, 20),
        "ctrl_blocks": _contextos(ctrl, r"blocks", 90, 40),
        "blocos_ctrl": _extrair_blocos_ctrl(ctrl),
        "result": _contextos(ctrl, r"result", 70, 15),
        "replay": _contextos(tudo, r"replay|clipId|youtube|\.mp4|m3u8|video", 80, 12),
    }


def painel_descobrir(c):
    race_id, data_str = c["id"], c["data"]
    track_id, r_time = c.get("tid", ""), c.get("hora", "")
    st.markdown("---")
    st.markdown("#### 🧪 Procurando o endereço do resultado")
    st.caption(f"Corrida {race_id} · {data_str} · track_id={track_id or '(não veio na lista)'} · r_time={r_time or '-'}")
    if not st.button("🔎 Procurar o endereço agora (leva ~1 minuto)", key=f"desc_{race_id}"):
        st.caption("Toque no botão para testar os endereços possíveis. O que funcionar fica salvo e o app passa a usar sozinho.")
        return
    with st.spinner("Lendo o código do site..."):
        v = varrer_site()
    with st.spinner("Testando endereços (até ~2 minutos)..."):
        testes, padrao, linhas = varredura_resultado(race_id, data_str, track_id, r_time, completo=True,
                                                     extras=tuple(v["blocos_ctrl"]))
    if padrao:
        _gravar_padrao(padrao)
        buscar_resultado.clear()
        st.success("Achei! O endereço foi salvo e o app já vai usá-lo. Reabra o resultado desta corrida.")
        st.code(json.dumps(padrao))
    else:
        st.warning("Ainda não achei. Toque em copiar e cole o relatório no chat que eu ajusto.")
    nao_vazios = [t for t in testes if t["Status"] == 200 and t["Amostra"]]
    linhas_rel = [f"Corrida {race_id} {data_str} track_id={track_id} r_time={r_time}",
                  f"Pagina inicial: {v['html']} caracteres | JavaScript: {len(v['scripts'])} arquivos",
                  "ENDERECOS .sd: " + ", ".join(v["caminhos"]),
                  "BLOCOS (extraidos do controllers): " + ", ".join(v["blocos_ctrl"]),
                  "CTRL BLOCKS:", *v["ctrl_blocks"], "CTRL ROTAS:", *v["rotas"], "CTRL RESULT:", *v["result"],
                  f"RESPOSTAS NAO VAZIAS ({len(nao_vazios)}):",
                  *[f"{t['Status']} | {t['Chaves']} | {t['Amostra']} | {t['Endereço']}" for t in nao_vazios[:15]],
                  f"TESTES ({len(testes)}):",
                  *[f"{t['Status']} | galgos={t['Galgos']} | {t['Chaves']} | {t['Endereço']}" for t in testes[:60]]]
    relatorio = "\n".join(linhas_rel)
    botao_copiar(relatorio)
    st.text_area("Relatório (se o botão não copiar, selecione e copie daqui):", relatorio, height=220)
    if testes:
        st.dataframe(pd.DataFrame(testes), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------- grafico estilo "Predictor"
BAR_STYLE = {
    1: ("background:#c62828;", "invert"),
    2: ("background:#1d4ed8;", "invert"),
    3: ("background:#eeeeee;", "dark"),
    4: ("background:#151515;", "invert"),
    5: ("background:#f26b21;", "invert"),
    6: ("background:repeating-linear-gradient(180deg,#111 0 3px,#fff 3px 6px);", "stripe"),
}


def greyhound_svg(trap):
    cor = "#111" if trap == 3 else "#fff"
    if trap == 6:
        sh = "filter:drop-shadow(0 0 .6px #000) drop-shadow(0 0 .6px #000) drop-shadow(0 0 .6px #000);"
    elif trap == 3:
        sh = ""
    else:
        sh = "filter:drop-shadow(0 0 .7px rgba(0,0,0,.8));"
    return (
        f"<svg viewBox='0 0 104 42' width='28' height='11' xmlns='http://www.w3.org/2000/svg' "
        f"style='display:block;{sh}'>"
        f"<g fill='{cor}' stroke='{cor}' stroke-linecap='round' stroke-linejoin='round'>"
        "<path stroke-width='0.4' d='M24 13 C32 9.6 44 8.8 54 8.6 C62 8.4 68 7.2 74 6 C78 5 81 4.2 84 3.8 "
        "C87 3.4 89 4 91 5 L99 9 C100.4 9.8 100.4 11 99 11.6 L94 12.4 C91 12.6 89.4 11.4 87 11.2 "
        "C83 11.6 80 13 78.4 15.6 C77.4 19.2 75 22.6 70 22.6 C65 22.6 60 20 55 18.4 C50 16.8 44 15.8 38 16 "
        "C32 16 27 16.6 24 14.8 Z'/>"
        "<path stroke-width='0.3' d='M85.4 3.8 L86.4 0.6 L88.8 3.4 Z'/>"
        "<path fill='none' stroke-width='2.6' d='M77 15.4 L88 18'/>"
        "<path fill='none' stroke-width='1.6' d='M88 18 L98 18.6'/>"
        "<path fill='none' stroke-width='2.4' d='M76 17 L85 21.6'/>"
        "<path fill='none' stroke-width='1.6' d='M85 21.6 L94 22.4'/>"
        "<path fill='none' stroke-width='5' d='M29 13.6 L19 19.4'/>"
        "<path fill='none' stroke-width='2.4' d='M19 19.4 L10 24.6'/>"
        "<path fill='none' stroke-width='1.7' d='M10 24.6 L4 26.4'/>"
        "<path fill='none' stroke-width='3.8' d='M30 15.6 L23 24'/>"
        "<path fill='none' stroke-width='2.2' d='M23 24 L15 30.4'/>"
        "<path fill='none' stroke-width='1.7' d='M15 30.4 L8.4 32.6'/>"
        "<path fill='none' stroke-width='1.2' d='M24 12.6 C18 14.2 12 15 5 13.4'/>"
        "</g></svg>"
    )


def badge_p(t):
    return (badge(t).replace("min-width:24px;height:24px;line-height:24px", "min-width:16px;height:16px;line-height:16px")
            .replace("font-size:14px", "font-size:11px"))


def grafico_predictor(ds):
    """Barras = probabilidade de vitoria (simulacao sobre o tempo projetado), nao o Overall."""
    com = [d for d in ds if not d.get("nd") and d.get("p_vit") is not None]
    if not com:
        return ""
    mx = max(d["p_vit"] for d in com)
    linhas = []
    for d in sorted(ds, key=lambda x: x["trap"]):
        t = d["trap"]
        estilo, _ = BAR_STYLE.get(t, ("background:#888;", "invert"))
        pct = ""
        if d.get("nd") or d.get("p_vit") is None:
            fill = ""
        else:
            w = 100.0 if mx <= 0 else max(11.0, min(100.0, d["p_vit"] / mx * 100.0))
            tip = f"{d['name']} · {d['p_vit']:.1f}% de vencer"
            fill = (f"<div title=\"{tip}\" style='position:relative;width:{w:.1f}%;height:100%;"
                    f"border-radius:8px;box-shadow:inset 0 0 0 1px rgba(128,128,128,.35);{estilo}'>"
                    f"<span style='position:absolute;right:4px;top:50%;transform:translateY(-50%);"
                    f"line-height:0;'>{greyhound_svg(t)}</span></div>")
            pct = (f"<span style='color:var(--dib-tx,#14181F);font-size:12px;font-weight:800;min-width:36px;text-align:right'>"
                   f"{d['p_vit']:.0f}%</span>")
        linhas.append(f"<div style='display:flex;align-items:center;gap:6px;margin:4px 0'>{badge_p(t)}"
                      f"<div style='flex:1;height:15px;background:var(--dib-track,#E8ECF2);border-radius:8px;overflow:hidden'>"
                      f"{fill}</div>{pct}</div>")
    return ("<div style='background:var(--dib-card,#fff);border:1px solid var(--dib-bd,#E3E8EF);box-shadow:var(--dib-sh,none);"
            "border-radius:16px;padding:14px 12px 7px;margin:18px 0 6px;position:relative'>"
            "<div style='position:absolute;top:-1px;left:12px;background:var(--dib-acc,#2F6BFF);color:#fff;font-weight:700;"
            "font-size:11px;padding:3px 12px;border-radius:0 0 10px 10px'>Predictor · chance de vencer</div>"
            "<div style='height:6px'></div>" + "".join(linhas) + "</div>")


# ---------------------------------------------------------------- post pick
_RE_PP_TXT = re.compile(r"post\s*pick\s*[:\-]?\s*((?:[1-6]\s*[-,/]\s*)*[1-6])(?!\d)", re.I)
_RE_SEQ = re.compile(r"[1-6](?:\s*[-,/]\s*[1-6]){1,5}")
_TRAP_KEYS = ("trapNum", "trap", "dogTrap")


def _nums_pp(v):
    if isinstance(v, bool):
        return []
    if isinstance(v, int):
        return [v] if 1 <= v <= 6 else []
    if isinstance(v, str):
        if re.fullmatch(r"[\s1-6,\-/]+", v):
            return [int(x) for x in re.findall(r"[1-6]", v)]
        m = _RE_PP_TXT.search(v)
        return [int(x) for x in re.findall(r"[1-6]", m.group(1))] if m else []
    if isinstance(v, dict):
        for k in _TRAP_KEYS:
            if k in v:
                return _nums_pp(v[k])
        return [n for x in v.values() for n in _nums_pp(x)]
    if isinstance(v, list):
        return [n for x in v for n in _nums_pp(x)]
    return []


def extrair_post_pick(obj):
    n1, n2, n3, n4 = [], [], [], []

    def walk(o, caminho):
        if isinstance(o, dict):
            for k, v in o.items():
                nk = re.sub(r"[^a-z]", "", str(k).lower())
                if "postpick" in nk:
                    n = _nums_pp(v)
                    if n: n1.append((n, f"{caminho}/{k}"))
                elif "pick" in nk:
                    n = _nums_pp(v)
                    if n: n3.append((n, f"{caminho}/{k}"))
                elif "tip" in nk and isinstance(v, (str, list)):
                    if isinstance(v, str) and _RE_SEQ.fullmatch(v.strip()):
                        n4.append((_nums_pp(v), f"{caminho}/{k}"))
                walk(v, f"{caminho}/{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{caminho}[{i}]")
        elif isinstance(o, str):
            m = _RE_PP_TXT.search(o)
            if m:
                n2.append(([int(x) for x in re.findall(r"[1-6]", m.group(1))], caminho + " (texto)"))

    walk(obj, "")
    for grupo in (n1, n2, n3, n4):
        for n, onde in grupo:
            n = list(dict.fromkeys(n))[:6]
            if n:
                return n, onde
    return [], ""


def pistas_post_pick(obj, limite=15):
    res = []

    def walk(o, caminho):
        if len(res) >= limite:
            return
        if isinstance(o, dict):
            for k, v in o.items():
                nk = re.sub(r"[^a-z]", "", str(k).lower())
                if any(x in nk for x in ("pick", "tip", "verdict", "forecast")) and not isinstance(v, (dict, list)):
                    res.append(f"{caminho}/{k} = {str(v)[:60]}")
                elif "pick" in nk:
                    res.append(f"{caminho}/{k} = {str(v)[:60]}")
                walk(v, f"{caminho}/{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o[:12]):
                walk(v, f"{caminho}[{i}]")
        elif isinstance(o, str) and re.search(r"post\s*pick", o, re.I):
            res.append(f"{caminho} = {o[:60]}")

    walk(obj, "")
    return res[:limite]


def _corrida_no_json(obj, race_id):
    achado = []

    def walk(o):
        if achado:
            return
        if isinstance(o, dict):
            if str(o.get("raceId", o.get("race_id", ""))) == str(race_id):
                achado.append(o)
                return
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)

    walk(obj)
    return achado[0] if achado else None


@st.cache_data(ttl=300, show_spinner=False)
def buscar_post_pick(race_id, data_str):
    diag = []
    urls = [f"{BASE}/card/blocks.sd?race_id={race_id}&r_date={data_str}&blocks={b}"
            for b in ("card", "header%2Ccard", "card-header", "card-title",
                      "card-pager%2Ccard-header%2Ccard-tabs%2Ccard-title%2Ccard", "form")]
    urls.append(f"{BASE}/meeting/blocks.sd?r_date={data_str}&blocks=header%2Clist")
    urls.append(f"{BASE}/meeting/blocks.sd?r_date={data_str}&blocks=list")
    for u in urls:
        curto = u.replace(BASE, "")
        time.sleep(0.2)
        r = http().get(u, timeout=8)
        js = None
        if r is not None and r.status_code == 200:
            try: js = r.json()
            except Exception: pass
            
        alvo = js
        if js is not None and "/meeting/" in u:
            alvo = _corrida_no_json(js, race_id)
        nums, onde = extrair_post_pick(alvo) if alvo is not None else ([], "")
        diag.append({"Status": r.status_code if r else "Erro",
                     "Achado": f"{'-'.join(map(str, nums))} em {onde}" if nums else "",
                     "Chaves": _chaves(js) if js is not None else "",
                     "Pistas": pistas_post_pick(alvo) if alvo is not None else [],
                     "Endereço": curto})
        if nums:
            return "-".join(map(str, nums)), diag
    return "", diag


def _fmt_pp(pp):
    n = re.findall(r"[1-6]", str(pp or ""))
    return "-".join(dict.fromkeys(n)) if n else ""


# ---------------------------------------------------------------- analise
def preparar(race_id, r_date, c, classe_in, dist_in, pp_in, so_antes=False):
    cache = st.session_state.setdefault("cache_corridas", {})
    chave = f"{race_id}|{r_date}"
    if chave not in cache:
        res = dib.extrair_dados_racingpost(f"{BASE}/#card/race_id={race_id}&r_date={r_date}")
        if not res or not res[0]:
            return None
        cache[chave] = res
    dogs, meta, meta_info = cache[chave]
    if so_antes:
        dogs = [dict(d, runs=[r for r in d["runs"] if (r.get("date_str") or "") < r_date]) for d in dogs]
    classe = (classe_in or c.get("grade") or (meta_info or {}).get("classe") or "").strip().upper()
    dist = float(dist_in or c.get("dist") or (meta_info or {}).get("dist") or 0)
    if not dist:
        ds_all = [r["dist"] for d in dogs for r in d["runs"] if r["dist"]]
        dist = float(pd.Series(ds_all).mode().iloc[0]) if ds_all else 480.0
    pp = _fmt_pp(pp_in) or _fmt_pp((meta_info or {}).get("post_pick", ""))
    if not pp:
        pp = _fmt_pp(buscar_post_pick(race_id, r_date)[0])
    ctx = {"dist": dist, "today": dib.parse_date(meta["r_date"]), "classe_n": dib.grade_num(classe),
           "post_pick": [int(x) for x in re.findall(r"\d", pp)],
           "vazias": [t for t in range(1, 7) if t not in {d["trap"] for d in dogs if d["name"] != "vacant"}],
           # [NOVO] identificacao da corrida para o log de AvBs (permite fechar o resultado depois)
           "race_id": race_id, "pista": c.get("pista", "") or (meta_info or {}).get("pista", ""),
           "hora": c.get("hora", "") or (meta_info or {}).get("hora", ""),
           "race": c.get("num", "") or (meta_info or {}).get("race", ""), "classe": classe}
    ds = [dib.analisar_galgo(d, ctx) for d in dogs]
    rank, _ = dib.finalizar(ds, ctx)
    ds.sort(key=lambda d: d["trap"])
    res = dib.montar_avbs(rank, ctx)
    s1 = res[0] if isinstance(res, tuple) else res
    return {"ds": ds, "rank": rank, "ctx": ctx, "s1": s1, "classe": classe, "dist": dist, "pp": pp}


def titulo_corrida(c, p=None, prefixo=""):
    t = f"{c['pista']} {c['hora']} (BR {hora_br(c['hora'], True)})" if c.get("hora") else ""
    extra = f" · {p['classe']} · {int(p['dist'])}m · Post Pick: {p['pp'] or '-'}" if p else \
        f" · {c.get('grade', '')} · {c.get('dist', '')}m"
    return f"### {prefixo}{t} · Race {c.get('num', '')}{extra}"


# ---------------------------------------------------------------- exportar texto
def _ov(x):
    """Overall formatado como no core (sem sinal quando a referencia e o galgo mais lento)."""
    f = getattr(dib, "_fmt_ov", None)
    return f(x) if callable(f) else f"{x:+.1f}"


def _ref_txt():
    f = getattr(dib, "_ref_nome", None)
    return f() if callable(f) else "o galgo mediano"


def gerar_texto_analise(c, p):
    txt = []
    txt.append(titulo_corrida(c, p).replace("### ", ""))
    txt.append("")

    txt.append("**Planilha de Projeção**")
    txt.append("| Trp | Galgo | Overall | P. Vit. | Cat | Perfil | Grades | Peso | Dias | Split | Time | Méd. Split | Méd. Time | Time Ajust. | Recup. Média | Conf. |")
    txt.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")

    for d in p["ds"]:
        if d["nd"]:
            txt.append(f"| {d['trap']} | {d['name']} | " + " | ".join(["-"] * 14) + " |")
            continue

        nome = f"{d['name']} {'🚫' if d.get('bloqueado') else ''} {'🎯' if d.get('alvo') else ''}".strip()
        grades = dib.grades_txt(d)

        f_split = f"{d['split']:.2f}" if d.get("split") else "-"
        f_time = f"{d['time']:.2f}" if d.get("time") else "-"
        f_msplit = f"{d['msplit']:.2f}" if d.get("msplit") else "-"
        f_mtime = f"{d['mtime']:.2f}" if d.get("mtime") else "-"
        f_tadj = f"{d['tadj']:.2f}" if d.get("tadj") else "-"
        f_rec = f"{d['rec']:+.2f}%" if d.get("rec") is not None else "-"
        f_peso = f"{d['peso']:.1f}" if d.get("peso") else "-"
        f_pv = f"{d['p_vit']:.1f}%" if d.get("p_vit") is not None else "-"

        txt.append(f"| {d['trap']} | {nome} | {_ov(d['overall'])} | {f_pv} | {d['cat']:.1f} | {d['perfil']} | {grades} | {f_peso} | {d['dias']} | {f_split} | {f_time} | {f_msplit} | {f_mtime} | {f_tadj} | {f_rec} | {d['conf']:.0f}% |")

    txt.append("")
    txt.append(f"(Overall em corpos: vantagem sobre {_ref_txt()}. * = corrida de outra distância convertida com fator medido; † = convertida só por proporção, sem fator medido.)")
    txt.append("")

    classif = " > ".join(f"{d['pos']}º [T{d['trap']}]" for d in p["rank"])
    txt.append(f"**Classificação:** {classif}")
    txt.append("")

    txt.append("**AVBs Principais (≥ 60%)**")
    if not p["s1"]:
        txt.append("Nenhum confronto atingiu os critérios do AvB.")
    else:
        txt.append("| Vencedor (Trap/Nome) | Perdedor (Trap/Nome) | Probabilidade |")
        txt.append("|---|---|---|")
        for (V, D, prob, star) in p["s1"]:
            txt.append(f"| {V['trap']} - {V['name']} | {D['trap']} - {D['name']} | {prob:.1f}% |")

    txt.append("")

    txt.append("**🏁 O Cenário da Corrida:**")

    elegiveis = [d for d in p["rank"] if not d.get("bloqueado")]
    bloqueados = [d for d in p["rank"] if d.get("bloqueado")]
    alvos = [d for d in p["rank"] if d.get("alvo")]
    top_split = min([d for d in p["rank"] if d.get("msplit") is not None], key=lambda x: x["msplit"], default=None) if any(d.get("msplit") for d in p["rank"]) else None

    if elegiveis:
        fav = elegiveis[0]
        rec_fav = fav.get("rec")  # [CORRIGIDO] a Recup. pode não ter dado
        rec_fav_txt = f"{rec_fav:+.1f}%" if rec_fav is not None else "sem dado"
        bloc_acima = [d for d in bloqueados if d["pos"] < fav["pos"]]
        if bloc_acima:
            b_name = bloc_acima[0]['name']
            f_name = fav['name']
            txt.append(f"- 🏆 Melhor Elegível: O favorito absoluto ({b_name}) está bloqueado 🚫. O cão mais seguro é o {f_name} (Posição {fav['pos']} | Recup: {rec_fav_txt}).")
        else:
            f_name = fav['name']
            txt_rec = f" Ele tem recuperação excelente ({rec_fav:+.1f}%)." if (rec_fav is not None and rec_fav > 10) else ""
            txt.append(f"- 🏆 Favorito Claro: O {f_name} lidera o Overall ({_ov(fav['overall'])}).{txt_rec}")

    if bloqueados:
        b = bloqueados[0]
        b_name = b['name']
        avb_info = ""
        if elegiveis:
            for V, D, prob, star in p["s1"]:
                if (V["trap"] == elegiveis[0]["trap"] and D["trap"] == b["trap"]) or (D["trap"] == elegiveis[0]["trap"] and V["trap"] == b["trap"]):
                    avb_info = f" AVB apertado contra o elegível ({prob:.1f}%)."
                    break
        txt.append(f"- 🚫 Falso Favorito Bloqueado: O {b_name} tem Overall alto ({_ov(b['overall'])}), mas foi pego pela Trava (Conf. {b['conf']:.0f}%).{avb_info}")

    if alvos:
        nomes_alvo = ", ".join([d['name'] for d in alvos])
        txt.append(f"- 🎯 Alvo(s): {nomes_alvo} (fora do Top 3 largada e recuperação ≤ 0%).")

    all_splits = [d["msplit"] for d in p["rank"] if d.get("msplit") is not None]
    is_irish_metric = all(s < 2.0 for s in all_splits) if all_splits else False
    splits_ord = sorted(all_splits)
    # [CORRIGIDO] só alerta se o split mais rápido for um ponto fora da curva (>0,15s abaixo do 2º)
    split_outlier = len(splits_ord) >= 3 and (splits_ord[1] - splits_ord[0]) > 0.15

    if top_split and split_outlier and not is_irish_metric:
        s_name = top_split['name']
        txt.append(f"- ⚠️ Alerta de Dados: O {s_name} tem Split muito mais rápido que o resto do campo ({top_split['msplit']:.2f}). Pode ser erro na base.")
    elif top_split and top_split["pos"] > 3:
        txt.append(f"- 🦓 Alerta de Zebra: O {top_split['name']} (Posição {top_split['pos']}) tem o melhor Split médio. Pode largar na frente e surpreender.")
    sem_split = [d["name"] for d in p["rank"] if d.get("msplit") is None]
    if sem_split:
        txt.append(f"- ℹ️ Sem Split na distância exata (largada neutra): {', '.join(sem_split)}.")

    pior_rec = min([d for d in p["rank"] if d.get("rec") is not None], key=lambda x: x["rec"], default=None)
    if pior_rec and pior_rec["rec"] < -10.0:
        rec_name = pior_rec['name']
        txt.append(f"- ⚠️ Tráfego: O {rec_name} tem recuperação ruim ({pior_rec['rec']:+.1f}%).")

    dropping = [d for d in p["rank"] if d.get("cat_mod", 0) > 0]
    if dropping:
        nomes = ", ".join([d['name'] for d in dropping])
        txt.append(f"- 📉 Queda de Classe: {nomes} desceu(ram) de categoria hoje.")

    top3_ms = p["ctx"].get("top3_ms", set())
    if len(top3_ms) >= 3:
        txt.append("- ⚠️ Conflito de Pace: Múltiplos cães com largada rápida (Top 3 Split). Risco de trombada na 1ª curva.")

    return "\n".join(txt)


def badge_g(t):
    return (badge(t).replace("min-width:24px;height:24px;line-height:24px", "min-width:30px;height:30px;line-height:30px")
            .replace("font-size:14px", "font-size:17px"))


def cabecalho_corrida(c, p):
    borda = "border:1px solid rgba(128,128,128,.35);"
    titulo = ""
    if c.get("hora"):
        titulo = (f"<div style='font-size:1.7rem;font-weight:700;line-height:1.25;margin:4px 0 12px'>"
                  f"{c['pista']} {c['hora']} (BR {hora_br(c['hora'], True)})</div>")
    num = str(c.get("num") or "").strip()
    chips = [f"Race {num}" if num else "", p["classe"], f"{int(p['dist'])}m"]
    chips_html = "".join(
        f"<span style='display:inline-block;{borda}background:rgba(128,128,128,.12);border-radius:999px;"
        f"padding:5px 14px;margin:0 8px 8px 0;font-size:1rem'>{x}</span>" for x in chips if x)
    sep = "<span style='opacity:.6'>–</span>"
    ordem = sep.join(badge_g(d["trap"]) for d in p["rank"])
    pp_nums = re.findall(r"[1-6]", p["pp"] or "")
    pp_html = ("<span style='opacity:.6'>-</span>" if not pp_nums
               else "<span style='opacity:.6;margin:0 3px'>-</span>".join(badge_g(n) for n in pp_nums))
    return (titulo + f"<div>{chips_html}</div>"
            "<div style='font-size:1.3rem;font-weight:700;margin:10px 0 8px'>Classificação geral</div>"
            f"<div style='{borda}background:rgba(128,128,128,.08);border-radius:10px;padding:12px 14px'>"
            f"<div style='display:flex;flex-wrap:wrap;align-items:center;gap:8px'>{ordem}</div>"
            f"<div style='margin:10px 0 0 10px;font-size:1rem'><span style='opacity:.8'>Post Pick do site:</span> {pp_html}</div>"
            "</div>")


# ---------------------------------------------------------------- colunas travadas ao rolar para o lado
_JS_TRAVAR = """<script>
(function () {
  var win, doc;
  try { win = window.parent; doc = win.document; } catch (e) { return; }

  // As colunas travadas ficam no CSS (vale para TODAS as linhas, inclusive as de baixo);
  // o JavaScript so marca a tabela e mede a largura da 1a coluna.
  var NOT = ':not(.sep):not(.sep-avb)';
  var CSS =
    '.dib-table.sticky-1 td:nth-child(1)' + NOT + ',' +
    '.dib-table.sticky-2 td:nth-child(1)' + NOT + ',' +
    '.dib-table.sticky-1 th:nth-child(1),' +
    '.dib-table.sticky-2 th:nth-child(1)' +
    '{ position: sticky !important; left: 0 !important; z-index: 2 !important; }' +
    '.dib-table.sticky-2 td:nth-child(2)' + NOT + ',' +
    '.dib-table.sticky-2 th:nth-child(2)' +
    '{ position: sticky !important; left: var(--dib-left2, 0px) !important; z-index: 2 !important;' +
    '  box-shadow: 8px 0 10px -8px rgba(0,0,0,.3) !important; }' +
    '.dib-table.sticky-1 td:nth-child(1)' + NOT + ',' +
    '.dib-table.sticky-2 td:nth-child(1)' + NOT + ',' +
    '.dib-table.sticky-2 td:nth-child(2)' + NOT +
    '{ background-color: var(--dib-card, #fff) !important; }' +
    '.dib-table.sticky-1 td:nth-child(1)' + NOT + '{ box-shadow: 8px 0 10px -8px rgba(0,0,0,.3) !important; }' +
    '.dib-table.sticky-1 th:nth-child(1),' +
    '.dib-table.sticky-2 th:nth-child(1),' +
    '.dib-table.sticky-2 th:nth-child(2)' +
    '{ background-color: var(--dib-head, #f0f2f6) !important; z-index: 3 !important; }' +
    '.dib-table.sticky-1 th:nth-child(1){ box-shadow: 8px 0 10px -8px rgba(0,0,0,.3) !important; }';

  var styleId = 'dib-sticky-style-v2';
  var estilo = doc.getElementById(styleId);
  if (!estilo) {
    estilo = doc.createElement('style');
    estilo.id = styleId;
    doc.head.appendChild(estilo);
  }
  estilo.innerHTML = CSS;

  function aplicar() {
    Array.prototype.forEach.call(doc.querySelectorAll('table.dib-table'), function (t) {
      var tr0 = t.querySelector('tr');
      if (!tr0) return;
      var cab = Array.prototype.map.call(tr0.children, function (c) {
        return (c.innerText || '').trim().toLowerCase();
      });
      var n = 0;
      if (cab[0] === 'trap' && cab[1] === 'galgo') n = 2;
      else if (cab[0] === 'avb') n = 1;
      if (!n) return;
      if (n === 2 && tr0.children[0]) {
        var w = Math.floor(tr0.children[0].getBoundingClientRect().width) - 1;
        if (w > 0) t.style.setProperty('--dib-left2', w + 'px');
      }
      if (!t.classList.contains('sticky-' + n)) t.classList.add('sticky-' + n);
    });
  }
  [0, 250, 700, 1500, 3000].forEach(function (ms) { setTimeout(aplicar, ms); });
  setInterval(aplicar, 800);
})();
</script>"""


def fixar_colunas():
    components.html(_JS_TRAVAR + f"<!-- {time.time()} -->", height=0)


def analisar(c, classe_in, dist_in, pp_in):
    p = preparar(c["id"], c["data"], c, classe_in, dist_in, pp_in)
    if not p:
        return
    st.markdown(dib_ui.cabecalho(c, p, badge_g, hora_br), unsafe_allow_html=True)
    st.markdown(dib_ui.cards_top3(p["rank"], badge), unsafe_allow_html=True)
    st.markdown(dib_ui.cabecalho_curto(c, p, hora_br), unsafe_allow_html=True)
    st.markdown(dib_ui.cards_avb(p["s1"], badge), unsafe_allow_html=True)
    st.markdown(grafico_predictor(p["ds"]), unsafe_allow_html=True)
    with st.expander("📊 Planilha de Projeção (completa)"):
        st.markdown(dib.tabela_projecao(p["ds"]), unsafe_allow_html=True)
    if not p["pp"]:
        st.caption("Post Pick não encontrado automaticamente. Você pode digitar em ⚙️ Ajustes (ex: 1-2-5).")
        with st.expander("🔎 Diagnóstico do Post Pick (copie e cole no chat)", expanded=True):
            diag = buscar_post_pick(c["id"], c["data"])[1]
            linhas = [f"corrida {c['id']} {c['data']}"]
            for d_ in diag:
                linhas.append(f"{d_['Status']} | {d_['Endereço']} | chaves: {d_['Chaves']}")
                linhas += [f"    {x}" for x in d_["Pistas"]]
            relatorio = "\n".join(linhas)
            botao_copiar(relatorio)
            st.text_area("Relatório:", relatorio, height=200)
            st.dataframe(pd.DataFrame([{k: v for k, v in d_.items() if k != "Pistas"} for d_ in diag]),
                         use_container_width=True, hide_index=True)
    with st.expander("⚔️ Planilha de AvB (completa)"):
        dib.tabela_avb(p["s1"], "AvBs — ★ principal · 🔹 alternativo · 🔥 Trombador × Limpo")
    if hasattr(dib, "gerar_observacoes"):
        dib.gerar_observacoes(p["rank"], p["s1"], p["ctx"])

    st.markdown("---")
    with st.expander("📋 Exportar Análise (Copiar e Colar para o Chat)"):
        texto_gerado = gerar_texto_analise(c, p)
        botao_copiar(texto_gerado)
        st.text_area("Se o botão acima não funcionar, copie o texto aqui:", texto_gerado, height=200)
    fixar_colunas()


# ---------------------------------------------------------------- aba Form
def mostrar_form(c):
    raw = buscar_form_raw(c["id"], c["data"])
    st.markdown(titulo_corrida(c, None, "📄 Form · "))
    if not raw:
        st.warning("Não consegui carregar o Form desta corrida.")
        return
    dib.descobrir_chaves(raw)
    heads = ["Data", "Pista", "Dis", "Trp", "Split", "Bends", "Fin", "By", "Win/Sec", "Remarks",
             "WnTm", "Gng", "Wght", "SP", "Grade", "CalTm"]
    for dog in sorted(raw, key=lambda x: int(re.search(r"\d+", str(x.get("trapNum", 9))).group())
                      if re.search(r"\d+", str(x.get("trapNum", ""))) else 9):
        trap = re.search(r"\d+", str(dog.get("trapNum", "")))
        trainer = _get(dog, "trainer", EXTRA) or ""
        peso = dog.get("weight") or ""
        st.markdown(f"{badge(trap.group()) if trap else ''} **{dog.get('dogName', '?')}**"
                    f"{' · Tnr: ' + str(trainer) if trainer else ''}{' · ' + str(peso) + ' kg' if peso else ''}",
                    unsafe_allow_html=True)
        rows = []
        for f in dog.get("forms", []):
            n = dib.norm_run(f)
            g = lambda k: dib.pick_fb(f, k)
            data = n["date"].strftime("%d%b%y") if n["date"] else n["date_str"]
            rows.append([data, n["track"], f"{int(n['dist'])}m" if n["dist"] else "", n["trap"] or "",
                         g("split") or "", n["bends"], g("fin") or "", g("by") or "",
                         _get(f, "winsec", EXTRA) or "", g("remarks") or "", g("wntm") or "",
                         g("gng") or "", g("weight") or "", _get(f, "sp", EXTRA) or "",
                         n["grade"], g("caltm") or ""])
        if rows:
            tabela_html(heads, rows)
        else:
            st.caption("Sem corridas anteriores (galgo vacant ou sem histórico).")


# ---------------------------------------------------------------- resultados
def _comparar_previsto_real(c, linhas, classe_in, dist_in, pp_in):
    p = preparar(c["id"], c["data"], c, classe_in, dist_in, pp_in, so_antes=True)
    if not p or not p["rank"]:
        return
    prev = {d["trap"]: d["pos"] for d in p["rank"]}
    real = {l["trap"]: l["pos"] for l in linhas if l["trap"]}
    st.markdown("#### 🔍 Previsto × Real (projeção só com corridas anteriores)")
    tabela_html(["Real", "Galgo", "Previsto"],
                [[f"{l['pos']}º", f"{badge(l['trap'])} {l['nome']}", f"{prev.get(l['trap'], '-')}º"]
                 for l in linhas])
    fav, venc = p["rank"][0], linhas[0]
    top3_prev = {d["trap"] for d in p["rank"][:3]}
    top3_real = {l["trap"] for l in linhas[:3] if l["trap"]}
    st.markdown(f"- **Vencedor:** previsto {badge(fav['trap'])} {fav['name']} → "
                f"{'✅ acertou' if fav['trap'] == venc['trap'] else '❌ venceu ' + venc['nome']}",
                unsafe_allow_html=True)
    st.markdown(f"- **Top 3:** {len(top3_prev & top3_real)} de 3 galgos previstos entre os 3 primeiros.")
    if p["s1"]:
        st.markdown("**AVBs aprovados:**")
        for (V, D, prob, star) in p["s1"]:
            pv, pd_ = real.get(V["trap"]), real.get(D["trap"])
            ok = ("✅" if pv < pd_ else "❌") if (pv and pd_) else ("✅" if pv else ("❌" if pd_ else "—"))
            st.markdown(f"- {ok} {badge(V['trap'])} {V['name']} ({pv or '-'}º) vence "
                        f"{badge(D['trap'])} {D['name']} ({pd_ or '-'}º) · {prob:.1f}%", unsafe_allow_html=True)
    else:
        st.markdown("- Nenhum AVB aprovado nesta corrida.")


def mostrar_resultado(c, classe_in, dist_in, pp_in):
    linhas, tent, primeira = buscar_resultado(c["id"], c["data"], c.get("tid", ""), c.get("hora", ""))
    st.markdown(titulo_corrida(c, None, "📊 Resultado · "))
    mostrar_replay(c)
    if not linhas:
        st.warning("Não consegui ler o resultado desta corrida (ela pode ainda não ter sido disputada, "
                   "ou o endereço do resultado ainda não foi descoberto). Veja o diagnóstico abaixo.")
        st.dataframe(pd.DataFrame(tent), use_container_width=True, hide_index=True)
        if primeira is not None:
            st.caption("Primeira resposta recebida:")
            st.json(primeira if len(str(primeira)) < 6000 else {"(cortado)": str(primeira)[:6000]})
        painel_descobrir(c)
        return
    tabela_html(["Pos", "Trap", "Galgo", "SP", "Tempo", "Margem", "Comentário"],
                [[f"{l['pos']}º", badge(l["trap"]), l["nome"], l["sp"], l["tempo"], l["margem"], l["coment"]]
                 for l in linhas])
    # [NOVO] fecha os AvBs desta corrida sem digitar nada (antes e depois da comparacao, que tambem registra previsoes)
    fechados = _fechar_confrontos(c["data"], linhas)
    try:
        _comparar_previsto_real(c, linhas, classe_in, dist_in, pp_in)
    except Exception as e:
        st.caption(f"Não foi possível comparar com a projeção: {e}")
    fechados += _fechar_confrontos(c["data"], linhas)
    if fechados:
        st.caption(f"✅ {fechados} confrontos de AvB fechados automaticamente com este resultado.")


# ---------------------------------------------------------------- tela
_CSS_SIDEBAR = """<style>
section[data-testid="stSidebar"]{width:21rem !important;min-width:21rem !important;max-width:21rem !important;}
section[data-testid="stSidebar"] .stButton > button{padding:.35rem .4rem;min-height:0;}
span[data-baseweb="tag"]{background-color:#2F6BFF !important;color:#fff !important;}
div[data-baseweb="slider"]{filter:hue-rotate(228deg) saturate(1.15);}
section[data-testid="stSidebar"] .stButton > button p{font-size:.85rem;line-height:1.25;}
</style>"""


# ---------------------------------------------------------------- filtro de galgos
_FIL_METRICAS = [("overall", "Overall"), ("split", "Melhor Split"), ("time", "Melhor Time"),
                 ("msplit", "Média Split"), ("mtime", "Média Time"), ("tadj", "Tadj"),
                 ("metrica", "Métrica"), ("rec", "Recup. média")]


def _ranks_corrida(ds):
    """Posicao (1 = melhor) de cada galgo em cada metrica, dentro da corrida."""
    out = {d["trap"]: {} for d in ds}
    for k, _ in _FIL_METRICAS:
        if k == "overall":
            for d in ds:
                if not d.get("nd") and d.get("pos"):
                    out[d["trap"]][k] = int(d["pos"])
            continue
        vals = [(d["trap"], d[k]) for d in ds if not d.get("nd") and d.get(k) is not None]
        vals.sort(key=lambda x: x[1], reverse=(k == "rec"))
        for r, (t, _) in enumerate(vals, 1):
            out[t][k] = r
    return out


_PP_OPCOES = ["1º do Post Pick", "2º do Post Pick", "3º do Post Pick", "Fora do Post Pick"]


def _passa_filtro(d, rk, f, pp=()):
    if d.get("nd"):
        return False
    sel_pp = f.get("pp")
    if sel_pp:
        if not pp:
            return False  # corrida sem Post Pick conhecido: não dá para afirmar
        if d["trap"] in pp:
            rot = f"{pp.index(d['trap']) + 1}º do Post Pick"
            if rot not in sel_pp:
                return False
        elif "Fora do Post Pick" not in sel_pp:
            return False
    for k, _ in _FIL_METRICAS:
        sel_ = f.get(k)
        if sel_ and rk.get(k) not in sel_:
            return False
    if f.get("perfil") and d.get("perfil") not in f["perfil"]:
        return False
    pmin, pmax = f.get("peso", (None, None))
    if pmin is not None and (d.get("peso") is None or d["peso"] < pmin):
        return False
    if pmax is not None and (d.get("peso") is None or d["peso"] > pmax):
        return False
    rmin, rmax = f.get("rec_faixa", (None, None))
    if rmin is not None or rmax is not None:
        if d.get("rec") is None:
            return False
        if rmin is not None and d["rec"] < rmin:
            return False
        if rmax is not None and d["rec"] > rmax:
            return False
    if (d.get("conf") or 0) < f.get("conf_min", 0):
        return False
    return True


def painel_filtro(lista, data_str, classe_in, dist_in, pp_in):
    st.markdown("### 🔎 Filtro de galgos")
    st.caption("Escolha as características (pode marcar mais de uma em cada). Os filtros se combinam (E). "
               "As posições são do galgo **dentro da própria corrida** (1º = melhor; em Recup. 1º = maior recuperação). "
               "Campo vazio = sem filtro.")
    pos = [1, 2, 3, 4, 5, 6]
    f = {}
    cols = st.columns(4)
    for i, (k, nome) in enumerate(_FIL_METRICAS):
        with cols[i % 4]:
            f[k] = st.multiselect(nome, pos, key=f"fil_{k}", format_func=lambda x: f"{x}º")
    rmin_, rmax_ = st.slider("Recup. média — margem (%)", -50, 50, (-50, 50), step=1, key="fil_rec_faixa",
                             help="Recuperação média em % (positivo = ganha posições na corrida). "
                                  "Nas pontas (-50 / 50) não há limite.")
    f["rec_faixa"] = (rmin_ if rmin_ > -50 else None, rmax_ if rmax_ < 50 else None)
    f["pp"] = st.multiselect("Post Pick", _PP_OPCOES, key="fil_pp",
                             help="Escolha 'Fora do Post Pick' para galgos que o mercado não colocou. "
                                  "Corridas sem Post Pick conhecido ficam de fora quando este filtro está ativo.")
    c1, c2, c3 = st.columns(3)
    with c1:
        f["perfil"] = st.multiselect("Perfil", ["Limpo", "Irregular", "Trombador"], key="fil_perfil")
    with c2:
        pmin, pmax = st.slider("Peso (kg)", 20.0, 40.0, (20.0, 40.0), step=0.5, key="fil_peso")
        f["peso"] = (pmin if pmin > 20.0 else None, pmax if pmax < 40.0 else None)
    with c3:
        f["conf_min"] = st.slider("Confiança mínima (%)", 0, 100, 0, step=5, key="fil_conf")

    cache = st.session_state.setdefault("fil_dados", {})
    chave = f"{data_str}|{len(lista)}|{lista[0]['id'] if lista else ''}|{classe_in}|{dist_in}|{pp_in}"
    dados = cache.get(chave)
    ja = len(dados) if dados else 0
    st.markdown("---")
    b1, b2 = st.columns([1, 3])
    with b1:
        carregar = st.button(f"⚙️ Analisar {len(lista)} corridas" if not dados else "🔄 Reanalisar", key="fil_carregar")
    with b2:
        if dados is None:
            st.caption("Primeiro analise as corridas do dia (respeita o filtro de Pistas da barra lateral). "
                       "Depois, mudar os filtros é instantâneo.")
        else:
            st.caption(f"{ja} corridas analisadas.")
    if carregar:
        dados = {}
        barra = st.progress(0.0, text="Analisando corridas...")
        for i, c in enumerate(lista):
            try:
                p = preparar(c["id"], data_str, c, classe_in, dist_in, pp_in)
            except Exception:
                p = None
            if p:
                dados[c["id"]] = (c, p, _ranks_corrida(p["ds"]))
            barra.progress((i + 1) / max(len(lista), 1), text=f"Analisando {i + 1}/{len(lista)}")
        barra.empty()
        cache.clear()
        cache[chave] = dados
        st.rerun()
    if not dados:
        return

    ativo = any(f.get(k) for k, _ in _FIL_METRICAS) or f["perfil"] or f["pp"] or f["peso"] != (None, None) or f["rec_faixa"] != (None, None) or f["conf_min"] > 0
    if not ativo:
        st.info("Defina pelo menos um filtro para ver as corridas.")
        return
    achadas, total = 0, 0
    blocos = []
    for c, p, rk in sorted(dados.values(), key=lambda x: (x[0]["hora"], x[0]["pista"])):
        pp_l = [int(x) for x in re.findall(r"[1-6]", str(p.get("pp") or ""))]
        bons = [d for d in sorted(p["ds"], key=lambda d: d["trap"]) if _passa_filtro(d, rk.get(d["trap"], {}), f, pp_l)]
        if not bons:
            continue
        achadas += 1
        total += len(bons)
        linhas = []
        for d in bons:
            r = rk[d["trap"]]
            linhas.append([dib.trap_label(d), dib.nome_marcado(d) + dib.brt_html(d),
                           f"{r.get('overall', '-')}º", dib.perfil_pilula(d["perfil"]),
                           (f"{pp_l.index(d['trap']) + 1}º" if d["trap"] in pp_l else ("fora" if pp_l else "-")), dib.peso_txt(d),
                           *[(f"{r[k]}º · {d[k]:.2f}" if r.get(k) and d.get(k) is not None else "-")
                             for k in ("split", "time", "msplit", "mtime", "tadj", "metrica", "rec")],
                           f"{d['conf']:.0f}%"])
        tab = dib.tbl(["Trap", "Galgo", "Overall", "Perfil", "Post<br>Pick", "Peso", "Melhor<br>Split", "Melhor<br>Time",
                       "Média<br>Split", "Média<br>Time", "Tadj", "Métrica", "Recup.<br>Média", "Conf."],
                      linhas, sticky=2, w1=64, w2=125)
        blocos.append((c, p, tab))
    st.success(f"{total} galgos em {achadas} corridas (de {len(dados)} analisadas).")
    for c, p, tab in blocos:
        st.markdown(f"**{c['pista']} {c['hora']} (BR {hora_br(c['hora'], True)}) · Race {c.get('num', '')} · "
                    f"{p['classe']} · {int(p['dist'])}m**")
        st.markdown(tab, unsafe_allow_html=True)
    fixar_colunas()


def main():
    dib_ui.aplicar_tema()
    dib.mostrar_logo()  # logo: fundo branco no tema claro, fundo preto no tema escuro (assets/logo_*.jpg)

    st.markdown(_CSS_SIDEBAR, unsafe_allow_html=True)
    with st.sidebar:
        modo_txt = st.radio("Ver", ["🏁 Corridas", "📊 Resultados", "🔎 Filtro", "🧪 Coleta"], horizontal=True, label_visibility="collapsed")
        modo = "col" if "Coleta" in modo_txt else ("res" if "Resultados" in modo_txt else ("fil" if "Filtro" in modo_txt else "ana"))
        data = st.date_input("Data", value=agora_uk().date())
        data_str = data.strftime("%Y-%m-%d")
        ocultar = st.checkbox("Ocultar corridas já realizadas", value=True) if modo == "ana" else False
        with st.expander("⚙️ Ajustes (opcional)"):
            classe_in = st.text_input("Classe (vazio = da lista)", value="")
            dist_in = st.number_input("Distância (m) - 0 = da lista", value=0, step=10)
            pp_in = st.text_input("Post Pick (ex: 1-2-3)", value="")
            url_custom = st.text_input("Endereço da lista (use {data})", value="")
        corridas, tentativas, primeira = buscar_lista(data_str, url_custom)
        memoria = st.session_state.setdefault("lista_ok", {})
        if corridas:
            memoria[data_str] = corridas
        elif data_str in memoria:
            corridas = memoria[data_str]
            st.caption("⚠️ Usando a última lista carregada (o site não respondeu agora).")
        if not corridas and any(t.get("Status") in (403, 406) for t in tentativas):
            st.error("O site recusou o acesso (bloqueio Anti-Bot). Costuma ser bloqueio temporário. "
                     "Espere alguns minutos, escolha o dia anterior ou toque em Tentar de novo.")
        if st.button("🔄 Recarregar lista"):
            buscar_lista.clear()
            st.rerun()

        # [NOVO] fecha, de uma vez, os resultados dos AvBs que ficaram pendentes
        if hasattr(dib, "corridas_pendentes") and st.button("🔁 Fechar resultados pendentes"):
            pend = dib.corridas_pendentes()
            cmap = {x["id"]: x for lst in memoria.values() for x in lst}
            for d_ in {d for _, d in pend if d}:
                try:
                    for x in buscar_lista(d, url_custom)[0]:
                        cmap[x["id"]] = x
                except Exception:
                    pass
            fechados, consultadas = 0, 0
            with st.spinner("Buscando resultados..."):
                for rid, d_ in pend[:25]:
                    cc = cmap.get(rid, {})
                    linhas_, _, _ = buscar_resultado(rid, d_, cc.get("tid", ""), cc.get("hora", ""))
                    consultadas += 1
                    if linhas_:
                        fechados += _fechar_confrontos(d_, linhas_)
            st.success(f"{fechados} confrontos fechados · {consultadas} corridas consultadas"
                       + (f" · {len(pend) - consultadas} ficaram para a próxima vez." if len(pend) > consultadas else "."))
            if consultadas and not fechados:
                st.caption("Nenhum resultado lido. Abra uma corrida em 📊 Resultados para descobrir o endereço do resultado.")

        sel = st.session_state.get("sel")
        if corridas:
            pistas = sorted({c["pista"] for c in corridas})
            filtro = st.multiselect("Pistas (vazio = todas)" if modo != "fil" else "Limitar a pistas (opcional)", pistas)
            if modo == "fil":
                st.caption("👉 Os filtros de galgos ficam na tela principal. Feche este menu (setas «) para vê-los.")
            lista = [c for c in corridas if not filtro or c["pista"] in filtro]
            hoje = data == agora_uk().date()
            limite = agora_uk().strftime("%H:%M")
            if modo == "ana" and ocultar and hoje:
                lista = [c for c in lista if c["hora"] >= limite]
            if modo == "res":
                if hoje: lista = [c for c in lista if c["hora"] < limite]
                lista = sorted(lista, key=lambda c: (c["hora"], c["pista"]), reverse=True)
            st.caption(f"{len(lista)} corridas · horário da pista (Brasil = −3h)")
            for c in ([] if modo == "fil" else lista):
                ativo = bool(sel and sel.get("id") == c["id"] and sel.get("modo") == modo)
                rotulo = f"{'▶ ' if ativo else ''}{c['hora']} (BR {hora_br(c['hora'], True)}) · {c['pista']} R{c['num'] or '?'} · " \
                         f"{c['grade'] or '?'} · {c['dist'] or '?'}m"
                st.button(rotulo, key=f"{modo}_{c['id']}", use_container_width=True,
                          on_click=escolher, args=(c, data_str, modo))
        else:
            st.warning("Não consegui carregar a lista. Veja o diagnóstico abaixo.")

        with st.expander("🔎 Diagnóstico da lista"):
            st.dataframe(pd.DataFrame(tentativas), use_container_width=True, hide_index=True)
            if not corridas and primeira is not None:
                st.caption("Resposta recebida:")
                st.json(primeira if len(str(primeira)) < 6000 else {"(cortado)": str(primeira)[:6000]})
        with st.expander("🔗 Usar link manual"):
            link = st.text_input("Link da corrida", placeholder="Cole o link aqui...")
            if st.button("Analisar link") and link:
                rid = re.search(r"race_id=(\d+)", link)
                rd = re.search(r"r_date=([\d-]+)", link)
                tid_m = re.search(r"track_id=(\d+)", link)
                rt_m = re.search(r"r_time=(\d{1,2}(?::|%3A)\d{2})", link)
                if rid and rd:
                    escolher({"id": rid.group(1), "hora": (rt_m.group(1).replace("%3A", ":") if rt_m else ""),
                              "pista": "", "num": "", "grade": "", "dist": 0,
                              "tid": (tid_m.group(1) if tid_m else "")},
                             rd.group(1), "ana")
                    st.rerun()
                else:
                    st.error("Link inválido: precisa ter race_id e r_date.")

    if modo != "fil":
        st.session_state["modo_ant"] = modo
    if modo == "col":
        painel_coleta(url_custom)
        return
    if modo == "fil":
        if st.session_state.get("modo_ant") != "fil":
            fechar_sidebar()  # no celular o menu cobre a tela: fecha para mostrar os filtros
        st.session_state["modo_ant"] = "fil"
        painel_filtro(lista if corridas else [], data_str, classe_in, dist_in, pp_in)
        return

    sel = st.session_state.get("sel")
    if sel:
        if sel.get("modo") == "res":
            aba1, aba2 = st.tabs(["📊 Resultado", "📄 Form"])
            with aba1: mostrar_resultado(sel, classe_in, dist_in, pp_in)
        else:
            aba1, aba2 = st.tabs(["📋 Análise", "📄 Form"])
            with aba1: analisar(sel, classe_in, dist_in, pp_in)
        with aba2:
            mostrar_form(sel)
        if st.session_state.pop("fechar", False):
            fechar_sidebar()


main()
