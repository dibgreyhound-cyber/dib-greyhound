# -*- coding: utf-8 -*-
import re
import html
import math
import json
from datetime import datetime
import numpy as np
import pandas as pd
import requests
import streamlit as st

# =====================================================================
# DICIONÁRIO DE REMARKS
# =====================================================================
DICIONARIO_REMARKS = {
    "ald": "Liderou Sempre", "awk": "Desajeitado", "blk": "Trombada Forte",
    "bmp": "Trombou na Curva", "chl": "Desafiado na Curva", "clrrn": "Corrida Limpa",
    "crd": "Truncado na Curva", "crdnrln": "Truncado no Final", "crdrnln": "Truncado na Reta",
    "crdrnup": "Truncado no Início", "crmp": "Espaço Apertado", "disp": "Disputou",
    "dsp": "Disputou na Curva", "dis pld": "Liderou com Disputa", "ep": "Ritmo Acelerado",
    "evch": "Evitou Choque", "fcd": "Forçado a Algo", "fcdck": "Forçado na Curva",
    "fell": "Caiu", "hldon": "Posição Mantida", "imp": "Impedido", "jmp": "Saltou",
    "jmplate": "Saltou Atrasado", "ko": "Derrubado", "lame": "Manco", "ld": "Liderou a Curva",
    "ldnrln": "Liderou na Reta", "in": "Linha de Chegada", "mid": "Corre pelo Meio",
    "msdbrk": "Passou Reto", "on": "Até o Final", "qaw": "Largada Rápida", "rls": "Corre por Dentro",
    "rnln": "Reta Linha", "rnon": "Manteve Galope", "rnonwll": "Galope até o Final",
    "rnup": "Distância Trap 1", "saw": "Largada Lenta", "snled": "Liderou desde o Início",
    "stmb": "Tropeçou", "strfn": "Chegada Forte", "stt": "Início", "struck": "Atingido",
    "styd": "Ficou", "turnedin trps": "Ficou na Trap", "vsaw": "Largada Muito Lenta",
    "vw": "Corredor Aberto", "w": "Curva Ampla"
}

# =====================================================================
# CONFIGURAÇÃO GLOBAL (DIB 8.0 - Calibrado por Backtest)
# =====================================================================
CFG = {
    "N_RUNS": 5, "N_CORREDORES": 6, "CAT_BONUS": 1.5,
    "TRAFFIC_ADJ": {"baulk": 0.20, "crd": 0.10, "bmp": 0.10, "fcd": 0.10},
    "PERFIL_PTS": {"Limpo": 10.0, "Irregular": 5.0, "Trombador": 0.0},
    "TRAP_VAZIA": 6.0, 
    "TRAFEGO_SEVERO": -4.0, 
    "CONF_MIN_VENCEDOR": 40.0,

    "VEL_PTS": {"tadj": 25, "mtime": 20, "msplit": 25, "ritmo": 10},
    "CONSIST_PTS": 10, "PICO_PTS": 10, "RECUP_PTS": 10,
}

TRAP_BIAS = {1: 4.0, 2: 2.0, 3: 2.0, 4: 2.0, 5: 0.0, 6: 0.0}

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

def traffic_penalty(rem, peso=31.0):
    s = str(rem or "").lower()
    pen = 0.0
    graves = sum(s.count(k) for k in ("baulk", "fell", "ko", "msdbrk"))
    if graves > 0: pen += graves * 0.30
    moderados = sum(s.count(k) for k in ("bmp", "crd", "fcd", "crmp"))
    if moderados > 0: pen += moderados * 0.15
    return min(pen, 0.50)

def not_free(rem):
    return bool(RE_NOFREE.search(str(rem or "").lower()))

def first_bend_traffic(rem):
    s = str(rem or "").lower()
    if "baulk" in s: return True
    return bool(re.search(rf"{RE_TRAF.pattern}\s*[,/\-]?\s*1\b", s))

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
    info = {"pista": "", "hora": "", "race": "", "classe": "", "post_pick": ""}
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
                "trap": trap or 0, "peso_atual": to_float(dog.get("weight")), "runs": runs,
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

def oficial(r, ctx):
    g = str(r["grade"] or "").strip().upper()
    if not g or g.startswith("HP"):
        return False
    return (r["dist"] is not None
            and abs(r["dist"] - ctx["dist"]) < 1
            and r["caltm"] is not None and r["caltm"] > 0)

