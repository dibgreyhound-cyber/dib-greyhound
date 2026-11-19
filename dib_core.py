def nome_marcado(d):
    n = html.escape(d["name"])
    if d.get("alerta_trial"): n += " ⚠️"
    if d.get("alvo"): n += " 🎯"
    if d.get("bloqueado"): n += " 🚫"
    return n

def trap_label(d): return f"{TRAP_EMOJI.get(d['trap'], '')} {d['trap']}"

def tabela_projecao(ds):
    cols = ["split", "time", "tadj", "msplit", "mtime", "ritmo", "rec"]
    rk, max_rk = {c: [None]*len(ds) for c in cols}, {}
    for c in cols:
        vals = [(i, d[c]) for i, d in enumerate(ds) if d.get(c) is not None]
        max_rk[c] = len(vals)
        vals.sort(key=lambda x: x[1], reverse=(c == "rec"))
        for rank, (i, _) in enumerate(vals, 1): rk[c][i] = rank

    rows = []
    for i, d in enumerate(ds):
        if d["nd"]: rows.append([trap_label(d), nome_marcado(d)] + ["-"] * 15); continue
        fat = "<br>".join(f"{k} ({v:+.1f})" for k, v in d["fatores"]) or "-"
        if d.get("remarks_translated"): fat += f"<br><small style='color:#aaa'>{', '.join(set(d['remarks_translated']))}</small>"
        rows.append([
            trap_label(d), nome_marcado(d), f"{MEDALS.get(d['pos'], str(d['pos'])+'º')} {d['overall']:.1f}",
            f"{d['cat']:.1f} ({d['cat_mod']:+.0f})", fat, f"{ {'Limpo':'✅','Irregular':'⚠️','Trombador':'🔴'}[d['perfil']] } {d['perfil']}",
            "-".join((r["grade"] or "?") for r in d["runs"]), f"{d['peso']:.1f}", f"{d['dias']} ⚠️" if d['dias'] > 21 else str(d['dias']),
            get_rank_html(d["split"], rk["split"][i], max_rk["split"]), get_rank_html(d["time"], rk["time"][i], max_rk["time"]),
            get_rank_html(d["msplit"], rk["msplit"][i], max_rk["msplit"]) if d.get("msplit") else (f"<span style='color:#ffa500'>Pos: {d.get('msplit_pos', 0):.1f}</span>" if d.get("msplit_pos") else "-"),
            get_rank_html(d["mtime"], rk["mtime"][i], max_rk["mtime"]), get_rank_html(d["tadj"], rk["tadj"][i], max_rk["tadj"]),
            get_rank_html(d["ritmo"], rk["ritmo"][i], max_rk["ritmo"]), get_rank_html(d["rec"], rk["rec"][i], max_rk["rec"]) + f"<br><small>{d['rec_txt'].split()[1]}</small>", f"{d['conf']:.0f}%"
        ])
    return tbl(["Trap", "Galgo", "Overall", "Cat", "Fatores", "Perfil", "Grades", "Peso", "Dias", "Split", "Time", "Méd. Split", "Méd. Time", "Time Ajust.", "Ritmo", "Recup. Média", "Conf."], rows)

