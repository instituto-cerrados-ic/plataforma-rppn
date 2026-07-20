# -*- coding: utf-8 -*-
"""
mapa_tecnico.py — layout de mapa técnico da RPPN (PNG, A4 paisagem).

Segue o modelo oficial do Programa Jurema / Instituto Cerrados:
mapa principal (satélite + imóvel branco + RPPN amarela + vértices numerados +
grid UTM + norte + escalas) e painel lateral com logos (IC + Jurema), mapa de
contexto (UFs, triângulo vermelho), blocos de informação (denominação,
proprietário, município/UF, áreas, escala, resp. técnico), legenda e datum.
"""
from __future__ import annotations

import io
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import matplotlib.patheffects
import numpy as np
from matplotlib.patches import Polygon as MplPoly, Rectangle

ASSETS = Path(__file__).resolve().parent / "assets"
VERDE = "#004F23"      # verde oficial IC/Jurema
BEGE = "#DDCCA4"
MAGENTA = "#E00080"    # acento Jurema

UF_SIGLA = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
            "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
            "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
            "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
            "51": "MT", "52": "GO", "53": "DF"}

# cores iguais às da ferramenta de desenho
COR_IMOVEL = {"edge": "#FFFFFF", "face": "#FFFFFF", "face_a": 0.15, "lw": 2.6}
COR_RPPN = {"edge": "#8B6914", "face": "#FFF176", "face_a": 0.40, "lw": 2.2}


def _esri_imagem(xmin, ymin, xmax, ymax, epsg, size=(1100, 1100)):
    import requests
    url = ("https://services.arcgisonline.com/ArcGIS/rest/services/"
           "World_Imagery/MapServer/export")
    params = {"bbox": f"{xmin},{ymin},{xmax},{ymax}", "bboxSR": epsg,
              "imageSR": epsg, "size": f"{size[0]},{size[1]}",
              "format": "png", "f": "image"}
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        from PIL import Image
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:
        return None


def _passo_nice(alvo):
    exp = math.floor(math.log10(alvo)) if alvo > 0 else 0
    base = alvo / (10 ** exp)
    nice = 1 if base < 1.5 else 2 if base < 3.5 else 5 if base < 7.5 else 10
    return nice * (10 ** exp)


def _caixa(ax):
    """Moldura preta padrão dos boxes do painel."""
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_linewidth(0.9); s.set_color("black")


def _norm_txt(s):
    import unicodedata
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower().strip()


def _malha_municipio(uf, municipio):
    """GeoJSON do município (malha IBGE), cacheado em assets. None se falhar.
    Para o DF (distrito), usa a malha da própria UF."""
    import requests
    if not uf:
        return None
    uf = str(uf).upper()
    try:
        if uf == "DF":
            cache = ASSETS / "mun_df.json"
            if cache.exists():
                return json.load(open(cache, encoding="utf-8"))
            gj = requests.get("https://servicodados.ibge.gov.br/api/v3/malhas/"
                              "estados/DF?formato=application/vnd.geo+json",
                              timeout=15).json()
            json.dump(gj, open(cache, "w", encoding="utf-8"))
            return gj
        if not municipio:
            return None
        cache = ASSETS / f"mun_{uf.lower()}_{_norm_txt(municipio).replace(' ', '_')}.json"
        if cache.exists():
            return json.load(open(cache, encoding="utf-8"))
        lst = requests.get("https://servicodados.ibge.gov.br/api/v1/localidades/"
                           f"estados/{uf}/municipios", timeout=12).json()
        mid = next((m["id"] for m in lst
                    if _norm_txt(m["nome"]) == _norm_txt(municipio)), None)
        if mid is None:
            return None
        gj = requests.get("https://servicodados.ibge.gov.br/api/v3/malhas/"
                          f"municipios/{mid}?formato=application/vnd.geo+json",
                          timeout=15).json()
        json.dump(gj, open(cache, "w", encoding="utf-8"))
        return gj
    except Exception:
        return None