def analisar_galgo(dog, ctx):
    if dog.get("name") == "vacant":
        return {"name": "vacant", "trap": dog["trap"], "runs": [], "val": [], "nd": True,
                "conf": 0.0, "bloqueado": False, "alvo": False, "pos": 0, "elegivel": False,
                "alerta_trial": False, "n_trials": 0}

    runs = sorted(dog["runs"], key=lambda r: r["date"] or datetime.min, reverse=True)[:CFG["N_RUNS"]]
    R = [r for r in runs if oficial(r, ctx)]

    n_trials = sum(1 for r in runs if is_trial_grade(r["grade"]))

    d = {"name": dog["name"], "trap": dog["trap"], "runs": runs, "val": R, "nd": not R,
         "conf": min(100.0, len(R) * 20.0), "bloqueado": False, "alvo": False, "pos": 0, "elegivel": False,
         "alerta_trial": n_trials >= 3, "n_trials": n_trials}

    ultima_any = runs[0] if runs else None
    d["dias"] = (ctx["today"] - ultima_any["date"]).days if ultima_any and ultima_any["date"] else 0

    if not R: return d

    today_n = ctx.get("classe_n")
    last_n = grade_num(R[0]["grade"])
    mod = 0.0
    if today_n and last_n:
        mod = CFG["CAT_BONUS"] if today_n > last_n else (-CFG["CAT_BONUS"] if today_n < last_n else 0.0)

    valid_grades = [grade_num(r["grade"]) for r in R if grade_num(r["grade"]) is not None]
    avg_grade_n = sum(valid_grades) / len(valid_grades) if valid_grades else (today_n or 0)
    
    base = 13.0 - (avg_grade_n * 0.6)
    d["cat_mod"], d["cat"] = mod, base + mod

    d["peso"] = dog.get("peso_atual") or R[0]["weight"]
    d["split"], d["time"] = R[0]["split"], R[0]["caltm"]

    has_split = any(r["split"] for r in R)
    if has_split:
        d["msplit"] = float(np.mean([r["split"] for r in R if r["split"] is not None]))
        d["msplit_pos"] = None
    else:
        pos_curve = [bends_digits(r["bends"])[0] for r in R if bends_digits(r["bends"])]
        d["msplit"] = None
        d["msplit_pos"] = float(np.mean(pos_curve)) if pos_curve else None

    d["mtime"] = float(np.mean([r["caltm"] for r in R if r["caltm"] is not None])) if any(r["caltm"] for r in R) else None

    if has_split:
        d["ritmo"] = d["mtime"] - d["msplit"] if d["mtime"] and d["msplit"] else None
    else:
        d["ritmo"] = None

    peso_atual = d["peso"] or 31.0
    adj_times = [r["caltm"] - traffic_penalty(r["remarks"], peso_atual) for r in R]
    d["tadj"] = float(np.mean(adj_times)) if adj_times else None

    cal = [r["caltm"] for r in R]
    d["sd"] = float(np.std(cal)) if len(cal) > 1 else 0.0
    d["pico"] = min(cal) if cal else None

    recs = [(bends_digits(r["bends"])[0] - r["fin"]) / CFG["N_CORREDORES"] * 100.0 for r in R if bends_digits(r["bends"]) and r["fin"]]
    d["rec"] = float(np.mean(recs)) if recs else 0.0
    d["rec_txt"] = f"{d['rec']:+.2f}% ({'Ganhou' if d['rec'] > 0.005 else ('Perdeu' if d['rec'] < -0.005 else 'Manteve')})"

    n_traf = sum(count_traf(r["remarks"]) for r in R)
    d["perfil"] = "Limpo" if n_traf <= 1 else ("Irregular" if n_traf == 2 else "Trombador")

    d["early_cnt"] = sum(1 for r in R if any(re.match(r"^(ep|ald|snld|ld)", t) for t in re.split(r"[,\s]+", str(r["remarks"]).lower())))
    d["saw_cnt"] = sum(1 for r in R if any(t.startswith("saw") or t.startswith("vsaw") for t in re.split(r"[,\s]+", str(r["remarks"]).lower())))
    d["fbt_cnt"] = sum(1 for r in R if first_bend_traffic(r["remarks"]))

    d["remarks_translated"] = []
    for r in R:
        for token in re.split(r"[,\s]+", str(r["remarks"]).lower()):
            if token in DICIONARIO_REMARKS:
                d["remarks_translated"].append(DICIONARIO_REMARKS[token])

    return d

