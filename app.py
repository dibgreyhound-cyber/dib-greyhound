# -*- coding: utf-8 -*-
"""
app.py - Versão Ajustada e Estável para o DIB GREYHOUND
"""
import re
import time
import json
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="DIB GREYHOUND", layout="wide", initial_sidebar_state="auto")
import dib_core as dib

BASE = "https://greyhoundbet.racingpost.com"
LISTA_CANDIDATOS = [
    BASE + "/meeting/blocks.sd?r_date={d}&blocks=header%2Clist",
    BASE + "/meeting/blocks.sd?r_date={d}&blocks=list",
    BASE + "/meeting-list/blocks.sd?r_date={d}&blocks=list",
]
KEYS = {
    "id": ["raceId", "race_id", "rid"],
    "hora": ["raceDate", "offTime", "scheduledTime", "displayTime", "raceTime", "time", "startTime"],
    "pista": ["trackName", "track", "meetingName", "courseName", "venue"],
    "num": ["raceTitle", "raceNum", "raceNumber", "rNum", "number", "raceNo"],
    "grade": ["raceClass", "raceGrade", "grade", "class", "raceClassDesc"],
    "dist": ["distMetres", "distMeters", "distance", "dist", "raceDistance"],
    "clip": ["clipId", "clip_id", "videoId", "replayId"],
}


class _Http:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*", "Accept-Language": "en-GB,en;q=0.9",
            "Referer": BASE + "/", "Origin": BASE})
        self.pronto = False

    def get(self, url, headers=None, timeout=15):
        if not self.pronto:
            try: self.s.get(BASE + "/", timeout=8)
            except Exception: pass
            self.pronto = True
        try:
            r = self.s.get(url, timeout=timeout)
            return r
        except Exception as e:
            raise e


@st.cache_resource
def http():
    return _Http()


dib.requests = http()


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


def botao_copiar(texto):
    texto_js = json.dumps(texto)
    html = f"""
    <html>
    <head>
    <style>
    .copy-btn {{
        background-color: #ff4b4b; color: white; border: none; padding: 12px 20px;
        border-radius: 8px; cursor: pointer; font-size: 16px; font-weight: bold; width: 100%; transition: 0.2s;
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
            document.getElementById("copyBtn").innerText = "✅ Texto Copiado!";
            setTimeout(() => {{
                document.getElementById("copyBtn").innerText = "📋 Copiar Análise para o Chat";
            }}, 4000);
        }} catch (err) {{ document.getElementById("copyBtn").innerText = "❌ Erro"; }}
    }});
    </script>
    </body>
    </html>
    """
    components.html(html, height=65)


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
    def walk(o, pista_ctx):
        if isinstance(o, dict):
            p = _get(o, "pista")
            if isinstance(p, str): pista_ctx = p
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
                }
            for v in o.values(): walk(v, pista_ctx)
        elif isinstance(o, list):
            for v in o: walk(v, pista_ctx)
    walk(obj, "")
    return sorted(achados.values(), key=lambda c: (c["hora"], c["pista"]))


def tentar(urls, parser):
    tentativas, achado, primeira = [], [], None
    for u in urls:
        curto = u.replace(BASE, "")
        time.sleep(0.3)
        try:
            r = http().get(u, timeout=8)
        except Exception as e:
            tentativas.append({"Status": f"erro", "Achados": 0, "Endereço": curto})
            continue
        js = None
        if r.status_code == 200:
            try: js = r.json()
            except Exception: pass
        res = parser(js) if js is not None else []
        tentativas.append({"Status": r.status_code, "Achados": len(res), "Endereço": curto})
        if res:
            achado = res
            break
    return achado, tentativas, primeira


@st.cache_data(ttl=120, show_spinner=False)
def buscar_lista(data_str, url_custom):
    urls = ([url_custom.replace("{data}", data_str)] if url_custom.strip() else []) \
        + [u.format(d=data_str) for u in LISTA_CANDIDATOS]
    return tentar(urls, achar_corridas)


@st.cache_data(ttl=300, show_spinner=False)
def buscar_form_raw(race_id, data_str):
    try:
        r = http().get(f"{BASE}/card/blocks.sd?race_id={race_id}&r_date={data_str}&blocks=form", timeout=15)
        if r.status_code != 200: return []
        return r.json().get("form", {}).get("dogs", [])
    except Exception:
        return []


