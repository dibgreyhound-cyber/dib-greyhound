# -*- coding: utf-8 -*-
"""
dib_ui.py - visual do app (estilo "Esportivo cromado"): paleta clara/escura, cards, chips e barras.
Só monta HTML/CSS; os números vêm do dib_core. Troca de tema ao vivo (lê o tema ativo do Streamlit).

Paleta
  claro : fundo #F4F6F9 | card #FFFFFF | texto #14181F | secundário #5B6573 | borda #E3E8EF
  escuro: fundo #0E1116 | card #171B22 | texto #E8ECF2 | secundário #9AA5B5 | borda #2A313C
  destaque azul #2F6BFF | prata #AEB6C2 | positivo #16A34A | alerta #F59E0B | negativo #E5484D
"""
import html
import re

import streamlit as st
import streamlit.components.v1 as components

import dib_core as dib

# ------------------------------------------------------------------ CSS
_CSS = """<style>
:root{
  --dib-bg:#F4F6F9; --dib-card:#FFFFFF; --dib-tx:#14181F; --dib-mute:#5B6573; --dib-bd:#E3E8EF;
  --dib-track:#E8ECF2; --dib-head:#EDF1F6; --dib-sh:0 1px 2px rgba(16,24,40,.06),0 4px 14px rgba(16,24,40,.06);
  --dib-acc:#2F6BFF; --dib-acc2:#6EA0FF; --dib-silver:#AEB6C2;
  --dib-ok:#16A34A; --dib-warn:#F59E0B; --dib-bad:#E5484D;
}
:root[data-dib="dark"]{
  --dib-bg:#0E1116; --dib-card:#171B22; --dib-tx:#E8ECF2; --dib-mute:#9AA5B5; --dib-bd:#2A313C;
  --dib-track:#232A34; --dib-head:#1D232C; --dib-sh:0 1px 0 rgba(255,255,255,.03) inset,0 6px 18px rgba(0,0,0,.35);
}
@media (prefers-color-scheme: dark){
  :root:not([data-dib]){
    --dib-bg:#0E1116; --dib-card:#171B22; --dib-tx:#E8ECF2; --dib-mute:#9AA5B5; --dib-bd:#2A313C;
    --dib-track:#232A34; --dib-head:#1D232C; --dib-sh:0 6px 18px rgba(0,0,0,.35);
  }
}
.stApp{background:var(--dib-bg) !important}
.block-container{padding-top:2.6rem !important;padding-bottom:2rem !important}
div[data-testid="stTabs"] [role="tablist"]{margin-top:-4px}
img{max-width:100%}
div[data-testid="stVerticalBlock"]{gap:.7rem !important}
header[data-testid="stHeader"]{background:transparent !important}
div[data-testid="stExpander"]{background:transparent !important;border:1px solid var(--dib-bd) !important;border-radius:14px !important;overflow:hidden}
div[data-testid="stExpander"] summary{font-weight:600}
.dib-sec{display:flex;align-items:center;gap:10px;font-size:1.288rem;font-weight:800;letter-spacing:.2px;margin:18px 0 10px;color:var(--dib-tx)}
.dib-sec::before{content:"";width:5px;height:1.2em;border-radius:3px;background:linear-gradient(var(--dib-acc),var(--dib-acc2))}
.dib-sec small{font-weight:500;color:var(--dib-mute);font-size:0.896rem;margin-left:4px}
.dib-hero{margin:6px 0 4px}
.dib-hero .t{font-size:1.9rem;font-weight:800;line-height:1.15;color:var(--dib-tx)}
.dib-hero .t span{font-weight:500;font-size:1.176rem;color:var(--dib-mute);margin-left:6px}
.dib-chips{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 4px}
.dib-chip{display:inline-flex;align-items:center;gap:5px;padding:4px 12px;border-radius:999px;font-size:0.963rem;font-weight:600;
  background:var(--dib-card);border:1px solid var(--dib-bd);color:var(--dib-tx);white-space:nowrap}
.dib-chip.acc{background:var(--dib-acc);border-color:var(--dib-acc);color:#fff}
.dib-chip.ok{color:var(--dib-ok);border-color:rgba(22,163,74,.45);background:rgba(22,163,74,.10)}
.dib-chip.warn{color:#B45309;border-color:rgba(245,158,11,.5);background:rgba(245,158,11,.12)}
.dib-chip.bad{color:var(--dib-bad);border-color:rgba(229,72,77,.45);background:rgba(229,72,77,.10)}
:root[data-dib="dark"] .dib-chip.warn{color:#FBBF24}
.dib-chip.mute{color:var(--dib-mute);font-weight:500}
.dib-card{background:var(--dib-card);border:1px solid var(--dib-bd);border-radius:14px;padding:14px 16px;box-shadow:var(--dib-sh);color:var(--dib-tx)}
.dib-strip{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.dib-strip .arr{color:var(--dib-silver);font-size:1.008rem}
.dib-strip-pp{margin-top:12px;padding-top:10px;border-top:1px dashed var(--dib-bd);font-size:1.03rem;color:var(--dib-mute);display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.dib-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px}
.dib-top{position:relative;overflow:hidden}
.dib-top .rk{position:absolute;right:12px;top:6px;font-size:2.6rem;font-weight:900;color:var(--dib-silver);opacity:.22;line-height:1}
.dib-top.p1{border-color:var(--dib-acc);box-shadow:0 0 0 1px var(--dib-acc) inset,var(--dib-sh)}
.dib-name{font-size:1.21rem;font-weight:800;line-height:1.25;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.dib-brt{font-size:0.874rem;color:var(--dib-mute);margin:3px 0 0 0}
.dib-nums{display:grid;grid-template-columns:1.15fr .8fr 1fr 1fr .9fr;gap:6px;align-items:start;margin:12px 0 8px}
.dib-top .dib-num .v{font-size:1.322rem;font-weight:800}
.dib-num .v{font-size:1.75rem;font-weight:800;line-height:1;color:var(--dib-tx)}
.dib-num .v.acc{color:var(--dib-acc)}
.dib-top .dib-num .l{font-size:0.65rem;letter-spacing:.3px;line-height:1.15}
.dib-num .l{font-size:0.784rem;text-transform:uppercase;letter-spacing:.6px;color:var(--dib-mute);margin-top:4px}
.dib-bar{height:9px;border-radius:999px;background:var(--dib-track);overflow:hidden}
.dib-bar>i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,var(--dib-acc),var(--dib-acc2))}
.dib-card .dib-chips{margin:10px 0 0}
.dib-avb-h{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px}
.dib-nm{font-size:0.806rem;font-weight:600;color:var(--dib-mute);margin-top:3px;line-height:1.15}
.dib-vs{display:flex;flex-direction:column;gap:6px}
.dib-vs .row{display:flex;align-items:center;gap:8px;font-weight:700;flex-wrap:wrap}
.dib-vs .row.d{font-weight:500;color:var(--dib-mute)}
.dib-pos{font-size:0.874rem;font-weight:800;color:var(--dib-acc);margin-right:6px}
.dib-prob{font-size:2rem;font-weight:900;color:var(--dib-ok);line-height:1}
.dib-mini{width:100%;border-collapse:collapse;margin-top:6px;font-size:17px;font-variant-numeric:tabular-nums;color:var(--dib-tx)}
.dib-det summary{cursor:pointer;margin-top:10px;font-size:.95rem;font-weight:600;color:var(--dib-acc);list-style:none}
.dib-det summary::-webkit-details-marker{display:none}
.dib-det summary::before{content:'▸ '}
.dib-det[open] summary::before{content:'▾ '}
.dib-mini td,.dib-mini th{padding:11px 4px;border:0 !important;border-top:1px solid var(--dib-bd) !important;text-align:center;background:transparent !important}
.dib-mini tr:first-child td{border-top:0 !important}
.dib-mini .df{font-size:.72em;font-weight:500;color:var(--dib-mute);margin-left:2px;opacity:.85}
.dib-mini td:first-child{text-align:left;color:var(--dib-mute)}
.dib-mini .w{color:var(--dib-ok);font-weight:800}
.dib-mini .l{color:var(--dib-bad)}
.dib-pred .row{display:flex;align-items:center;gap:10px;margin:7px 0}
.dib-pred .nm{flex:0 0 28%;min-width:0;font-size:0.952rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dib-pred .bar{flex:1}
.dib-pred .pc{flex:0 0 44px;text-align:right;font-weight:800;font-size:1.008rem}
.dib-empty{color:var(--dib-mute);text-align:center;padding:18px}
</style>"""