def finalizar(ds, ctx):
    ok = [d for d in ds if not d["nd"]]
    vac = [t for t in range(1, 7) if t not in {d["trap"] for d in ds if d["name"] != "vacant"}]

    ms_rank = sorted([d for d in ok if d.get("msplit") is not None], key=lambda x: x["msplit"])
    if not ms_rank:
        ms_rank = sorted([d for d in ok if d.get("msplit_pos") is not None], key=lambda x: x["msplit_pos"])
    top3_ms = {d["name"] for d in ms_rank[:3]}
    top_split_name = ms_rank[0]["name"] if ms_rank else None
    ctx["top3_ms"] = top3_ms

    ritmo_rank = sorted([d for d in ok if d.get("ritmo")], key=lambda x: x["ritmo"])
    top3_ritmo = {d["name"] for d in ritmo_rank[:3]}
    ctx["top3_ritmo"] = top3_ritmo

    def pts_prop(key, maxp, d, invert=True):
        vals = [x[key] for x in ok if x.get(key) is not None]
        if d.get(key) is None or not vals: return 0.0
        lo, hi = min(vals), max(vals)
        if hi == lo: return float(maxp / 2.0) 
        return maxp * (hi - d[key]) / (hi - lo) if invert else maxp * (d[key] - lo) / (hi - lo)

    for d in ok:
        pts_cat = d["cat"] * 2.0 
        pts_perfil = CFG["PERFIL_PTS"][d["perfil"]]
        pts_trap = TRAP_BIAS.get(d["trap"], 0.0)
        
        pts_trial = -25.0 if d.get("n_trials", 0) >= 3 else 0.0

        vel = (pts_prop("tadj", CFG["VEL_PTS"]["tadj"], d) +
               pts_prop("mtime", CFG["VEL_PTS"]["mtime"], d) +
               (pts_prop("msplit", CFG["VEL_PTS"]["msplit"], d) if d["msplit"] else (CFG["VEL_PTS"]["msplit"] * (1 - (d["msplit_pos"] / 6)) if d.get("msplit_pos") else 0)) +
               pts_prop("ritmo", CFG["VEL_PTS"]["ritmo"], d))

        f = []
        if d["early_cnt"] > 0 and d["perfil"] == "Limpo":
            f.append(("Ritmo Acelerado", min(d["early_cnt"], 2) * 4.0)) 
        if d["saw_cnt"] > 0:
            f.append(("Largada Lenta", min(d["saw_cnt"], 2) * -4.0)) 
        if d["fbt_cnt"] > 0:
            f.append(("Tráfego 1ª Curva", min(d["fbt_cnt"], 2) * -3.0))
        if any(abs(d["trap"] - v) == 1 for v in vac):
            f.append(("Trap Vazia", CFG["TRAP_VAZIA"]))
            
        if d["perfil"] == "Trombador" and d["trap"] in [1,2,3,4,5] and d["name"] not in top3_ms:
            if not (d.get("msplit_pos") and d["msplit_pos"] <= 2):
                if d.get("rec", 0) < -25.0:
                    f.append(("Tráfego Severo", CFG["TRAFEGO_SEVERO"]))

        if len(top3_ms) >= 3 and d["saw_cnt"] > 0 and d.get("rec", 0) > 10.0:
            f.append(("Conflito Pace (Favorável)", 5.0)) 

        d["fatores"] = f
        d["overall"] = vel + pts_cat + pts_perfil + pts_trap + pts_trial + pts_prop("sd", CFG["CONSIST_PTS"], d, True) + pts_prop("pico", CFG["PICO_PTS"], d, True) + pts_prop("rec", CFG["RECUP_PTS"], d, False) + sum(v for _, v in f)

    ok.sort(key=lambda x: -x["overall"])
    for i, d in enumerate(ok, 1):
        d["pos"] = i
        d["bloqueado"] = d["conf"] < CFG["CONF_MIN_VENCEDOR"]
        
        top2_safe = (i <= 2) and (d.get("rec", -100) >= -10.0)
        d["alvo"] = (d["name"] not in top3_ms) and (d["name"] != top_split_name) and (d.get("rec", 0) < -30.0) and not top2_safe
        
        d["elegivel"] = not d["bloqueado"]
    return ok, top3_ms