def hora_br(hhmm):
    h, m = [int(x) for x in hhmm.split(":")]
    t = datetime(2000, 1, 1, h, m) - timedelta(hours=3)
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


def tabela_html(headers, rows):
    st.markdown(dib.tbl(headers, rows), unsafe_allow_html=True)


def _link(url, rotulo):
    try: st.link_button(rotulo, url)
    except Exception: st.markdown(f"[{rotulo}]({url})")


def mostrar_replay(c):
    link_site_replay = f"{BASE}/#result-meeting-result/race_id={c['id']}&r_date={c['data']}"
    st.info("🎬 Para assistir ao replay com o token de segurança atualizado do site:")
    _link(link_site_replay, "Abrir Resultado e Replay no Racing Post")


BAR_STYLE = {
    1: ("background:#c62828;", "invert"), 2: ("background:#1d4ed8;", "invert"),
    3: ("background:#eeeeee;", "dark"), 4: ("background:#151515;", "invert"),
    5: ("background:#f26b21;", "invert"), 6: ("background:repeating-linear-gradient(180deg,#111 0 3px,#fff 3px 6px);", "invert"),
}


def grafico_predictor(ds):
    com = [d for d in ds if not d.get("nd") and d.get("overall") is not None]
    if not com: return ""
    mx = max(d["overall"] for d in com)
    linhas = []
    for d in sorted(ds, key=lambda x: x["trap"]):
        t = d["trap"]
        estilo, icone = BAR_STYLE.get(t, ("background:#888;", "invert"))
        if d.get("nd") or d.get("overall") is None:
            fill = ""
        else:
            w = 100.0 if mx <= 0 else max(4.0, min(100.0, d["overall"] / mx * 100.0))
            filtro = "brightness(0)" if icone == "dark" else "brightness(0) invert(1)"
            fill = (f"<div style='position:relative;width:{w:.1f}%;height:100%;border-radius:14px;{estilo}'>"
                    f"<span style='position:absolute;right:6px;top:50%;transform:translateY(-50%);font-size:15px;filter:{filtro};'>🐕</span></div>")
        linhas.append(f"<div style='display:flex;align-items:center;gap:8px;margin:7px 0'>{badge(t)}"
                      f"<div style='flex:1;height:24px;background:#0a2a52;border-radius:14px;overflow:hidden'>{fill}</div></div>")
    return ("<div style='background:#143f6f;border-radius:16px;padding:16px 12px 8px;max-width:640px;margin:8px 0;position:relative'>"
            "<div style='position:absolute;top:-1px;left:10px;background:#d32f2f;color:#fff;font-weight:700;font-size:13px;padding:3px 14px;border-radius:0 0 12px 12px'>Predictor</div>"
            "<div style='height:10px'></div>" + "".join(linhas) + "</div>")


def preparar(race_id, r_date, c, classe_in, dist_in, pp_in, so_antes=False):
    cache = st.session_state.setdefault("cache_corridas", {})
    chave = f"{race_id}|{r_date}"
    if chave not in cache:
        try:
            res = dib.extrair_dados_racingpost(f"{BASE}/#card/race_id={race_id}&r_date={r_date}")
            if not res or not res[0]: return None
            cache[chave] = res
        except Exception:
            return None
    dogs, meta, meta_info = cache[chave]
    if so_antes:
        dogs = [dict(d, runs=[r for r in d["runs"] if (r.get("date_str") or "") < r_date]) for d in dogs]
    classe = (classe_in or c.get("grade") or (meta_info or {}).get("classe") or "").strip().upper()
    dist = float(dist_in or c.get("dist") or 0)
    if not dist:
        ds_all = [r["dist"] for d in dogs for r in d["runs"] if r["dist"]]
        dist = float(pd.Series(ds_all).mode().iloc[0]) if ds_all else 480.0
    pp = pp_in or (meta_info or {}).get("post_pick", "")
    ctx = {"dist": dist, "today": dib.parse_date(meta["r_date"]), "classe_n": dib.grade_num(classe),
           "post_pick": [int(x) for x in re.findall(r"\d", pp)],
           "vazias": [t for t in range(1, 7) if t not in {d["trap"] for d in dogs if d["name"] != "vacant"}]}
    ds = [dib.analisar_galgo(d, ctx) for d in dogs]
    rank, _ = dib.finalizar(ds, ctx)
    ds.sort(key=lambda d: d["trap"])
    res = dib.montar_avbs(rank, ctx)
    s1 = res[0] if isinstance(res, tuple) else res
    return {"ds": ds, "rank": rank, "ctx": ctx, "s1": s1, "classe": classe, "dist": dist, "pp": pp}


