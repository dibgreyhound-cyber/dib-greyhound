# -*- coding: utf-8 -*-
"""
descobrir.py - Descobre qual endereco do Racing Post devolve o RESULTADO de uma corrida.
Le a pagina inicial e os arquivos JavaScript do site, procura os enderecos ".sd" e testa os que parecem ser de resultado.
Uso (no app.py):  import descobrir   ...   descobrir.painel(http(), BASE, c["id"], c["data"])
"""
import re
import time

import pandas as pd
import streamlit as st

RE_SD = re.compile(r"""["']((?:/?[\w\-]+/)*[\w\-]*\.sd)(?:\?[^"']*)?["']""")
RE_BLOCKS = re.compile(r"""blocks\s*[:=]\s*["']([\w,%\-]+)["']""")


def _baixar(http, url, tam=3_000_000):
    try:
        r = http.get(url, timeout=15)
        if r.status_code == 200:
            return r.text[:tam]
    except Exception:
        pass
    return ""


def _achar_scripts(http, base):
    html = _baixar(http, base + "/")
    urls = re.findall(r"""<script[^>]+src=["']([^"']+)["']""", html)
    out = []
    for u in urls:
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = base + u
        elif not u.startswith("http"):
            u = base + "/" + u
        if "racingpost" in u and u not in out:
            out.append(u)
    return html, out[:8]


def _contextos(texto, padrao, n=60, limite=25):
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


def _tem_resultado(js):
    """Procura galgos com posicao final dentro de um JSON qualquer."""
    achados = 0

    def walk(o):
        nonlocal achados
        if isinstance(o, dict):
            nome = o.get("dogName")
            pos = re.search(r"\d+", str(o.get("outcomeDesc") or o.get("finishPos") or o.get("position") or ""))
            if isinstance(nome, str) and pos:
                achados += 1
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(js)
    return achados


def painel(http, base, race_id, data_str):
    st.markdown("---")
    st.markdown("#### 🧪 Descobrir o endereço do resultado")
    st.caption("Lê o código do site para achar de onde vem o resultado. Leva alguns segundos.")
    if not st.button("🧪 Descobrir agora", key="btn_descobrir"):
        return
    with st.spinner("Lendo o site..."):
        html, scripts = _achar_scripts(http, base)
        st.write(f"Página inicial: {len(html)} caracteres · {len(scripts)} arquivos JavaScript")
        textos = [_baixar(http, u) for u in scripts]
        tudo = "\n".join(textos)
        st.write(f"JavaScript lido: {len(tudo)} caracteres")

        caminhos = sorted({m.group(1) for m in RE_SD.finditer(tudo)})
        blocos = sorted({m.group(1) for m in RE_BLOCKS.finditer(tudo)})
        st.markdown("**Endereços .sd encontrados no site:**")
        st.code("\n".join(caminhos[:80]) or "(nenhum)")
        st.markdown("**Nomes de blocks encontrados:**")
        st.code(", ".join(blocos[:80]) or "(nenhum)")
        st.markdown("**Trechos do código com a palavra result:**")
        st.code("\n\n".join(_contextos(tudo, r"result", 70, 20)) or "(nenhum)")

        # testa enderecos que parecem de resultado
        base_paths = [p for p in caminhos if "result" in p.lower()]
        bases = base_paths[:6] + ["/results/blocks.sd", "/result/blocks.sd", "/card/blocks.sd"]
        nomes = [b for b in blocos if "result" in b.lower()] + ["result", "results", "card", "header%2Ccard"]
        testes, achado = [], None
        vistos = set()
        for p in bases:
            p = p if p.startswith("/") else "/" + p
            for b in dict.fromkeys(nomes[:6]):
                u = f"{base}{p}?race_id={race_id}&r_date={data_str}&blocks={b}"
                if u in vistos or len(testes) >= 30:
                    continue
                vistos.add(u)
                time.sleep(0.25)
                try:
                    r = http.get(u, timeout=8)
                    js = r.json() if r.status_code == 200 else None
                except Exception as e:
                    testes.append({"Status": f"erro", "Galgos": 0, "Endereço": u.replace(base, "")})
                    continue
                n = _tem_resultado(js) if js is not None else 0
                testes.append({"Status": r.status_code, "Galgos": n, "Endereço": u.replace(base, "")})
                if n >= 2 and not achado:
                    achado = (u, js)
        st.markdown("**Testes de endereço:**")
        st.dataframe(pd.DataFrame(testes), use_container_width=True, hide_index=True)
        if achado:
            st.success("Achei um endereço com resultado! Me mande a foto desta tela.")
            st.code(achado[0])
        else:
            st.warning("Ainda não achei. Me mande as fotos das listas acima (endereços .sd, blocks e trechos com result).")