def _contexto(ax, lon, lat, uf_alvo, municipio=""):
    """Mapa de contexto NA ESCALA DO MUNICÍPIO (ou do DF): limite municipal em
    destaque, UFs ao fundo, triângulo vermelho no local. O box mantém a largura
    das caixas vizinhas (aspect com adjustable='datalim')."""
    _caixa(ax)
    ax.set_facecolor("white")
    mun = _malha_municipio(uf_alvo, municipio)
    if mun and mun.get("features"):
        arrs = []
        for f in mun["features"]:
            geom = f["geometry"]
            polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
            arrs.extend(np.asarray(p[0]) for p in polys)
        xs = np.concatenate([a[:, 0] for a in arrs])
        ys = np.concatenate([a[:, 1] for a in arrs])
        px = max(xs.max() - xs.min(), ys.max() - ys.min()) * 0.22 + 0.02
        ax.set_xlim(xs.min() - px, xs.max() + px)
        ax.set_ylim(ys.min() - px, ys.max() + px)
    else:
        win = 2.0
        ax.set_xlim(lon - win, lon + win)
        ax.set_ylim(lat - win, lat + win)
    # 'datalim' preserva o tamanho do box (mesma largura das caixas vizinhas)
    ax.set_aspect("equal", adjustable="datalim")
    # UFs ao fundo
    try:
        d = json.load(open(ASSETS / "br_ufs.json", encoding="utf-8"))
        for f in d["features"]:
            geom = f["geometry"]
            polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
            for p in polys:
                arr = np.asarray(p[0])
                ax.add_patch(MplPoly(arr, closed=True, facecolor="#F7F5EE",
                                     edgecolor="#8a8a8a", linewidth=0.6, zorder=1))
    except Exception:
        pass
    # município em destaque
    if mun and mun.get("features"):
        for a in arrs:
            ax.add_patch(MplPoly(a, closed=True, facecolor="white",
                                 edgecolor="black", linewidth=1.3, zorder=2))
        rot = municipio if str(uf_alvo).upper() != "DF" else "Distrito Federal"
        if rot:
            ax.text(0.5, 0.045, f"{rot} - {str(uf_alvo).upper()}",
                    transform=ax.transAxes, ha="center", fontsize=6.2,
                    style="italic", color="#333", zorder=4)
    ax.plot(lon, lat, marker="^", color="red", ms=10, mec="darkred", zorder=3)


def _logo(ax, arquivo):
    ax.axis("off")
    try:
        img = mpimg.imread(ASSETS / arquivo)
        ax.imshow(img)
    except Exception:
        pass


def _texto_caixa(a, s, y, fs, largura=24, peso="normal", cor="black"):
    """Escreve texto SEMPRE dentro do box: quebra em linhas e reduz a fonte
    se necessário."""
    import textwrap
    s = str(s or "")
    linhas = textwrap.wrap(s, largura) or [""]
    if len(linhas) > 2:
        fs = max(4.8, fs * 0.82)
        linhas = textwrap.wrap(s, int(largura * 1.35))
    if len(linhas) > 3:
        linhas = linhas[:3]
        linhas[-1] += "…"
    a.text(0.5, y, "\n".join(linhas), fontsize=fs, ha="center", va="center",
           transform=a.transAxes, weight=peso, color=cor, linespacing=1.25)