def titulo_corrida(c, p=None, prefixo=""):
    t = f"{c['pista']} {c['hora']} (BR {hora_br(c['hora'])})" if c.get("hora") else ""
    extra = f" · {p['classe']} · {int(p['dist'])}m" if p else f" · {c.get('grade', '')} · {c.get('dist', '')}m"
    return f"### {prefixo}{t} · Race {c.get('num', '')}{extra}"


def gerar_texto_analise(c, p):
    txt = [titulo_corrida(c, p).replace("### ", ""), "", "**Planilha de Projeção**"]
    txt.append("| Trp | Galgo | Overall | Cat | Fatores | Perfil | Grades | Peso | Dias | Split | Time | Méd. Split | Méd. Time | Time Ajust. | Ritmo | Recup. Média | Conf. |")
    txt.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for d in p["ds"]:
        if d["nd"]: continue
        nome = f"{d['name']} {'🚫' if d.get('bloqueado') else ''} {'🎯' if d.get('alvo') else ''}".strip()
        fat = "<br>".join(f"{k} ({v:+.1f})" for k, v in d["fatores"]) or "-"
        grades = "-".join((r["grade"] or "?") for r in d["runs"])
        txt.append(f"| {d['trap']} | {nome} | {d['overall']:.1f} | {d['cat']:.1f} | {fat} | {d['perfil']} | {grades} | {d['peso']:.1f} | {d['dias']} | {d['split']:.2f} | {d['time']:.2f} | {d['msplit']:.2f} | {d['mtime']:.2f} | {d['tadj']:.2f} | {d['ritmo']:.2f} | {d['rec']:+.2f}% | {d['conf']:.0f}% |")
    return "\n".join(txt)


def analisar(c, classe_in, dist_in, pp_in):
    p = preparar(c["id"], c["data"], c, classe_in, dist_in, pp_in)
    if not p:
        st.warning("⚠️ O Racing Post bloqueou temporariamente a leitura automática deste cartão (Erro 580). Utilize a opção **Usar link manual** na barra lateral para carregar a corrida via link direto.")
        return
    st.markdown(titulo_corrida(c, p))
    st.markdown("#### Planilha de Projeção")
    st.markdown(dib.tabela_projecao(p["ds"]), unsafe_allow_html=True)
    st.markdown(grafico_predictor(p["ds"]), unsafe_allow_html=True)
    st.markdown(titulo_corrida(c, p))
    dib.tabela_avb(p["s1"], "1ª Planilha — AVB Principal (Prob ≥ 60%)")
    if hasattr(dib, "gerar_observacoes"):
        dib.gerar_observacoes(p["rank"], p["s1"], p["ctx"])
    st.markdown("---")
    with st.expander("📋 Exportar Análise"):
        texto_gerado = gerar_texto_analise(c, p)
        botao_copiar(texto_gerado)
        st.text_area("Copiar texto:", texto_gerado, height=200)


def mostrar_form(c):
    raw = buscar_form_raw(c["id"], c["data"])
    st.markdown(titulo_corrida(c, None, "📄 Form · "))
    if not raw:
        st.warning("Não foi possível carregar o Form desta corrida devido a restrições do servidor do site.")
        return
    heads = ["Data", "Pista", "Dis", "Trp", "Split", "Bends", "Fin", "By", "Win/Sec", "Remarks", "WnTm", "Gng", "Wght", "SP", "Grade", "CalTm"]
    for dog in sorted(raw, key=lambda x: int(re.search(r"\d+", str(x.get("trapNum", 9))).group()) if re.search(r"\d+", str(x.get("trapNum", ""))) else 9):
        trap = re.search(r"\d+", str(dog.get("trapNum", "")))
        st.markdown(f"{badge(trap.group()) if trap else ''} **{dog.get('dogName', '?')}**", unsafe_allow_html=True)
        rows = []
        for f in dog.get("forms", []):
            n = dib.norm_run(f)
            g = lambda k: dib.pick_fb(f, k)
            data = n["date"].strftime("%d%b%y") if n["date"] else n["date_str"]
            rows.append([data, n["track"], f"{int(n['dist'])}m" if n["dist"] else "", n["trap"] or "", g("split") or "", n["bends"], g("fin") or "", g("by") or "", _get(f, "winsec", EXTRA) if 'EXTRA' in globals() else "", g("remarks") or "", g("wntm") or "", g("gng") or "", g("weight") or "", "", n["grade"], g("caltm") or ""])
        if rows: tabela_html(heads, rows)