# ------------------------------------------------------------------ tema ao vivo (claro/escuro)
_JS_TEMA = """<script>
(function(){
  var win,doc; try{win=window.parent;doc=win.document;}catch(e){return;}
  function lum(c){var m=(c||'').match(/[\\d.]+/g);if(!m||m.length<3)return null;return 0.299*m[0]+0.587*m[1]+0.114*m[2];}
  function tema(){
    try{
      var el=doc.querySelector('.stApp')||doc.body;
      var l=lum(win.getComputedStyle(el).color);   // cor do TEXTO do tema do Streamlit (claro no tema escuro)
      if(l===null)return;
      doc.documentElement.setAttribute('data-dib', l>140?'dark':'light');
    }catch(x){}
  }
  tema(); setInterval(tema,400);
})();
</script>"""


def aplicar_tema():
    """Chamar uma vez por execução, logo no começo do main()."""
    st.markdown(_CSS, unsafe_allow_html=True)
    components.html(_JS_TEMA, height=0)


# ------------------------------------------------------------------ blocos pequenos
def _e(x):
    return html.escape(str(x))


def chip(txt, tone=""):
    return f"<span class='dib-chip {tone}'>{txt}</span>"


def secao(titulo, sub=""):
    return f"<div class='dib-sec'>{titulo}{f'<small>{sub}</small>' if sub else ''}</div>"


