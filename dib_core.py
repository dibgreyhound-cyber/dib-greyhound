# -*- coding: utf-8 -*-
"""
dib_core.py (v4.1)

Base: o v4 enviado pelo usuario. Mudancas desta versao (3 pontos):

  1) JANELA DE DISTANCIA 200 m (antes 100 m): o Don Cici (so corridas de 575 m, prova de 400 m, diferenca de 175 m)
     agora entra na planilha, no Overall e no Predictor.
  2) FATOR DE DISTANCIA MEDIDO nos seus proprios dados (calibracao_corridas.csv): galgos que correram duas distancias
     na mesma pista em ate 75 dias. Ajusta a velocidade por 100 m (ex.: -1,5 %/100 m) em vez de assumir velocidade igual.
       - pista com poucos pares usa o fator global; sem dados suficientes = conversao so proporcional,
         com incerteza grande (DIST_SD_100M_SEM_FATOR) e o galgo NAO entra em AvB (AVB.exige_fator_medido).
       - Grades: "*" = corrida convertida com fator medido; "†" = convertida so por proporcao (sem fator medido).
  3) OVERALL = TEMPO PROJETADO EM CORPOS: o mesmo tempo projetado que alimenta o AvB e o Predictor
     (Overall = (mediana do campo - tempo projetado) / CORPO_S). Planilha, Predictor e AvB nao discordam mais.
     Categoria, Recuperacao e Regularidade continuam aparecendo e entram como criterios do AvB / na incerteza.
     Post Pick (palpite de tipster) nao entra mais no tempo (postpick_sec = 0.0), para o modelo ser independente.

  4) (v4.2) ENCOLHIMENTO (shrinkage) do tempo projetado: galgo com historico incerto (poucas corridas, corridas de outra
     distancia sem fator medido) tem o tempo puxado para o meio do campo. Antes, a incerteza maior INFLAVA a chance de
     vencer de galgos pouco conhecidos (ex.: 38 % e 30 % para dois galgos marcados com a reguinha).
  5) (v4.2) OVERALL sem valores negativos: referencia = galgo mais lento do campo (CFG["OVERALL_REF"] = "ultimo").
     Opcoes: "mediano" (positivo e negativo) ou "lider" (0 = lider, demais negativos).

  VERSAO = "avb-unico-4" (a validacao separa as amostras por versao).
"""
import re
import html
import math
import json
import os
import csv
import time
import hashlib
from datetime import datetime
import numpy as np
import pandas as pd
import requests
import streamlit as st

# =====================================================================
# DICIONARIO DE REMARKS (TABELA DO MARKO)
# chave -> (significado, tipo, ajuste de tempo)
# ajuste: light/medium/heavy = interferencia | saw/vsaw = largada lenta | exclui = fora da media | None = nao mexe
# =====================================================================
REMARKS_INFO = {
    "ald": ("Liderou Sempre", "pos", None),
    "awk": ("Desajeitado", "neg", "light"),
    "blk": ("Trombada Forte na Curva", "neg", "heavy"),
    "bmp": ("Trombou Durante uma Curva", "neg", "medium"),
    "chl": ("Desafiado na Curva", "alerta", None),
    "clrrn": ("Corrida Limpa", "pos", None),
    "crd": ("Truncado na Curva", "alerta", "medium"),
    "crdnrln": ("Truncado no Final", "alerta", "light"),
    "crdrnln": ("Truncado na Reta Final", "alerta", "medium"),
    "crdrnup": ("Truncado desde o Início", "alerta", "medium"),
    "crmp": ("Correu em Espaço Apertado na Curva", "neg", "medium"),
    "disp": ("Disputou", "alerta", None),
    "dsp": ("Disputou na Curva", "alerta", None),
    "displd": ("Liderou com Muita Disputa", "alerta", None),
    "ep": ("Ritmo Acelerado", "pos", None),
    "evch": ("Ganharia se Fosse Bom o Suficiente", "neg", None),
    "fcd": ("Forçado a Algo", "alerta", "medium"),
    "fcdck": ("Forçado a Manter-se na Curva", "alerta", "medium"),
    "fell": ("Caiu na Curva", "neg", "exclui"),
    "hldon": ("Posição Mantida", "pos", None),
    "imp": ("Impedido na Curva", "alerta", "medium"),
    "jmp": ("Saltou", "alerta", None),
    "jmplate": ("Saltou Atrasado", "neg", "saw"),
    "ko": ("Derrubado na Curva", "neg", "exclui"),
    "lame": ("Manco", "neg", "exclui"),
    "ld": ("Liderou a Curva", "pos", None),
    "ldbmp": ("Tomou a Liderança com Esbarrão", "pos", None),
    "ldnrln": ("Tomou a Liderança na Reta Final", "pos", None),
    "in": ("Linha de Chegada", "alerta", None),
    "mid": ("Corre pelo Meio", "alerta", None),
    "msdbrk": ("Passou Reto na Curva", "neg", "vsaw"),
    "on": ("Até o Final", "alerta", None),
    "qaw": ("Largada Rápida", "pos", None),
    "rls": ("Corre por Dentro", "alerta", None),
    "rnln": ("Linha Reta e Alterou Pouco seu Traçado", "alerta", None),
    "rnon": ("Manteve um Galope Forte até o Final", "pos", None),
    "rnonwll": ("Manteve um Galope Forte até o Final", "pos", None),
    "rnup": ("Distância entre a Trap e a 1ª Curva", "alerta", None),
    "saw": ("Largada Lenta", "neg", "saw"),
    "snled": ("Liderou desde o Início", "pos", None),
    "stmb": ("Tropeçou", "neg", "medium"),
    "strfn": ("Chegada Forte", "pos", None),
    "stt": ("Início", "alerta", None),
    "struck": ("Atingido", "alerta", "medium"),
    "styd": ("Ficou", "neg", None),
    "turnedintrps": ("Voltou e/ou Ficou na Trap", "neg", "exclui"),
    "vsaw": ("Largada Muito Lenta", "neg", "vsaw"),
    "vw": ("Corredor Mais Aberto", "alerta", None),
    "w": ("Curva Ampla", "alerta", None),
    "baulk": ("Bloqueado (Baulk)", "neg", "heavy"),
}
DICIONARIO_REMARKS = {k: v[0] for k, v in REMARKS_INFO.items()}

REMARKS_ALIASES = {
    "crowded": "crd", "crwd": "crd", "crowd": "crd", "bumped": "bmp", "bump": "bmp", "bmpd": "bmp",
    "baulked": "baulk", "baulking": "baulk", "blocked": "blk", "checked": "fcd", "cramped": "crmp",
    "stumbled": "stmb", "stumble": "stmb", "snld": "snled", "stayed": "styd", "turnedin": "turnedintrps",
    "turnedintraps": "turnedintrps", "knockedout": "ko", "knocked": "ko", "missedbreak": "msdbrk",
    "slowaway": "saw", "slowlyaway": "saw", "veryslowaway": "vsaw", "veryslowlyaway": "vsaw",
    "quickaway": "qaw", "quicklyaway": "qaw", "awkward": "awk", "impeded": "imp", "disputed": "disp",
}
_ORD = {"first": "1", "second": "2", "third": "3", "fourth": "4"}

# =====================================================================
# CONFIGURACAO GLOBAL
# =====================================================================
CFG = {
    "N_RUNS": 5, "N_CORREDORES": 6, "CAT_BONUS": 2.0,

    # ---- Janela de distancia ----
    "JANELA_M": 200.0,        # corridas oficiais de (dist - JANELA_M) a (dist + JANELA_M) entram nas medias de tempo
    "CONF_PESO_MIN": 0.5,     # peso de uma corrida na PONTA da janela na Confianca (1.0 = distancia exata)
    # incerteza extra (s) por 100 m de diferenca de distancia, entra na variancia do tempo projetado:
    "DIST_SD_100M_MEDIDO": 0.06,      # quando existe fator de distancia medido para a pista
    "DIST_SD_100M_SEM_FATOR": 0.20,   # conversao so proporcional (sem fator medido): incerteza grande

    # ---- Fator de distancia medido nos proprios dados (velocidade por 100 m) ----
    "FATOR_DIST": {
        "min_pares_pista": 25,    # pares (mesmo galgo, mesma pista, duas distancias) para usar o fator da pista
        "min_pares_global": 60,   # pares para usar o fator global (todas as pistas) quando a pista tem poucos
        "janela_dias": 75,        # as duas corridas do par devem estar a ate N dias uma da outra
        "dx_min": 0.4,            # diferenca minima de distancia no par (em 100 m)
        "slope_min": -0.06,       # fator plausivel: de -6 % a +2 % de velocidade por 100 m (fora disso = ignora)
        "slope_max": 0.02,
        "recalc_s": 600,          # recalcula no maximo a cada N segundos
    },

    # ---- Overall = tempo projetado em CORPOS (sem teto artificial) ----
    "CORPO_S": 0.08,          # segundos por corpo (medido nos cards: ~0,08 a 0,09 s). CALIBRAR com overall_previsoes.csv
    # referencia do Overall: "ultimo" = vantagem sobre o galgo MAIS LENTO do campo (todos >= 0, quanto maior melhor);
    #                        "mediano" = sobre o galgo mediano (positivo e negativo); "lider" = 0 para o lider, demais negativos
    "OVERALL_REF": "ultimo",

    # ---- Encolhimento do tempo projetado para o meio do campo (galgo de historico incerto) ----
    "SHRINK": {"ativo": True, "tau_min": 0.10},   # tau_min: dispersao minima (s) de habilidade real entre os galgos do campo

    # ---- Perfil: nº minimo de corridas (de ate 5) para classificar ----
    "PERFIL_MIN": 3,

    "CONF_MIN_VENCEDOR": 40.0,

    # Penalidade por variacao de peso (s por kg acima/abaixo da media das corridas). CALIBRAR com o CSV.
    "PESO_PENALTY_KG": 0.05, "PESO_ADJ_MAX": 0.15,

    "ADJ": {"light": 0.05, "medium": 0.15, "heavy": 0.30, "saw": 0.08, "vsaw": 0.15,
            "first_bend_mult": 1.5, "cap_total": 0.60, "split_loss_cap": 0.35},
    "REC_W": [0.30, 0.25, 0.20, 0.15, 0.10],
    "CALIB_FILE": "calibracao_corridas.csv",

    "AVB": {"w_tadj": 0.45, "w_mtime": 0.35, "w_brt": 0.20, "risk_k": 0.5,
            "brt_max_dias": 90, "brt_grade_gap": 2,
            "sigma0": 0.25, "sigma_k": 2.0, "sigma_min": 0.15, "prob_scale": 1.0,
            "start_bonus": 0.04,
            "postpick_sec": 0.0,     # 0.0 = o Post Pick (palpite de tipster) NAO entra no tempo projetado
            "trap_sec": {1: -0.02, 2: -0.01, 3: 0.0, 4: 0.0, 5: 0.01, 6: 0.02},
            # ---- Regra ÚNICA de aprovação do AvB ----
            "prob_min": 62.0,        # probabilidade mínima (RECALIBRAR: o modelo mudou)
            "conf_min_v": 60.0,      # confiança mínima do galgo escolhido (V)
            "conf_min_d": 40.0,      # confiança mínima do adversário (D)
            "apoio_min": 1,          # mínimo de critérios de apoio (categoria, largada) de 2
            "exige_fator_medido": True,  # galgo com corrida convertida SEM fator de distancia medido nao entra em AvB
            # ---- Calibração logística (ativa só com amostra suficiente) ----
            "calib_min_n": 150, "calib_lambda": 5.0},
    "AVB_FILE": "avb_previsoes.csv",
    "OVERALL_FILE": "overall_previsoes.csv",
    "VERSAO": "avb-unico-4",
}

FIELD_MAP = {
    "date": ["raceTime", "raceDate", "date"], "track": ["trackName", "track"],
    "dist": ["distMetres", "distance", "dist", "raceDistance"],
    "grade": ["raceClass", "raceGrade", "grade", "raceClassDesc"],
    "trap": ["trapNum", "trap"], "split": ["sectionalTime", "split"],
    "bends": ["bndPos", "bends"], "fin": ["outcomeDesc", "fin", "finPos"],
    "by": ["distBtn", "by", "beatenDistance", "btnDist"],
    "wntm": ["winTimeS", "winTime", "wnTm", "winnerTime"],
    "gng": ["goingType", "gng", "going"], "weight": ["weight", "dogWeight", "wght"],
    "remarks": ["closeUpCmnt", "remarks"], "caltm": ["calcRTimes", "calTm", "calcTime"],
}

TRAP_EMOJI = {1: "🟥", 2: "🟦", 3: "⬜", 4: "⬛", 5: "🟧", 6: "🔳"}
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://greyhoundbet.racingpost.com/",
}

# --- Compatibilidade (podem ser importados pelo app.py) ---
RE_TRAF = re.compile(r"(awk|blk|bmp|crmp|evch|fcd|fell|ko|msdbrk|saw|stmb|struck|vsaw|crd|imp|lame)")
RE_NOFREE = re.compile(r"(awk|blk|bmp|crmp|evch|fcd|fell|ko|msdbrk|saw|stmb|struck|vsaw|crd|imp|lame|baulk)")


def pick(d, keys, default=None):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, ""):
            return d[k]
    return default


def to_float(x):
    if x is None: return None
    try:
        s = re.sub(r"[^\d.\-+]", "", str(x).strip().replace(",", "."))
        return float(s) if s not in ("", "+", "-", ".") else None
    except Exception: return None


def fin_num(x):
    m = re.search(r"\d+", str(x or ""))
    return int(m.group()) if m else None