def mostrar_resultado(c, classe_in, dist_in, pp_in):
    st.markdown(titulo_corrida(c, None, "📊 Resultado · "))
    mostrar_replay(c)
    st.markdown("---")
    st.warning("ℹ️ Para visualizar os resultados oficiais detalhados e a tabela de posições com segurança sem bloqueio de API do site, acesse diretamente a página oficial:")
    _link(f"{BASE}/#result-meeting-result/race_id={c['id']}&r_date={c['data']}", "Abrir Resultados Completos no Racing Post")


def main():
    st.title("🐾 DIB GREYHOUND")
    with st.sidebar:
        modo_txt = st.radio("Ver", ["🏁 Corridas", "📊 Resultados"], horizontal=True, label_visibility="collapsed")
        modo = "res" if "Resultados" in modo_txt else "ana"
        data = st.date_input("Data", value=agora_uk().date())
        data_str = data.strftime("%Y-%m-%d")
        ocultar = st.checkbox("Ocultar corridas já realizadas", value=True) if modo == "ana" else False
        with st.expander("⚙️ Ajustes"):
            classe_in = st.text_input("Classe", value="")
            dist_in = st.number_input("Distância (m)", value=0, step=10)
            pp_in = st.text_input("Post Pick", value="")
            url_custom = st.text_input("Endereço da lista", value="")
        corridas, tentativas, _ = buscar_lista(data_str, url_custom)
        if st.button("🔄 Recarregar lista"):
            buscar_lista.clear()
            st.rerun()

        sel = st.session_state.get("sel")
        if corridas:
            pistas = sorted({c["pista"] for c in corridas})
            filtro = st.multiselect("Pistas", pistas)
            lista = [c for c in corridas if not filtro or c["pista"] in filtro]
            hoje = data == agora_uk().date()
            limite = agora_uk().strftime("%H:%M")
            if modo == "ana" and ocultar and hoje:
                lista = [c for c in lista if c["hora"] >= limite]
            if modo == "res":
                if hoje: lista = [c for c in lista if c["hora"] < limite]
                lista = sorted(lista, key=lambda c: (c["hora"], c["pista"]), reverse=True)
            for c in lista:
                ativo = sel and sel.get("id") == c["id"] and sel.get("modo"] == modo
                rotulo = f"{'▶ ' if ativo else ''}{c['hora']} · {c['pista']} R{c['num'] or '?'} · {c['grade'] or '?'} · {c['dist'] or '?'}m"
                st.button(rotulo, key=f"{modo}_{c['id']}", use_container_width=True, on_click=escolher, args=(c, data_str, modo))

        with st.expander("🔗 Usar link manual"):
            link = st.text_input("Link da corrida", placeholder="Cole o link aqui...")
            if st.button("Analisar link") and link:
                rid = re.search(r"race_id=(\d+)", link)
                rd = re.search(r"r_date=([\d-]+)", link)
                if rid and rd:
                    escolher({"id": rid.group(1), "hora": "", "pista": "", "num": "", "grade": "", "dist": 0}, rd.group(1), "ana")
                    st.rerun()
                else:
                    st.error("Link inválido: precisa ter race_id e r_date.")

    sel = st.session_state.get("sel")
    if sel:
        if sel.get("modo"] == "res":
            aba1, aba2 = st.tabs(["📊 Resultado", "📄 Form"])
            with aba1: mostrar_resultado(sel, classe_in, dist_in, pp_in)
        else:
            aba1, aba2 = st.tabs(["📋 Análise", "📄 Form"])
            with aba1: analisar(sel, classe_in, dist_in, pp_in)
        with aba2: mostrar_form(sel)
        if st.session_state.pop("fechar", False): fechar_sidebar()

main()
