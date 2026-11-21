# -*- coding: utf-8 -*-
import re
import html
import math
import json
import os
import csv
import hashlib
from datetime import datetime
import numpy as np
import pandas as pd
import requests
import streamlit as st

REMARKS_INFO = {
    "ald": ("Liderou Sempre", "pos", None), "awk": ("Desajeitado", "neg", "light"),
    "blk": ("Trombada Forte na Curva", "neg", "heavy"), "bmp": ("Trombou Durante uma Curva", "neg", "medium"),
    "chl": ("Desafiado na Curva", "alerta", None), "clrrn": ("Corrida Limpa", "pos", None),
    "crd": ("Truncado na Curva", "alerta", "medium"), "crdnrln": ("Truncado no Final", "alerta", "light"),
    "crdrnln": ("Truncado na Reta Final", "alerta", "medium"), "crdrnup": ("Truncado desde o Início", "alerta", "medium"),
    "crmp": ("Correu em Espaço Apertado na Curva", "neg", "medium"), "disp": ("Disputou", "alerta", None),
    "dsp": ("Disputou na Curva", "alerta", None), "displd": ("Liderou com Muita Disputa", "alerta", None),
    "ep": ("Ritmo Acelerado", "pos", None), "evch": ("Ganharia se Fosse Bom o Suficiente", "neg", None),
    "fcd": ("Forçado a Algo", "alerta", "medium"), "fcdck": ("Forçado a Manter-se na Curva", "alerta", "medium"),
    "fell": ("Caiu na Curva", "neg", "exclui"), "hldon": ("Posição Mantida", "pos", None),
    "imp": ("Impedido na Curva", "alerta", "medium"), "jmp": ("Saltou", "alerta", None),
    "jmplate": ("Saltou Atrasado", "neg", "saw"), "ko": ("Derrubado na Curva", "neg", "exclui"),
    "lame": ("Manco", "neg", "exclui"), "ld": ("Liderou a Curva", "pos", None),
    "ldbmp": ("Tomou a Liderança com Esbarrão", "pos", None), "ldnrln": ("Tomou a Liderança na Reta Final", "pos", None),
    "in": ("Linha de Chegada", "alerta", None), "mid": ("Corre pelo Meio", "alerta", None),
    "msdbrk": ("Passou Reto na Curva", "neg", "vsaw"), "on": ("Até o Final", "alerta", None),
    "qaw": ("Largada Rápida", "pos", None), "rls": ("Corre por Dentro", "alerta", None),
    "rnln": ("Linha Reta e Alterou Pouco seu Traçado", "alerta", None), "rnon": ("Manteve um Galope Forte até o Final", "pos", None),
    "rnonwll": ("Manteve um Galope Forte até o Final", "pos", None), "rnup": ("Distância entre a Trap e a 1ª Curva", "alerta", None),
    "saw": ("Largada Lenta", "neg", "saw"), "snled": ("Liderou desde o Início", "pos", None),
    "stmb": ("Tropeçou", "neg", "medium"), "strfn": ("Chegada Forte", "pos", None),
    "stt": ("Início", "alerta", None), "struck": ("Atingido", "alerta", "medium"),
    "styd": ("Ficou", "neg", None), "turnedintrps": ("Voltou e/ou Ficou na Trap", "neg", "exclui"),
    "vsaw": ("Largada Muito Lenta", "neg", "vsaw"), "vw": ("Corredor Mais Aberto", "alerta", None),
    "w": ("Curva Ampla", "alerta", None), "baulk": ("Bloqueado (Baulk)", "neg", "heavy"),
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

CFG = {
    "N_RUNS": 5, "N_CORREDORES": 6, "CAT_BONUS": 2.0,
    "TRIAL_OFICIAL": True, 
    "TRAFFIC_ADJ": {"baulk": 0.20, "crd": 0.10, "bmp": 0.10, "fcd": 0.10},
    "PERFIL_PTS": {"Limpo": 5.0, "Irregular": 2.0, "Trombador": 0.0},
    "PERFIL_LIM": {"limpo_max": 0, "irregular_max": 1},
    "TRAP_VAZIA": 12.0,
    "TRAFEGO_SEVERO": -12.0,
    "CONF_MIN_VENCEDOR": 40.0,

    "VEL_PTS": {"tadj": 100, "mtime": 80, "msplit": 100},
    "CONSIST_PTS": 30, "PICO_PTS": 20, "RECUP_PTS": 10,

    "PESO_PENALTY_KG": 0.05, "PESO_ADJ_MAX": 0.15,

    "ADJ": {"light": 0.05, "medium": 0.15, "heavy": 0.30, "saw": 0.08, "vsaw": 0.15,
            "first_bend_mult": 1.5, "cap_total": 0.60, "split_loss_cap": 0.35},
    "REC_W": [0.30, 0.25, 0.20, 0.15, 0.10],
    "CALIB_FILE": "calibracao_corridas.csv",

    "AVB": {"w_tadj": 0.45, "w_mtime": 0.35, "w_brt": 0.20, "risk_k": 0.5,
            "brt_max_dias": 90, "brt_grade_gap": 2,
            "sigma0": 0.25, "sigma_k": 2.0, "sigma_min": 0.15, "prob_scale": 1.0,
            "start_bonus": 0.04,
            "trap_sec": {1: -0.02, 2: -0.01, 3: 0.0, 4: 0.0, 5: 0.01, 6: 0.02},
            "prob_min": 62.0, "conf_min_v": 60.0, "conf_min_d": 40.0, "apoio_min": 1,
            "calib_min_n": 150, "calib_lambda": 5.0},
    "AVB_FILE": "avb_previsoes.csv",
    "VERSAO": "avb-unico-1",
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
    "Accept": "application/json, text/plain, */*", "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://greyhoundbet.racingpost.com/",
}

RE_TRAF = re.compile(r"(awk|blk|bmp|crmp|evch|fcd|fell|ko|msdbrk|saw|stmb|struck|vsaw|crd|imp|lame)")
RE_NOFREE = re.compile(r"(awk|blk|bmp|crmp|evch|fcd|fell|ko|msdbrk|saw|stmb|struck|vsaw|crd|imp|lame|baulk)")

def pick(d, keys, default=None):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, ""): return d[k]
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

