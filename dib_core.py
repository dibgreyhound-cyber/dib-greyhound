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
    return min(pen, 0.50)

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
    
    limpos = [r["split"] for r, i in usar if i["limpa"] and r["split"] is not None and r["split"] > 2.0 and abs(r["dist"] - target_dist) < 1]
    ref_split = float(np.median(limpos)) if limpos else None
    
    speeds, descs = [], []
    for r, i in usar:
        loss = 0.0
        if i["slow"] and abs(r["dist"] - target_dist) < 1:
            if ref_split is not None and r["split"] is not None and r["split"] > 2.0:
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
        kl = str(k).lower()
        if ("brt" in kl or "best" in kl) and ("date" in kl or kl.endswith("dt")):
            dt = _fmt_data_brt(v)
            if dt: break
    return f"BRT: {brt:.2f}" + (f" ({dt})" if dt else "")

def oficial(r, ctx):
    g = str(r["grade"] or "").strip().upper()
    if g.startswith("HP"): return False
    if is_trial_grade(g) and not CFG["TRIAL_OFICIAL"]: return False
    
    # [AJUSTE] Aceita uma margem de tolerância de 100 metros
    return (r["dist"] is not None 
            and abs(r["dist"] - ctx["dist"]) <= 100 
            and r["caltm"] is not None and r["caltm"] > 0)

def analisar_galgo(dog, ctx):
    if dog.get("name") == "vacant":
        return {"name": "vacant", "trap": dog["trap"], "runs": [], "val": [], "nd": True, "conf": 0.0, "bloqueado": False, "alvo": False, "pos": 0, "elegivel": False, "alerta_trial": False, "n_trials": 0, "n_val": 0}

    todas = sorted(dog["runs"], key=lambda r: r["date"] or datetime.min, reverse=True)
    runs = todas[:CFG["N_RUNS"]]
    n_trials = sum(1 for r in runs if is_trial_grade(r["grade"]))

    oficiais = [r for r in todas if oficial(r, ctx)]
    validas = [r for r in oficiais if not analisar_remarks(r["remarks"])["excluir"]]
    R = (validas or oficiais)[:CFG["N_RUNS"]]

    d = {"name": dog["name"], "trap": dog["trap"], "runs": runs, "val": R, "nd": not R, "n_val": len(R), "conf": min(100.0, len(R) * 20.0), "bloqueado": False, "alvo": False, "pos": 0, "elegivel": False, "alerta_trial": n_trials >= 3, "n_trials": n_trials}

    d["brt_raw"] = dog.get("brt")
    d["brt_txt"] = dog.get("brt_txt")
    ultima_any = todas[0] if todas else None
    d["dias"] = (ctx["today"] - ultima_any["date"]).days if ultima_any and ultima_any["date"] else 0
    if d["dias"] > 21: d["conf"] *= 0.8

    if not R: return d

    today_n = ctx.get("classe_n")
    valid_grades = [grade_num(r["grade"]) for r in R if grade_num(r["grade"]) is not None]
    avg_grade_n = sum(valid_grades) / len(valid_grades) if valid_grades else (today_n or 0)
    if today_n and valid_grades: mod = max(-CFG["CAT_BONUS"], min(CFG["CAT_BONUS"], today_n - avg_grade_n))
    else: mod = 0.0
    base = 13.0 - (avg_grade_n * 0.6)
    d["cat_mod"], d["cat"] = mod, base + mod
    d["peso"] = dog.get("peso_atual") or R[0]["weight"]

    exact_dist_runs = [r for r in R if abs(r["dist"] - ctx["dist"]) < 1]
    valid_splits = [r["split"] for r in exact_dist_runs if r["split"] is not None and r["split"] > 2.0]
    
    if valid_splits:
        d["msplit"] = float(np.mean(valid_splits))
        d["msplit_pos"] = None
    else:
        pos_curve = [bends_digits(r["bends"])[0] for r in exact_dist_runs if bends_digits(r["bends"])]
        d["msplit"] = None
        d["msplit_pos"] = float(np.mean(pos_curve)) if pos_curve else None

    valid_speeds = [r["dist"] / r["caltm"] for r in R if r["dist"] is not None and r["caltm"] is not None and r["caltm"] > 0]
    if valid_speeds:
        avg_speed = float(np.mean(valid_speeds))
        d["mtime"] = ctx["dist"] / avg_speed if avg_speed > 0 else None
    else:
        d["mtime"] = None

    d["split"] = min(valid_splits) if valid_splits else None
    d["time"] = min([r["caltm"] for r in exact_dist_runs if r["caltm"] is not None]) if exact_dist_runs else None

    d["brt"] = _brt_valido(d, ctx)
    if d["brt"] and d["mtime"] and abs(d["brt"] - d["mtime"]) > 3.0: d["brt"] = None

    d["tadj"], d["tadj_excl"], d["tadj_desc"] = tempo_limpo(R, ctx["dist"])
    d["tadj_excl"] = len(oficiais) - len(validas)

    valores_metrica = [v for v in [d.get("brt"), d.get("tadj"), d.get("mtime")] if v is not None]
    d["metrica"] = sum(valores_metrica) / len(valores_metrica) if valores_metrica else None
    
    valid_caltm = [r["caltm"] for r in R if r["caltm"] is not None and r["caltm"] > 0]
    d["sd"] = float(np.std(valid_caltm)) if len(valid_caltm) > 1 else None 
    d["pico"] = min(valid_caltm) if valid_caltm else None

    recs = []
    for r in R:
        b = bends_digits(r["bends"])
        if b and r["fin"] and analisar_remarks(r["remarks"])["interf"] == 0: recs.append((b[0] - r["fin"]) / CFG["N_CORREDORES"] * 100.0)
    if recs:
        d["rec"] = float(np.mean(recs))
        d["rec_txt"] = f"{d['rec']:+.2f}% ({'Ganhou' if d['rec'] > 0.005 else ('Perdeu' if d['rec'] < -0.005 else 'Manteve')})"
    else:
        d["rec"] = None
        d["rec_txt"] = "-"

    n_traf = sum(1 for r in R if analisar_remarks(r["remarks"])["interf"] > 0)
    L = CFG["PERFIL_LIM"]
    d["perfil"] = "Limpo" if n_traf <= L["limpo_max"] else ("Irregular" if n_traf <= L["irregular_max"] else "Trombador")

    d["early_cnt"] = sum(1 for r in R if any(it["key"] in _EARLY_KEYS for it in ler_remarks(r["remarks"])))
    d["saw_cnt"] = sum(1 for r in R if any(it["key"] in _SAW_KEYS for it in ler_remarks(r["remarks"])))
    d["fbt_cnt"] = sum(1 for r in R if first_bend_traffic(r["remarks"]))

    d["remarks_translated"] = []
    for r in R: d["remarks_translated"].extend(traducao_remarks(r["remarks"]))

    pesos_hist = [r["weight"] for r in R if r.get("weight") is not None]
    if pesos_hist and d["peso"]:
        adj = (d["peso"] - float(np.mean(pesos_hist))) * CFG["PESO_PENALTY_KG"]
        d["peso_adj"] = float(max(-CFG["PESO_ADJ_MAX"], min(CFG["PESO_ADJ_MAX"], adj)))
    else:
        d["peso_adj"] = 0.0

    return d