def _perfil_chip(d):
    p = d.get("perfil")
    return {"Limpo": chip("✅ Limpo", "ok"), "Irregular": chip("⚠️ Irregular", "warn"),
            "Trombador": chip("🔴 Trombador", "bad")}.get(p, chip(_e(p or "-"), "mute"))


def _fmt(x, nd=1, suf=""):
    return "-" if x is None else f"{x:.{nd}f}{suf}"


# ------------------------------------------------------------------ cabeçalho + classificação
def cabecalho(c, p, badge, hora_br):
    titulo = ""
    if c.get("hora"):
        titulo = (f"<div class='dib-hero'><div class='t'>{_e(c['pista'])} {_e(c['hora'])}"
                  f"<span>BR {hora_br(c['hora'], True)}</span></div></div>")
    num = str(c.get("num") or "").strip()
    chips = []
    if num: chips.append(chip(f"Race {_e(num)}"))
    chips.append(chip(_e(p["classe"]), "acc"))
    chips.append(chip(f"{int(p['dist'])} m"))
    seta = "<span class='arr'>›</span>"
    ordem = seta.join(badge(d["trap"]) for d in p["rank"])
    pp_nums = re.findall(r"[1-6]", p["pp"] or "")
    pp_html = (chip("não encontrado", "mute") if not pp_nums else seta.join(badge(n) for n in pp_nums))
    return (titulo + f"<div class='dib-chips'>{''.join(chips)}</div>"
            + secao("Classificação geral", "ordem prevista · 1º → 6º")
            + f"<div class='dib-card'><div class='dib-strip'>{ordem}</div>"
              f"<div class='dib-strip-pp'><span>Post Pick do site</span>{pp_html}</div></div>")


def cabecalho_curto(c, p, hora_br):
    """Mesmo cabeçalho do topo (pista, horário, BR e chips), sem a classificação geral."""
    return cabecalho(c, p, lambda t: "", hora_br).split("<div class='dib-sec'>")[0]


# ------------------------------------------------------------------ Top 3
def _medalha(i):
    return dib.MEDALS.get(i) or "<span class='dib-pos'>" + str(i) + "º</span>"