def calc_prob(V, D, rank, ctx):
    if V.get("overall") is None or D.get("overall") is None: return 50.0

    diff = V["overall"] - D["overall"]

    pp = str(ctx.get("post_pick") or "")
    if pp and str(V["trap"]) in pp: diff += 1.5
    if pp and str(D["trap"]) in pp: diff -= 1.5

    trap_bias = {1: 1.0, 2: 0.5, 3: 0.0, 4: 0.0, 5: -0.5, 6: -1.0}
    diff += trap_bias.get(V["trap"], 0.0)
    diff -= trap_bias.get(D["trap"], 0.0)

    try:
        prob = 100.0 / (1.0 + math.exp(-0.015 * diff))
    except OverflowError:
        prob = 100.0 if diff > 0 else 0.0

    return max(25.0, min(75.0, prob))

def montar_avbs(rank, ctx):
    elig = [d for d in rank if d.get("name") != "vacant" and not d.get("nd") and d.get("conf", 0) >= 20.0]
    if len(elig) < 2: return []

    s1 = []
    perdedores_usados = set() 

    for i in range(len(elig)):
        for j in range(i+1, len(elig)):
            A, B = elig[i], elig[j]
            
            if A.get("bloqueado", False) or A.get("alvo", False) or B.get("bloqueado", False) or B.get("alvo", False):
                continue

            prob_A = calc_prob(A, B, rank, ctx)

            if prob_A >= 50.0:
                V, D, prob = A, B, prob_A
            else:
                V, D, prob = B, A, 100.0 - prob_A

            if D["name"] in perdedores_usados:
                continue

            if prob >= 58.0:
                c1 = (V["name"] in ctx.get("top3_ms", set())) and (D["name"] not in ctx.get("top3_ms", set()))
                c2 = V.get("cat", 0) >= D.get("cat", 0)
                c3 = (V.get("split") is not None and D.get("split") is not None and V["split"] < D["split"])
                c4 = (V.get("mtime") is not None and D.get("mtime") is not None and V["mtime"] < D["mtime"])
                c5 = (V.get("rec") is not None and D.get("rec") is not None and V["rec"] >= -10.0 and V["rec"] > D["rec"])

                is_premium = sum([c1, c2, c3, c4, c5]) >= 3
                
                s1.append((V, D, prob, is_premium))
                perdedores_usados.add(D["name"]) 

    return sorted(s1, key=lambda x: -x[2])

def get_rank_html(val, rank, max_rank):
    if val is None or rank is None: return "-"
    sup = {1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶"}.get(rank, "")
    color = "color:#12873a;font-weight:bold" if rank == 1 else ("color:#ff4b4b" if rank == max_rank and max_rank > 1 else "")
    return f"<span style='{color}'>{val:.2f}{sup}</span>"

def tbl(headers, rows):
    css = """<style>.dib-container{overflow-x:auto;width:100%;margin-bottom:20px}.dib-table{width:100%;border-collapse:collapse;text-align:center;font-size:15px;table-layout:auto}.dib-table th,.dib-table td{padding:8px 6px;border-bottom:1px solid rgba(128,128,128,0.2);white-space:nowrap;line-height:1.3}.dib-table th{background-color:rgba(128,128,128,0.1);font-weight:600}.dib-table td.sep{padding:0;height:2px;background-color:rgba(128,128,128,0.4)}.dib-table td.sep-avb{padding:0;height:1px;background-color:rgba(128,128,128,0.15)}</style>"""
    out = []
    for row in rows:
        if len(row) == 1 and "<hr" in str(row[0]): out.append(f"<tr><td class='sep' colspan='{len(headers)}'></td></tr>"); continue
        if len(row) == 1 and "sep-avb" in str(row[0]): out.append(f"<tr><td class='sep-avb' colspan='{len(headers)}'></td></tr>"); continue
        cells = [c if isinstance(c, str) and c.strip().startswith("<td") else f"<td>{c}</td>" for c in row]
        out.append("<tr>" + "".join(cells) + "</tr>")
    return f"{css}<div class='dib-container'><table class='dib