_CALIB_COLS = ["registrado_em", "pista", "data", "dist", "galgo", "trap", "grade", "caltm", "split", "bends", "fin", "remarks", "peso", "brt"]
def registrar_calibracao(ds):
    path = CFG["CALIB_FILE"]; vistos = set()
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f): vistos.add((row["galgo"], row["data"], row["pista"], row["dist"], row["caltm"]))
    novas = []
    for d in ds:
        if d.get("name") in (None, "vacant"): continue
        for r in d.get("runs", []):
            if r.get("caltm") is None or r["caltm"] <= 0: continue
            chave = (d["name"], r["date_str"], r["track"], str(r["dist"]), str(r["caltm"]))
            if chave in vistos: continue
            vistos.add(chave)
            novas.append([datetime.now().strftime("%Y-%m-%d %H:%M"), r["track"], r["date_str"], r["dist"], d["name"], r["trap"], r["grade"], r["caltm"], r["split"], r["bends"], r["fin"], r["remarks"], r["weight"], d.get("brt_raw")])
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

def finalizar(ds, ctx):
    try: registrar_calibracao(ds)
    except Exception: pass
    ok = [d for d in ds if not d["nd"]]
    vac = [t for t in range(1, 7) if t not in {d["trap"] for d in ds if d["name"] != "vacant"}]

    ms_rank = sorted([d for d in ok if d.get("msplit") is not None], key=lambda x: x["msplit"])
    if not ms_rank: ms_rank = sorted([d for d in ok if d.get("msplit_pos") is not None], key=lambda x: x["msplit_pos"])
    top3_ms = {d["name"] for d in ms_rank[:3]}
    top_split_name = ms_rank[0]["name"] if ms_rank else None
    ctx["top3_ms"] = top3_ms

    def pts_prop(key, maxp, d, invert=True, neutro=False):
        vals = [x[key] for x in ok if x.get(key) is not None]
        if d.get(key) is None or not vals: return maxp * 0.5 if neutro else 0.0
        lo, hi = min(vals), max(vals)
        if hi == lo: return float(maxp)
        return maxp * (hi - d[key]) / (hi - lo) if invert else maxp * (d[key] - lo) / (hi - lo)

    for d in ok:
        pts_cat = d["cat"] * 1.5
        pts_perfil = CFG["PERFIL_PTS"][d["perfil"]]

        vel = (pts_prop("tadj", CFG["VEL_PTS"]["tadj"], d) +
               pts_prop("mtime", CFG["VEL_PTS"]["mtime"], d) +
               (pts_prop("msplit", CFG["VEL_PTS"]["msplit"], d) if d["msplit"] else (CFG["VEL_PTS"]["msplit"] * (1 - (d["msplit_pos"] / 6)) if d.get("msplit_pos") else 0)))

        f = []
        if d["early_cnt"] > 0 and d["perfil"] == "Limpo": f.append(("Ritmo Acelerado", d["early_cnt"] * 5.0))
        if d["saw_cnt"] > 0: f.append(("Largada Lenta", d["saw_cnt"] * -6.0))
        if d["fbt_cnt"] > 0: f.append(("Tráfego 1ª Curva", d["fbt_cnt"] * -4.0))
        if any(abs(d["trap"] - v) == 1 for v in vac): f.append(("Trap Vazia", CFG["TRAP_VAZIA"]))
        if d["perfil"] == "Trombador" and d["trap"] in [1, 2, 3, 4, 5] and d["name"] not in top3_ms: f.append(("Tráfego Severo", CFG["TRAFEGO_SEVERO"]))

        d["fatores"] = f
        d["overall"] = (vel + pts_cat + pts_perfil + pts_prop("sd", CFG["CONSIST_PTS"], d, True, True) + pts_prop("pico", CFG["PICO_PTS"], d, True) + pts_prop("rec", CFG["RECUP_PTS"], d, False, True) + sum(v for _, v in f))

    if ok:
        max_ov = max(d["overall"] for d in ok)
        min_ov = min(d["overall"] for d in ok)
        for d in ok: d["overall"] = 40.0 + (60.0 * (d["overall"] - min_ov) / (max_ov - min_ov)) if max_ov > min_ov else 70.0

    ok.sort(key=lambda x: -x["overall"])
    for i, d in enumerate(ok, 1):
        d["pos"] = i
        d["bloqueado"] = d["conf"] < CFG["CONF_MIN_VENCEDOR"]
        rec = d.get("rec")
        top2_safe = (i <= 2) and (rec is not None and rec >= -10.0)
        d["alvo"] = (d["name"] not in top3_ms) and (d["name"] != top_split_name) and (rec is not None and rec < -10.0) and not top2_safe
        d["elegivel"] = not d["bloqueado"]
    return ok, top3_ms