def cards_top3(rank, badge, n=None):
    mx = max([d.get("p_vit") or 0.0 for d in rank] + [1.0])
    cards = []
    for i, d in enumerate(rank[:n] if n else rank, 1):
        pv = d.get("p_vit")
        w = 0 if pv is None else max(4.0, min(100.0, pv / mx * 100.0))
        brt = d.get("brt_txt") or (f"BRT: {d['brt_raw']:.2f}" if d.get("brt_raw") else "")
        chips = [_perfil_chip(d), chip(f"Conf. {d.get('conf', 0):.0f}%", "mute"), chip(f"Cat {_fmt(d.get('cat'))}", "mute")]
        if d.get("rec") is not None:
            chips.append(chip(f"Recup. {d['rec']:+.0f}%", "ok" if d["rec"] >= 0 else "bad"))
        cards.append(
            f"<div class='dib-card dib-top p{i}'><div class='rk'>{i}º</div>"
            f"<div class='dib-name'>{_medalha(i)}{badge(d['trap'])}<span>{dib.nome_marcado(d)}</span></div>"
            f"<div class='dib-brt'>{_e(brt) if brt else '&nbsp;'}</div>"
            f"<div class='dib-nums'><div class='dib-num'><div class='v acc'>{_fmt(pv, 0, '%')}</div><div class='l'>chance de vencer</div></div>"
            f"<div class='dib-num'><div class='v'>{dib._fmt_ov(d['overall'])}</div><div class='l'>Overall (pts)</div></div>"
            f"<div class='dib-num'><div class='v'>{_fmt(d.get('msplit'), 2)}</div><div class='l'>Média Split</div></div>"
            f"<div class='dib-num'><div class='v'>{_fmt(d.get('mtime'), 2)}</div><div class='l'>Média Time</div></div>"
            f"<div class='dib-num'><div class='v'>{_fmt(d.get('tadj'), 2)}</div><div class='l'>Tadj</div></div></div>"
            f"<div class='dib-bar'><i style='width:{w:.0f}%'></i></div>"
            f"<div class='dib-chips'>{''.join(chips)}</div></div>")
    return secao("GALGOS", f"{len(rank)} na corrida · ordem de classificação") + f"<div class='dib-grid'>{''.join(cards)}</div>"