def bends_digits(b): return [int(c) for c in str(b or "") if c.isdigit()]
def grade_num(g):
    m = re.fullmatch(r"([ADSB])(\d{1,2})", str(g or "").strip().upper()); return int(m.group(2)) if m else None
def is_trial_grade(g): return bool(re.match(r"^T\d*$", str(g or "").strip().upper()))
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

def count_traf(rem): return sum(1 for p in parts_of(rem) if RE_TRAF.search(p))

GRAVES_PATTERNS = (r"\bbaulk(?:ed|s|ing)?\d*\b", r"\bfell\d*\b", r"\bko\d*\b|\bknocked\s+out\b", r"\bmsdbrk\d*\b|\bmissed\s+break\b")
MODERADOS_PATTERNS = (r"\bbmp\d*\b|\bbumped(?:\s+first)?\b", r"\bcrd\d*\b|\bcrowded(?:\s+quarter)?\b", r"\bfcd\d*\b|\bchecked\b", r"\bcrmp\d*\b|\bcramped\b")

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

def not_free(rem): return bool(RE_NOFREE.search(str(rem or "").lower()))

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

_EARLY_KEYS = {"ald", "ep", "snled", "ld", "ldbmp"}
_SAW_KEYS = {"saw", "vsaw"}

def analisar_remarks(rem):
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

def tempo_limpo(R, target_dist):
    A = CFG["ADJ"]
    info = [(r, analisar_remarks(r["remarks"])) for r in R if r["caltm"] is not None and r["caltm"] > 0 and r["dist"] is not None]
    usar = [(r, i) for r, i in info if not i["excluir"]] or info
    if not usar: return None, 0, 0.0
    
    limpos = [r["split"] for r, i in usar if i["limpa"] and r["split"] is not None and r["split"] > 0 and abs(r["dist"] - target_dist) < 1]
    ref_split = float(np.median(limpos)) if limpos else None
    
    speeds, descs = [], []
    for r, i in usar:
        loss = 0.0
        if i["slow"] and abs(r["dist"] - target_dist) < 1:
            if ref_split is not None and r["split"] is not None and r["split"] > 0:
                loss = min(max(r["split"] - ref_split, 0.0), A["split_loss_cap"])
            else:
                loss = A[i["slow"]]
        desc = min(i["interf"] + loss, A["cap_total"])
        
        adj_time = r["caltm"] - desc
        if adj_time > 0:
            speed = r["dist"] / adj_time
            speeds.append(speed)
            descs.append(desc)
            
    if not speeds: return None, len(info) - len(usar), 0.0

    w = np.array(CFG["REC_W"][:len(speeds)] + [CFG["REC_W"][-1]] * max(0, len(speeds) - len(CFG["REC_W"])), dtype=float)
    w = w / w.sum()
    avg_speed = float(np.dot(w, speeds))
    tadj = target_dist / avg_speed if avg_speed > 0 else None
    return tadj, len(info) - len(usar) if len(usar) != len(info) else 0, float(np.mean(descs))