def _brt_valido(d, ctx):
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

def projetar_tempo(d, ctx):
    A = CFG["AVB"]
    partes = []
    if d.get("tadj") is not None: partes.append((A["w_tadj"], d["tadj"] + A["risk_k"] * (d.get("tadj_desc") or 0.0)))
    if d.get("mtime") is not None: partes.append((A["w_mtime"], d["mtime"]))
    brt = _brt_valido(d, ctx)
    if brt: partes.append((A["w_brt"], brt))
    if not partes: return None, None
    t = sum(w * x for w, x in partes) / sum(w for w, _ in partes)
    t += d.get("peso_adj", 0.0)
    t += A["trap_sec"].get(d["trap"], 0.0)
    if d["name"] in ctx.get("top3_ms", set()): t -= A["start_bonus"]
    
    n = max(d.get("n_val") or len(d.get("val") or []), 1)
    sd = d.get("sd") or 0.0
    var = (n * sd ** 2 + A["sigma_k"] * A["sigma0"] ** 2) / (n + A["sigma_k"])
    var = max(var, A["sigma_min"] ** 2)
    var = var + var / n
    d["t_proj"] = t
    return t, var

def _dif_proj(V, D, ctx):
    tV, vV = projetar_tempo(V, ctx); tD, vD = projetar_tempo(D, ctx)
    if tV is None or tD is None: return None
    return tD - tV, math.sqrt(vV + vD), tV, tD

def calc_prob(V, D, rank, ctx):
    r = _dif_proj(V, D, ctx)
    if r is None: return 50.0
    delta, sd_tot, _, _ = r
    z = CFG["AVB"]["prob_scale"] * delta / sd_tot
    return 100.0 * 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

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

def _vantagem_largada(V, D, ctx):
    top3 = ctx.get("top3_ms", set())
    if V.get("msplit") is not None and D.get("msplit") is not None: melhor = V["msplit"] < D["msplit"]
    elif V.get("msplit_pos") is not None and D.get("msplit_pos") is not None: melhor = V["msplit_pos"] < D["msplit_pos"]
    else: melhor = False 
    return bool(melhor or (V["name"] in top3 and D["name"] not in top3))

def _avaliar_confronto(V, D, prob, ctx):
    A = CFG["AVB"]
    c_tadj = (V.get("tadj") is not None and D.get("tadj") is not None and V["tadj"] < D["tadj"])
    c_mtime = (V.get("mtime") is not None and D.get("mtime") is not None and V["mtime"] < D["mtime"])
    
    c_cat = (V.get("cat", 0) >= D.get("cat", 0))
    rv, rd = V.get("rec"), D.get("rec")
    c_rec = (rv is None or rv >= -10.0) and (rv is None or rd is None or rv >= rd)
    c_larg = _vantagem_largada(V, D, ctx)
    c_perfil = V.get("perfil") != "Trombador"

    apoio = sum([c_cat, c_larg]) 
    obrig = c_tadj and c_mtime and c_rec and c_perfil
    conf_ok = V.get("conf", 0) >= A["conf_min_v"] and D.get("conf", 0) >= A["conf_min_d"]
    
    aprovado = bool(prob >= A["prob_min"] and conf_ok and obrig and apoio >= 1) 
    
    score = sum([c_tadj, c_mtime, c_rec, c_perfil]) + apoio
    flags = {"c_tadj": c_tadj, "c_mtime": c_mtime, "c_cat": c_cat, "c_rec": c_rec, "c_larg": c_larg, "c_perfil": c_perfil}
    return aprovado, score, flags

AVB_META = {}
_FLAGS = ["c_tadj", "c_mtime", "c_cat", "c_rec", "c_larg", "c_perfil"]
_AVB_COLS = (["corrida_id", "registrado_em", "data", "pista", "hora", "race", "race_id", "classe", "dist", "galgo_V", "trap_V", "galgo_D", "trap_D", "prob", "prob_cal", "aprovado", "criterios"] + _FLAGS + ["exibido", "tproj_V", "tproj_D", "delta_s", "sd_total", "tadj_V", "tadj_D", "mtime_V", "mtime_D", "brt_V", "brt_D", "pos_V", "pos_D", "acertou", "versao"])

def corrida_id(dogs, ctx):
    chave = str(ctx.get("today"))[:10] + "|" + "|".join(sorted(f"{d['trap']}{d['name']}" for d in dogs if d.get("name") != "vacant"))
    return hashlib.md5(chave.encode("utf-8")).hexdigest()[:10]