def gerar_mapa_tecnico(imovel, rppn, epsg, vertices_df, dados=None,
                       out_png="mapa_tecnico.png", titulo=None, subtitulo=None):
    """
    imovel/rppn: shapely Polygon em UTM (epsg); um pode ser None.
    vertices_df: DataFrame PONTO,X,Y da RPPN (ou do imóvel, se não houver RPPN).
    dados: dict com nome_rppn, nome_imovel, proprietario, municipio, uf,
           area_imovel_ha, area_rppn_ha, resp_tecnico, crea, solicitacao.
    (titulo/subtitulo aceitos por compatibilidade; dados prevalece)
    """
    dados = dados or {}
    zona_txt = ""
    try:
        z = epsg - 31960 if 31961 <= epsg <= 31985 else None
        zona_txt = f"ZONA {z}S" if z else f"EPSG {epsg}"
    except Exception:
        zona_txt = f"EPSG {epsg}"

    geoms = [g for g in (imovel, rppn) if g is not None]
    xs = [c for g in geoms for c in g.exterior.xy[0]]
    ys = [c for g in geoms for c in g.exterior.xy[1]]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    pad = max(xmax - xmin, ymax - ymin) * 0.30 + 1
    lado = max(xmax - xmin, ymax - ymin) + 2 * pad
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    # espaço extra à esquerda para a tabela de vértices sobreposta
    xmin = cx - lado * 0.62
    xmax = cx + lado * 0.50
    ymin, ymax = cy - lado / 2, cy + lado / 2

    fig = plt.figure(figsize=(11.69, 8.27), dpi=150)  # A4 paisagem
    ax = fig.add_axes([0.045, 0.06, 0.645, 0.895])

    img = _esri_imagem(xmin, ymin, xmax, ymax, epsg,
                       size=(1100, int(1100 * (ymax - ymin) / (xmax - xmin))))
    if img is not None:
        ax.imshow(img, extent=[xmin, xmax, ymin, ymax], origin="upper", zorder=0)
    else:
        ax.set_facecolor("#dfe7df")

    if imovel is not None:
        ax.add_patch(MplPoly(list(imovel.exterior.coords), closed=True,
                     facecolor=COR_IMOVEL["face"], alpha=COR_IMOVEL["face_a"],
                     edgecolor=COR_IMOVEL["edge"], linewidth=COR_IMOVEL["lw"], zorder=3))
    if rppn is not None:
        ax.add_patch(MplPoly(list(rppn.exterior.coords), closed=True,
                     facecolor=COR_RPPN["face"], alpha=COR_RPPN["face_a"],
                     edgecolor=COR_RPPN["edge"], linewidth=COR_RPPN["lw"], zorder=4))

    # vértices numerados (ponto vermelho + número com halo, como no modelo)
    for i, (_, r) in enumerate(vertices_df.iterrows(), start=1):
        vx, vy = float(r["X"]), float(r["Y"])
        ax.plot(vx, vy, "o", color="red", mec="#7a0000", ms=4.5, zorder=6)
        ax.annotate(str(i), (vx, vy), xytext=(4, 4), textcoords="offset points",
                    fontsize=6.5, weight="bold", color="black", zorder=6,
                    path_effects=[matplotlib.patheffects.withStroke(linewidth=2,
                                                                    foreground="white")])

    ax.set_xlim(xmin, xmax); ax.set_ylim(ymin, ymax)

    # grid UTM + rótulos externos
    passo = _passo_nice((xmax - xmin) / 4)
    xt = np.arange(math.ceil(xmin / passo) * passo, xmax, passo)
    yt = np.arange(math.ceil(ymin / passo) * passo, ymax, passo)
    ax.set_xticks(xt); ax.set_yticks(yt)
    ax.grid(True, color="white", alpha=0.30, linewidth=0.6)
    # cruzetas nas interseções
    for gx in xt:
        for gy in yt:
            ax.plot(gx, gy, "+", color="black", ms=6, mew=0.8, alpha=0.85, zorder=5)
    # rótulos só no topo/baixo/esquerda — à direita apenas os ticks, para NÃO
    # sobrepor as caixas do painel lateral
    ax.tick_params(labelsize=6.5, top=True, right=True, labeltop=True,
                   labelright=False)
    ax.set_xticklabels([f"{v:.0f}" for v in xt])
    ax.set_yticklabels([f"{v:.0f}" for v in yt], rotation=90, va="center")
    for s in ax.spines.values():
        s.set_linewidth(1.2)

    # tabela de vértices sobreposta no mapa (como no modelo)
    linhas = [[str(i + 1),
               f"{float(r['X']):.2f}".replace(".", ","),
               f"{float(r['Y']):.2f}".replace(".", ",")]
              for i, (_, r) in enumerate(vertices_df.iterrows())]
    nv = len(linhas)
    fs = 6.0 if nv <= 24 else 5.2 if nv <= 34 else 4.5
    alt = min(0.88, 0.035 + nv * (0.0155 if nv <= 34 else 0.012))
    tab = ax.table(cellText=linhas, colLabels=["Vértice", "E (m)", "N (m)"],
                   cellLoc="center", colWidths=[0.22, 0.39, 0.39],
                   bbox=[0.012, 0.5 - alt / 2, 0.225, alt])
    tab.auto_set_font_size(False)
    tab.set_fontsize(fs)
    for (row, _c), cell in tab.get_celld().items():
        cell.set_linewidth(0.5)
        cell.set_facecolor("#FFFFFF" if row % 2 else "#F1EBDD")
        cell.set_alpha(0.92)
        if row == 0:
            cell.set_facecolor(VERDE)
            cell.set_text_props(color="white", weight="bold")
            cell.set_alpha(1)

    # ---- canto inferior DIREITO: norte + escala gráfica + escala absoluta ----
    ax_w_m = ax.get_position().width * fig.get_figwidth() * 0.0254
    escala_n = (xmax - xmin) / ax_w_m
    escala_txt = f"1:{round(escala_n / 50) * 50:,.0f}".replace(",", ".")

    halo = [matplotlib.patheffects.withStroke(linewidth=2.2, foreground="black")]
    # seta de Norte
    ax.annotate("", xy=(0.945, 0.235), xytext=(0.945, 0.155),
                xycoords="axes fraction",
                arrowprops=dict(facecolor="white", edgecolor="black",
                                width=5, headwidth=14, headlength=12))
    ax.text(0.945, 0.135, "N", transform=ax.transAxes, ha="center", va="top",
            fontsize=11, weight="bold", color="white", path_effects=halo)
    # escala gráfica (preto/branco), encostada à direita
    bar = _passo_nice((xmax - xmin) * 0.18)
    x1 = xmin + (xmax - xmin) * 0.975
    x0 = x1 - bar
    y0 = ymin + (ymax - ymin) * 0.055
    h = (ymax - ymin) * 0.010
    ax.add_patch(Rectangle((x0, y0), bar / 2, h, facecolor="black",
                           edgecolor="black", zorder=7))
    ax.add_patch(Rectangle((x0 + bar / 2, y0), bar / 2, h, facecolor="white",
                           edgecolor="black", zorder=7))
    lbl_m = f"{bar:.0f} m" if bar < 1000 else f"{bar/1000:g} km"
    for fx, t in ((0, "0"), (0.5, f"{bar/2:g}"), (1.0, lbl_m)):
        ax.text(x0 + bar * fx, y0 + h * 1.8, t, ha="center", fontsize=7,
                color="white", weight="bold", zorder=7, path_effects=halo)
    # escala absoluta logo abaixo da barra
    ax.text(0.975, 0.018, f"Escala {escala_txt}", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=7.5, weight="bold", color="white",
            zorder=7, path_effects=halo)

    # ---------------- PAINEL LATERAL ----------------
    PX, PW = 0.705, 0.278

    # 1) Cabeçalho com logos
    axh = fig.add_axes([PX, 0.875, PW, 0.080]); _caixa(axh)
    axl1 = fig.add_axes([PX + 0.004, 0.879, 0.075, 0.072]); _logo(axl1, "logo_ic_dark.jpg")
    axl2 = fig.add_axes([PX + PW - 0.062, 0.879, 0.058, 0.072]); _logo(axl2, "logo_jurema_transparente.png")
    axh.text(0.5, 0.5, "INSTITUTO CERRADOS\nPROGRAMA JUREMA DE\nPROTEÇÃO AO CERRADO",
             transform=axh.transAxes, ha="center", va="center",
             fontsize=7.5, weight="bold", color="black", linespacing=1.5)

    # 2) Mapa de contexto (na escala do município / DF)
    axc = fig.add_axes([PX, 0.640, PW, 0.225])
    from pyproj import Transformer
    tr = Transformer.from_crs(epsg, 4674, always_xy=True)
    ref = rppn or imovel
    lon, lat = tr.transform(ref.centroid.x, ref.centroid.y)
    _contexto(axc, lon, lat, str(dados.get("uf", "")).upper(),
              municipio=dados.get("municipio", ""))

    # 3) Blocos de informação (grade 2 colunas) — texto sempre dentro do box
    info_esq = [("Denominação:", dados.get("nome_imovel", "")),
                ("Interessado(a)/Proprietário(a):", dados.get("proprietario", "")),
                ("Município / UF:", f"{dados.get('municipio','')} - {dados.get('uf','')}")]
    info_dir = [("Solicitação:", dados.get("solicitacao", "Criação de RPPN")),
                ("Escala", escala_txt),
                ("Área da RPPN proposta:", f"{dados.get('area_rppn_ha','—')} ha"),
                ("Área do Imóvel:", f"{dados.get('area_imovel_ha','—')} ha")]
    y_top, y_bot = 0.630, 0.435
    n_l = len(info_esq); h_l = (y_top - y_bot) / n_l
    for i, (k, v) in enumerate(info_esq):
        a = fig.add_axes([PX, y_top - (i + 1) * h_l, PW * 0.555, h_l]); _caixa(a)
        _texto_caixa(a, k, 0.80, 6.0, largura=30, peso="bold")
        _texto_caixa(a, v, 0.38, 7.0, largura=24)
    n_r = len(info_dir); h_r = (y_top - y_bot) / n_r
    for i, (k, v) in enumerate(info_dir):
        a = fig.add_axes([PX + PW * 0.555, y_top - (i + 1) * h_r, PW * 0.445, h_r]); _caixa(a)
        _texto_caixa(a, k, 0.72, 5.8, largura=24, peso="bold")
        _texto_caixa(a, v, 0.28, 6.6, largura=20)

    # 4) Responsável técnico / conferência
    axr = fig.add_axes([PX, 0.355, PW, 0.075]); _caixa(axr)
    rt = dados.get("resp_tecnico", "")
    crea = dados.get("crea", "")
    _texto_caixa(axr, "Responsável Técnico:", 0.80, 6.0, largura=40, peso="bold")
    _texto_caixa(axr, rt, 0.46, 7.2, largura=34)
    _texto_caixa(axr, f"CREA: {crea}" if crea else "", 0.16, 6.2, largura=40)

    # 5) Legenda
    axg = fig.add_axes([PX, 0.135, PW, 0.205]); _caixa(axg)
    axg.text(0.5, 0.92, "Legenda", fontsize=9.5, weight="bold", ha="center",
             transform=axg.transAxes)
    itens = [("dot", "Vértices da RPPN"),
             ("tri", "Localização da Propriedade"),
             ("rppn", "Área da RPPN"),
             ("imovel", "Área do Imóvel Rural"),
             ("uf", "Limite Estadual")]
    for i, (tipo, txt) in enumerate(itens):
        yy = 0.76 - i * 0.155
        if tipo == "dot":
            axg.plot(0.10, yy, "o", color="red", mec="#7a0000", ms=6,
                     transform=axg.transAxes)
        elif tipo == "tri":
            axg.plot(0.10, yy, "^", color="red", mec="darkred", ms=8,
                     transform=axg.transAxes)
        elif tipo == "rppn":
            axg.add_patch(Rectangle((0.055, yy - 0.045), 0.09, 0.09,
                          transform=axg.transAxes, facecolor=COR_RPPN["face"],
                          alpha=0.7, edgecolor=COR_RPPN["edge"], linewidth=1.6))
        elif tipo == "imovel":
            axg.add_patch(Rectangle((0.055, yy - 0.045), 0.09, 0.09,
                          transform=axg.transAxes, facecolor="#f2f2f2",
                          edgecolor="#9a9a9a", linewidth=1.6))
        else:
            axg.add_patch(Rectangle((0.055, yy - 0.045), 0.09, 0.09,
                          transform=axg.transAxes, facecolor="white",
                          edgecolor="black", linewidth=1.0))
        axg.text(0.20, yy, txt, fontsize=7.2, va="center", transform=axg.transAxes)

    # 6) Rodapé (datum / créditos) — linhas curtas + fonte pequena, SEMPRE dentro
    axf = fig.add_axes([PX, 0.052, PW, 0.078]); _caixa(axf)
    linhas_rod = [
        f"Datum: SIRGAS 2000 · Projeção UTM · {zona_txt}",
        "Base: Esri World Imagery · IBGE (malhas municipal e estadual)",
        "Elaboração: Plataforma RPPN",
        "Instituto Cerrados / Programa Jurema",
    ]
    maior = max(len(li) for li in linhas_rod)
    fs_rod = 5.4 if maior <= 58 else 4.8
    axf.text(0.5, 0.5, "\n".join(linhas_rod), fontsize=fs_rod, ha="center",
             va="center", transform=axf.transAxes, linespacing=1.55, clip_on=True)

    # título discreto (nome da RPPN) sobre o mapa
    nome = dados.get("nome_rppn") or titulo or ""
    if nome:
        ax.text(0.5, 0.985, nome, transform=ax.transAxes, ha="center", va="top",
                fontsize=11, weight="bold", color="white",
                path_effects=[matplotlib.patheffects.withStroke(linewidth=3,
                                                                foreground=VERDE)])

    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, facecolor="white")
    plt.close(fig)
    return {"arquivo": str(out_png), "escala": escala_txt, "zona_epsg": epsg,
            "com_satelite": img is not None}