def first_bend_traffic(rem):
    for it in ler_remarks(rem):
        if it["key"] and REMARKS_INFO[it["key"]][2] in ("light", "medium", "heavy") and (it["num"] == "1" or it["key"] == "crdrnup"):
            return True
    return False

HINTS = {"dist": (("dist", "metre", "meter"), ("btn", "beat", "by")), "grade": (("class", "grade"), ()), "by": (("btn", "beaten"), ()), "wntm": (("win", "time"), ())}
def pick_fb(f, k):
    v = pick(f, FIELD_MAP[k])
    if v is not None or k not in HINTS: return v
    inc, exc = HINTS[k]
    for key, val in f.items():
        kl = str(key).lower()
        ok = all(x in kl for x in inc) if k == "wntm" else any(x in kl for x in inc)
        if ok and not any(x in kl for x in exc) and val not in (None, ""): return val
    return None

def norm_run(f):
    g = lambda k: pick_fb(f, k)
    return {"date": parse_date(g("date")), "date_str": str(g("date") or "")[:10], "track": str(g("track") or ""), "dist": to_float(g("dist")),
            "grade": str(g("grade") or "").strip().upper(), "trap": fin_num(g("trap")), "split": to_float(g("split")), "bends": str(g("bends") or ""),
            "fin": fin_num(g("fin")), "by": parse_lengths(g("by")), "wntm": to_float(g("wntm")), "gng": g("gng"), "weight": to_float(g("weight")),
            "remarks": str(g("remarks") or ""), "caltm": to_float(g("caltm"))}

GRADE_RE = re.compile(r"^(A\d{1,2}|T\d?|HP|OR|IT|S\d|D\d|B\d|ON\d)$")
def descobrir_chaves(dogs):
    vals = {}
    for dog in dogs:
        for f in dog.get("forms", []):
            for k, v in f.items():
                if isinstance(v, (str, int, float)) and v not in ("", None): vals.setdefault(k, []).append(v)
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
    info = {"pista": "", "hora": "", "race": "", "classe": "", "post_pick": "", "going": "NORMAL"}
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
    if not info["pista"] and dogs and dogs[0].get("runs"): info["pista"] = str(dogs[0]["runs"][0].get("track", "Desconhecida")).strip()
    for src in fontes:
        for k in ["offTime", "scheduledTime", "displayTime", "time", "raceTime"]:
            val = src.get(k)
            if val:
                m = re.search(r"\b([1-9]|1[0-2]):\d{2}\b", str(val))
                if m: info["hora"] = m.group(0); break
        if info["hora"]: break
    for src in fontes:
        r_num = pick(src, ["raceNum", "raceNumber", "rNum", "raceNumberDesc", "number"])
        if r_num is not None: info["race"] = str(r_num).replace("Race", "").strip(); break
    for src in fontes:
        grade = pick(src, ["raceClass", "grade", "class", "raceClassDesc", "raceGrade"])
        if grade: info["classe"] = str(grade).strip().upper(); break
    if not info["classe"] and dogs and dogs[0].get("runs"): info["classe"] = str(dogs[0]["runs"][0].get("grade", "")).strip().upper()
    for src in fontes:
        pp = pick(src, ["postPick", "post_pick", "tips", "tip"])
        if pp:
            m = re.search(r"\b([1-6][-/.][1-6][-/.][1-6])\b", str(pp))
            if m: info["post_pick"] = m.group(1).strip().replace("/", "-").replace(".", "-"); break
            elif re.search(r"[1-6]", str(pp)): info["post_pick"] = str(pp).strip().replace("/", "-").replace(".", "-"); break
    for src in fontes:
        gng = pick(src, ["going", "goingType", "gng"])
        if gng: info["going"] = str(gng).strip().upper(); break
    return info

def extrair_dados_racingpost(url):
    try:
        if not url.startswith("http"): url = "https://greyhoundbet.racingpost.com/" + url
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
            if resp_card.status_code == 200: info_card = resp_card.json()
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
            out.append({"name": dog.get("dogName", "Desconhecido"), "trap": trap or 0, "peso_atual": to_float(dog.get("weight")), "runs": runs, "brt": extrair_brt(dog), "brt_txt": extrair_brt_txt(dog)})
        existing_traps = {d["trap"] for d in out}
        for t in range(1, 7):
            if t not in existing_traps: out.append({"name": "vacant", "trap": t, "peso_atual": None, "runs": []})
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

_MESES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
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