def _ler_avb_csv(path):
    if not os.path.exists(path): return []
    with open(path, newline="", encoding="utf-8") as f: return list(csv.DictReader(f))

def _gravar_avb_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_AVB_COLS, extrasaction="ignore"); w.writeheader(); w.writerows(rows)

def _chave_par(cid, a, b):
    x, y = sorted([str(a), str(b)]); return (str(cid), x, y)

def registrar_previsoes(dogs, linhas, ctx):
    if not linhas: return 0
    path = CFG["AVB_FILE"]; cid = corrida_id(dogs, ctx); rows = _ler_avb_csv(path)
    idx = {_chave_par(r["corrida_id"], r["trap_V"], r["trap_D"]): r for r in rows}
    novos = 0
    fmt = lambda x: "" if x in (None, "") else round(float(x), 4)
    for V, D, prob_raw, prob_cal, aprovado, crit, flags in linhas:
        r = _dif_proj(V, D, ctx); delta, sd_tot, tV, tD = r if r else ("", "", "", "")
        antigo = idx.get(_chave_par(cid, V["trap"], D["trap"]))
        if antigo and antigo.get("acertou") not in (None, ""): continue
        novo = {"corrida_id": cid, "registrado_em": datetime.now().strftime("%Y-%m-%d %H:%M"), "data": str(ctx.get("today"))[:10], "pista": ctx.get("pista", ""), "hora": ctx.get("hora", ""), "race": ctx.get("race", ""), "race_id": ctx.get("race_id", ""), "classe": ctx.get("classe", ""), "dist": ctx.get("dist", ""), "galgo_V": V["name"], "trap_V": V["trap"], "galgo_D": D["name"], "trap_D": D["trap"], "prob": round(prob_raw, 2), "prob_cal": "" if prob_cal is None else round(prob_cal, 2), "aprovado": int(aprovado), "criterios": crit, "exibido": int(aprovado), "tproj_V": fmt(tV), "tproj_D": fmt(tD), "delta_s": fmt(delta), "sd_total": fmt(sd_tot), "tadj_V": fmt(V.get("tadj")), "tadj_D": fmt(D.get("tadj")), "mtime_V": fmt(V.get("mtime")), "mtime_D": fmt(D.get("mtime")), "brt_V": fmt(V.get("brt")), "brt_D": fmt(D.get("brt")), "pos_V": "", "pos_D": "", "acertou": "", "versao": CFG["VERSAO"]}
        for k in _FLAGS: novo[k] = int(bool(flags.get(k)))
        if antigo: antigo.update(novo)
        else: rows.append(novo); idx[_chave_par(cid, V["trap"], D["trap"])] = novo; novos += 1
    _gravar_avb_csv(path, rows); return novos

def registrar_resultado(cid, ordem):
    txt = re.sub(r"[^0-9]", "", str(ordem or ""))
    traps = [int(c) for c in txt]
    if not traps: return 0
    if len(set(traps)) != len(traps) or any(t < 1 or t > 6 for t in traps): return -1
    pos = {t: i + 1 for i, t in enumerate(traps)}
    path = CFG["AVB_FILE"]; rows = _ler_avb_csv(path); n = 0
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
    calib_path = calib_path or CFG["CALIB_FILE"]; avb_path = avb_path or CFG["AVB_FILE"]
    if not (os.path.exists(calib_path) and os.path.exists(avb_path)): return 0
    rows = _ler_avb_csv(avb_path); pend = [r for r in rows if r.get("acertou") in (None, "")]
    if not pend: return 0
    datas = {r.get("data") for r in pend}; hist = {}
    with open(calib_path, newline="", encoding="utf-8") as f:
        for h in csv.DictReader(f):
            if h.get("data") in datas and h.get("fin") not in (None, ""): hist.setdefault((h.get("galgo"), h.get("data")), []).append(h)
    def achar(nome, data, dist, trap):
        ok = []
        for h in hist.get((nome, data), []):
            try:
                if dist not in (None, "") and h.get("dist") not in (None, "") and abs(float(h["dist"]) - float(dist)) >= 1: continue
            except Exception: pass
            ok.append(h)
        if len(ok) > 1: ok = [h for h in ok if str(h.get("trap")) == str(trap)] or ok
        if len(ok) != 1: return None
        try: return int(float(ok[0]["fin"]))
        except Exception: return None
    n = 0
    for r in pend:
        fv = achar(r.get("galgo_V"), r.get("data"), r.get("dist"), r.get("trap_V"))
        fd = achar(r.get("galgo_D"), r.get("data"), r.get("dist"), r.get("trap_D"))
        if fv is None or fd is None or fv == fd: continue
        r["pos_V"], r["pos_D"], r["acertou"] = fv, fd, (1 if fv < fd else 0); n += 1
    if n: _gravar_avb_csv(avb_path, rows)
    return n

def resolver_por_resultado(data_str, linhas):
    path = CFG["AVB_FILE"]
    if not linhas or not os.path.exists(path): return 0
    pos = {}
    for l in linhas:
        try: pos[str(l["nome"]).strip().lower()] = int(l["pos"])
        except Exception: pass
    rows = _ler_avb_csv(path); n = 0; dia = str(data_str)[:10]
    for r in rows:
        if r.get("acertou") not in (None, "") or r.get("data") != dia: continue
        pv = pos.get(str(r.get("galgo_V", "")).strip().lower()); pd_ = pos.get(str(r.get("galgo_D", "")).strip().lower())
        if pv is None or pd_ is None or pv == pd_: continue
        r["pos_V"], r["pos_D"], r["acertou"] = pv, pd_, (1 if pv < pd_ else 0); n += 1
    if n: _gravar_avb_csv(path, rows)
    return n