def tabela_avb(lista, titulo):
    st.markdown(f"#### {titulo}")
    if not lista: st.info("Nenhum confronto com vantagem superior a 58% nesta corrida."); return
    def fmt_pair(v, d, is_time=False, prec=2, is_pct=False):
        if v is None or d is None: return "-", "-"
        p, s = f".{prec}f", "%" if is_pct else ""
        vs, ds = f"{v:{p}}{s}", f"{d:{p}}{s}"
        diff = v - d
        if v <= d: vs += f" ({diff:{p}}{s})"
        else: ds += f" (+{abs(diff):{p}}{s})"
        if is_time:
            if v < d: vs, ds = f"<span style='color:#12873a;font-weight:bold'>{vs}</span>", f"<span style='color:#ff4b4b'>{ds}</span>"
            elif v > d: vs, ds = f"<span style='color:#ff4b4b'>{vs}</span>", f"<span style='color:#12873a;font-weight:bold'>{ds}</span>"
        else:
            if v > d: vs, ds = f"<span style='color:#12873a;font-weight:bold'>{vs}</span>", f"<span style='color:#ff4b4b'>{ds}</span>"
            elif v < d: vs, ds = f"<span style='color:#ff4b4b'>{vs}</span>", f"<span style='color:#12873a;font-weight:bold'>{ds}</span>"
        return vs, ds

    rows = []
    for i, (V, D, prob, is_premium) in enumerate(lista):
        if i > 0: rows.append(["<hr>"])
        ov_v, ov_d = fmt_pair(V['overall'], D['overall'], False, 1)
        cat_v, cat_d = fmt_pair(V['cat'], D['cat'], False, 1)
        sp_v, sp_d = fmt_pair(V['split'], D['split'], True, 2)
        t_v, t_d = fmt_pair(V['time'], D['time'], True, 2)
        if V.get("msplit") and D.get("msplit"): ms_v, ms_d = fmt_pair(V['msplit'], D['msplit'], True, 2)
        elif V.get("msplit_pos") and D.get("msplit_pos"): ms_v, ms_d = fmt_pair(V['msplit_pos'], D['msplit_pos'], True, 1)
        else: ms_v, ms_d = "-", "-"
        mt_v, mt_d = fmt_pair(V['mtime'], D['mtime'], True, 2)
        ta_v, ta_d = fmt_pair(V['tadj'], D['tadj'], True, 2)
        r_v, r_d = fmt_pair(V['ritmo'], D['ritmo'], True, 2)
        rec_v, rec_d = fmt_pair(V['rec'], D['rec'], False, 1, True)

        prob_cell = f"<td rowspan='2' style='vertical-align:middle;font-weight:bold;font-size:16px;'><span style='color:#12873a'>{prob:.1f}%</span></td>"
        star = "<span style='color:#FFD700; font-size:16px; margin-right:6px;'>★</span>" if is_premium else ""

        rows.append([
            f"{star}{trap_label(V)} - {nome_marcado(V)}",
            ov_v, cat_v, V['perfil'], "-".join((r["grade"] or "?") for r in V["runs"]),
            f"{V['peso']:.1f}", f"{V['dias']}", sp_v, t_v, ms_v, mt_v, ta_v, r_v, rec_v, f"{V['conf']:.0f}%",
            prob_cell
        ])

        rows.append([
            f"{trap_label(D)} - {nome_marcado(D)}",
            ov_d, cat_d, D['perfil'], "-".join((r["grade"] or "?") for r in D["runs"]),
            f"{D['peso']:.1f}", f"{D['dias']}", sp_d, t_d, ms_d, mt_d, ta_d, r_d, rec_d, f"{D['conf']:.0f}%"
        ])

    heads = ["AvB", "Overall", "Cat", "Perfil", "Grades", "Peso", "Dias", "Split", "Time", "Méd. Split", "Méd. Time", "Time Ajust.", "Ritmo", "Recup.", "Conf.", "Probabilidade"]
    st.markdown(tbl(heads, rows), unsafe_allow_html=True)
    def gerar_observacoes(rank, avbs, ctx):
    if not rank: return
    st.markdown("---")
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
        insights.append(f"**⚔️ Duelo de Favoritos:** O mercado elegeu o **{TRAP_EMOJI.get(pp_fav['trap'])} {pp_fav['name']}** (Post Pick 1), mas o App crava o **{TRAP_EMOJI.get(fav_app['trap'])} {fav_app['name']}** ({fav_app['overall']:.1f} de Overall) como o verdadeiro dono da prova. É um choque direto.")
    else:
        insights.append(f"**🤝 Consenso Total:** O mercado e o App concordam que o **{TRAP_EMOJI.get(fav_app['trap'])} {fav_app['name']}** é o cão a ser batido. Overall {fav_app['overall']:.1f} e Confiança {fav_app['conf']:.0f}%.")

    trombadores_internos = [d for d in elegiveis if d["perfil"] == "Trombador" and d["trap"] <= 4]
    if len(trombadores_internos) >= 2:
        nomes_tromb = " e ".join([f"{TRAP_EMOJI.get(d['trap'])} {d['name']}" for d in trombadores_internos])
        clean_candidates = [d for d in elegiveis if d["perfil"] != "Trombador"]
        
        if clean_candidates:
            c_clean = clean_candidates[0]
            local = "por fora" if c_clean["trap"] >= 5 else ("pelo meio" if c_clean["trap"] == 4 else "no trilho (por dentro)")
            insights.append(f"**💥 Risco de Colisão:** O {nomes_tromb} são Trombadores e correm nas traps internas. Se eles se chocarem na 1ª curva, o {TRAP_EMOJI.get(c_clean['trap'])} {c_clean['name']}, que corre {local} e está limpo, pode herdar a pista livre.")
        else:
            insights.append(f"**💥 Risco de Colisão:** O {nomes_tromb} são Trombadores e correm nas traps internas. A briga pelo trilho será intensa.")

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