def parse_lengths(x):
    if x in (None, ""): return None
    s = str(x).strip().lower()
    words = {"shd": 0.1, "hd": 0.2, "nk": 0.3, "dist": 30.0, "dis": 30.0}
    if s in words: return words[s]
    m = re.fullmatch(r"(\d+)?\s*(\d+)/(\d+)", s)
    if m: return float(m.group(1) or 0) + int(m.group(2)) / int(m.group(3))
    s = s.replace("¼", ".25").replace("½", ".5").replace("¾", ".75")
    try: return float(s)
    except Exception: return None


def bends_digits(b):
    return [int(c) for c in str(b or "") if c.isdigit()]


def grade_num(g):
    m = re.fullmatch(r"([ADSB])(\d{1,2})", str(g or "").strip().upper())
    return int(m.group(2)) if m else None


def is_trial_grade(g):
    return bool(re.match(r"^T\d*$", str(g or "").strip().upper()))


def parse_date(s):
    if not s: return None
    s = str(s)[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try: return datetime.strptime(s, fmt)
        except Exception: pass
    return None


def parts_of(rem):
    for tok in re.split(r"[,\s]+", str(rem or "").lower()):
        if tok:
            for p in tok.split("-"):
                if p: yield p


def count_traf(rem):
    return sum(1 for p in parts_of(rem) if RE_TRAF.search(p))


GRAVES_PATTERNS = (
    r"\bbaulk(?:ed|s|ing)?\d*\b",
    r"\bfell\d*\b",
    r"\bko\d*\b|\bknocked\s+out\b",
    r"\bmsdbrk\d*\b|\bmissed\s+break\b",
)
MODERADOS_PATTERNS = (
    r"\bbmp\d*\b|\bbumped(?:\s+first)?\b",
    r"\bcrd\d*\b|\bcrowded(?:\s+quarter)?\b",
    r"\bfcd\d*\b|\bchecked\b",
    r"\bcrmp\d*\b|\bcramped\b",
)


def traffic_penalty(rem, peso=31.0):
    s = str(rem or "").lower()
    pen = 0.0
    graves = sum(len(re.findall(p, s)) for p in GRAVES_PATTERNS)
    if graves > 0: pen += graves * 0.30
    moderados = sum(len(re.findall(p, s)) for p in MODERADOS_PATTERNS)
    if moderados > 0: pen += moderados * 0.15
    pen = min(pen, 0.50)
    if pen == 0: return 0.0
    if peso > 30.0: fator = 0.8
    elif peso < 28.0: fator = 1.2
    else: fator = 1.0
    return pen * fator


def not_free(rem):
    return bool(RE_NOFREE.search(str(rem or "").lower()))


# =====================================================================
# LEITURA DOS REMARKS
# =====================================================================
def _norm_rem_text(rem):
    s = str(rem or "").lower()
    s = re.sub(r"turned\s*in\s*tr(?:a)?ps", "turnedintrps", s)
    s = re.sub(r"dis\s*p\s*ld", "displd", s)
    s = re.sub(r"knocked\s*out", "ko", s)
    s = re.sub(r"missed\s*break", "msdbrk", s)
    s = re.sub(r"very\s*slow(?:ly)?\s*away", "vsaw", s)
    s = re.sub(r"slow(?:ly)?\s*away", "saw", s)
    s = re.sub(r"quick(?:ly)?\s*away", "qaw", s)
    s = re.sub(r"\b([a-z]+)\s+(first|second|third|fourth)\b", lambda m: m.group(1) + _ORD[m.group(2)], s)
    return s


def ler_remarks(rem):
    """Cada item: tok, key (chave oficial), num (nº da curva), status = exato | alias | aprox | desconhecido."""
    out = []
    for tok in re.split(r"[-,;/\s]+", _norm_rem_text(rem)):
        tok = tok.strip(".()[]'\"")
        if not tok: continue
        m = re.match(r"([a-z]+)(\d*)", tok)
        if not m: continue
        w, num = m.group(1), m.group(2)
        if w in REMARKS_INFO: key, st_ = w, "exato"
        elif w in REMARKS_ALIASES: key, st_ = REMARKS_ALIASES[w], "alias"
        else:
            cands = [k for k in REMARKS_INFO if len(k) >= 3 and w.startswith(k)]
            if cands: key, st_ = max(cands, key=len), "aprox"
            else: key, st_ = None, "desconhecido"
        out.append({"tok": tok, "key": key, "num": num, "status": st_})
    return out


def analisar_remarks(rem):
    """Classifica os remarks de UMA corrida: exclusão, desconto por interferência e largada lenta.
    O mesmo remark repetido na mesma curva (ex.: Bmp1 duas vezes) conta uma vez só."""
    A = CFG["ADJ"]
    excluir, interf, slow = False, 0.0, None
    vistos = set()
    for it in ler_remarks(rem):
        if not it["key"]: continue
        if (it["key"], it["num"]) in vistos: continue
        vistos.add((it["key"], it["num"]))
        adj = REMARKS_INFO[it["key"]][2]
        if adj == "exclui": excluir = True
        elif adj in ("saw", "vsaw"):
            if slow != "vsaw": slow = adj
        elif adj in ("light", "medium", "heavy"):
            base = A[adj]
            if it["num"] == "1" or it["key"] == "crdrnup": base *= A["first_bend_mult"]
            interf += base
    return {"excluir": excluir, "interf": interf, "slow": slow, "limpa": (not excluir and interf == 0 and slow is None)}


def traducao_remarks(rem):
    return [REMARKS_INFO[it["key"]][0] for it in ler_remarks(rem) if it["key"]]


def diagnostico_remarks(dogs):
    cont = {"exato": 0, "alias": 0, "aprox": 0, "desconhecido": 0}
    aprox, desc = {}, {}
    for d in dogs:
        for r in d.get("runs", []):
            for it in ler_remarks(r.get("remarks")):
                cont[it["status"]] += 1
                if it["status"] in ("alias", "aprox"): aprox[it["tok"]] = it["key"]
                if it["status"] == "desconhecido": desc[it["tok"]] = desc.get(it["tok"], 0) + 1
    return cont, aprox, desc


# =====================================================================
# FATOR DE DISTANCIA (velocidade por 100 m), MEDIDO NOS PROPRIOS DADOS
# =====================================================================
_SLOPE_CACHE = {"t": 0.0, "mtime": None, "val": {"por_pista": {}, "global": None}}


def _ajustar_slope(lst):
    """Regressao pela origem de ln(v2/v1) sobre a diferenca de distancia (em 100 m). Retorna dict ou None."""
    if not lst: return None
    x = np.array([a for a, _ in lst], dtype=float)
    y = np.array([b for _, b in lst], dtype=float)
    den = float(np.sum(x * x))
    if den <= 0: return None
    b = float(np.sum(x * y) / den)
    return {"b": b, "n": int(len(lst)), "sd": float(np.std(y - b * x))}


def _slopes_dist(forcar=False):
    """{'por_pista': {pista: {b, n, sd}}, 'global': {b, n, sd} | None}.
    Pares: mesmo galgo, mesma pista, duas distancias diferentes, ate `janela_dias` de intervalo, so corridas limpas."""
    F = CFG["FATOR_DIST"]
    c = _SLOPE_CACHE
    path = CFG["CALIB_FILE"]
    if not os.path.exists(path): return c["val"]
    mt = os.path.getmtime(path)
    if not forcar:
        if c["mtime"] == mt: return c["val"]
        if c["mtime"] is not None and (time.time() - c["t"]) < F["recalc_s"]:
            return c["val"]
    vazio = {"por_pista": {}, "global": None}
    try:
        df = pd.read_csv(path, usecols=["pista", "data", "dist", "galgo", "caltm", "remarks"])
        df["caltm"] = pd.to_numeric(df["caltm"], errors="coerce")
        df["dist"] = pd.to_numeric(df["dist"], errors="coerce")
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        df = df[(df["caltm"] > 0) & df["dist"].notna() & df["data"].notna()]
        df = df.drop_duplicates(subset=["galgo", "pista", "data", "dist", "caltm"])
        df = df[df["remarks"].fillna("").map(lambda s: analisar_remarks(s)["limpa"])]
        df = df.assign(v=df["dist"] / df["caltm"])
        pares = {}
        for (g, p), grp in df.groupby(["galgo", "pista"]):
            if len(grp) < 2: continue
            grp = grp.sort_values("data")
            datas, dists, vs = grp["data"].tolist(), grp["dist"].tolist(), grp["v"].tolist()
            n = len(grp)
            for i in range(n):
                for j in range(i + 1, n):
                    if (datas[j] - datas[i]).days > F["janela_dias"]: break
                    dx = (dists[j] - dists[i]) / 100.0
                    if abs(dx) < F["dx_min"]: continue
                    pares.setdefault(p, []).append((dx, math.log(vs[j] / vs[i])))
        por_pista = {}
        for p, lst in pares.items():
            a = _ajustar_slope(lst)
            if a and a["n"] >= F["min_pares_pista"] and F["slope_min"] <= a["b"] <= F["slope_max"]:
                por_pista[p] = a
        tudo = [t for lst in pares.values() for t in lst]
        g = _ajustar_slope(tudo)
        glob = g if (g and g["n"] >= F["min_pares_global"] and F["slope_min"] <= g["b"] <= F["slope_max"]) else None
        val = {"por_pista": por_pista, "global": glob, "pares_total": len(tudo),
               "pares_pista": {p: len(l) for p, l in pares.items()}}
    except Exception:
        val = vazio
    c["t"], c["mtime"], c["val"] = time.time(), mt, val
    return val


def _slope_para(track):
    """Fator (variacao relativa de velocidade por 100 m) para a pista, ou None se nao houver dado suficiente."""
    v = _slopes_dist()
    a = v["por_pista"].get(str(track))
    if a: return a["b"]
    g = v.get("global")
    return g["b"] if g else None


def _conv_tempo(t, r_dist, D, b):
    """Converte o tempo `t` feito em `r_dist` metros para o tempo equivalente em D metros.
    b = None -> velocidade igual (proporcional). b != None -> v(D) = v(r) * exp(b * (D - r)/100)."""
    v = r_dist / t
    if b: v *= math.exp(b * (D - r_dist) / 100.0)
    return D / v


def resumo_fator_dist():
    """Para exibir na tela: fatores medidos por pista e quantidade de pares."""
    v = _slopes_dist()
    linhas = []
    for p, a in sorted(v["por_pista"].items()):
        linhas.append({"Pista": p, "Fator (%/100m)": round(100 * (math.exp(a["b"]) - 1), 2), "Pares": a["n"], "Origem": "medido na pista"})
    g = v.get("global")
    if g:
        linhas.append({"Pista": "(global)", "Fator (%/100m)": round(100 * (math.exp(g["b"]) - 1), 2), "Pares": g["n"], "Origem": "todas as pistas"})
    return linhas, v.get("pares_pista", {}), v.get("pares_total", 0)


# =====================================================================
# TEMPO POR VELOCIDADE (janela de distancia)
# =====================================================================
def _dist_na_janela(r, ctx):
    return r.get("dist") is not None and abs(r["dist"] - ctx["dist"]) <= CFG["JANELA_M"]


def _conf_dados(R, ctx):
    """Confianca: cada corrida vale 20 pontos x peso da distancia (1,0 na exata ... CONF_PESO_MIN na ponta da janela)."""
    J, pmin = CFG["JANELA_M"], CFG["CONF_PESO_MIN"]
    tot = 0.0
    for r in R:
        delta = abs(r["dist"] - ctx["dist"])
        tot += 1.0 - (1.0 - pmin) * min(delta / J, 1.0)
    return min(100.0, tot * 20.0)


def tempo_limpo(R, ctx):
    """(tadj, n_excluidas, desconto_medio_s): velocidade media ponderada por recencia, depois de descontar
    interferencia e largada lenta (em segundos, na propria corrida), convertida para a distancia de hoje
    (com o fator de distancia medido quando existir).
    Nunca fica mais rapido que o melhor tempo equivalente real - 0,05 s."""
    A = CFG["ADJ"]
    D = ctx["dist"]
    info = [(r, analisar_remarks(r["remarks"])) for r in R if r.get("caltm") and r["caltm"] > 0 and r.get("dist")]
    usar = [(r, i) for r, i in info if not i["excluir"]] or info
    if not usar: return None, 0, 0.0

    def ref_split(r):
        # largada lenta: referencia = mediana dos splits LIMPOS da mesma pista e distancia (splits de distancias diferentes nao se comparam)
        limpos = [x["split"] for x, i in usar
                  if i["limpa"] and x.get("split") and x["split"] > 0 and x["dist"] == r["dist"] and x["track"] == r["track"]]
        return float(np.median(limpos)) if limpos else None

    vals, descs, brutos = [], [], []
    for r, i in usar:
        loss = 0.0
        if i["slow"]:
            rs = ref_split(r)
            if rs is not None and r.get("split") and r["split"] > 0:
                loss = min(max(r["split"] - rs, 0.0), A["split_loss_cap"])
            else:
                loss = A[i["slow"]]
        desc = min(i["interf"] + loss, A["cap_total"])
        b = _slope_para(r["track"]) if abs(r["dist"] - D) >= 1 else None
        bruto = _conv_tempo(r["caltm"], r["dist"], D, b)
        limpo = _conv_tempo(max(r["caltm"] - desc, 0.5), r["dist"], D, b)
        brutos.append(bruto)
        vals.append(limpo)
        descs.append(bruto - limpo)
    piso = min(brutos) - 0.05
    vals = [max(v, piso) for v in vals]
    w = np.array(CFG["REC_W"][:len(vals)] + [CFG["REC_W"][-1]] * max(0, len(vals) - len(CFG["REC_W"])), dtype=float)
    w = w / w.sum()
    v_med = float(np.dot(w, [D / t for t in vals]))
    return D / v_med, (len(info) - len(usar) if len(usar) != len(info) else 0), float(np.mean(descs))


# =====================================================================
# EXTRAÇÃO DE DADOS DO RACING POST
# =====================================================================
HINTS = {
    "dist": (("dist", "metre", "meter"), ("btn", "beat", "by")),
    "grade": (("class", "grade"), ()), "by": (("btn", "beaten"), ()),
    "wntm": (("win", "time"), ()),
}


def pick_fb(f, k):
    v = pick(f, FIELD_MAP[k])
    if v is not None or k not in HINTS: return v
    inc, exc = HINTS[k]
    for key, val in f.items():
        kl = str(key).lower()
        ok = all(x in kl for x in inc) if k == "wntm" else any(x in kl for x in inc)
        if ok and not any(x in kl for x in exc) and val not in (None, ""):
            return val
    return None


def norm_run(f):
    g = lambda k: pick_fb(f, k)
    return {
        "date": parse_date(g("date")), "date_str": str(g("date") or "")[:10],
        "track": str(g("track") or ""), "dist": to_float(g("dist")),
        "grade": str(g("grade") or "").strip().upper(), "trap": fin_num(g("trap")),
        "split": to_float(g("split")), "bends": str(g("bends") or ""),
        "fin": fin_num(g("fin")), "by": parse_lengths(g("by")),
        "wntm": to_float(g("wntm")), "gng": g("gng"),
        "weight": to_float(g("weight")), "remarks": str(g("remarks") or ""),
        "caltm": to_float(g("caltm")),
    }


GRADE_RE = re.compile(r"^(A\d{1,2}|T\d?|HP|OR|IT|S\d|D\d|B\d|ON\d)$")


def descobrir_chaves(dogs):
    vals = {}
    for dog in dogs:
        for f in dog.get("forms", []):
            for k, v in f.items():
                if isinstance(v, (str, int, float)) and v not in ("", None):
                    vals.setdefault(k, []).append(v)
    for k, vs in vals.items():
        kl = str(k).lower()
        if any(x in kl for x in ("btn", "beat", "weight", "time", "id")): continue
        nums = [to_float(v) for v in vs]
        if all(n is not None and 150 <= n <= 900 for n in nums) and len(set(nums)) <= 6:
            if k not in FIELD_MAP["dist"]: FIELD_MAP["dist"].insert(0, k)
            break
    for k, vs in vals.items():
        if sum(1 for v in vs if GRADE_RE.match(str(v).strip().upper())) >= 0.8 * len(vs):
            if k not in FIELD_MAP["grade"]: FIELD_MAP["grade"].insert(0, k)
            break


def extrair_metadados_json(data, info_card, dogs):
    info = {"pista": "", "hora": "", "race": "", "classe": "", "post_pick": "", "going": "NORMAL", "dist": 0.0}
    fontes = [info_card] if isinstance(info_card, dict) else []
    for src in [data]:
        if isinstance(src, dict):
            fontes.append(src)
            if isinstance(src.get("race"), dict): fontes.append(src["race"])
            if isinstance(src.get("form"), dict):
                fontes.append(src["form"])
                if isinstance(src["form"].get("race"), dict): fontes.append(src["form"]["race"])
    for src in fontes:
        pista = pick(src, ["trackName", "track", "meetingName", "courseName"])
        if pista: info["pista"] = str(pista).strip(); break
    if not info["pista"] and dogs and dogs[0].get("runs"):
        info["pista"] = str(dogs[0]["runs"][0].get("track", "Desconhecida")).strip()
    for src in fontes:
        for k in ["offTime", "scheduledTime", "displayTime", "time", "raceTime"]:
            val = src.get(k)
            if val:
                m = re.search(r"\b([1-9]|1[0-2]):\d{2}\b", str(val))
                if m: info["hora"] = m.group(0); break
        if info["hora"]: break
    for src in fontes:
        r_num = pick(src, ["raceNum", "raceNumber", "rNum", "raceNumberDesc", "number"])
        if r_num is not None:
            info["race"] = str(r_num).replace("Race", "").strip(); break
    for src in fontes:
        grade = pick(src, ["raceClass", "grade", "class", "raceClassDesc", "raceGrade"])
        if grade: info["classe"] = str(grade).strip().upper(); break
    if not info["classe"] and dogs and dogs[0].get("runs"):
        info["classe"] = str(dogs[0]["runs"][0].get("grade", "")).strip().upper()
    for src in fontes:
        pp = pick(src, ["postPick", "post_pick", "tips", "tip"])
        if pp:
            m = re.search(r"\b([1-6][-/.][1-6][-/.][1-6])\b", str(pp))
            if m:
                info["post_pick"] = m.group(1).strip().replace("/", "-").replace(".", "-"); break
            elif re.search(r"[1-6]", str(pp)):
                info["post_pick"] = str(pp).strip().replace("/", "-").replace(".", "-"); break
    for src in fontes:
        gng = pick(src, ["going", "goingType", "gng"])
        if gng: info["going"] = str(gng).strip().upper(); break
    # distancia da prova lida do proprio card (evita adivinhar pela moda das corridas dos galgos)
    for src in fontes:
        dv = to_float(pick(src, ["distMetres", "distMeters", "distance", "dist", "raceDistance"]))
        if dv and 100 <= dv <= 1000:
            info["dist"] = float(dv); break
    return info


def extrair_dados_racingpost(url):
    try:
        if not url.startswith("http"):
            url = "https://greyhoundbet.racingpost.com/" + url
        race_id_match = re.search(r"race_id=(\d+)", url)
        r_date_match = re.search(r"r_date=([\d-]+)", url)
        if not race_id_match or not r_date_match:
            st.error("Não foi possível extrair o ID da corrida do link.")
            return None, None, None
        race_id, r_date_str = race_id_match.group(1), r_date_match.group(1)
        card_api_url = f"https://greyhoundbet.racingpost.com/card/race.sd?race_id={race_id}&r_date={r_date_str}"
        info_card = {}
        try:
            resp_card = requests.get(card_api_url, headers=HEADERS, timeout=10)
            if resp_card.status_code == 200:
                info_card = resp_card.json()
        except Exception: pass
        api_url = f"https://greyhoundbet.racingpost.com/card/blocks.sd?race_id={race_id}&r_date={r_date_str}&blocks=form"
        resp = requests.get(api_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        dogs = data.get("form", {}).get("dogs", [])
        if not dogs:
            st.warning("Nenhum dado encontrado para esta corrida.")
            return None, None, None
        descobrir_chaves(dogs)
        out = []
        for dog in dogs:
            trap = fin_num(dog.get("trapNum"))
            runs = [norm_run(f) for f in dog.get("forms", [])]
            out.append({
                "name": dog.get("dogName", "Desconhecido"),
                "trap": trap or 0, "peso_atual": to_float(dog.get("weight")), "runs": runs, "brt": extrair_brt(dog), "brt_txt": extrair_brt_txt(dog),
            })
        existing_traps = {d["trap"] for d in out}
        for t in range(1, 7):
            if t not in existing_traps:
                out.append({"name": "vacant", "trap": t, "peso_atual": None, "runs": []})
        out.sort(key=lambda x: x["trap"])
        meta_info = extrair_metadados_json(data, info_card, out)
        return out, {"r_date": r_date_str, "raw_first": dogs[0]}, meta_info
    except Exception as e:
        st.error(f"Erro ao extrair dados: {e}")
        return None, None, None


_BRT_KEYS = ("brt", "bestTime", "bestRTime", "bestTm", "bestTimeS", "bestRaceTime", "bestCalTime", "bestRaceTm")


def extrair_brt(dog):
    def _num(v):
        m = re.search(r"\b(\d{2}\.\d{2})\b", str(v))
        return float(m.group(1)) if m else None
    for k in _BRT_KEYS:
        if k in dog and dog[k] not in (None, ""):
            n = _num(dog[k])
            if n: return n
    for k, v in dog.items():
        kl = str(k).lower()
        if ("brt" in kl or "best" in kl) and isinstance(v, (str, int, float)):
            n = _num(v)
            if n: return n
    return None


_MESES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_RE_BRT_FULL = re.compile(r"(\d{2}\.\d{2})\s*([A-Za-z]{1,2}\d{0,2})?\s*\(?(\d{1,2}[A-Za-z]{3}\d{2})\)?")


def _fmt_data_brt(v):
    v = str(v or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", v)
    if m: return f"{int(m.group(3))}{_MESES[int(m.group(2)) - 1]}{m.group(1)[2:]}"
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", v)
    if m: return f"{int(m.group(1))}{_MESES[int(m.group(2)) - 1]}{m.group(3)[-2:]}"
    m = re.search(r"\d{1,2}[A-Za-z]{3}\d{2}", v)
    return m.group(0) if m else ""


def extrair_brt_txt(dog):
    """Texto do BRT como no card: 'BRT: 27.39 A7 (1Aug26)'. Vazio se não achar."""
    def varre(obj, depth=0):
        if isinstance(obj, dict):
            for v in obj.values():
                r = varre(v, depth + 1)
                if r: return r
        elif isinstance(obj, (list, tuple)) and depth < 2:
            for v in obj[:6]:
                r = varre(v, depth + 1)
                if r: return r
        elif isinstance(obj, str):
            m = _RE_BRT_FULL.search(obj)
            if m: return m
        return None
    dog_sem_forms = {k: v for k, v in dog.items() if k != "forms"}
    m = varre(dog_sem_forms)
    if m:
        t, g, dt = m.group(1), (m.group(2) or "").upper(), m.group(3)
        return f"BRT: {t}" + (f" {g}" if g else "") + f" ({dt})"
    brt = extrair_brt(dog)
    if not brt: return ""
    dt = ""
    for k, v in dog.items():
        kl = str(k).lower()
        if ("brt" in kl or "best" in kl) and ("date" in kl or kl.endswith("dt")):
            dt = _fmt_data_brt(v)
            if dt: break
    return f"BRT: {brt:.2f}" + (f" ({dt})" if dt else "")


# =====================================================================
# ANÁLISE DE CADA GALGO
# =====================================================================
def oficial(r, ctx):
    """Corrida valida: distancia dentro da janela (+-JANELA_M), com CalTm. Trials contam; so HP fica de fora."""
    g = str(r["grade"] or "").strip().upper()
    if g.startswith("HP"):
        return False
    return (_dist_na_janela(r, ctx)
            and r["caltm"] is not None and r["caltm"] > 0)


def analisar_galgo(dog, ctx):
    if dog.get("name") == "vacant":
        return {"name": "vacant", "trap": dog["trap"], "runs": [], "val": [], "nd": True,
                "conf": 0.0, "bloqueado": False, "alvo": False, "pos": 0, "elegivel": False,
                "alerta_trial": False, "n_trials": 0, "n_val": 0, "p_vit": None, "conv_ok": True}

    D = ctx["dist"]
    todas = sorted(dog["runs"], key=lambda r: r["date"] or datetime.min, reverse=True)
    runs = todas[:CFG["N_RUNS"]]  # só para Dias, trials e calibração
    n_trials = sum(1 for r in runs if is_trial_grade(r["grade"]))

    # Filtro único: oficiais (janela de distância, sem HP) -> sem quedas/manca -> 5 mais recentes
    oficiais = [r for r in todas if oficial(r, ctx)]
    validas = [r for r in oficiais if not analisar_remarks(r["remarks"])["excluir"]]
    R = (validas or oficiais)[:CFG["N_RUNS"]]

    d = {"name": dog["name"], "trap": dog["trap"], "runs": runs, "val": R, "nd": not R, "n_val": len(R),
         "conf": _conf_dados(R, ctx) if R else 0.0, "bloqueado": False, "alvo": False, "pos": 0, "elegivel": False,
         "alerta_trial": n_trials >= 3, "n_trials": n_trials, "p_vit": None, "dist_alvo": D, "conv_ok": True}

    d["brt_raw"] = dog.get("brt")
    d["brt_txt"] = dog.get("brt_txt")
    ultima_any = todas[0] if todas else None
    d["dias"] = (ctx["today"] - ultima_any["date"]).days if ultima_any and ultima_any["date"] else 0
    if d["dias"] > 21: d["conf"] *= 0.8  # parado há muito tempo = menos confiável

    if not R: return d

    # --- Categoria: classe de hoje vs. classe média das corridas válidas (contínuo, limitado a ±CAT_BONUS) ---
    today_n = ctx.get("classe_n")
    valid_grades = [grade_num(r["grade"]) for r in R if grade_num(r["grade"]) is not None]
    avg_grade_n = sum(valid_grades) / len(valid_grades) if valid_grades else (today_n or 0)
    if today_n and valid_grades:
        mod = max(-CFG["CAT_BONUS"], min(CFG["CAT_BONUS"], today_n - avg_grade_n))
    else:
        mod = 0.0
    base = 13.0 - (avg_grade_n * 0.6)
    d["cat_mod"], d["cat"] = mod, base + mod

    d["peso"] = dog.get("peso_atual") or R[0]["weight"]  # None se não houver (a tabela mostra "-")

    # --- Tempo equivalente na distância de hoje (fator de distância medido quando existir) ---
    bs = [(_slope_para(r["track"]) if abs(r["dist"] - D) >= 1 else None) for r in R]
    teqs = [_conv_tempo(r["caltm"], r["dist"], D, b) for r, b in zip(R, bs)]
    vs_D = [D / t for t in teqs]
    d["mtime"] = D / float(np.mean(vs_D))          # Média Time: velocidade média (na distância de hoje)
    d["pico"] = min(teqs)                           # melhor tempo equivalente
    d["time"] = d["pico"]                           # coluna "M. Time"
    d["sd"] = float(np.std(teqs)) if len(teqs) > 1 else None

    # Corridas convertidas: quantas, e quantas SEM fator medido (só proporção)
    conv = [(r, b) for r, b in zip(R, bs) if abs(r["dist"] - D) >= 1]
    d["n_conv"] = len(conv)
    d["n_conv_sem_fator"] = sum(1 for r, b in conv if b is None)
    d["conv_ok"] = (d["n_conv_sem_fator"] == 0)
    # incerteza extra por diferença de distância (entra na variância do tempo projetado)
    sd_m, sd_s = CFG["DIST_SD_100M_MEDIDO"], CFG["DIST_SD_100M_SEM_FATOR"]
    d["dist_var"] = float(np.mean([((sd_m if b is not None else sd_s) * abs(r["dist"] - D) / 100.0) ** 2
                                   for r, b in zip(R, bs)]))

    # --- Split: SÓ corridas na distância exata; sem dado = neutro ---
    exatos = [r["split"] for r in R if abs(r["dist"] - D) < 1 and r.get("split") is not None and r["split"] > 0]
    d["msplit"] = float(np.mean(exatos)) if exatos else None
    d["split"] = min(exatos) if exatos else None
    d["n_split"] = len(exatos)

    # BRT: mesmo validador do AvB (recente e de classe próxima) + sanidade de 3s contra o tempo médio
    d["brt"] = dog.get("brt")
    d["brt"] = _brt_valido(d, ctx)
    if d["brt"] and d["mtime"] and abs(d["brt"] - d["mtime"]) > 3.0:
        d["brt"] = None

    d["tadj"], d["tadj_excl"], d["tadj_desc"] = tempo_limpo(R, ctx)
    d["tadj_excl"] = len(oficiais) - len(validas)

    d["metrica"] = ((d["brt"] + d["tadj"] + d["mtime"]) / 3.0
                    if d.get("brt") and d["tadj"] is not None and d["mtime"] is not None else None)

    # Recuperação: só corridas sem interferência
    recs = []
    for r in R:
        b = bends_digits(r["bends"])
        if b and r["fin"] and analisar_remarks(r["remarks"])["interf"] == 0:
            recs.append((b[0] - r["fin"]) / CFG["N_CORREDORES"] * 100.0)
    if recs:
        d["rec"] = float(np.mean(recs))
        d["rec_txt"] = f"{d['rec']:+.2f}% ({'Ganhou' if d['rec'] > 0.005 else ('Perdeu' if d['rec'] < -0.005 else 'Manteve')})"
    else:
        d["rec"] = None
        d["rec_txt"] = "-"

    # Perfil: 3+ corridas limpas = Limpo; 3+ com bloqueio/toque/trombada = Trombador; senão Irregular
    interf = [analisar_remarks(r["remarks"])["interf"] for r in R]
    d["n_traf"] = sum(1 for x in interf if x > 0)
    d["n_limpas"] = sum(1 for x in interf if x == 0)
    P = CFG["PERFIL_MIN"]
    d["perfil"] = "Limpo" if d["n_limpas"] >= P else ("Trombador" if d["n_traf"] >= P else "Irregular")

    d["remarks_translated"] = []
    for r in R:
        d["remarks_translated"].extend(traducao_remarks(r["remarks"]))

    # Ajuste por variação de peso (limitado a ±PESO_ADJ_MAX segundos)
    pesos_hist = [r["weight"] for r in R if r.get("weight") is not None and r["weight"] > 0]
    if pesos_hist and d["peso"]:
        adj = (d["peso"] - float(np.mean(pesos_hist))) * CFG["PESO_PENALTY_KG"]
        d["peso_adj"] = float(max(-CFG["PESO_ADJ_MAX"], min(CFG["PESO_ADJ_MAX"], adj)))
    else:
        d["peso_adj"] = 0.0

    return d


# =====================================================================
# CALIBRAÇÃO DOS REMARKS (CSV de corridas)
# =====================================================================
_CALIB_COLS = ["registrado_em", "pista", "data", "dist", "galgo", "trap", "grade", "caltm", "split", "bends", "fin", "remarks", "peso", "brt"]


def registrar_calibracao(ds):
    path = CFG["CALIB_FILE"]
    vistos = set()
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                vistos.add((row["galgo"], row["data"], row["pista"], row["dist"], row["caltm"]))
    novas = []
    for d in ds:
        if d.get("name") in (None, "vacant"): continue
        for r in d.get("runs", []):
            if r.get("caltm") is None or r["caltm"] <= 0: continue
            chave = (d["name"], r["date_str"], r["track"], str(r["dist"]), str(r["caltm"]))
            if chave in vistos: continue
            vistos.add(chave)
            novas.append([datetime.now().strftime("%Y-%m-%d %H:%M"), r["track"], r["date_str"], r["dist"], d["name"], r["trap"], r["grade"],
                          r["caltm"], r["split"], r["bends"], r["fin"], r["remarks"], r["weight"], d.get("brt_raw")])
    if not novas: return 0
    novo_arquivo = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if novo_arquivo: w.writerow(_CALIB_COLS)
        w.writerows(novas)
    return len(novas)


def calibracao_bytes():
    path = CFG["CALIB_FILE"]
    if not os.path.exists(path): return None
    with open(path, "rb") as f: return f.read()


def analisar_calibracao(path=None, min_n=5):
    """Perda média REAL (s) por remark: CalTm com o remark menos a média das corridas limpas do mesmo galgo/pista/distância."""
    df = pd.read_csv(path or CFG["CALIB_FILE"])
    df = df[(df["caltm"] > 0)].copy()
    df["info"] = df["remarks"].fillna("").map(analisar_remarks)
    df["limpa"] = df["info"].map(lambda i: i["limpa"])
    base = df[df["limpa"]].groupby(["galgo", "pista", "dist"])["caltm"].mean().rename("base")
    df = df.join(base, on=["galgo", "pista", "dist"]).dropna(subset=["base"])
    df = df[~df["limpa"]]
    df["delta"] = df["caltm"] - df["base"]
    linhas = []
    for _, r in df.iterrows():
        for key in {it["key"] for it in ler_remarks(r["remarks"]) if it["key"] and REMARKS_INFO[it["key"]][2]}:
            linhas.append((key, r["delta"]))
    if not linhas: return pd.DataFrame(columns=["remark", "n", "perda_media_s"])
    out = pd.DataFrame(linhas, columns=["remark", "delta"]).groupby("remark")["delta"].agg(["count", "mean"]).reset_index()
    out.columns = ["remark", "n", "perda_media_s"]
    return out[out["n"] >= min_n].sort_values("perda_media_s", ascending=False)


# =====================================================================
# OVERALL (TEMPO PROJETADO EM CORPOS) / RANKING
# =====================================================================
def _ref_nome():
    return {"ultimo": "o galgo mais lento do campo", "lider": "o líder", "mediano": "o galgo mediano"}.get(CFG["OVERALL_REF"], "o galgo mediano")


def _fmt_ov(x):
    """Overall para exibir: sem sinal quando a referencia e o galgo mais lento (valores >= 0)."""
    return f"{x:.1f}" if CFG["OVERALL_REF"] == "ultimo" else f"{x:+.1f}"


def _ref_vals(vals):
    modo = CFG["OVERALL_REF"]
    if modo == "ultimo": return float(max(vals))
    if modo == "lider": return float(min(vals))
    return float(np.median(vals))


def calcular_overall(ok, ctx):
    """Overall = (tempo projetado de referencia - tempo projetado do galgo) / CORPO_S, em CORPOS.
    Referencia (CFG["OVERALL_REF"]): "ultimo" (galgo mais lento, Overall >= 0), "mediano" ou "lider".
    Usa o MESMO tempo projetado (ja encolhido) do AvB e do Predictor. Sem reescala.
    Componentes (em corpos): tempo base (Time Ajust./Media Time/BRT), peso, trap, largada e Post Pick."""
    cs = CFG["CORPO_S"]
    zero = {"tempo": 0.0, "peso": 0.0, "trap": 0.0, "largada": 0.0, "postpick": 0.0}
    for d in ok:
        t, var = projetar_tempo(d, ctx)
        d["t_sd"] = math.sqrt(var) if var else None
    com = [d for d in ok if d.get("t_proj") is not None]
    if not com:
        for d in ok:
            d["overall"] = 0.0
            d["ovr_comp"] = dict(zero)
        return
    ref = _ref_vals([d["t_proj"] for d in com])
    ref_base = _ref_vals([d["t_base"] for d in com])
    for d in ok:
        if d.get("t_proj") is None:
            d["overall"] = 0.0
            d["ovr_comp"] = dict(zero)
            continue
        c = d["t_comp"]
        d["overall"] = (ref - d["t_proj"]) / cs
        d["ovr_comp"] = {"tempo": (ref_base - d["t_base"]) / cs, "peso": -c["peso"] / cs, "trap": -c["trap"] / cs,
                         "largada": -c["largada"] / cs, "postpick": -c["postpick"] / cs}


def _calcular_shrink(ok, ctx):
    """Parametros do encolhimento: centro (mediana dos tempos base) e dispersao real de habilidade no campo (tau2).
    tau2 = variancia observada dos tempos base - media da incerteza de cada galgo (minimo tau_min^2)."""
    ctx.pop("_shrink", None)
    S = CFG["SHRINK"]
    if not S.get("ativo"): return
    raws = [r for r in (_base_raw(d, ctx) for d in ok) if r is not None]
    if len(raws) < 3: return
    tb = np.array([r[0] for r in raws]); ve = np.array([r[2] for r in raws])
    obs = float(np.var(tb, ddof=1))
    tau2 = max(obs - float(np.mean(ve)), S["tau_min"] ** 2)
    ctx["_shrink"] = {"ref": float(np.median(tb)), "tau2": tau2}


def finalizar(ds, ctx):
    try: registrar_calibracao(ds)
    except Exception: pass
    ok = [d for d in ds if not d["nd"]]

    ms_rank = sorted([d for d in ok if d.get("msplit") is not None], key=lambda x: x["msplit"])
    top3_ms = {d["name"] for d in ms_rank[:3]}
    top_split_name = ms_rank[0]["name"] if ms_rank else None
    ctx["top3_ms"] = top3_ms

    _calcular_shrink(ok, ctx)
    calcular_overall(ok, ctx)
    ok.sort(key=lambda x: (-x["overall"], -x.get("cat", 0.0)))
    for i, d in enumerate(ok, 1):
        d["pos"] = i
        d["bloqueado"] = d["conf"] < CFG["CONF_MIN_VENCEDOR"]
        rec = d.get("rec")
        top2_safe = (i <= 2) and (rec is not None and rec >= -10.0)
        # Alvo: sem split não entra (galgo sem split na distância exata não é "sem largada", é sem dado)
        d["alvo"] = (d.get("msplit") is not None and d["name"] not in top3_ms and d["name"] != top_split_name
                     and rec is not None and rec < -10.0 and not top2_safe)
        d["elegivel"] = not d["bloqueado"]

    try: calcular_prob_vitoria(ok, ctx)
    except Exception: pass
    try: registrar_overall(ok, ctx)
    except Exception: pass
    return ok, top3_ms


# =====================================================================
# PROJEÇÃO DE TEMPO E PROBABILIDADE DO AVB
# =====================================================================
def _brt_valido(d, ctx):
    """BRT só entra se for recente e de classe próxima da corrida de hoje."""
    A = CFG["AVB"]
    brt = d.get("brt")
    if not brt: return None
    txt = str(d.get("brt_txt") or "")
    m = re.search(r"\((\d{1,2}[A-Za-z]{3}\d{2})\)", txt)
    hoje = ctx.get("today")
    if m and hoje:
        try:
            dt = datetime.strptime(m.group(1), "%d%b%y")
            if (hoje - dt).days > A["brt_max_dias"]: return None
        except Exception: pass
    g = re.search(r"BRT:\s*\d+\.\d+\s*([A-Za-z]\d+)", txt)
    gn, cn = (grade_num(g.group(1).upper()) if g else None), ctx.get("classe_n")
    if gn and cn and abs(gn - cn) > A["brt_grade_gap"]: return None
    return brt


def _base_raw(d, ctx):
    """(t_base, var_dog, var_est) SEM encolhimento, ou None.
    t_base = mistura Time Ajust./Media Time/BRT; var_dog = variancia de uma corrida do galgo (dia de prova);
    var_est = incerteza sobre a media dele (poucas corridas + diferenca de distancia)."""
    A = CFG["AVB"]
    partes = []
    if d.get("tadj") is not None: partes.append((A["w_tadj"], d["tadj"] + A["risk_k"] * (d.get("tadj_desc") or 0.0)))
    if d.get("mtime") is not None: partes.append((A["w_mtime"], d["mtime"]))
    brt = _brt_valido(d, ctx)
    if brt: partes.append((A["w_brt"], brt))
    if not partes: return None
    t_base = sum(w * x for w, x in partes) / sum(w for w, _ in partes)
    n = max(d.get("n_val") or len(d.get("val") or []), 1)
    sd = d.get("sd") or 0.0
    var_dog = (n * sd ** 2 + A["sigma_k"] * A["sigma0"] ** 2) / (n + A["sigma_k"])  # encolhe o desvio para o padrão
    var_dog = max(var_dog, A["sigma_min"] ** 2)
    var_est = var_dog / n + d.get("dist_var", 0.0)
    return t_base, var_dog, var_est


def projetar_tempo(d, ctx):
    """(tempo projetado em s, variância em s²) ou (None, None).
    Com ctx["_shrink"] (calculado em finalizar), o tempo base é puxado para o centro do campo na proporção da incerteza
    do galgo: k = tau2 / (tau2 + var_est). Galgo bem conhecido (k ~ 1) fica como está; galgo incerto (k baixo) vira "mediano".
    Grava d["t_base"] (já encolhido), d["t_base_raw"], d["shrink_k"] e d["t_comp"] (ajustes em s; positivo = mais lento)."""
    A = CFG["AVB"]
    r = _base_raw(d, ctx)
    if r is None: return None, None
    t_raw, var_dog, var_est = r
    k = 1.0
    sh = ctx.get("_shrink")
    if sh:
        k = sh["tau2"] / (sh["tau2"] + var_est)
        t_base = sh["ref"] + k * (t_raw - sh["ref"])
    else:
        t_base = t_raw
    peso = d.get("peso_adj", 0.0)
    trap = A["trap_sec"].get(d["trap"], 0.0)
    largada = -A["start_bonus"] if d["name"] in ctx.get("top3_ms", set()) else 0.0
    pp = str(ctx.get("post_pick") or "")
    postpick = -A["postpick_sec"] if (pp and str(d["trap"]) in pp) else 0.0
    t = t_base + peso + trap + largada + postpick
    var = var_dog + k * var_est  # variancia preditiva: ruido da prova + incerteza residual sobre a habilidade (posterior)
    d["t_proj"], d["t_base"], d["t_base_raw"], d["shrink_k"] = t, t_base, t_raw, k
    d["t_comp"] = {"peso": peso, "trap": trap, "largada": largada, "postpick": postpick}
    return t, var


def _dif_proj(V, D, ctx):
    tV, vV = projetar_tempo(V, ctx); tD, vD = projetar_tempo(D, ctx)
    if tV is None or tD is None: return None
    return tD - tV, math.sqrt(vV + vD), tV, tD


def calc_prob(V, D, rank, ctx):
    """P(V vencer D) BRUTA (%), pela diferença de tempo projetado (s) dividida pela incerteza combinada."""
    r = _dif_proj(V, D, ctx)
    if r is None: return 50.0
    delta, sd_tot, _, _ = r
    z = CFG["AVB"]["prob_scale"] * delta / sd_tot
    return 100.0 * 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def calcular_prob_vitoria(rank, ctx, n_sim=6000):
    """Probabilidade (%) de cada galgo vencer a corrida: simula o tempo de cada um como Normal(tempo projetado, variância)
    e conta quantas vezes cada um fica com o menor tempo. Usa o MESMO tempo projetado do AvB. Grava d["p_vit"]."""
    pares = []
    for d in rank:
        d["p_vit"] = None
        t, var = projetar_tempo(d, ctx)
        if t is not None: pares.append((d, t, math.sqrt(var)))
    if len(pares) < 2: return
    rng = np.random.default_rng(12345)
    T = np.array([p[1] for p in pares]); S = np.array([p[2] for p in pares])
    sims = T[None, :] + S[None, :] * rng.standard_normal((n_sim, len(pares)))
    win = np.bincount(np.argmin(sims, axis=1), minlength=len(pares)) / float(n_sim) * 100.0
    for (d, _, _), w in zip(pares, win):
        d["p_vit"] = float(w)


# ---------------------------------------------------------------------
# Calibração logística: prob_cal = sigmoid(a * logit(prob_bruta) + b), ajustada nos resultados já registrados
# (só da versão atual do modelo, e só quando houver amostra suficiente)
# ---------------------------------------------------------------------
def _df_resolvidos(path=None, versao="atual"):
    path = path or CFG["AVB_FILE"]
    if not os.path.exists(path): return None
    df = pd.read_csv(path)
    if df.empty or "acertou" not in df.columns: return None
    df["acertou"] = pd.to_numeric(df["acertou"], errors="coerce")
    df["prob"] = pd.to_numeric(df["prob"], errors="coerce")
    df = df[df["acertou"].isin([0, 1]) & df["prob"].notna()].copy()
    if versao and "versao" in df.columns:
        df = df[df["versao"] == (CFG["VERSAO"] if versao == "atual" else versao)]
    return df


def ajustar_calibracao(path=None, min_n=None, versao="atual"):
    A = CFG["AVB"]
    min_n = A["calib_min_n"] if min_n is None else min_n
    df = _df_resolvidos(path, versao)
    if df is None or len(df) < min_n: return None
    p = np.clip(df["prob"].astype(float).values / 100.0, 1e-4, 1 - 1e-4)
    x = np.log(p / (1 - p)); y = df["acertou"].astype(float).values
    lam = A["calib_lambda"]; a, b = 1.0, 0.0
    for _ in range(50):
        q = 1.0 / (1.0 + np.exp(-(a * x + b))); w = q * (1 - q)
        g = np.array([np.sum((q - y) * x) + lam * (a - 1.0), np.sum(q - y) + lam * b])
        H = np.array([[np.sum(w * x * x) + lam, np.sum(w * x)], [np.sum(w * x), np.sum(w) + lam]])
        step = np.linalg.solve(H, g)
        a -= step[0]; b -= step[1]
        if np.max(np.abs(step)) < 1e-7: break
    return {"a": float(min(max(a, 0.3), 2.0)), "b": float(min(max(b, -1.0), 1.0)), "n": int(len(df))}


_CAL_CACHE = {"mtime": None, "params": None}


def _params_calibracao():
    path = CFG["AVB_FILE"]
    if not os.path.exists(path): return None
    mt = os.path.getmtime(path)
    if _CAL_CACHE["mtime"] == mt: return _CAL_CACHE["params"]
    try: params = ajustar_calibracao(path)
    except Exception: params = None
    _CAL_CACHE["mtime"], _CAL_CACHE["params"] = mt, params
    return params


def aplicar_calibracao(prob_pct, params):
    if not params: return prob_pct
    p = min(max(prob_pct / 100.0, 1e-4), 1 - 1e-4)
    z = params["a"] * math.log(p / (1 - p)) + params["b"]
    return 100.0 / (1.0 + math.exp(-z))


# ---------------------------------------------------------------------
# REGRA ÚNICA DO AVB
#   Obrigatórios: prob >= prob_min | conf V >= conf_min_v | conf D >= conf_min_d |
#                 V melhor em Time Ajust. | V melhor em Méd. Time | Recup. sem sinal ruim | V não é Trombador |
#                 (exige_fator_medido) nenhum dos dois com corrida convertida sem fator de distância medido
#   Apoio (mín. apoio_min de 2): Categoria, Largada
# ---------------------------------------------------------------------
def _vantagem_largada(V, D, ctx):
    top3 = ctx.get("top3_ms", set())
    if V.get("msplit") is not None and D.get("msplit") is not None:
        melhor = V["msplit"] < D["msplit"]
    else:
        melhor = False  # sem split na distância exata não há vantagem de largada comprovada
    return bool(melhor or (V["name"] in top3 and D["name"] not in top3))


def _avaliar_confronto(V, D, prob, ctx):
    A = CFG["AVB"]
    c_tadj = (V.get("tadj") is not None and D.get("tadj") is not None and V["tadj"] < D["tadj"])
    c_mtime = (V.get("mtime") is not None and D.get("mtime") is not None and V["mtime"] < D["mtime"])
    c_cat = (V.get("cat", 0) >= D.get("cat", 0))
    rv, rd = V.get("rec"), D.get("rec")
    c_rec = (rv is None or rv >= -10.0) and (rv is None or rd is None or rv >= rd)  # só reprova sinal ruim conhecido
    c_larg = _vantagem_largada(V, D, ctx)
    c_perfil = V.get("perfil") != "Trombador"

    apoio = sum([c_cat, c_larg])
    obrig = c_tadj and c_mtime and c_rec and c_perfil
    conf_ok = V.get("conf", 0) >= A["conf_min_v"] and D.get("conf", 0) >= A["conf_min_d"]
    conv_ok = (V.get("conv_ok", True) and D.get("conv_ok", True)) or not A.get("exige_fator_medido", True)
    aprovado = bool(prob >= A["prob_min"] and conf_ok and obrig and apoio >= A["apoio_min"] and conv_ok)
    score = sum([c_tadj, c_mtime, c_rec, c_perfil]) + apoio  # 0..6
    flags = {"c_tadj": c_tadj, "c_mtime": c_mtime, "c_cat": c_cat,
             "c_rec": c_rec, "c_larg": c_larg, "c_perfil": c_perfil}
    return aprovado, score, flags


# (nome_V, nome_D) -> ("AVB", nº de critérios 0-6, calibrada?)
AVB_META = {}

_FLAGS = ["c_tadj", "c_mtime", "c_cat", "c_rec", "c_larg", "c_perfil"]
_AVB_COLS = (["corrida_id", "registrado_em", "data", "pista", "hora", "race", "race_id", "classe", "dist",
              "galgo_V", "trap_V", "galgo_D", "trap_D", "prob", "prob_cal", "aprovado", "criterios"]
             + _FLAGS +
             ["exibido", "tproj_V", "tproj_D", "delta_s", "sd_total", "tadj_V", "tadj_D", "mtime_V", "mtime_D",
              "brt_V", "brt_D", "pos_V", "pos_D", "acertou", "versao"])

_OVR_COLS = ["corrida_id", "registrado_em", "data", "pista", "hora", "race", "race_id", "classe", "dist",
             "galgo", "trap", "overall", "pos_prev", "p_vit", "t_proj", "t_sd", "c_tempo", "c_peso", "c_trap", "c_larg", "c_pp",
             "tadj", "mtime", "pico", "msplit", "conf", "conv_ok", "pos_real", "margem_corpos", "tempo_real", "versao"]


def corrida_id(dogs, ctx):
    chave = str(ctx.get("today"))[:10] + "|" + "|".join(sorted(f"{d['trap']}{d['name']}" for d in dogs if d.get("name") != "vacant"))
    return hashlib.md5(chave.encode("utf-8")).hexdigest()[:10]


def _ler_avb_csv(path):
    if not os.path.exists(path): return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _gravar_csv(path, rows, cols):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def _gravar_avb_csv(path, rows):
    _gravar_csv(path, rows, _AVB_COLS)


def _chave_par(cid, a, b):
    x, y = sorted([str(a), str(b)])
    return (str(cid), x, y)


def registrar_previsoes(dogs, linhas, ctx):
    """Um registro por corrida+par (independe da orientação V/D). Previsão com resultado já salvo não é sobrescrita.
    `prob` guarda SEMPRE a probabilidade bruta (para a calibração não se retroalimentar)."""
    if not linhas: return 0
    path = CFG["AVB_FILE"]
    cid = corrida_id(dogs, ctx)
    rows = _ler_avb_csv(path)
    idx = {_chave_par(r["corrida_id"], r["trap_V"], r["trap_D"]): r for r in rows}
    novos = 0
    fmt = lambda x: "" if x in (None, "") else round(float(x), 4)
    for V, D, prob_raw, prob_cal, aprovado, crit, flags in linhas:
        r = _dif_proj(V, D, ctx)
        delta, sd_tot, tV, tD = r if r else ("", "", "", "")
        antigo = idx.get(_chave_par(cid, V["trap"], D["trap"]))
        if antigo and antigo.get("acertou") not in (None, ""): continue
        novo = {"corrida_id": cid, "registrado_em": datetime.now().strftime("%Y-%m-%d %H:%M"), "data": str(ctx.get("today"))[:10],
                "pista": ctx.get("pista", ""), "hora": ctx.get("hora", ""), "race": ctx.get("race", ""), "race_id": ctx.get("race_id", ""),
                "classe": ctx.get("classe", ""), "dist": ctx.get("dist", ""),
                "galgo_V": V["name"], "trap_V": V["trap"], "galgo_D": D["name"], "trap_D": D["trap"],
                "prob": round(prob_raw, 2), "prob_cal": "" if prob_cal is None else round(prob_cal, 2),
                "aprovado": int(aprovado), "criterios": crit, "exibido": int(aprovado),
                "tproj_V": fmt(tV), "tproj_D": fmt(tD), "delta_s": fmt(delta), "sd_total": fmt(sd_tot),
                "tadj_V": fmt(V.get("tadj")), "tadj_D": fmt(D.get("tadj")), "mtime_V": fmt(V.get("mtime")), "mtime_D": fmt(D.get("mtime")),
                "brt_V": fmt(V.get("brt")), "brt_D": fmt(D.get("brt")), "pos_V": "", "pos_D": "", "acertou": "", "versao": CFG["VERSAO"]}
        for k in _FLAGS: novo[k] = int(bool(flags.get(k)))
        if antigo: antigo.update(novo)
        else:
            rows.append(novo); idx[_chave_par(cid, V["trap"], D["trap"])] = novo; novos += 1
    _gravar_avb_csv(path, rows)
    return novos


def registrar_overall(rank, ctx):
    """Grava, por galgo, o Overall (corpos), a posição prevista, a probabilidade de vitória, o tempo projetado e os componentes.
    Depois que a corrida acontece, resolver_overall_por_resultado() preenche posição real, margem (corpos) e tempo."""
    if not rank: return 0
    path = CFG["OVERALL_FILE"]
    cid = corrida_id(rank, ctx)
    rows = _ler_avb_csv(path)
    idx = {(r["corrida_id"], r["galgo"]): r for r in rows}
    novos = 0
    fmt = lambda x: "" if x in (None, "") else round(float(x), 4)
    for d in rank:
        chave = (cid, d["name"])
        antigo = idx.get(chave)
        if antigo and antigo.get("pos_real") not in (None, ""): continue
        c = d.get("ovr_comp", {})
        novo = {"corrida_id": cid, "registrado_em": datetime.now().strftime("%Y-%m-%d %H:%M"), "data": str(ctx.get("today"))[:10],
                "pista": ctx.get("pista", ""), "hora": ctx.get("hora", ""), "race": ctx.get("race", ""), "race_id": ctx.get("race_id", ""),
                "classe": ctx.get("classe", ""), "dist": ctx.get("dist", ""), "galgo": d["name"], "trap": d["trap"],
                "overall": fmt(d.get("overall")), "pos_prev": d.get("pos", ""), "p_vit": fmt(d.get("p_vit")),
                "t_proj": fmt(d.get("t_proj")), "t_sd": fmt(d.get("t_sd")),
                "c_tempo": fmt(c.get("tempo")), "c_peso": fmt(c.get("peso")), "c_trap": fmt(c.get("trap")),
                "c_larg": fmt(c.get("largada")), "c_pp": fmt(c.get("postpick")),
                "tadj": fmt(d.get("tadj")), "mtime": fmt(d.get("mtime")), "pico": fmt(d.get("pico")),
                "msplit": fmt(d.get("msplit")), "conf": fmt(d.get("conf")), "conv_ok": int(bool(d.get("conv_ok", True))),
                "pos_real": "", "margem_corpos": "", "tempo_real": "", "versao": CFG["VERSAO"]}
        if antigo: antigo.update(novo)
        else:
            rows.append(novo); idx[chave] = novo; novos += 1
    _gravar_csv(path, rows, _OVR_COLS)
    return novos


def resolver_overall_por_resultado(data_str, linhas):
    """Preenche posição real, margem (corpos) e tempo real dos galgos de uma data, usando a ordem de chegada lida do site.
    ATENCAO: confira se a margem do site e ate o VENCEDOR (a do 3o deve ser maior que a do 2o); se for ate o galgo
    da frente, a margem acumulada precisa ser somada."""
    path = CFG["OVERALL_FILE"]
    if not linhas or not os.path.exists(path): return 0
    por_nome = {}
    for l in linhas:
        try: por_nome[str(l["nome"]).strip().lower()] = l
        except Exception: pass
    rows = _ler_avb_csv(path); n = 0
    dia = str(data_str)[:10]
    for r in rows:
        if r.get("pos_real") not in (None, "") or r.get("data") != dia: continue
        l = por_nome.get(str(r.get("galgo", "")).strip().lower())
        if not l: continue
        r["pos_real"] = l["pos"]
        m = 0.0 if l["pos"] == 1 else parse_lengths(l.get("margem"))
        r["margem_corpos"] = "" if m is None else m
        t = to_float(l.get("tempo"))
        r["tempo_real"] = "" if t is None else t
        n += 1
    if n: _gravar_csv(path, rows, _OVR_COLS)
    return n


def registrar_resultado(cid, ordem):
    """ordem: traps do 1º ao último, ex. '3-1-4-5-2-6' (aceita só o top 3). Quem não aparece fica atrás de quem aparece.
    Retorna nº de confrontos atualizados, ou -1 se a ordem for inválida (traps repetidas ou fora de 1-6)."""
    txt = re.sub(r"[^0-9]", "", str(ordem or ""))
    traps = [int(c) for c in txt]
    if not traps: return 0
    if len(set(traps)) != len(traps) or any(t < 1 or t > 6 for t in traps): return -1
    pos = {t: i + 1 for i, t in enumerate(traps)}
    path = CFG["AVB_FILE"]
    rows = _ler_avb_csv(path); n = 0
    for r in rows:
        if r["corrida_id"] != cid: continue
        v, d = int(r["trap_V"]), int(r["trap_D"])
        pv, pd_ = pos.get(v), pos.get(d)
        if pv is None and pd_ is None: continue
        ac = 1 if (pv is not None and (pd_ is None or pv < pd_)) else 0
        r["pos_V"], r["pos_D"], r["acertou"] = (pv or ""), (pd_ or ""), ac
        n += 1
    if n: _gravar_avb_csv(path, rows)
    return n


def resolver_pelo_historico(calib_path=None, avb_path=None):
    """Preenche SOZINHO o resultado dos confrontos pendentes, sem digitar nada.
    Usa o histórico dos galgos (calibracao_corridas.csv): depois que a corrida acontece, ela aparece no histórico de
    cada galgo com a posição final. Quando os DOIS galgos do confronto já têm essa corrida registrada, o confronto é resolvido.
    Casa por (galgo, data, distância e, se houver mais de uma, a trap). Empate ou posição ausente = continua pendente."""
    calib_path = calib_path or CFG["CALIB_FILE"]
    avb_path = avb_path or CFG["AVB_FILE"]
    if not (os.path.exists(calib_path) and os.path.exists(avb_path)): return 0
    rows = _ler_avb_csv(avb_path)
    pend = [r for r in rows if r.get("acertou") in (None, "")]
    if not pend: return 0
    datas = {r.get("data") for r in pend}
    hist = {}
    with open(calib_path, newline="", encoding="utf-8") as f:
        for h in csv.DictReader(f):
            if h.get("data") in datas and h.get("fin") not in (None, ""):
                hist.setdefault((h.get("galgo"), h.get("data")), []).append(h)

    def achar(nome, data, dist, trap):
        ok = []
        for h in hist.get((nome, data), []):
            try:
                if dist not in (None, "") and h.get("dist") not in (None, "") and abs(float(h["dist"]) - float(dist)) >= 1:
                    continue
            except Exception: pass
            ok.append(h)
        if len(ok) > 1:
            ok = [h for h in ok if str(h.get("trap")) == str(trap)] or ok
        if len(ok) != 1: return None
        try: return int(float(ok[0]["fin"]))
        except Exception: return None

    n = 0
    for r in pend:
        fv = achar(r.get("galgo_V"), r.get("data"), r.get("dist"), r.get("trap_V"))
        fd = achar(r.get("galgo_D"), r.get("data"), r.get("dist"), r.get("trap_D"))
        if fv is None or fd is None or fv == fd: continue
        r["pos_V"], r["pos_D"], r["acertou"] = fv, fd, (1 if fv < fd else 0)
        n += 1
    if n: _gravar_avb_csv(avb_path, rows)
    return n


def resolver_por_resultado(data_str, linhas):
    """Fecha os confrontos pendentes de uma data usando a ordem de chegada lida pelo site (aba Resultado).
    linhas: lista de dicts com 'nome' e 'pos' (e 'trap'). Só fecha o confronto se os DOIS galgos aparecem na lista com
    posições diferentes. Retorna quantos confrontos foram resolvidos."""
    path = CFG["AVB_FILE"]
    if not linhas or not os.path.exists(path): return 0
    pos = {}
    for l in linhas:
        try: pos[str(l["nome"]).strip().lower()] = int(l["pos"])
        except Exception: pass
    rows = _ler_avb_csv(path); n = 0
    dia = str(data_str)[:10]
    for r in rows:
        if r.get("acertou") not in (None, "") or r.get("data") != dia: continue
        pv = pos.get(str(r.get("galgo_V", "")).strip().lower())
        pd_ = pos.get(str(r.get("galgo_D", "")).strip().lower())
        if pv is None or pd_ is None or pv == pd_: continue
        r["pos_V"], r["pos_D"], r["acertou"] = pv, pd_, (1 if pv < pd_ else 0)
        n += 1
    if n: _gravar_avb_csv(path, rows)
    return n


def corridas_pendentes(avb_path=None):
    """Lista [(race_id, data)] das corridas com confrontos ainda sem resultado (só as que têm race_id gravado)."""
    rows = _ler_avb_csv(avb_path or CFG["AVB_FILE"])
    vistos = []
    for r in rows:
        if r.get("acertou") in (None, "") and r.get("race_id"):
            k = (str(r["race_id"]), r.get("data"))
            if k not in vistos: vistos.append(k)
    return vistos


def contar_pendentes(avb_path=None):
    """(pendentes, resolvidos) na versão atual do modelo."""
    rows = _ler_avb_csv(avb_path or CFG["AVB_FILE"])
    rows = [r for r in rows if r.get("versao") == CFG["VERSAO"]]
    res = sum(1 for r in rows if r.get("acertou") not in (None, ""))
    return len(rows) - res, res


def previsoes_bytes():
    path = CFG["AVB_FILE"]
    if not os.path.exists(path): return None
    with open(path, "rb") as f: return f.read()


def overall_bytes():
    path = CFG["OVERALL_FILE"]
    if not os.path.exists(path): return None
    with open(path, "rb") as f: return f.read()


# ---------------------------------------------------------------------
# VALIDAÇÃO
# ---------------------------------------------------------------------
def _wilson(k, n, z=1.96):
    if n <= 0: return 0.0, 1.0
    p = k / n; den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    marg = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centro - marg), min(1.0, centro + marg)


def avaliar_previsoes(path=None, so_exibidos=False, versao="atual"):
    """Faixa de probabilidade x acerto real (com intervalo de 95%), Brier e log-loss.
    Usa a probabilidade que foi exibida (calibrada, se houve) ou a bruta."""
    df = _df_resolvidos(path, versao)
    if df is None or df.empty: return None, {}
    if so_exibidos:
        df["exibido"] = pd.to_numeric(df.get("exibido"), errors="coerce")
        df = df[df["exibido"] == 1]
    if df.empty: return None, {}
    pc = pd.to_numeric(df["prob_cal"], errors="coerce") if "prob_cal" in df.columns else pd.Series(np.nan, index=df.index)
    df["p_usada"] = pc.where(pc.notna(), df["prob"])
    df["faixa"] = pd.cut(df["p_usada"], [50, 55, 60, 65, 70, 75, 80, 100.01], right=False)
    linhas = []
    for faixa, g in df.groupby("faixa", observed=True):
        n = len(g); k = int(g["acertou"].sum()); lo, hi = _wilson(k, n)
        linhas.append({"faixa": str(faixa), "n": n, "prob_media": round(g["p_usada"].mean(), 1),
                       "acerto_%": round(100 * k / n, 1), "ic95_inf_%": round(100 * lo, 1), "ic95_sup_%": round(100 * hi, 1),
                       "odd_justa": round(n / k, 2) if k else None, "odd_segura": round(1 / lo, 2) if lo > 0 else None})
    tab = pd.DataFrame(linhas)
    p = (df["p_usada"] / 100.0).clip(0.001, 0.999); y = df["acertou"]
    met = {"n": int(len(df)), "corridas": int(df["corrida_id"].nunique()),
           "acerto": float(y.mean()), "prob_media": float(p.mean()),
           "brier": float(((p - y) ** 2).mean()), "logloss": float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())}
    return tab, met


def avaliar_criterios(path=None, versao="atual"):
    """Para cada critério: taxa de acerto do V quando o critério é verdadeiro x falso (todos os pares registrados).
    Mostra quais critérios realmente separam acerto de erro."""
    df = _df_resolvidos(path, versao)
    if df is None or df.empty: return None
    linhas = []
    for c in _FLAGS:
        if c not in df.columns: continue
        col = pd.to_numeric(df[c], errors="coerce")
        v, f = df[col == 1], df[col == 0]
        linhas.append({"critério": c, "n_sim": len(v), "acerto_sim_%": round(100 * v["acertou"].mean(), 1) if len(v) else None,
                       "n_não": len(f), "acerto_não_%": round(100 * f["acertou"].mean(), 1) if len(f) else None})
    return pd.DataFrame(linhas)


def avaliar_overall(path=None):
    """Com o Overall e o resultado real já registrados: quantos corpos reais correspondem a 1 corpo previsto,
    e se a probabilidade de vitória (p_vit) está calibrada. Retorna (resumo, tabela) ou (None, None)."""
    path = path or CFG["OVERALL_FILE"]
    if not os.path.exists(path): return None, None
    df = pd.read_csv(path)
    for c in ("overall", "pos_prev", "pos_real", "margem_corpos", "p_vit"):
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[(df.get("versao") == CFG["VERSAO"]) & df["pos_real"].notna()].copy()
    if df.empty: return None, None
    df["venceu"] = (df["pos_real"] == 1).astype(int)
    resumo = {"galgos": int(len(df)), "corridas": int(df["corrida_id"].nunique()),
              "vencedor_previsto_ok": float(df[df["pos_prev"] == 1]["venceu"].mean()) if (df["pos_prev"] == 1).any() else None}
    d2 = df.dropna(subset=["margem_corpos", "overall"]).copy()
    if len(d2) >= 10:
        d2["lider"] = d2.groupby("corrida_id")["overall"].transform("max")
        d2["atras_prev"] = d2["lider"] - d2["overall"]
        x, y = d2["atras_prev"].values, d2["margem_corpos"].values
        if np.std(x) > 0:
            resumo["inclinacao_corpos_reais_por_corpo_previsto"] = float(np.polyfit(x, y, 1)[0])
    # calibração da probabilidade de vitória
    dv = df.dropna(subset=["p_vit"]).copy()
    if len(dv) >= 20:
        p = (dv["p_vit"] / 100.0).clip(0.001, 0.999); y = dv["venceu"]
        resumo["p_vit_n"] = int(len(dv))
        resumo["p_vit_brier"] = float(((p - y) ** 2).mean())
        resumo["p_vit_media"] = float(p.mean())
        resumo["p_vit_acerto_medio"] = float(y.mean())
        faixas = pd.cut(dv["p_vit"], [0, 10, 20, 30, 40, 50, 100.01], right=False)
        resumo["p_vit_faixas"] = [{"faixa": str(f), "n": len(g), "p_media_%": round(g["p_vit"].mean(), 1),
                                   "venceu_%": round(100 * g["venceu"].mean(), 1)} for f, g in dv.groupby(faixas, observed=True)]
    tab = df[["data", "pista", "galgo", "trap", "overall", "p_vit", "pos_prev", "pos_real", "margem_corpos"]].tail(60)
    return resumo, tab


def calibrar_escala(path=None):
    """(compatibilidade) escala única do z-score; prefira a calibração logística automática."""
    from statistics import NormalDist
    nd = NormalDist()
    df = _df_resolvidos(path, "atual")
    if df is None or len(df) < 30: return None
    z = np.array([nd.inv_cdf(min(max(p / 100.0, 0.001), 0.999)) for p in df["prob"]]); y = df["acertou"].values
    melhor = None
    for sc in np.arange(0.3, 2.01, 0.05):
        pp = np.array([nd.cdf(sc * x) for x in z]).clip(0.001, 0.999)
        ll = float(-(y * np.log(pp) + (1 - y) * np.log(1 - pp)).mean())
        if melhor is None or ll < melhor[1]: melhor = (float(sc), ll)
    return melhor


# ---------------------------------------------------------------------
# MONTAGEM DOS AVBS
# ---------------------------------------------------------------------
def montar_avbs(rank, ctx):
    elig = [d for d in rank if d.get("name") != "vacant" and not d.get("nd") and d.get("conf", 0) >= 20.0]
    if len(elig) < 2: return []

    try: resolver_pelo_historico()  # fecha sozinho os confrontos de corridas anteriores (sem digitar resultado)
    except Exception: pass
    params = _params_calibracao()
    s1, linhas_log = [], []
    AVB_META.clear()
    for i in range(len(elig)):
        for j in range(i + 1, len(elig)):
            A, B = elig[i], elig[j]
            if A.get("bloqueado") or A.get("alvo") or B.get("bloqueado") or B.get("alvo"): continue
            prob_A = calc_prob(A, B, rank, ctx)
            V, D, prob_raw = (A, B, prob_A) if prob_A >= 50.0 else (B, A, 100.0 - prob_A)
            prob = aplicar_calibracao(prob_raw, params)
            aprovado, crit, flags = _avaliar_confronto(V, D, prob, ctx)
            if aprovado: s1.append((V, D, prob, crit))
            linhas_log.append((V, D, prob_raw, (prob if params else None), aprovado, crit, flags))

    s1.sort(key=lambda x: (-x[2], -x[3]))  # maior probabilidade primeiro
    try: registrar_previsoes(rank, linhas_log, ctx)
    except Exception: pass
    out = []
    for V, D, prob, crit in s1:
        AVB_META[(V["name"], D["name"])] = ("AVB", crit, params is not None)
        out.append((V, D, prob, True))  # formato (V, D, prob, star): app.py continua desempacotando 4 itens
    return out


# =====================================================================
# TABELAS (HTML)
# =====================================================================
def get_rank_html(val, rank, max_rank):
    if val is None or rank is None: return "-"
    sup = {1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶"}.get(rank, "")
    color = "color:#12873a;font-weight:bold" if rank == 1 else ("color:#ff4b4b" if rank == max_rank and max_rank > 1 else "")
    return f"<span style='{color}'>{val:.2f}{sup}</span>"


_TBL_N = 0


def tbl(headers, rows, sticky=1, w1=None, w2=None):
    css = """<style>.dib-container{overflow-x:auto;width:100%;margin-bottom:20px}.dib-table{width:100%;border-collapse:collapse;text-align:center;font-size:15px;table-layout:auto}.dib-table th,.dib-table td{padding:8px 6px;border-bottom:1px solid rgba(128,128,128,0.2);white-space:nowrap;line-height:1.3}.dib-table th{background-color:rgba(128,128,128,0.1);font-weight:600}.dib-table td.sep{padding:0;height:2px;background-color:rgba(128,128,128,0.4)}.dib-table td.sep-avb{padding:0;height:1px;background-color:rgba(128,128,128,0.15)}"""
    css += (".dib-table th.stk,.dib-table td.stk{position:sticky;z-index:2;background-color:#ffffff;background-clip:padding-box;white-space:normal;overflow-wrap:anywhere;word-break:break-word;text-align:left;box-sizing:border-box}"
            ".dib-table th.stk{background-color:#f0f2f6;z-index:3}"
            ".dib-table .stk1{left:0}"
            ".dib-table .stk-last{box-shadow:2px 0 3px -1px rgba(128,128,128,0.45)}"
            "@media (prefers-color-scheme: dark){.dib-table th.stk,.dib-table td.stk{background-color:#0e1117}.dib-table th.stk{background-color:#262730}}")
    global _TBL_N
    _TBL_N += 1
    tid = f"dibt{_TBL_N}"
    if w1:
        css += f"#{tid} .stk1{{min-width:{w1}px;max-width:{w1}px;width:{w1}px}}#{tid} .stk2{{left:{w1}px}}"
    if w2:
        css += f"#{tid} .stk2{{min-width:{w2}px;max-width:{w2}px;width:{w2}px}}"
    css += "</style>"
    out = []
    for row in rows:
        if len(row) == 1 and "<hr" in str(row[0]): out.append(f"<tr><td class='sep' colspan='{len(headers)}'></td></tr>"); continue
        if len(row) == 1 and "sep-avb" in str(row[0]): out.append(f"<tr><td class='sep-avb' colspan='{len(headers)}'></td></tr>"); continue
        cells = []
        for ci, c in enumerate(row):
            cls = ""
            if ci < sticky:
                cls = f"stk stk{ci+1}" + (" stk-last" if ci == sticky - 1 else "")
            if isinstance(c, str) and c.strip().startswith("<td"):
                if cls: c = c.replace("<td", f"<td class='{cls}'", 1)
                cells.append(c)
            else:
                cells.append(f"<td class='{cls}'>{c}</td>" if cls else f"<td>{c}</td>")
        out.append("<tr>" + "".join(cells) + "</tr>")

    def _th(i, x):
        if i < sticky:
            return f"<th class='stk stk{i+1}{' stk-last' if i == sticky - 1 else ''}'>{x}</th>"
        return f"<th>{x}</th>"
    thead = "".join(_th(i, x) for i, x in enumerate(headers))
    return f"{css}<div class='dib-container' id='{tid}'><table class='dib-table'><thead><tr>{thead}</tr></thead><tbody>{''.join(out)}</tbody></table></div>"


def nome_marcado(d):
    n = html.escape(d["name"])
    if d.get("alerta_trial", False): n += " ⚠️"
    if d.get("alvo", False): n += " 🎯"
    if d.get("bloqueado", False): n += " 🚫"
    if d.get("conv_ok") is False: n += " 📏"  # tem corrida convertida sem fator de distância medido: fora dos AvBs
    return n


def brt_html(d):
    txt = d.get("brt_txt") or (f"BRT: {d['brt_raw']:.2f}" if d.get("brt_raw") else "")
    return f"<br><small style='color:#888;font-weight:normal'>{html.escape(txt)}</small>" if txt else ""


def trap_label(d): return f"{TRAP_EMOJI.get(d['trap'], '')} {d['trap']}"


def peso_txt(d):
    return f"{d['peso']:.1f}" if d.get("peso") else "-"


def grades_txt(d):
    """Grades das corridas usadas. '*' = convertida de outra distancia COM fator medido; '†' = convertida so por proporcao."""
    D = d.get("dist_alvo")
    out = []
    for r in d.get("val", []):
        g = r["grade"] or "?"
        if D and r.get("dist") is not None and abs(r["dist"] - D) >= 1:
            g += "*" if _slope_para(r.get("track", "")) is not None else "†"
        out.append(g)
    return "-".join(out)


def tabela_projecao(ds):
    cols = ["split", "time", "tadj", "metrica", "msplit", "mtime", "rec"]
    rk = {c: [None] * len(ds) for c in cols}
    max_rk = {}
    for c in cols:
        vals = [(i, d[c]) for i, d in enumerate(ds) if d.get(c) is not None]
        max_rk[c] = len(vals)
        vals.sort(key=lambda x: x[1], reverse=(c == "rec"))
        for rank, (i, _) in enumerate(vals, 1): rk[c][i] = rank

    rows = []
    for i, d in enumerate(ds):
        if d["nd"]:
            rows.append([trap_label(d), nome_marcado(d) + brt_html(d)] + ["-"] * 14); continue

        perfil_e = {"Limpo": "✅", "Irregular": "⚠️", "Trombador": "🔴"}[d["perfil"]]
        dias_txt = f"{d['dias']} ⚠️" if d['dias'] > 21 else str(d['dias'])

        split_display = get_rank_html(d.get("split"), rk["split"][i], max_rk["split"])
        msplit_display = get_rank_html(d.get("msplit"), rk["msplit"][i], max_rk["msplit"])

        if d.get("rec") is not None:
            rec_cell = get_rank_html(d["rec"], rk["rec"][i], max_rk["rec"]) + f"<br><small>{d['rec_txt'].split()[1]}</small>"
        else:
            rec_cell = "-"

        rows.append([
            trap_label(d), nome_marcado(d) + brt_html(d), f"{MEDALS.get(d['pos'], str(d['pos'])+'º')} {_fmt_ov(d['overall'])}",
            f"{d['cat']:.1f} ({d['cat_mod']:+.0f})", f"{perfil_e} {d['perfil']}",
            grades_txt(d), peso_txt(d), dias_txt,
            split_display, get_rank_html(d.get("time"), rk["time"][i], max_rk["time"]),
            msplit_display, get_rank_html(d.get("mtime"), rk["mtime"][i], max_rk["mtime"]),
            get_rank_html(d.get("tadj"), rk["tadj"][i], max_rk["tadj"]), get_rank_html(d.get("metrica"), rk["metrica"][i], max_rk["metrica"]),
            rec_cell, f"{d['conf']:.0f}%"
        ])
    return tbl(["Trap", "Galgo", "Overall", "Cat", "Perfil", "Grades", "Peso", "Dias", "M. Split", "M. Time", "Méd. Split", "Méd. Time", "Time Ajust.", "Métrica", "Recup. Média", "Conf."], rows, sticky=2, w1=64, w2=125)


def tabela_avb(lista, titulo):
    st.markdown(f"#### {titulo}")
    if not lista: st.info("Nenhum confronto aprovado nos critérios do AvB nesta corrida."); return

    def fmt_pair(val_v, val_d, is_time=False, precision=2, is_pct=False):
        if val_v is None or val_d is None: return "-", "-"
        p, suffix = f".{precision}f", "%" if is_pct else ""
        v_str, d_str = f"{val_v:{p}}{suffix}", f"{val_d:{p}}{suffix}"
        diff = val_v - val_d
        if val_v <= val_d: v_str += f" ({diff:{p}}{suffix})"
        else: d_str += f" (+{abs(diff):{p}}{suffix})"
        if is_time:
            if val_v < val_d: v_str, d_str = f"<span style='color:#12873a;font-weight:bold'>{v_str}</span>", f"<span style='color:#ff4b4b'>{d_str}</span>"
            elif val_v > val_d: v_str, d_str = f"<span style='color:#ff4b4b'>{v_str}</span>", f"<span style='color:#12873a;font-weight:bold'>{d_str}</span>"
        else:
            if val_v > val_d: v_str, d_str = f"<span style='color:#12873a;font-weight:bold'>{v_str}</span>", f"<span style='color:#ff4b4b'>{d_str}</span>"
            elif val_v < val_d: v_str, d_str = f"<span style='color:#ff4b4b'>{v_str}</span>", f"<span style='color:#12873a;font-weight:bold'>{d_str}</span>"
        return v_str, d_str

    badge = "<span style='color:#FFD700;font-weight:bold;margin-right:6px;' title='AvB aprovado'>★</span>"

    rows = []
    for i, item in enumerate(lista):
        V, D, prob = item[0], item[1], item[2]
        meta = AVB_META.get((V["name"], D["name"]))
        score_crit = meta[1] if meta else 0
        calibrada = bool(meta[2]) if meta and len(meta) > 2 else False

        if i > 0: rows.append(["<hr>"])

        ov_v, ov_d = fmt_pair(V['overall'], D['overall'], False, 1)
        cat_v, cat_d = fmt_pair(V['cat'], D['cat'], False, 1)
        sp_v, sp_d = fmt_pair(V.get('split'), D.get('split'), True, 2)
        t_v, t_d = fmt_pair(V.get('time'), D.get('time'), True, 2)
        ms_v, ms_d = fmt_pair(V.get('msplit'), D.get('msplit'), True, 2)
        mt_v, mt_d = fmt_pair(V.get('mtime'), D.get('mtime'), True, 2)
        ta_v, ta_d = fmt_pair(V.get('tadj'), D.get('tadj'), True, 2)
        me_v, me_d = fmt_pair(V.get('metrica'), D.get('metrica'), True, 2)
        rec_v, rec_d = fmt_pair(V.get('rec'), D.get('rec'), False, 1, True)

        prob_cell = (
            f"<td rowspan='2' style='vertical-align:middle;font-weight:bold;font-size:16px;'>"
            f"<span style='color:#12873a'>{prob:.1f}%</span><br>"
            f"<small style='color:#aaa;font-weight:normal'>{score_crit}/6 crit.</small><br>"
            f"<small style='color:#aaa;font-weight:normal'>{'calibrada' if calibrada else 'bruta'}</small></td>"
        )

        rows.append([
            f"{badge}{trap_label(V)} - {nome_marcado(V)}{brt_html(V)}",
            ov_v, cat_v, V['perfil'], grades_txt(V),
            peso_txt(V), f"{V['dias']}", sp_v, t_v, ms_v, mt_v, ta_v, me_v, rec_v, f"{V['conf']:.0f}%",
            prob_cell
        ])

        rows.append([
            f"{trap_label(D)} - {nome_marcado(D)}{brt_html(D)}",
            ov_d, cat_d, D['perfil'], grades_txt(D),
            peso_txt(D), f"{D['dias']}", sp_d, t_d, ms_d, mt_d, ta_d, me_d, rec_d, f"{D['conf']:.0f}%"
        ])

    heads = ["AvB", "Overall", "Cat", "Perfil", "Grades", "Peso", "Dias", "M. Split", "M. Time", "Méd. Split", "Méd. Time", "Time Ajust.", "Métrica", "Recup.", "Conf.", "Probabilidade"]
    st.markdown(tbl(heads, rows, sticky=1, w1=190), unsafe_allow_html=True)


# =====================================================================
# PAINEL DE VALIDAÇÃO + OBSERVAÇÕES
# =====================================================================
def painel_validacao():
    with st.expander("📊 Validação dos AvBs (acerto real × probabilidade)"):
        try:
            tab, met = avaliar_previsoes(so_exibidos=True)
            df_all = _df_resolvidos()
        except Exception as e:
            st.info(f"Não foi possível ler as previsões: {e}")
            return
        if tab is None or tab.empty:
            st.info("Ainda não há AvBs exibidos com resultado registrado nesta versão do modelo "
                    f"(`{CFG['VERSAO']}`). Registre a ordem de chegada de cada corrida.")
        else:
            st.markdown(f"**{met['n']} AvBs exibidos resolvidos em {met['corridas']} corridas** · "
                        f"acerto real **{100*met['acerto']:.1f}%** vs. prob. média {100*met['prob_media']:.1f}% · "
                        f"Brier {met['brier']:.3f} · log-loss {met['logloss']:.3f}")
            if met["n"] < 150:
                st.warning("Amostra pequena: com menos de ~150 confrontos a taxa de acerto tem margem de erro grande "
                           "(veja ic95_inf/sup). Mantenha stakes baixos até a taxa se sustentar.")
            st.markdown("Compare **acerto_%** com **prob_media**. A **odd_segura** usa o limite inferior do intervalo: só vale pagar abaixo dela se você aceitar o pior cenário.")
            st.dataframe(tab, hide_index=True)
        n_res = 0 if df_all is None else len(df_all)
        try:
            pend, resolv = contar_pendentes()
            st.markdown(f"Resultados: **{resolv} confrontos resolvidos** e {pend} pendentes. "
                        "Os resultados são preenchidos sozinhos quando os galgos aparecem em análises seguintes; "
                        "a digitação manual é opcional.")
        except Exception: pass
        params = _params_calibracao()
        if params:
            st.markdown(f"Calibração **ativa** (n={params['n']}): prob_cal = sigmoid({params['a']:.2f}·logit(prob_bruta) + {params['b']:+.2f})")
        else:
            st.markdown(f"Calibração **inativa**: {n_res} de {CFG['AVB']['calib_min_n']} confrontos resolvidos (todos os pares registrados).")
        crit = avaliar_criterios()
        if crit is not None and not crit.empty:
            st.markdown("**Quais critérios realmente separam acerto de erro** (todos os pares registrados):")
            st.dataframe(crit, hide_index=True)


def painel_overall():
    """Validação do Overall em corpos e da probabilidade de vitória, com as corridas já fechadas."""
    with st.expander("📐 Overall e probabilidade de vitória (previsto × real)"):
        try:
            resumo, tab = avaliar_overall()
        except Exception as e:
            st.info(f"Não foi possível ler o log do Overall: {e}")
            return
        if not resumo:
            st.info("Ainda não há corridas fechadas com Overall registrado nesta versão. "
                    "Abra o Resultado de corridas já disputadas para o app preencher posição real e margem.")
            return
        st.markdown(f"**{resumo['galgos']} galgos em {resumo['corridas']} corridas.**")
        if resumo.get("vencedor_previsto_ok") is not None:
            st.markdown(f"O 1º do Overall venceu em **{100 * resumo['vencedor_previsto_ok']:.0f}%** das corridas.")
        if resumo.get("inclinacao_corpos_reais_por_corpo_previsto") is not None:
            st.markdown(f"Cada corpo de diferença prevista para o líder virou **{resumo['inclinacao_corpos_reais_por_corpo_previsto']:.2f} corpos** reais "
                        "(1,00 = o Overall está na escala certa; abaixo de 1 = está exagerando as diferenças).")
        if resumo.get("p_vit_n"):
            st.markdown(f"Probabilidade de vitória: média prevista **{100 * resumo['p_vit_media']:.1f}%** vs. vitória real **{100 * resumo['p_vit_acerto_medio']:.1f}%** "
                        f"(Brier {resumo['p_vit_brier']:.3f}, n={resumo['p_vit_n']}).")
            if resumo.get("p_vit_faixas"):
                st.dataframe(pd.DataFrame(resumo["p_vit_faixas"]), hide_index=True)
        st.dataframe(tab, hide_index=True)


_DL_N = 0


def gerar_observacoes(rank, avbs, ctx):
    if not rank: return
    st.markdown("---")
    _dados_cal = calibracao_bytes()
    if _dados_cal:
        global _DL_N
        _DL_N += 1
        with st.expander("🧪 Dados para calibração (CSV)"):
            st.download_button("Baixar calibracao_corridas.csv", _dados_cal, file_name="calibracao_corridas.csv", mime="text/csv", key=f"dl_calib_{_DL_N}")
            _ovb = overall_bytes()
            if _ovb:
                st.download_button("Baixar overall_previsoes.csv", _ovb, file_name="overall_previsoes.csv", mime="text/csv", key=f"dl_ovr_{_DL_N}")
    cont, aprox, desc = diagnostico_remarks(rank)
    with st.expander(f"🔎 Leitura dos remarks ({cont['exato'] + cont['alias'] + cont['aprox']} lidos, {cont['desconhecido']} não reconhecidos)"):
        if desc: st.markdown("**Não reconhecidos (não afetam o tempo):** " + ", ".join(f"`{k}` ×{v}" for k, v in sorted(desc.items())))
        if aprox: st.markdown("**Interpretados por aproximação:** " + ", ".join(f"`{k}` → `{v}`" for k, v in sorted(aprox.items())))
        if not desc and not aprox: st.markdown("Todos os remarks foram reconhecidos exatamente.")
    with st.expander("🗒️ Remarks traduzidos por galgo"):
        for d in sorted(rank, key=lambda x: x["trap"]):
            trad = d.get("remarks_translated") or []
            if trad:
                st.markdown(f"{trap_label(d)} **{html.escape(d['name'])}** ({d['perfil']}): " + ", ".join(dict.fromkeys(trad)))
            else:
                st.markdown(f"{trap_label(d)} **{html.escape(d['name'])}** ({d['perfil']}): sem remarks reconhecidos.")
    # componentes do Overall (em corpos) — o MESMO tempo projetado do AvB e do Predictor
    with st.expander("🧮 Componentes do Overall (em corpos)"):
        linhas = []
        for d in sorted(rank, key=lambda x: x["pos"]):
            c = d.get("ovr_comp", {})
            linhas.append({"Trap": d["trap"], "Galgo": d["name"], "Overall": round(d["overall"], 2),
                           "Tempo": round(c.get("tempo", 0), 2), "Peso": round(c.get("peso", 0), 2),
                           "Trap (pista)": round(c.get("trap", 0), 2), "Largada": round(c.get("largada", 0), 2),
                           "Post Pick": round(c.get("postpick", 0), 2),
                           "Peso do histórico %": (round(100 * d.get("shrink_k", 1.0)) if d.get("t_proj") is not None else None),
                           "Tempo proj. (s)": (round(d["t_proj"], 2) if d.get("t_proj") is not None else None),
                           "± (s)": (round(d["t_sd"], 2) if d.get("t_sd") is not None else None),
                           "Prob. vitória %": (round(d["p_vit"], 1) if d.get("p_vit") is not None else None)})
        st.dataframe(pd.DataFrame(linhas), hide_index=True)
        st.caption(f"1 corpo = {CFG['CORPO_S']:.2f} s. Overall = vantagem em corpos sobre {_ref_nome()}: (tempo projetado de referência − tempo "
                   "projetado do galgo) ÷ 1 corpo. É o mesmo tempo projetado usado no AvB e no Predictor. "
                   "'Peso do histórico' mostra quanto do tempo do galgo vem do histórico dele (100% = historico confiavel; "
                   "menos que isso = puxado para a média do campo por ter poucas corridas ou corridas de outra distância). "
                   "Categoria, Recuperação e Regularidade seguem como critérios do AvB e na incerteza (±).")
    with st.expander("📏 Fator de distância (velocidade por 100 m)"):
        try:
            tabela_f, pares_pista, pares_total = resumo_fator_dist()
        except Exception:
            tabela_f, pares_pista, pares_total = [], {}, 0
        F = CFG["FATOR_DIST"]
        if tabela_f:
            st.dataframe(pd.DataFrame(tabela_f), hide_index=True)
            st.caption("Negativo = o galgo fica mais lento por 100 m a mais de prova. Medido com galgos que correram duas distâncias na mesma pista.")
        else:
            st.markdown(f"Nenhum fator medido ainda: são necessários {F['min_pares_pista']} pares por pista "
                        f"(ou {F['min_pares_global']} no total); há {pares_total} pares no `{CFG['CALIB_FILE']}`. "
                        "Enquanto isso, corridas de outra distância são convertidas só por proporção (†), com incerteza grande, "
                        "e o galgo aparece marcado com 📏 e fica fora dos AvBs.")
        sem = [d["name"] for d in rank if d.get("conv_ok") is False]
        if sem:
            st.markdown("Fora dos AvBs por falta de fator medido: " + ", ".join(html.escape(n) for n in sem))
    cid = corrida_id(rank, ctx)
    with st.expander("📝 Registrar resultado (calibração dos AvBs)"):
        ordem = st.text_input("Ordem de chegada (traps do 1º ao 6º, ex.: 3-1-4-5-2-6)", key=f"res_{cid}")
        if st.button("Salvar resultado", key=f"btn_res_{cid}"):
            n = registrar_resultado(cid, ordem)
            if n > 0: st.success(f"Resultado salvo em {n} confrontos.")
            elif n == -1: st.error("Ordem inválida: use traps de 1 a 6 sem repetir (ex.: 3-1-4-5-2-6).")
            else: st.warning("Nenhum confronto atualizado. Confira a ordem digitada.")
        _pv = previsoes_bytes()
        if _pv: st.download_button("Baixar avb_previsoes.csv", _pv, file_name="avb_previsoes.csv", mime="text/csv", key=f"dl_avb_{cid}")
    painel_validacao()
    painel_overall()
    st.markdown("#### 🏁 Leitura Tática da Corrida")

    elegiveis = [d for d in rank if not d.get("bloqueado")]
    bloqueados = [d for d in rank if d.get("bloqueado")]

    if not elegiveis:
        st.warning("Todos os cães estão bloqueados ou sem dados suficientes para esta corrida.")
        return

    fav_app = elegiveis[0]
    insights = []

    pp_str = str(ctx.get("post_pick") or "")
    pp_traps = [int(c) for c in pp_str if c.isdigit()]
    pp_fav_trap = pp_traps[0] if pp_traps else None
    pp_fav = next((d for d in elegiveis if d["trap"] == pp_fav_trap), None)

    if pp_fav and pp_fav["trap"] != fav_app["trap"]:
        insights.append(f"**⚔️ Duelo de Favoritos:** O mercado elegeu o **{TRAP_EMOJI.get(pp_fav['trap'])} {pp_fav['name']}** (Post Pick 1), mas o App crava o **{TRAP_EMOJI.get(fav_app['trap'])} {fav_app['name']}** (Overall {_fmt_ov(fav_app['overall'])}) como o verdadeiro dono da prova. É um choque direto.")
    else:
        insights.append(f"**🤝 Consenso Total:** O mercado e o App concordam que o **{TRAP_EMOJI.get(fav_app['trap'])} {fav_app['name']}** é o cão a ser batido. Overall {_fmt_ov(fav_app['overall'])} e Confiança {fav_app['conf']:.0f}%.")

    trombadores_internos = [d for d in elegiveis if d["perfil"] == "Trombador" and d["trap"] <= 4]
    if len(trombadores_internos) >= 2:
        nomes_tromb = " e ".join([f"{TRAP_EMOJI.get(d['trap'])} {d['name']}" for d in trombadores_internos])
        clean_candidates = [d for d in elegiveis if d["perfil"] != "Trombador"]

        if clean_candidates:
            c_clean = clean_candidates[0]
            if c_clean["trap"] >= 5: local = "por fora"
            elif c_clean["trap"] == 4: local = "pelo meio"
            else: local = "no trilho (por dentro)"
            insights.append(f"**💥 Risco de Colisão:** O {nomes_tromb} são Trombadores e correm nas traps internas. Se eles se chocarem na 1ª curva, o {TRAP_EMOJI.get(c_clean['trap'])} {c_clean['name']}, que corre {local} e não é Trombador, pode herdar a pista livre.")
        else:
            insights.append(f"**💥 Risco de Colisão:** O {nomes_tromb} são Trombadores e correm nas traps internas. A briga pelo trilho será intensa.")

    if bloqueados:
        b = max(bloqueados, key=lambda x: x["overall"])
        if b["overall"] > fav_app["overall"]:
            insights.append(f"**🚫 Armadilha do Histórico:** O {TRAP_EMOJI.get(b['trap'])} {b['name']} tem Overall bruto de {_fmt_ov(b['overall'])}, mas o App o bloqueou. O histórico dele nessa distância é curto ou ruim. Não caia na armadilha da odd baixa.")

    tadj_rank = sorted([d for d in elegiveis if d.get("tadj")], key=lambda x: x["tadj"])
    if len(tadj_rank) >= 3:
        top2_tadj_names = {d["name"] for d in tadj_rank[:2]}
        for z in elegiveis:
            if z["pos"] >= 4 and z["name"] in top2_tadj_names:
                is_mkt_zebra = True
                if pp_traps and z["trap"] in pp_traps[:2]: is_mkt_zebra = False
                if is_mkt_zebra:
                    insights.append(f"**🦓 A Zebra Escondida:** O {TRAP_EMOJI.get(z['trap'])} {z['name']} está apenas em {z['pos']}º no App, mas tem o **{z['tadj']:.2f}** de Tadj (Top 2 da prova). O mercado também esqueceu dele no Post Pick. É a aposta de risco/retorno mais alta da corrida.")

    alvos = [d for d in rank if d.get("alvo")]
    if alvos:
        nomes_alvo = ", ".join([f"{TRAP_EMOJI.get(a['trap'])} {a['name']}" for a in alvos])
        insights.append(f"**🎯 O Bode Expiatório:** O {nomes_alvo} foi marcado como Alvo. Sem largada e com recuperação negativa, ele vai ficar preso no bolo. Evite apostar nele como vencedor.")

    if not insights:
        insights.append("**📊 Corrida de Rotina:** O favorito tem dados sólidos, não há trombadores em excesso e as traps estão bem distribuídas. O App sugere seguir o Overall sem grandes riscos táticos.")

    for ins in insights[:4]:
        st.markdown(f"- {ins}")