def corridas_pendentes(avb_path=None):
    rows = _ler_avb_csv(avb_path or CFG["AVB_FILE"]); vistos = []
    for r in rows:
        if r.get("acertou") in (None, "") and r.get("race_id"):
            k = (str(r["race_id"]), r.get("data"))
            if k not in vistos: vistos.append(k)
    return vistos

def contar_pendentes(avb_path=None):
    rows = _ler_avb_csv(avb_path or CFG["AVB_FILE"]); rows = [r for r in rows if r.get("versao") == CFG["VERSAO"]]
    res = sum(1 for r in rows if r.get("acertou") not in (None, ""))
    return len(rows) - res, res

def previsoes_bytes():
    path = CFG["AVB_FILE"]
    if not os.path.exists(path): return None
    with open(path, "rb") as f: return f.read()

def _wilson(k, n, z=1.96):
    if n <= 0: return 0.0, 1.0
    p = k / n; den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den; marg = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centro - marg), min(1.0, centro + marg)

def avaliar_previsoes(path=None, so_exibidos=False, versao="atual"):
    df = _df_resolvidos(path, versao)
    if df is None or df.empty: return None, {}
    if so_exibidos:
        df["exibido"] = pd.to_numeric(df.get("exibido"), errors="coerce"); df = df[df["exibido"] == 1]
    if df.empty: return None, {}
    pc = pd.to_numeric(df["prob_cal"], errors="coerce") if "prob_cal" in df.columns else pd.Series(np.nan, index=df.index)
    df["p_usada"] = pc.where(pc.notna(), df["prob"])
    df["faixa"] = pd.cut(df["p_usada"], [50, 55, 60, 65, 70, 75, 80, 100.01], right=False)
    linhas = []
    for faixa, g in df.groupby("faixa", observed=True):
        n = len(g); k = int(g["acertou"].sum()); lo, hi = _wilson(k, n)
        linhas.append({"faixa": str(faixa), "n": n, "prob_media": round(g["p_usada"].mean(), 1), "acerto_%": round(100 * k / n, 1), "ic95_inf_%": round(100 * lo, 1), "ic95_sup_%": round(100 * hi, 1), "odd_justa": round(n / k, 2) if k else None, "odd_segura": round(1 / lo, 2) if lo > 0 else None})
    tab = pd.DataFrame(linhas)
    p = (df["p_usada"] / 100.0).clip(0.001, 0.999); y = df["acertou"]
    met = {"n": int(len(df)), "corridas": int(df["corrida_id"].nunique()), "acerto": float(y.mean()), "prob_media": float(p.mean()), "brier": float(((p - y) ** 2).mean()), "logloss": float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())}
    return tab, met

def avaliar_criterios(path=None, versao="atual"):
    df = _df_resolvidos(path, versao)
    if df is None or df.empty: return None
    linhas = []
    for c in _FLAGS:
        if c not in df.columns: continue
        col = pd.to_numeric(df[c], errors="coerce"); v, f = df[col == 1], df[col == 0]
        linhas.append({"critério": c, "n_sim": len(v), "acerto_sim_%": round(100 * v["acertou"].mean(), 1) if len(v) else None, "n_não": len(f), "acerto_não_%": round(100 * f["acertou"].mean(), 1) if len(f) else None})
    return pd.DataFrame(linhas)

def calibrar_escala(path=None):
    from statistics import NormalDist
    nd = NormalDist(); df = _df_resolvidos(path, "atual")
    if df is None or len(df) < 30: return None
    z = np.array([nd.inv_cdf(min(max(p / 100.0, 0.001), 0.999)) for p in df["prob"]]); y = df["acertou"].values
    melhor = None
    for sc in np.arange(0.3, 2.01, 0.05):
        pp = np.array([nd.cdf(sc * x) for x in z]).clip(0.001, 0.999); ll = float(-(y * np.log(pp) + (1 - y) * np.log(1 - pp)).mean())
        if melhor is None or ll < melhor[1]: melhor = (float(sc), ll)
    return melhor

def montar_avbs(rank, ctx):
    elig = [d for d in rank if d.get("name") != "vacant" and not d.get("nd") and d.get("conf", 0) >= 20.0]
    if len(elig) < 2: return []
    try: resolver_pelo_historico()
    except Exception: pass
    params = _params_calibracao(); s1, linhas_log = [], []
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
    s1.sort(key=lambda x: (-x[2], -x[3]))
    try: registrar_previsoes(rank, linhas_log, ctx)
    except Exception: pass
    out = []
    for V, D, prob, crit in s1:
        AVB_META[(V["name"], D["name"])] = ("AVB", crit, params is not None)
        out.append((V, D, prob, True))
    return out