# ------------------------------------------------------------------ AvB
_SUP = {1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶"}


def _cel(d, key, outro, menor_melhor=True, nd=2, suf="", mostrar_dif=False):
    """Valor com a POSIÇÃO NA CORRIDA sobrescrita (¹ = melhor), como na Planilha de Projeção: 1º em pílula verde, último em vermelho."""
    v, o = d.get(key), outro.get(key)
    if v is None: return "-"
    rk = (d.get("rk") or {}).get(key)
    txt = f"{v:.{nd}f}{suf}" + (_SUP.get(rk[0], "") if rk else "")
    if rk and rk[0] == 1:
        h = f"<span style='color:#16A34A;font-weight:800;background:rgba(22,163,74,.14);padding:3px 9px;border-radius:8px'>{txt}</span>"
    elif rk and rk[0] == rk[1] and rk[1] > 1:
        h = f"<span style='color:#E5484D'>{txt}</span>"
    else:
        h = txt
    if mostrar_dif and o is not None:
        h += f" <small class='df'>({v - o:+.{nd}f}{suf})</small>"
    return h


def _marcas(d):
    """Só os símbolos do galgo (⚠️ 🎯 🚫 📏), sem o nome."""
    return "".join(s for s, k in (("⚠️", d.get("alerta_trial")), ("🎯", d.get("alvo")), ("🚫", d.get("bloqueado")), ("📏", d.get("conv_ok") is False)) if k)


def _pos(d):
    return f"<span class='dib-pos'>{d['pos']}º</span>" if d.get('pos') else ''


def cards_avb(lista, badge):
    if not lista:
        return (secao("AvBs") + "<div class='dib-card dib-empty'>Nenhum confronto aprovado nos critérios do AvB nesta corrida.<br>"
                "<small>Abra “Diagnóstico dos AvBs” mais abaixo para ver o motivo.</small></div>")
    cards = []
    for it in lista:
        V, D, prob = it[0], it[1], it[2]
        meta = dib.AVB_META.get((V["name"], D["name"])) or ("AVB", 0, False, 1)
        crit = prob          # 3º item da tupla = nº de critérios cumpridos (de 9)
        fl = meta[4] if len(meta) > 4 else {}
        falhou = [nome for k, nome in dib.AVB_CRIT if not fl.get(k)]
        txt_falha = ("✅ Todos os critérios cumpridos" if not falhou else "Não cumpriu: " + ", ".join(falhou))
        _pf = lambda d: _perfil_chip(d)
        linhas = [f"<tr><td>Perfil</td><td>{_pf(V)}</td><td>{_pf(D)}</td></tr>"]
        for rot, k, nd, suf in (("Overall", "overall", 0, ""), ("Melhor Split", "split", 2, ""), ("Melhor Time", "time", 2, ""),
                                ("Média Split", "msplit", 2, ""), ("Média Time", "mtime", 2, ""), ("Tadj", "tadj", 2, ""),
                                ("Métrica", "metrica", 2, ""), ("Recup.", "rec", 0, "%")):
            if k == "overall":
                a_, b_ = V.get(k), D.get(k)
                hv = f"<span class='{'w' if a_ > b_ else 'l' if a_ < b_ else ''}'>{a_:.0f}</span> <small class='df'>({a_ - b_:+.0f})</small>"
                hd = f"<span class='{'w' if b_ > a_ else 'l' if b_ < a_ else ''}'>{b_:.0f}</span>"
            else:
                hv, hd = _cel(V, k, D, mostrar_dif=True, nd=nd, suf=suf), _cel(D, k, V, nd=nd, suf=suf)
            linhas.append(f"<tr><td>{rot}</td><td>{hv}</td><td>{hd}</td></tr>")
        cards.append(
            f"<div class='dib-card'><div class='dib-avb-h'>"
            f"<span class='dib-chip mute'>{_e(txt_falha)}</span></div>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;gap:10px'>"
            f"<div class='dib-vs'><div class='row'>{badge(V['trap'])}<span>{_e(V['name'])} {_pos(V)}{_marcas(V)}</span></div>"
            f"<div class='row d'>vence {badge(D['trap'])}<span>{_e(D['name'])} {_pos(D)}{_marcas(D)}</span></div></div>"
            f"<div style='text-align:right'><div class='dib-prob'>{crit}/9</div>"
            f"<div class='dib-num'><div class='l'>critérios</div></div></div></div>"
            f"<div class='dib-bar' style='margin-top:10px'><i style='width:{max(4.0, min(100.0, crit / 9.0 * 100.0)):.0f}%;"
            f"background:linear-gradient(90deg,var(--dib-ok),#5BD68A)'></i></div>"
            f"<details class='dib-det'><summary>Comparar números</summary><table class='dib-mini'><tr><td></td><td>{badge(V['trap'])}<div class='dib-nm'>{_e(V['name'])}</div></td><td>{badge(D['trap'])}<div class='dib-nm'>{_e(D['name'])}</div></td></tr>{''.join(linhas)}</table></details></div>")
    return secao("AvBs", f"{len(lista)} confronto(s) · mais critérios primeiro") + f"<div class='dib-grid'>{''.join(cards)}</div>"


# ------------------------------------------------------------------ Predictor
def predictor(ds, badge):
    com = [d for d in ds if not d.get("nd") and d.get("p_vit") is not None]
    if not com:
        return ""
    mx = max(d["p_vit"] for d in com)
    linhas = []
    for d in sorted(com, key=lambda x: -x["p_vit"]):
        w = 100.0 if mx <= 0 else max(4.0, min(100.0, d["p_vit"] / mx * 100.0))
        linhas.append(f"<div class='row'>{badge(d['trap'])}<span class='nm'>{_e(d['name'])}</span>"
                      f"<div class='bar dib-bar'><i style='width:{w:.0f}%'></i></div><span class='pc'>{d['p_vit']:.0f}%</span></div>")
    return secao("Predictor", "chance de vencer") + f"<div class='dib-card dib-pred'>{''.join(linhas)}</div>"