def get_rank_html(val, rank, max_rank):
    if val is None or rank is None: return "-"
    sup = {1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶"}.get(rank, "")
    color = "color:#12873a;font-weight:bold" if rank == 1 else ("color:#ff4b4b" if rank == max_rank and max_rank > 1 else "")
    return f"<span style='{color}'>{val:.2f}{sup}</span>"

_TBL_N = 0
def tbl(headers, rows, sticky=1, w1=None, w2=None):
    css = """<style>.dib-container{overflow-x:auto;width:100%;margin-bottom:20px}.dib-table{width:100%;border-collapse:collapse;text-align:center;font-size:15px;table-layout:auto}.dib-table th,.dib-table td{padding:8px 6px;border-bottom:1px solid rgba(128,128,128,0.2);white-space:nowrap;line-height:1.3}.dib-table th{background-color:rgba(128,128,128,0.1);font-weight:600}.dib-table td.sep{padding:0;height:2px;background-color:rgba(128,128,128,0.4)}.dib-table td.sep-avb{padding:0;height:1px;background-color:rgba(128,128,128,0.15)}"""
    css += (".dib-table th.stk,.dib-table td.stk{position:sticky;z-index:2;background-color:#ffffff;background-clip:padding-box;white-space:normal;overflow-wrap:anywhere;word-break:break-word;text-align:left;box-sizing:border-box}.dib-table th.stk{background-color:#f0f2f6;z-index:3}.dib-table .stk1{left:0}.dib-table .stk-last{box-shadow:2px 0 3px -1px rgba(128,128,128,0.45)}@media (prefers-color-scheme: dark){.dib-table th.stk,.dib-table td.stk{background-color:#0e1117}.dib-table th.stk{background-color:#262730}}")
    global _TBL_N; _TBL_N += 1; tid = f"dibt{_TBL_N}"
    if w1: css += f"#{tid} .stk1{{min-width:{w1}px;max-width:{w1}px;width:{w1}px}}#{tid} .stk2{{left:{w1}px}}"
    if w2: css += f"#{tid} .stk2{{min-width:{w2}px;max-width:{w2}px;width:{w2}px}}"
    css += "</style>"
    out = []
    for row in rows:
        if len(row) == 1 and "<hr" in str(row[0]): out.append(f"<tr><td class='sep' colspan='{len(headers)}'></td></tr>"); continue
        if len(row) == 1 and "sep-avb" in str(row[0]): out.append(f"<tr><td class='sep-avb' colspan='{len(headers)}'></td></tr>"); continue
        cells = []
        for ci, c in enumerate(row):
            cls = f"stk stk{ci+1}" + (" stk-last" if ci == sticky - 1 else "") if ci < sticky else ""
            if isinstance(c, str) and c.strip().startswith("<td"):
                if cls: c = c.replace("<td", f"<td class='{cls}'", 1); cells.append(c)
                else: cells.append(c)
            else: cells.append(f"<td class='{cls}'>{c}</td>" if cls else f"<td>{c}</td>")
        out.append("<tr>" + "".join(cells) + "</tr>")
    def _th(i, x): return f"<th class='stk stk{i+1}{' stk-last' if i == sticky - 1 else ''}'>{x}</th>" if i < sticky else f"<th>{x}</th>"
    thead = "".join(_th(i, x) for i, x in enumerate(headers))
    return f"{css}<div class='dib-container' id='{tid}'><table class='dib-table'><thead><tr>{thead}</tr></thead><tbody>{''.join(out)}</tbody></table></div>"

def nome_marcado(d):
    n = html.escape(d["name"])
    if d.get("alerta_trial", False): n += " ⚠️"
    if d.get("alvo", False): n += " 🎯"
    if d.get("bloqueado", False): n += " 🚫"
    return n

def brt_html(d):
    txt = d.get("brt_txt") or (f"BRT: {d['brt_raw']:.2f}" if d.get("brt_raw") else "")
    return f"<br><small style='color:#888;font-weight:normal'>{html.escape(txt)}</small>" if txt else ""

def trap_label(d): return f"{TRAP_EMOJI.get(d['trap'], '')} {d['trap']}"
def peso_txt(d): return f"{d['peso']:.1f}" if d.get("peso") else "-"
def grades_txt(d): return "-".join((r["grade"] or "?") for r in d.get("val", []))

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
        if d["nd"]: rows.append([trap_label(d), nome_marcado(d) + brt_html(d)] + ["-"] * 15); continue
        fat = "<br>".join(f"{k} ({v:+.1f})" for k, v in d["fatores"]) or "-"
        if d.get("remarks_translated"):
            rem_txt = ", ".join(set(d["remarks_translated"])); fat += f"<br><small style='color:#aaa'>{rem_txt}</small>"
        perfil_e = {"Limpo": "✅", "Irregular": "⚠️", "Trombador": "🔴"}[d["perfil"]]
        dias_txt = f"{d['dias']} ⚠️" if d['dias'] > 21 else str(d['dias'])
        split_display = get_rank_html(d["split"], rk["split"][i], max_rk["split"])
        msplit_display = get_rank_html(d["msplit"], rk["msplit"][i], max_rk["msplit"]) if d.get("msplit") else (f"<span style='color:#ffa500'>Pos: {d.get('msplit_pos', 0):.1f}</span>" if d.get("msplit_pos") else "-")
        rec_cell = get_rank_html(d["rec"], rk["rec"][i], max_rk["rec"]) + f"<br><small>{d['rec_txt'].split()[1]}</small>" if d.get("rec") is not None else "-"

        rows.append([
            trap_label(d), nome_marcado(d) + brt_html(d), f"{MEDALS.get(d['pos'], str(d['pos'])+'º')} {d['overall']:.1f}",
            f"{d['cat']:.1f} ({d['cat_mod']:+.0f})", fat, f"{perfil_e} {d['perfil']}", grades_txt(d), peso_txt(d), dias_txt,
            split_display, get_rank_html(d["time"], rk["time"][i], max_rk["time"]), msplit_display, get_rank_html(d["mtime"], rk["mtime"][i], max_rk["mtime"]),
            get_rank_html(d["tadj"], rk["tadj"][i], max_rk["tadj"]), get_rank_html(d.get("metrica"), rk["metrica"][i], max_rk["metrica"]), rec_cell, f"{d['conf']:.0f}%"
        ])
    return tbl(["Trap", "Galgo", "Overall", "Cat", "Fatores", "Perfil", "Grades", "Peso", "Dias", "M. Split", "M. Time", "Méd. Split", "Méd. Time", "Time Ajust.", "Métrica", "Recup. Média", "Conf."], rows, sticky=2, w1=64, w2=125)

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
        meta = AVB_META.get((V["name"], D["name"])); score_crit = meta[1] if meta else 0; calibrada = bool(meta[2]) if meta and len(meta) > 2 else False
        if i > 0: rows.append(["<hr>"])
        ov_v, ov_d = fmt_pair(V['overall'], D['overall'], False, 1); cat_v, cat_d = fmt_pair(V['cat'], D['cat'], False, 1)
        sp_v, sp_d = fmt_pair(V['split'], D['split'], True, 2); t_v, t_d = fmt_pair(V['time'], D['time'], True, 2)
        if V.get("msplit") and D.get("msplit"): ms_v, ms_d = fmt_pair(V['msplit'], D['msplit'], True, 2)
        elif V.get("msplit_pos") and D.get("msplit_pos"): ms_v, ms_d = fmt_pair(V['msplit_pos'], D['msplit_pos'], True, 1)
        else: ms_v, ms_d = "-", "-"
        mt_v, mt_d = fmt_pair(V['mtime'], D['mtime'], True, 2); ta_v, ta_d = fmt_pair(V['tadj'], D['tadj'], True, 2)
        me_v, me_d = fmt_pair(V.get('metrica'), D.get('metrica'), True, 2)
        rec_v, rec_d = fmt_pair(V.get('rec'), D.get('rec'), False, 1, True)
        prob_cell = (f"<td rowspan='2' style='vertical-align:middle;font-weight:bold;font-size:16px;'><span style='color:#12873a'>{prob:.1f}%</span><br><small style='color:#aaa;font-weight:normal'>{score_crit}/6 crit.</small><br><small style='color:#aaa;font-weight:normal'>{'calibrada' if calibrada else 'bruta'}</small></td>")
        rows.append([f"{badge}{trap_label(V)} - {nome_marcado(V)}{brt_html(V)}", ov_v, cat_v, V['perfil'], grades_txt(V), peso_txt(V), f"{V['dias']}", sp_v, t_v, ms_v, mt_v, ta_v, me_v, rec_v, f"{V['conf']:.0f}%", prob_cell])
        rows.append([f"{trap_label(D)} - {nome_marcado(D)}{brt_html(D)}", ov_d, cat_d, D['perfil'], grades_txt(D), peso_txt(D), f"{D['dias']}", sp_d, t_d, ms_d, mt_d, ta_d, me_d, rec_d, f"{D['conf']:.0f}%"])
    heads = ["AvB", "Overall", "Cat", "Perfil", "Grades", "Peso", "Dias", "M. Split", "M. Time", "Méd. Split", "Méd. Time", "Time Ajust.", "Métrica", "Recup.", "Conf.", "Probabilidade"]
    st.markdown(tbl(heads, rows, sticky=1, w1=190), unsafe_allow_html=True)

def painel_validacao():
    with st.expander("📊 Validação dos AvBs (acerto real × probabilidade)"):
        try: tab, met = avaliar_previsoes(so_exibidos=True); df_all = _df_resolvidos()
        except Exception as e: st.info(f"Não foi possível ler as previsões: {e}"); return
        if tab is None or tab.empty: st.info(f"Ainda não há AvBs exibidos com resultado registrado nesta versão do modelo (`{CFG['VERSAO']}`). Registre a ordem de chegada de cada corrida.")
        else:
            st.markdown(f"**{met['n']} AvBs exibidos resolvidos em {met['corridas']} corridas** · acerto real **{100*met['acerto']:.1f}%** vs. prob. média {100*met['prob_media']:.1f}% · Brier {met['brier']:.3f} · log-loss {met['logloss']:.3f}")
            if met["n"] < 150: st.warning("Amostra pequena: com menos de ~150 confrontos a taxa de acerto tem margem de erro grande (veja ic95_inf/sup). Mantenha stakes baixos até a taxa se sustentar.")
            st.markdown("Compare **acerto_%** com **prob_media**. A **odd_segura** usa o limite inferior do intervalo: só vale pagar abaixo dela se você aceitar o pior cenário.")
            st.dataframe(tab, hide_index=True)
        n_res = 0 if df_all is None else len(df_all)
        try:
            pend, resolv = contar_pendentes()
            st.markdown(f"Resultados: **{resolv} confrontos resolvidos** e {pend} pendentes. Os resultados são preenchidos sozinhos quando os galgos aparecem em análises seguintes; a digitação manual é opcional.")
        except Exception: pass
        params = _params_calibracao()
        if params: st.markdown(f"Calibração **ativa** (n={params['n']}): prob_cal = sigmoid({params['a']:.2f}·logit(prob_bruta) + {params['b']:+.2f})")
        else: st.markdown(f"Calibração **inativa**: {n_res} de {CFG['AVB']['calib_min_n']} confrontos resolvidos (todos os pares registrados).")
        crit = avaliar_criterios()
        if crit is not None and not crit.empty: st.markdown("**Quais critérios realmente separam acerto de erro** (todos os pares registrados):"); st.dataframe(crit, hide_index=True)

_DL_N = 0
def gerar_observacoes(rank, avbs, ctx):
    if not rank: return
    st.markdown("---")
    _dados_cal = calibracao_bytes()
    if _dados_cal:
        global _DL_N; _DL_N += 1
        with st.expander("🧪 Dados para calibração (CSV)"):
            st.download_button("Baixar calibracao_corridas.csv", _dados_cal, file_name="calibracao_corridas.csv", mime="text/csv", key=f"dl_calib_{_DL_N}")
    cont, aprox, desc = diagnostico_remarks(rank)
    with st.expander(f"🔎 Leitura dos remarks ({cont['exato'] + cont['alias'] + cont['aprox']} lidos, {cont['desconhecido']} não reconhecidos)"):
        if desc: st.markdown("**Não reconhecidos (não afetam o tempo):** " + ", ".join(f"`{k}` ×{v}" for k, v in sorted(desc.items())))
        if aprox: st.markdown("**Interpretados por aproximação:** " + ", ".join(f"`{k}` → `{v}`" for k, v in sorted(aprox.items())))
        if not desc and not aprox: st.markdown("Todos os remarks foram reconhecidos exatamente.")
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
    st.markdown("#### 🏁 Leitura Tática da Corrida")

    elegiveis = [d for d in rank if not d.get("bloqueado")]
    bloqueados = [d for d in rank if d.get("bloqueado")]
    if not elegiveis: st.warning("Todos os cães estão bloqueados ou sem dados suficientes para esta corrida."); return

    fav_app = elegiveis[0]; insights = []
    pp_str = str(ctx.get("post_pick") or ""); pp_traps = [int(c) for c in pp_str if c.isdigit()]
    pp_fav_trap = pp_traps[0] if pp_traps else None; pp_fav = next((d for d in elegiveis if d["trap"] == pp_fav_trap), None)

    if pp_fav and pp_fav["trap"] != fav_app["trap"]:
        insights.append(f"**⚔️ Duelo de Favoritos:** O mercado elegeu o **{TRAP_EMOJI.get(pp_fav['trap'])} {pp_fav['name']}** (Post Pick 1), mas o App crava o **{TRAP_EMOJI.get(fav_app['trap'])} {fav_app['name']}** ({fav_app['overall']:.1f} de Overall) como o verdadeiro dono da prova. É um choque direto.")
    else:
        insights.append(f"**🤝 Consenso Total:** O mercado e o App concordam que o **{TRAP_EMOJI.get(fav_app['trap'])} {fav_app['name']}** é o cão a ser batido. Overall {fav_app['overall']:.1f} e Confiança {fav_app['conf']:.0f}%.")

    trombadores_internos = [d for d in elegiveis if d["perfil"] == "Trombador" and d["trap"] <= 4]
    if len(trombadores_internos) >= 2:
        nomes_tromb = " e ".join([f"{TRAP_EMOJI.get(d['trap'])} {d['name']}" for d in trombadores_internos]); clean_candidates = [d for d in elegiveis if d["perfil"] != "Trombador"]
        if clean_candidates:
            c_clean = clean_candidates[0]
            if c_clean["trap"] >= 5: local = "por fora"
            elif c_clean["trap"] == 4: local = "pelo meio"
            else: local = "no trilho (por dentro)"
            insights.append(f"**💥 Risco de Colisão:** O {nomes_tromb} são Trombadores e correm nas traps internas. Se eles se chocarem na 1ª curva, o {TRAP_EMOJI.get(c_clean['trap'])} {c_clean['name']}, que corre {local} e está limpo, pode herdar a pista livre.")
        else: insights.append(f"**💥 Risco de Colisão:** O {nomes_tromb} são Trombadores e correm nas traps internas. A briga pelo trilho será intensa.")

    if bloqueados:
        b = max(bloqueados, key=lambda x: x["overall"])
        if b["overall"] > fav_app["overall"]:
            insights.append(f"**🚫 Armadilha do Histórico:** O {TRAP_EMOJI.get(b['trap'])} {b['name']} tem Overall bruto de {b['overall']:.1f}, mas o App o bloqueou. O histórico dele nessa distância é curto ou ruim. Não caia na armadilha da odd baixa.")

    tadj_rank = sorted([d for d in elegiveis if d.get("tadj")], key=lambda x: x["tadj"])
    if len(tadj_rank) >= 3:
        top2_tadj_names = {d["name"] for d in tadj_rank[:2]}
        for z in elegiveis:
            if z["pos"] >= 4 and z["name"] in top2_tadj_names:
                is_mkt_zebra = True
                if pp_traps and z["trap"] in pp_traps[:2]: is_mkt_zebra = False
                if is_mkt_zebra: insights.append(f"**🦓 A Zebra Escondida:** O {TRAP_EMOJI.get(z['trap'])} {z['name']} está apenas em {z['pos']}º no App, mas tem o **{z['tadj']:.2f}** de Tadj (Top 2 da prova). O mercado também esqueceu dele no Post Pick. É a aposta de risco/retorno mais alta da corrida.")

    alvos = [d for d in rank if d.get("alvo")]
    if alvos:
        nomes_alvo = ", ".join([f"{TRAP_EMOJI.get(a['trap'])} {a['name']}" for a in alvos])
        insights.append(f"**🎯 O Bode Expiatório:** O {nomes_alvo} foi marcado como Alvo. Sem largada e com recuperação negativa, ele vai ficar preso no bolo. Evite apostar nele como vencedor.")

    if not insights: insights.append("**📊 Corrida de Rotina:** O favorito tem dados sólidos, não há trombadores em excesso e as traps estão bem distribuídas. O App sugere seguir o Overall sem grandes riscos táticos.")
    for ins in insights[:4]: st.markdown(f"- {ins}")
