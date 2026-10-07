# -*- coding: utf-8 -*-
"""
Plataforma RPPN — Instituto Cerrados / Programa Jurema
Front-end para preencher os dados de uma RPPN sem entrar no SIMRPPN,
incluindo o perímetro georreferenciado e o mapa técnico.
FASE 1: layout e funcionalidades (sem login, sem publicação).
"""
from __future__ import annotations

import base64
import importlib
import json
import sys
import tempfile
import zipfile
from datetime import date, datetime
from pathlib import Path

import streamlit as st
from shapely.geometry import shape
from shapely.ops import transform as shp_transform

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gerar_coordenadas as gc          # noqa: E402
import geo_utils as G                    # noqa: E402
import mapa_tecnico as MT                # noqa: E402
# dev: garante que edições nos módulos entrem sem reiniciar o servidor
G = importlib.reload(G)
MT = importlib.reload(MT)

# ----- identidade visual: Programa Jurema (base IC) ------------------------
VERDE = "#004F23"        # verde oficial IC/Jurema
BEGE = "#DDCCA4"
MAGENTA = "#E00080"      # rosa da flor do Jurema — acento
ASSETS = Path(__file__).resolve().parent / "assets"

UFS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
       "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
       "SP", "SE", "TO"]
SAIDAS = Path(__file__).resolve().parent / "saidas"
SAIDAS.mkdir(exist_ok=True)

st.set_page_config(page_title="Plataforma RPPN — Programa Jurema",
                   page_icon=str(ASSETS / "logo_jurema_transparente.png")
                   if (ASSETS / "logo_jurema_transparente.png").exists() else "🌳",
                   layout="wide")


def _b64(path):
    try:
        return base64.b64encode(Path(path).read_bytes()).decode()
    except Exception:
        return ""


_LOGO_IC = _b64(ASSETS / "logo_ic.png")                    # branca (p/ fundo verde)
_LOGO_JU = _b64(ASSETS / "logo_jurema_transparente.png")   # colorida (p/ chip branco)

st.markdown(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Londrina+Solid:wght@400&family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  .stApp {{ background: #FCFAF4; font-family: 'Montserrat', sans-serif; }}
  h1,h2,h3 {{ font-family: 'Montserrat', sans-serif; }}
  .ic-header {{ background: {VERDE}; color:#fff; padding:14px 24px;
    border-radius:12px; margin-bottom:8px; display:flex; align-items:center;
    gap:20px; border-bottom: 4px solid {MAGENTA}; }}
  .ic-header img.ic {{ height:44px; }}
  .ic-header .chip {{ background:#fff; border-radius:10px; padding:4px 8px;
    margin-left:auto; }}
  .ic-header .chip img {{ height:52px; }}
  .ic-header a.guia {{ background:{BEGE}; color:#1a1a1a; text-decoration:none;
    font-weight:600; font-size:.9rem; padding:9px 16px; border-radius:20px;
    white-space:nowrap; border:2px solid transparent; }}
  .ic-header a.guia:hover {{ border-color:{MAGENTA}; color:#1a1a1a; }}
  .ic-header h1 {{ margin:0; font-size:1.45rem; font-family:'Londrina Solid',
    'Montserrat', sans-serif; font-weight:400; letter-spacing:.5px; }}
  .ic-header p {{ margin:2px 0 0; opacity:.92; font-size:.88rem; }}
  .stTabs [data-baseweb="tab-list"] {{ gap:6px; flex-wrap:wrap; }}
  .stTabs [data-baseweb="tab"] {{ background:#F1EBDD; border-radius:8px 8px 0 0;
     padding:10px 16px; height:auto; }}
  .stTabs [data-baseweb="tab"] p {{ font-size:.95rem; white-space:nowrap; margin:0; }}
  .stTabs [aria-selected="true"] {{ background:{VERDE}; }}
  .stTabs [aria-selected="true"] p {{ color:#fff; }}
  /* a última aba (Administrar) fica encostada à direita */
  .stTabs [data-baseweb="tab-list"] button:last-child {{ margin-left:auto;
     background:#E9E2CE; }}
  .stTabs [data-baseweb="tab-list"] button:last-child[aria-selected="true"] {{
     background:{VERDE}; }}
  div[data-testid="stMetricValue"] {{ color:{VERDE}; }}
  .instr-box {{ background:#F5F0E3; border-left:5px solid {MAGENTA};
     padding:12px 16px; border-radius:6px; margin:6px 0 12px; font-size:.95rem; }}
  .instr-box b {{ color:{VERDE}; }}
  .instr-box svg {{ vertical-align:-3px; margin-right:6px; }}
</style>
<div class="ic-header">
  <img class="ic" src="data:image/png;base64,{_LOGO_IC}" alt="Instituto Cerrados"/>
  <div><h1>Plataforma RPPN</h1>
  <p>Programa Jurema — Proteção do Cerrado · Preencha os dados da sua Reserva;
     a plataforma organiza tudo e envia ao SIMRPPN por você.</p></div>
  {{BOTAO_GUIA}}
  <span class="chip"><img src="data:image/png;base64,{_LOGO_JU}" alt="Jurema"/></span>
</div>
""".replace("{BOTAO_GUIA}", (
    '<a class="guia" href="/app/static/guia_usuario.html" target="_blank">'
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#1a1a1a" '
    'stroke-width="2" style="vertical-align:-2px;margin-right:6px">'
    '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>'
    '<path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>'
    '</svg>Guia do Usuário</a>')
    if st.config.get_option("server.enableStaticServing") else ""),
    unsafe_allow_html=True)

# fallback: sem static serving (servidor iniciado antes da config), o guia sai
# como download — nunca uma página em branco
if not st.config.get_option("server.enableStaticServing"):
    _guia = Path(__file__).resolve().parent / "static" / "guia_usuario.html"
    if _guia.exists():
        st.download_button("Guia do Usuário (abre no navegador)",
                           _guia.read_bytes(), file_name="guia_usuario.html",
                           mime="text/html", icon=":material/menu_book:")
        st.caption("Dica: reinicie o servidor (Ctrl+C e rodar de novo) para o guia "
                   "abrir direto do cabeçalho, sem download.")

# --- Autenticação: acesso restrito a contas @cerrados.org ------------------
DOMINIO = "@cerrados.org"
try:
    _tem_auth = "auth" in st.secrets
except Exception:
    _tem_auth = False
if _tem_auth:
    if not st.user.is_logged_in:
        c = st.columns([1, 2, 1])[1]
        with c:
            st.markdown("### Acesso restrito")
            st.write(f"Entre com sua conta **{DOMINIO}** para acessar a "
                     "Plataforma RPPN.")
            st.button("Entrar com Google", type="primary", on_click=st.login,
                      icon=":material/login:")
            st.caption("Ferramenta interna do Instituto Cerrados · Programa Jurema.")
        st.stop()
    if not str(st.user.email or "").lower().endswith(DOMINIO):
        st.error(f"Acesso restrito a contas {DOMINIO}. A conta "
                 f"**{st.user.email}** não tem permissão.")
        st.button("Sair", on_click=st.logout, icon=":material/logout:")
        st.stop()
    with st.sidebar:
        st.caption(f"Conectado: {st.user.email}")
        st.button("Sair", on_click=st.logout, icon=":material/logout:")

# ícones SVG (profissionais, sem emoji)
_SVG = {
    "draw": f'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="{VERDE}" stroke-width="2"><path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/><circle cx="11" cy="11" r="2"/></svg>',
    "edit": f'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="{VERDE}" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>',
    "check": f'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="{VERDE}" stroke-width="2.4"><polyline points="20 6 9 17 4 12"/></svg>',
    "pin": f'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="{MAGENTA}" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
}

ss = st.session_state
ss.setdefault("n_imoveis", 1)
ss.setdefault("n_prop", 1)
for role in ("imovel", "rppn"):
    ss.setdefault(role, None)


# ---------------------------------------------------------------------------
def _reproj(poly, src, dst):
    from pyproj import Transformer
    t = Transformer.from_crs(src, dst, always_xy=True)
    return shp_transform(lambda x, y, z=None: t.transform(x, y), poly)


def _verts_df(poly_utm):
    import pandas as pd
    coords = list(poly_utm.exterior.coords)[:-1]
    return pd.DataFrame({"PONTO": [f"P-{i:02d}" for i in range(1, len(coords) + 1)],
                         "X": [round(x, 2) for x, _ in coords],
                         "Y": [round(y, 2) for _, y in coords], "Descrição": ""})


def _guarda_role(role, poly_utm, epsg, verts=None):
    geo_wgs = json.loads(__import__("geopandas").GeoSeries([poly_utm], crs=epsg)
                         .to_crs(4326).to_json())
    ss[role] = {"poly_utm": poly_utm, "epsg": epsg,
                "verts_df": verts if verts is not None else _verts_df(poly_utm),
                "geo_wgs": geo_wgs}


def _guia_poly(spec, epsg):
    if spec == "car":
        feats = ss["car_geo"]["features"]
        poly4326 = max((shape(f["geometry"]) for f in feats), key=lambda p: p.area)
        return _reproj(poly4326, 4326, epsg)
    p = spec["poly_utm"]
    return p if spec["epsg"] == epsg else _reproj(p, spec["epsg"], epsg)


def _snap_auto(role):
    """Aderência automática (estilo ArcGIS): aplicada ao definir a geometria.
    Guarda mensagem em ss['_snap_msgs'] (exibida de forma persistente)."""
    if not ss.get("snap_on", True) or ss[role] is None:
        return
    tol = ss.get("snap_tol", 10)
    epsg = ss[role]["epsg"]
    guias, ref = [], ""
    if role == "rppn" and ss["imovel"]:
        guias.append(_guia_poly(ss["imovel"], epsg)); ref = "imóvel"
    if role == "imovel" and ss.get("car_geo"):
        guias.append(_guia_poly("car", epsg)); ref = "CAR"
    if not guias:
        return
    novo, n = G.aderir_vertices(ss[role]["poly_utm"], guias, tol)
    msgs = ss.setdefault("_snap_msgs", [])
    nome = "RPPN" if role == "rppn" else "Imóvel"
    if n:
        _guarda_role(role, novo, epsg)
        msgs.append(("ok", f"Aderência: {n} vértice(s) do {nome} colado(s) ao "
                           f"{ref} (tolerância {tol} m)."))
    else:
        msgs.append(("info", f"Aderência: nenhum vértice do {nome} estava a até "
                             f"{tol} m do {ref}. Se esperava colar, aumente a "
                             f"tolerância e clique em “Aplicar aderência agora”."))


def _definir_geometria(role, poly, crs_origem, verts=None):
    """Reprojeta p/ UTM SIRGAS2000 (zona automática), guarda e aplica aderência."""
    poly4326 = _reproj(poly, crs_origem, 4326) if crs_origem != 4326 else poly
    c = poly4326.centroid
    zona = gc.zona_pelo_centroide(c.x, c.y)
    epsg = gc.epsg_da_zona(zona)
    _guarda_role(role, _reproj(poly4326, 4326, epsg), epsg, verts)
    _snap_auto(role)
    return zona


def _ler_arquivo_geo(files):
    import geopandas as gpd
    tmp = Path(tempfile.mkdtemp())
    caminho = None
    for f in (files if isinstance(files, list) else [files]):
        dest = tmp / f.name
        dest.write_bytes(f.getbuffer())
        low = f.name.lower()
        if low.endswith(".zip"):
            with zipfile.ZipFile(dest) as z:
                z.extractall(tmp)
            shp = list(tmp.glob("**/*.shp"))
            caminho = shp[0] if shp else caminho
        elif low.endswith((".kml", ".gpkg", ".geojson", ".json", ".shp")):
            caminho = dest
    if caminho is None:
        raise ValueError("Envie um .zip do shapefile, ou um .kml/.gpkg/.geojson.")
    gdf = gpd.read_file(caminho)
    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])]
    if gdf.empty:
        raise ValueError("O arquivo não contém polígonos.")
    if gdf.crs is None:
        gdf = gdf.set_crs(4674)
    g = gdf.geometry.union_all()
    if g.geom_type == "MultiPolygon":
        g = max(g.geoms, key=lambda p: p.area)
    return g, gdf.crs.to_epsg() or 4674


# Estilos do mapa: Imóvel branco; RPPN amarelo escuro/claro
ESTILO = {
    "imovel": {"color": "#FFFFFF", "weight": 3, "fillColor": "#FFFFFF", "fillOpacity": .18},
    "rppn":   {"color": "#8B6914", "weight": 3, "fillColor": "#FFF176", "fillOpacity": .40},
}

_DRAW_PTBR = """{% macro script(this, kwargs) %}
if (window.L && L.drawLocal) {
  var D = L.drawLocal;
  D.draw.toolbar.actions = {title:'Cancelar o desenho', text:'Cancelar'};
  D.draw.toolbar.finish  = {title:'Concluir o desenho', text:'Concluir'};
  D.draw.toolbar.undo    = {title:'Apagar o último vértice', text:'Apagar último ponto'};
  D.draw.toolbar.buttons.polygon = 'Desenhar o limite (polígono)';
  D.draw.handlers.polygon.tooltip.start = 'Clique no mapa para iniciar o polígono.';
  D.draw.handlers.polygon.tooltip.cont  = 'Clique para adicionar vértices.';
  D.draw.handlers.polygon.tooltip.end   = 'Clique no primeiro vértice para fechar.';
  D.edit.toolbar.actions.save   = {title:'Salvar as alterações', text:'Salvar'};
  D.edit.toolbar.actions.cancel = {title:'Cancelar; descartar as alterações', text:'Cancelar'};
  D.edit.toolbar.actions.clearAll = {title:'Apagar todos os polígonos', text:'Apagar tudo'};
  D.edit.toolbar.buttons.edit = 'Editar polígono (arrastar vértices)';
  D.edit.toolbar.buttons.editDisabled = 'Nada para editar — desenhe primeiro';
  D.edit.toolbar.buttons.remove = 'Apagar polígono';
  D.edit.toolbar.buttons.removeDisabled = 'Nada para apagar — desenhe primeiro';
  D.edit.handlers.edit.tooltip.text = 'Arraste os vértices para ajustar o limite.';
  D.edit.handlers.edit.tooltip.subtext = 'Clique em Cancelar para desfazer.';
  D.edit.handlers.remove.tooltip.text = 'Clique num polígono para apagá-lo.';
}
{% endmacro %}"""


def _ring_latlon(role):
    """Anel externo do polígono salvo, como [(lat, lon), ...] p/ folium.Polygon."""
    coords = ss[role]["geo_wgs"]["features"][0]["geometry"]["coordinates"][0]
    return [(lat, lon) for lon, lat in coords]


def _mapa(desenhar=False, role_desenho="imovel"):
    import folium
    from folium import MacroElement
    from jinja2 import Template
    # tiles=None: sem base implícita. A ÚLTIMA base adicionada fica ativa no
    # Leaflet — satélite por último garante satélite como padrão em TODO
    # re-render (modo edição, troca Imóvel↔RPPN etc.).
    m = folium.Map(location=[-15.6, -47.8], zoom_start=5, control_scale=True,
                   tiles=None)
    folium.TileLayer("OpenStreetMap", name="Mapa (ruas)", overlay=False).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
              "MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="Satélite", overlay=False).add_to(m)
    bounds = None
    nomes = {"imovel": "Limite do Imóvel (propriedade)", "rppn": "Limite da RPPN"}
    if ss.get("car_on") and ss.get("car_geo"):
        folium.GeoJson(ss["car_geo"], name="Limite do CAR (SICAR)",
                       style_function=lambda _f: {"color": "#E8A400", "weight": 2.5,
                       "dashArray": "6 4", "fill": False}).add_to(m)
    for role in ("imovel", "rppn"):
        if not ss[role]:
            continue
        # o polígono do ALVO atual, em modo desenho, vai para o feature group do
        # editor (vira L.polygon editável); os demais ficam como camada estática
        if desenhar and role == role_desenho:
            continue
        gj = folium.GeoJson(ss[role]["geo_wgs"], name=nomes[role],
                            style_function=lambda _f, s=ESTILO[role]: s)
        gj.add_to(m)
        b = gj.get_bounds()
        if b and b[0][0] is not None:
            bounds = b if bounds is None else [
                [min(bounds[0][0], b[0][0]), min(bounds[0][1], b[0][1])],
                [max(bounds[1][0], b[1][0]), max(bounds[1][1], b[1][1])]]
    if desenhar:
        from folium.plugins import Draw
        loc = MacroElement()
        loc._template = Template(_DRAW_PTBR)
        m.add_child(loc)
        s = ESTILO[role_desenho]
        # feature group do editor: o que estiver aqui ganha alças de edição
        fg = folium.FeatureGroup(name=nomes[role_desenho])
        if ss[role_desenho]:
            pol = folium.Polygon(locations=_ring_latlon(role_desenho),
                                 color=s["color"], weight=3, fill=True,
                                 fill_color=s["fillColor"],
                                 fill_opacity=s["fillOpacity"])
            pol.add_to(fg)
            b = pol.get_bounds()
            if b and b[0][0] is not None:
                bounds = b if bounds is None else [
                    [min(bounds[0][0], b[0][0]), min(bounds[0][1], b[0][1])],
                    [max(bounds[1][0], b[1][0]), max(bounds[1][1], b[1][1])]]
        fg.add_to(m)
        Draw(export=False, position="topleft", feature_group=fg,
             draw_options={"polyline": False, "circle": False, "marker": False,
                           "circlemarker": False, "rectangle": False,
                           "polygon": {"allowIntersection": False, "showArea": True,
                                       "shapeOptions": {"color": s["color"],
                                       "fillColor": s["fillColor"],
                                       "fillOpacity": s["fillOpacity"], "weight": 3}}},
             edit_options={"edit": True, "remove": True}).add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    if bounds:
        m.fit_bounds(bounds)
    return m


def _tabela_rppns_html(dfv):
    """Tabela HTML no padrão da ferramenta: cabeçalho verde, zebra bege, links."""
    import html as _html
    cols = [("nome", "RPPN"), ("uf", "UF"), ("municipio", "Município"),
            ("proprietario", "Proprietário(a)"), ("status", "Status"),
            ("area_rppn_ha", "Área (ha)"), ("data_criacao", "Criação"),
            ("pagina", "Página")]
    th = "".join(f"<th>{_html.escape(t)}</th>" for _, t in cols)
    rows = []
    for _, r in dfv.iterrows():
        tds = []
        for key, _t in cols:
            val = r.get(key, "")
            if key == "area_rppn_ha":
                try:
                    cell = f"{float(val):.2f}".replace(".", ",")
                except (TypeError, ValueError):
                    cell = "—"
                tds.append(f'<td style="text-align:right">{cell}</td>')
            elif key == "pagina":
                u = str(val or "")
                cell = (f'<a href="{_html.escape(u)}" target="_blank">abrir</a>'
                        if u else "—")
                tds.append(f'<td style="text-align:center">{cell}</td>')
            else:
                cell = _html.escape(str(val)) if val not in (None, "") else "—"
                tds.append(f"<td>{cell}</td>")
        rows.append("<tr>" + "".join(tds) + "</tr>")
    css = (
        "<style>"
        ".tbl-adm{border-collapse:collapse;width:100%;font-size:.85rem;"
        "font-family:Montserrat,sans-serif}"
        ".tbl-adm thead th{background:" + VERDE + ";color:#fff;padding:7px 9px;"
        "text-align:left;position:sticky;top:0;z-index:1}"
        ".tbl-adm td{border:1px solid #e6e0cf;padding:5px 9px}"
        ".tbl-adm tbody tr:nth-child(even){background:#FAF7EE}"
        ".tbl-adm a{color:" + VERDE + ";font-weight:600;text-decoration:none}"
        ".tbl-adm-wrap{max-height:360px;overflow:auto;border:1px solid #e3ddcb;"
        "border-radius:6px}"
        "</style>")
    return (css + '<div class="tbl-adm-wrap"><table class="tbl-adm"><thead><tr>'
            + th + "</tr></thead><tbody>" + "".join(rows)
            + "</tbody></table></div>")


# ===========================================================================
abas = st.tabs([
    ":material/forest: RPPN",
    ":material/home_work: Imóvel",
    ":material/group: Proprietários",
    ":material/engineering: Resp. Técnico",
    ":material/map: Perímetro / Mapa",
    ":material/folder: Documentos",
    ":material/fact_check: Revisão",
    ":material/timeline: Processos",
    ":material/admin_panel_settings: Administrar",
])


import dados_remotos as DR
DR = importlib.reload(DR)


def _publicar_arquivos(arquivos: dict[str, str], mensagem: str) -> bool:
    """Grava {nome: conteúdo} no repositório privado de dados (token nos secrets)
    ou na pasta local dados/ (desenvolvimento). A tela vê o resultado na hora."""
    with st.spinner("Gravando…"):
        try:
            onde = DR.gravar(arquivos, mensagem)
        except Exception as e:
            st.error(f"Falha ao gravar: {e}")
            return False
    st.success(f"Pronto — {onde}.")
    return True

# --- 1. RPPN ---------------------------------------------------------------
with abas[0]:
    st.subheader("Dados da RPPN")
    c1, c2 = st.columns(2)
    with c1:
        st.text_input("Nome da RPPN *", key="rppn_nome",
                      placeholder="Ex.: RPPN Santuário Ecológico Mãe Terra")
        st.selectbox("Unidade da Federação (UF) *", UFS, key="rppn_uf",
                     index=UFS.index("GO"))
    with c2:
        st.text_input("Área proposta da RPPN, em hectares (ha) *", key="rppn_area",
                      placeholder="Ex.: 2,38")
        st.text_input("Município *", key="rppn_municipio",
                      placeholder="Ex.: Alto Paraíso de Goiás")
    st.caption("Campos com * são obrigatórios no SIMRPPN.")

# --- 2. Imóvel -------------------------------------------------------------
with abas[1]:
    st.subheader("Dados do(s) Imóvel(is)")
    st.caption("Uma RPPN pode abranger mais de um imóvel. Use “Adicionar imóvel” se necessário.")
    for i in range(ss["n_imoveis"]):
        with st.container(border=True):
            st.markdown(f"**Imóvel {i + 1}**")
            a, b = st.columns(2)
            with a:
                st.text_input("Nome do Imóvel", key=f"im_{i}_nome_imovel")
                st.text_input("Área do Imóvel, em hectares (ha)", key=f"im_{i}_area_imovel_ha")
                st.text_input("Registro / Matrícula", key=f"im_{i}_registro_matricula")
                st.text_input("Área da RPPN referente a este imóvel (ha)",
                              key=f"im_{i}_area_rppn_neste_imovel_ha")
                st.text_input("Logradouro", key=f"im_{i}_logradouro")
                st.text_input("Número", key=f"im_{i}_numero")
                st.text_input("Complemento", key=f"im_{i}_complemento")
                st.text_input("Bairro", key=f"im_{i}_bairro")
            with b:
                st.text_input("CEP", key=f"im_{i}_cep")
                st.selectbox("Unidade da Federação (UF)", UFS, key=f"im_{i}_uf")
                st.text_input("Município", key=f"im_{i}_municipio")
                st.text_input("Telefone", key=f"im_{i}_telefone")
                st.text_input("E-mail", key=f"im_{i}_email")
                st.radio("Tipo de Imóvel", ["Rural", "Urbano"],
                         key=f"im_{i}_tipo_imovel", horizontal=True)
                st.text_input("Código do Imóvel Rural (CCIR)", key=f"im_{i}_ccir")
                st.text_input("Código do CAR (SICAR)", key=f"im_{i}_codigo_car")
            if ss["n_imoveis"] > 1:
                if st.button("Remover este imóvel", key=f"rm_im_{i}",
                             icon=":material/delete:"):
                    ss["n_imoveis"] -= 1
                    st.rerun()
    if st.button("Adicionar imóvel", icon=":material/add:"):
        ss["n_imoveis"] += 1
        st.rerun()

# --- 3. Proprietários ------------------------------------------------------
with abas[2]:
    st.subheader("Proprietário(s) do Imóvel")
    for i in range(ss["n_prop"]):
        with st.container(border=True):
            st.markdown(f"**Proprietário {i + 1}**")
            a, b = st.columns(2)
            with a:
                st.text_input("Nome completo", key=f"pr_{i}_nome")
                st.text_input("CPF ou CNPJ", key=f"pr_{i}_cpf_cnpj")
                st.text_input("E-mail", key=f"pr_{i}_email")
            with b:
                st.text_input("Telefone", key=f"pr_{i}_telefone")
                st.text_input("Celular", key=f"pr_{i}_celular")
            if ss["n_prop"] > 1:
                if st.button("Remover este proprietário", key=f"rm_pr_{i}",
                             icon=":material/delete:"):
                    ss["n_prop"] -= 1
                    st.rerun()
    if st.button("Adicionar proprietário", icon=":material/add:"):
        ss["n_prop"] += 1
        st.rerun()

# --- 4. Responsável técnico ------------------------------------------------
with abas[3]:
    st.subheader("Responsável Técnico pelas peças cartográficas")
    st.caption("Profissional habilitado (CREA + ART). Necessário para o memorial descritivo.")
    a, b = st.columns(2)
    with a:
        st.text_input("Nome completo *", key="rt_nome")
        st.text_input("CPF *", key="rt_cpf")
        st.text_input("Número de Registro no CREA *", key="rt_crea")
        st.text_input("Título do Profissional *", key="rt_titulo",
                      placeholder="Ex.: Engenheiro Agrimensor")
    with b:
        st.text_input("Número da ART específica (devidamente paga) *", key="rt_art")
        st.text_input("Telefone *", key="rt_tel")
        st.text_input("E-mail *", key="rt_email")

# --- 5. Perímetro / Mapa ---------------------------------------------------
with abas[4]:
    st.subheader("Perímetro georreferenciado e Mapa técnico")

    with st.expander("Como preparar cada arquivo (leia antes de enviar)",
                     expanded=False, icon=":material/info:"):
        st.markdown("""
**Você pode informar o perímetro de 3 formas:**

1. **Desenhar no mapa** — digitalize o polígono sobre a imagem de satélite.
   Dá para sobrepor o **limite do CAR** para apoiar a digitalização e a conferência.
2. **Arquivo geográfico** — *shapefile* (envie um **.zip** com `.shp`, `.shx`, `.dbf`, `.prj`),
   **KML**, **GeoPackage (.gpkg)** ou **GeoJSON**, contendo **um polígono** por perímetro.
3. **Tabela de vértices** — planilha **CSV** ou **Excel** com colunas de coordenadas.
   A plataforma **corrige automaticamente** os erros mais comuns: nomes de coluna
   diferentes (X/E/Este/Longitude…), **colunas X/Y trocadas**, **vírgula decimal**,
   separador de milhar, e **converte coordenadas geográficas para UTM SIRGAS 2000**
   (a zona é deduzida sozinha). Se os dados já forem UTM, informe a zona.

A saída é sempre **SIRGAS 2000 (UTM)**, exigido pelo SIMRPPN. A **RPPN precisa estar
contida no imóvel** (podendo compartilhar trechos de limite) — validado antes de concluir.
        """)

    # ordem: primeiro a propriedade
    tem_imovel = ss["imovel"] is not None
    if not tem_imovel:
        st.markdown(f'<div class="instr-box">{_SVG["pin"]} Comece pelo '
                    '<b>Imóvel (a propriedade)</b>. A opção <b>RPPN</b> é liberada '
                    'depois que a propriedade estiver definida — assim a plataforma '
                    'valida se a RPPN está dentro (ou limítrofe) do imóvel.</div>',
                    unsafe_allow_html=True)

    c_modo, c_alvo = st.columns([2.4, 1.6])
    modo = c_modo.radio("Como você quer informar o perímetro?",
                        ["Desenhar no mapa", "Enviar arquivo geográfico",
                         "Enviar tabela de vértices"], horizontal=True, key="modo_geo")
    opcoes_alvo = ["Imóvel"] if not tem_imovel else ["Imóvel", "RPPN"]
    alvo = c_alvo.radio("Este perímetro é do:", opcoes_alvo, horizontal=True,
                        key="alvo_geo")
    role = "imovel" if alvo == "Imóvel" else "rppn"

    # aderência (snapping) — estilo ArcGIS: liga/desliga + tolerância, automática
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.4, 1.6, 3])
        ss["snap_on"] = c1.toggle("Aderência (snapping)", value=ss.get("snap_on", True),
                                  help="Como no ArcGIS: ao concluir um limite, os vértices "
                                       "próximos 'grudam' na geometria de referência — a RPPN "
                                       "adere ao imóvel; o imóvel adere ao CAR (se carregado).")
        ss["snap_tol"] = c2.slider("Tolerância (m)", 1, 100, ss.get("snap_tol", 10),
                                   disabled=not ss["snap_on"],
                                   help="Desenho à mão costuma pedir 10–50 m; "
                                        "arquivos precisos, 1–5 m.")
        with c3:
            aplicar = st.button("Aplicar aderência agora",
                                icon=":material/join_inner:",
                                disabled=not ((ss["rppn"] and ss["imovel"]) or
                                              (ss["imovel"] and ss.get("car_geo"))))
        if aplicar:
            ss["_snap_msgs"] = []
            for r_ in ("imovel", "rppn"):
                if ss[r_]:
                    _snap_auto(r_)
        for kind, msg in ss.get("_snap_msgs", []):
            (st.success if kind == "ok" else st.info)(msg)
        ss["_snap_msgs"] = []

    # ---- entradas por modo ----
    if modo == "Enviar arquivo geográfico":
        up = st.file_uploader("Shapefile (.zip), KML, GPKG ou GeoJSON",
                              accept_multiple_files=True, key="up_geo")
        if st.button("Processar arquivo", type="primary", icon=":material/upload_file:"):
            try:
                g, epsg_in = _ler_arquivo_geo(up)
                zona = _definir_geometria(role, g, epsg_in)
                st.success(f"{alvo} processado — zona UTM {zona}, "
                           f"{ss[role]['verts_df'].shape[0]} vértices.")
            except Exception as e:
                st.error(f"Falha: {e}")

    elif modo == "Enviar tabela de vértices":
        c = st.columns([3, 1])
        up = c[0].file_uploader("Tabela CSV ou Excel de vértices",
                                type=["csv", "xls", "xlsx"], key="up_tab")
        zona_f = c[1].text_input("Zona UTM (se já for UTM)", placeholder="ex.: 23S",
                                 key="zona_tab")
        if st.button("Processar tabela", type="primary", icon=":material/table_view:"):
            try:
                tmp = Path(tempfile.mkdtemp()) / up.name
                tmp.write_bytes(up.getbuffer())
                df_utm, meta = G.parse_tabela_vertices(tmp, zona_forcada=zona_f or None)
                _guarda_role(role, meta["poligono"], meta["epsg"], df_utm)
                _snap_auto(role)
                st.success(f"{alvo} processado — zona {meta['zona']}, "
                           f"{meta['n_pontos']} pontos, {meta['area_ha']} ha.")
                if meta["correcoes"]:
                    st.warning("**Correções automáticas aplicadas:**\n\n- " +
                               "\n- ".join(meta["correcoes"]))
            except Exception as e:
                st.error(f"Falha ao ler a tabela: {e}")

    else:  # desenhar
        st.markdown(
            f'<div class="instr-box">{_SVG["draw"]} <b>Como desenhar:</b> na barra do '
            'canto <b>superior esquerdo</b> do mapa, clique no ícone de <b>polígono</b>; '
            'clique no mapa para marcar cada <b>vértice</b> e feche clicando no primeiro '
            'vértice.<br>'
            f'{_SVG["edit"]} <b>Para editar:</b> use “Editar polígono” e <b>arraste os '
            'vértices</b>; conclua em “Salvar”. Para recomeçar, “Apagar polígono”. '
            'Se o limite selecionado acima já foi definido, ele aparece no mapa '
            '<b>pronto para edição</b>.<br>'
            f'{_SVG["check"]} Ao terminar (ou após editar), clique em '
            '<b>“Usar polígono desenhado”</b>, logo abaixo do mapa.</div>',
            unsafe_allow_html=True)

    # ---- MAPA ÚNICO ----
    from streamlit_folium import st_folium
    desenhando = modo == "Desenhar no mapa"
    out = st_folium(_mapa(desenhar=desenhando, role_desenho=role),
                    use_container_width=True, height=470, key="mapa_unico",
                    returned_objects=["all_drawings"] if desenhando else [])

    if desenhando:
        if out and out.get("all_drawings"):
            ss["tem_desenho"] = True
        if ss.get("tem_desenho") and not ss.get("car_geo"):
            st.info("Deseja **sobrepor o limite do CAR** desta área? Ajuda na "
                    "digitalização e conferência do limite.")
        ss["car_on"] = st.toggle("Sobrepor limite do CAR (SICAR)",
                                 value=ss.get("car_on", False))
        if ss["car_on"] and not ss.get("car_geo"):
            carf = st.file_uploader("Arquivo do CAR (KML / SHP.zip / GPKG)",
                                    accept_multiple_files=True, key="up_car")
            if carf and st.button("Carregar CAR", icon=":material/layers:"):
                try:
                    g, epsg_in = _ler_arquivo_geo(carf)
                    ss["car_geo"] = json.loads(__import__("geopandas")
                        .GeoSeries([g], crs=epsg_in).to_crs(4326).to_json())
                    st.rerun()
                except Exception as e:
                    st.error(f"Falha ao ler o CAR: {e}")
        if out and out.get("all_drawings"):
            if st.button(f"Usar polígono desenhado como {alvo}", type="primary",
                         icon=":material/check_circle:"):
                try:
                    poly = shape(out["all_drawings"][-1]["geometry"])
                    zona = _definir_geometria(role, poly, 4326)
                    st.success(f"{alvo} definido a partir do desenho — zona UTM {zona}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Falha: {e}")

    # ---- resumo + validação ----
    if ss["imovel"] or ss["rppn"]:
        m1, m2, m3 = st.columns(3)
        ai = ss["imovel"]["poly_utm"].area / 10_000 if ss["imovel"] else None
        ar = ss["rppn"]["poly_utm"].area / 10_000 if ss["rppn"] else None
        m1.metric("Área do imóvel (ha)", f"{ai:.4f}".replace(".", ",") if ai else "—")
        m2.metric("Área da RPPN (ha)", f"{ar:.4f}".replace(".", ",") if ar else "—")
        epsg = (ss["rppn"] or ss["imovel"])["epsg"]
        m3.metric("Projeção", f"UTM SIRGAS 2000 · EPSG {epsg}")

        if ss["imovel"] and ss["rppn"]:
            e = ss["imovel"]["epsg"]
            rp = ss["rppn"]["poly_utm"]
            if ss["rppn"]["epsg"] != e:
                rp = _reproj(rp, ss["rppn"]["epsg"], e)
            ok, status, det = G.validar_topologia(ss["imovel"]["poly_utm"], rp)
            (st.success if ok else st.error)(f"**Validação RPPN × Imóvel:** {det}")
            ss["topo_ok"] = ok
        elif ss["rppn"] and not ss["imovel"]:
            st.info("Informe também o perímetro do **imóvel** para validar a relação com a RPPN.")

        # ---- Fazer mapa ----
        st.markdown("### Mapa técnico")
        st.caption("Layout oficial: satélite, grid UTM, norte, escalas, legenda, mapa de "
                   "contexto, memorial de vértices e identificação (modelo Jurema/IC).")
        if st.button("Fazer mapa", type="primary", icon=":material/map:"):
            with st.spinner("Gerando o mapa técnico — baixando a imagem de satélite, "
                            "o limite municipal (IBGE) e montando o layout...",
                            show_time=True):
                try:
                    imv = ss["imovel"]["poly_utm"] if ss["imovel"] else None
                    rpp = ss["rppn"]["poly_utm"] if ss["rppn"] else None
                    epsg = (ss["rppn"] or ss["imovel"])["epsg"]
                    if imv is not None and ss["imovel"]["epsg"] != epsg:
                        imv = _reproj(imv, ss["imovel"]["epsg"], epsg)
                    verts = (ss["rppn"] or ss["imovel"])["verts_df"]
                    dados = {
                        "nome_rppn": ss.get("rppn_nome", ""),
                        "nome_imovel": ss.get("im_0_nome_imovel", ""),
                        "proprietario": ss.get("pr_0_nome", ""),
                        "municipio": ss.get("rppn_municipio", ""),
                        "uf": ss.get("rppn_uf", ""),
                        "area_imovel_ha": (f"{ai:.4f}".replace(".", ",") if ai else
                                           ss.get("im_0_area_imovel_ha", "—")),
                        "area_rppn_ha": (f"{ar:.4f}".replace(".", ",") if ar else
                                         ss.get("rppn_area", "—")),
                        "resp_tecnico": ss.get("rt_nome", ""),
                        "crea": ss.get("rt_crea", ""),
                        "solicitacao": "Criação de RPPN",
                    }
                    png = SAIDAS / "mapa_tecnico.png"
                    info = MT.gerar_mapa_tecnico(imv, rpp, epsg, verts, dados=dados,
                                                 out_png=png)
                    ss["mapa_png"] = str(png)
                    st.success(f"Mapa técnico gerado — escala {info['escala']}, "
                               f"{'com' if info['com_satelite'] else 'sem'} satélite.")
                except Exception as e:
                    st.error(f"Falha ao gerar o mapa: {e}")
        if ss.get("mapa_png") and Path(ss["mapa_png"]).exists():
            st.image(ss["mapa_png"], use_container_width=True)
            st.download_button("Baixar mapa técnico (PNG)",
                               Path(ss["mapa_png"]).read_bytes(),
                               file_name="mapa_tecnico.png",
                               icon=":material/download:")
        cdl = st.columns(2)
        if ss["imovel"]:
            xlsx = SAIDAS / "imovel_coords.xlsx"
            G.gerar_excel_coords(ss["imovel"]["verts_df"], xlsx)
            cdl[0].download_button("Coordenadas do imóvel (Excel SIMRPPN)",
                                   xlsx.read_bytes(), file_name="imovel_coords.xlsx",
                                   icon=":material/download:")
        if ss["rppn"]:
            xlsx = SAIDAS / "rppn_coords.xlsx"
            G.gerar_excel_coords(ss["rppn"]["verts_df"], xlsx)
            cdl[1].download_button("Coordenadas da RPPN (Excel SIMRPPN)",
                                   xlsx.read_bytes(), file_name="rppn_coords.xlsx",
                                   icon=":material/download:")

# --- 6. Documentos ---------------------------------------------------------
with abas[5]:
    st.subheader("Documentos (PDF)")
    st.caption("Anexos exigidos pelo SIMRPPN. As plantas e memoriais são gerados pelo "
               "próprio sistema a partir do perímetro; os demais são certidões externas.")
    docs = [
        ("identidade", "Cédula de identidade do(s) proprietário(s) ou representante legal"),
        ("cnd_itr", "Certidão Negativa de Débitos (ITR)"),
        ("ccir", "Certificado de Cadastro do Imóvel Rural (CCIR)"),
        ("matricula", "Certidão de Matrícula e Registro do Imóvel (atualizada)"),
        ("cadeia_dominial", "Cadeia Dominial Trintenária"),
        ("onus_reais", "Certidão de ônus reais e ações reipersecutórias"),
        ("art_paga", "Anotação de Responsabilidade Técnica (ART) devidamente paga"),
        ("termo_compromisso", "Termo de Compromisso assinado pelo(s) proprietário(s)"),
    ]
    cols = st.columns(2)
    for i, (chave, rotulo) in enumerate(docs):
        with cols[i % 2]:
            st.file_uploader(rotulo, type=["pdf", "doc", "docx", "rtf"], key=f"doc_{chave}")

# --- 7. Revisão ------------------------------------------------------------
with abas[6]:
    st.subheader("Revisão")
    pend = []
    if not ss.get("rppn_nome"): pend.append("Nome da RPPN (aba RPPN)")
    if not ss.get("rppn_area"): pend.append("Área da RPPN (aba RPPN)")
    if not ss.get("imovel"): pend.append("Perímetro do imóvel (aba Perímetro / Mapa)")
    if not ss.get("rppn"): pend.append("Perímetro da RPPN (aba Perímetro / Mapa)")
    if ss.get("imovel") and ss.get("rppn") and not ss.get("topo_ok"):
        pend.append("A RPPN precisa estar contida no imóvel (validação topológica)")
    if not ss.get("rt_crea"): pend.append("Responsável técnico — CREA/ART (aba Resp. Técnico)")

    if pend:
        st.warning("**Pendências antes de enviar ao SIMRPPN:**\n\n- " + "\n- ".join(pend))
    else:
        st.success("Tudo preenchido e válido. Pronto para gerar o pacote de envio.")
    st.info("Login e envio automático ao SIMRPPN entram na Fase 2. "
            "Por ora, valide o layout e as funcionalidades.")

# --- 8. Processos ----------------------------------------------------------
with abas[7]:
    import pandas as pd
    import altair as alt
    import processos as PR
    PR = importlib.reload(PR)
    DADOS = Path(__file__).resolve().parent / "dados"
    _quem = (st.user.email if _tem_auth and st.user.is_logged_in else "local")
    _quem_curto = _quem.split("@")[0]

    if "proc_base" not in ss:
        ss.proc_base = DR.carregar("processos.json") or {
            "versao": PR.VERSAO, "atualizado_em": "", "por": "", "processos": []}
        ss.proc_sujo = False
    base_p = ss.proc_base
    procs = base_p["processos"]

    CORES_FASE = {"1": "#B8860B", "2": "#E85718", "3": "#E00080",
                  "4": "#603010", "5": "#2E7D32", "6": "#004F23"}
    NOMES_FASE = {p[0]: f"{p[0]}. {p[1]}" for p in PR.PASSOS}

    def _marcar_sujo():
        ss.proc_sujo = True

    # ---------- cabeçalho: salvar / situação ----------
    ch1, ch2 = st.columns([3, 1.2])
    with ch1:
        st.subheader("Gestão dos processos de criação de RPPN")
        st.caption("Passos conforme o documento *Processo de Criação de RPPNs* (vigente "
                   "07/10/2026)" + (f" · última gravação: {base_p['atualizado_em']}"
                                     + (f" por {base_p['por']}" if base_p.get("por") else "")
                                     if base_p.get("atualizado_em") else ""))
    with ch2:
        if ss.proc_sujo:
            st.warning("Há alterações não gravadas.", icon=":material/edit_note:")
        if st.button("Gravar alterações", type="primary", icon=":material/save:",
                     disabled=not ss.proc_sujo, use_container_width=True, key="proc_salvar"):
            ok = _publicar_arquivos({"processos.json": PR.serializar(base_p, _quem)},
                                    f"Processos de RPPN atualizados ({_quem})")
            if ok:
                ss.proc_sujo = False

    # ---------- resumo + gráficos ----------
    ativos = [p for p in procs if p.get("situacao", "ativo") == "ativo"]
    linhas = []
    for p in ativos:
        r = PR.resumo(p)
        linhas.append({"Processo": p["nome"], "UF": p.get("uf", ""), "fase": r["fase"],
                       "Fase": NOMES_FASE[r["fase"]], "Completude (%)": r["completude"],
                       "Tarefas": f"{r['concluidas']}/{r['total']}",
                       "Dias restantes (estim.)": r["dias_restantes"],
                       "Previsão": r["previsao"],
                       "Parado há (dias)": r["parado_ha"] if r["parado_ha"] is not None else "",
                       "Responsável": p.get("responsavel", "")})
    if not ativos:
        st.info("Nenhum processo ativo ainda. Crie um abaixo ou importe os que já estão "
                "em trâmite no SIMRPPN.")
    else:
        dfp = pd.DataFrame(linhas)
        mm = st.columns(4)
        mm[0].metric("Processos ativos", len(ativos))
        mm[1].metric("Completude média", f"{dfp['Completude (%)'].mean():.0f}%")
        mm[2].metric("Na análise do ICMBio (passo 5)", int((dfp["fase"] == "5").sum()))
        parados = pd.to_numeric(dfp["Parado há (dias)"], errors="coerce")
        mm[3].metric("Parados há mais de 30 dias", int((parados > 30).sum()))

        g1, g2 = st.columns([1.6, 1])
        with g1:
            with st.container(border=True):
                st.markdown("**Completude de cada processo** (cor = fase atual)")
                _dom = list(CORES_FASE)
                bar = alt.Chart(dfp).mark_bar().encode(
                    x=alt.X("Completude (%):Q", scale=alt.Scale(domain=[0, 100]),
                            title="Tarefas concluídas (%)"),
                    y=alt.Y("Processo:N", sort="-x", title=None,
                            axis=alt.Axis(labelLimit=220)),
                    color=alt.Color("fase:N", title="Fase atual",
                                    scale=alt.Scale(domain=_dom, range=[CORES_FASE[k] for k in _dom]),
                                    legend=alt.Legend(labelExpr="'Passo ' + datum.label")),
                    tooltip=["Processo", "Fase", "Completude (%)", "Tarefas",
                             "Dias restantes (estim.)", "Previsão"])
                txt = alt.Chart(dfp).mark_text(align="left", dx=4, fontSize=11).encode(
                    x="Completude (%):Q", y=alt.Y("Processo:N", sort="-x"),
                    text=alt.Text("Completude (%):Q", format=".0f"))
                st.altair_chart((bar + txt).properties(height=max(200, 26 * len(dfp) + 40)),
                                use_container_width=True)
        with g2:
            with st.container(border=True):
                st.markdown("**Processos por fase**")
                cf = pd.DataFrame({"fase": list(CORES_FASE)})
                cf["n"] = cf["fase"].map(dfp["fase"].value_counts()).fillna(0).astype(int)
                cf["Fase"] = cf["fase"].map(NOMES_FASE)
                bf = alt.Chart(cf).mark_bar(size=30).encode(
                    x=alt.X("fase:O", title="Passo", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("n:Q", title="Processos", axis=alt.Axis(tickMinStep=1)),
                    color=alt.Color("fase:N", legend=None,
                                    scale=alt.Scale(domain=list(CORES_FASE),
                                                    range=list(CORES_FASE.values()))),
                    tooltip=[alt.Tooltip("Fase:N"), alt.Tooltip("n:Q", title="Processos")]
                ).properties(height=max(200, 26 * len(dfp) + 40))
                st.altair_chart(bf, use_container_width=True)

        with st.container(border=True):
            st.markdown("**Situação, o que falta e previsão** (estimativa: duração prevista "
                        "de cada passo × fração que falta)")
            st.dataframe(dfp.drop(columns=["fase"]).sort_values("Completude (%)", ascending=False),
                         use_container_width=True, hide_index=True)

    # ---------- novo processo / importar ----------
    with st.expander("Novo processo", icon=":material/add_circle:"):
        n1, n2, n3 = st.columns([2, .7, 1.3])
        nv_nome = n1.text_input("Nome da RPPN (ou do imóvel/proprietário, se ainda sem nome)", key="np_nome")
        nv_uf = n2.selectbox("UF", UFS, index=UFS.index("GO"), key="np_uf")
        nv_mun = n3.text_input("Município", key="np_mun")
        n4, n5, n6 = st.columns(3)
        nv_prop = n4.text_input("Proprietário(a)", key="np_prop")
        nv_resp = n5.text_input("Responsável no IC", value=_quem_curto, key="np_resp")
        nv_ini = n6.date_input("Início do processo", value=date.today(), format="DD/MM/YYYY", key="np_ini")
        if st.button("Criar processo", icon=":material/add:", key="np_criar", disabled=not nv_nome.strip()):
            procs.append(PR.novo_processo(nv_nome.strip(), nv_uf, nv_mun.strip(), None,
                                          nv_prop.strip(), nv_resp.strip(),
                                          nv_ini.strftime(PR.FMT)))
            _marcar_sujo()
            st.rerun()
        _rp = (DR.carregar("rppns.json") or {}).get("rppns", [])
        if _rp:
            sug = PR.a_partir_do_simrppn(_rp, procs)
            if sug:
                st.markdown(f"**{len(sug)} RPPN(s) em trâmite no SIMRPPN ainda sem ficha de "
                            "processo:** " + ", ".join(s["nome"] for s in sug))
                st.caption("Ao importar, os passos 1 a 3 e a abertura no SIMRPPN ficam marcados "
                           "como feitos (presumido pela existência do requerimento) — confira "
                           "na ficha.")
                if st.button("Importar do SIMRPPN", icon=":material/download:", key="np_importar"):
                    procs.extend(sug)
                    _marcar_sujo()
                    st.rerun()

    # ---------- ficha do processo ----------
    if procs:
        st.markdown("---")
        nomes = {f"{p['nome']} ({p.get('uf','')})" + (" — concluído" if p.get("situacao") == "concluído" else "")
                 + (" — arquivado" if p.get("situacao") == "arquivado" else ""): i
                 for i, p in enumerate(procs)}
        sel = st.selectbox("Ficha do processo", list(nomes), key="proc_sel")
        p = procs[nomes[sel]]
        r = PR.resumo(p)

        with st.container(border=True):
            f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
            f1.markdown(f"### {p['nome']}")
            f1.caption(f"{p.get('municipio','') or '—'} / {p.get('uf','')} · proprietário(a): "
                       f"{p.get('proprietario','') or '—'}"
                       + (f" · [página no SIMRPPN](https://simrppn.sisicmbio.icmbio.gov.br/RPPNPage/{p['rppnid']})"
                          if p.get("rppnid") else ""))
            f2.metric("Fase atual", f"Passo {r['fase']}")
            f3.metric("Completude", f"{r['completude']}%")
            f4.metric("Previsão de conclusão", r["previsao"],
                      help="Soma da duração prevista dos passos que faltam, proporcional ao que falta em cada um.")
            e1, e2, e3, e4 = st.columns(4)
            p["responsavel"] = e1.text_input("Responsável no IC", p.get("responsavel", ""),
                                             key=f"pr_resp_{p['id']}", on_change=_marcar_sujo)
            try:
                _ini = datetime.strptime(p.get("inicio", ""), PR.FMT).date()
            except ValueError:
                _ini = date.today()
            _ini_novo = e2.date_input("Início", _ini, format="DD/MM/YYYY", key=f"pr_ini_{p['id']}",
                                      on_change=_marcar_sujo)
            p["inicio"] = _ini_novo.strftime(PR.FMT)
            p["situacao"] = e3.selectbox("Situação", ["ativo", "concluído", "arquivado"],
                                         index=["ativo", "concluído", "arquivado"].index(p.get("situacao", "ativo")),
                                         key=f"pr_sit_{p['id']}", on_change=_marcar_sujo)
            e4.metric("Parado há", f"{r['parado_ha']} dias" if r["parado_ha"] is not None else "—",
                      help="Dias desde a última tarefa concluída com data.")
            st.markdown(f"**Agora:** {r['fase_titulo']} — próximas tarefas: "
                        + ("; ".join(r["proximas"][:3]) if r["proximas"] else "nenhuma")
                        + f". **Faltam ≈ {r['dias_restantes']} dias** no ritmo previsto.")

            # barras por passo
            dfs = pd.DataFrame([{"Passo": f"{ps['id']}. {ps['titulo']}", "pct": ps["pct"],
                                 "fase": ps["id"], "Tarefas": f"{ps['feitas']}/{ps['n']}",
                                 "Dias previstos": ps["dias"]} for ps in r["passos"]])
            bp = alt.Chart(dfs).mark_bar().encode(
                x=alt.X("pct:Q", scale=alt.Scale(domain=[0, 100]), title="Concluído (%)"),
                y=alt.Y("Passo:N", sort=None, title=None, axis=alt.Axis(labelLimit=320)),
                color=alt.Color("fase:N", legend=None,
                                scale=alt.Scale(domain=list(CORES_FASE), range=list(CORES_FASE.values()))),
                tooltip=["Passo", "Tarefas", "Dias previstos"]).properties(height=190)
            st.altair_chart(bp, use_container_width=True)

        # tarefas por passo
        def _toggle(pid_tid, pid_proc):
            key = f"tk_{pid_proc}_{pid_tid}"
            prc = next(x for x in procs if x["id"] == pid_proc)
            reg = prc["tarefas"].setdefault(pid_tid, {"feito": False, "data": "", "por": "", "obs": ""})
            reg["feito"] = bool(ss[key])
            if reg["feito"] and not reg.get("data"):
                reg["data"] = date.today().strftime(PR.FMT)
                reg["por"] = _quem_curto
            _marcar_sujo()

        def _obs(pid_tid, pid_proc, campo):
            key = f"{campo}_{pid_proc}_{pid_tid}"
            prc = next(x for x in procs if x["id"] == pid_proc)
            reg = prc["tarefas"].setdefault(pid_tid, {"feito": False, "data": "", "por": "", "obs": ""})
            val = ss[key]
            reg[campo] = val.strftime(PR.FMT) if hasattr(val, "strftime") else (val or "")
            _marcar_sujo()

        for ps in r["passos"]:
            aberto = ps["id"] == r["fase"]
            rot = f"Passo {ps['id']} — {ps['titulo']}  ·  {ps['feitas']}/{ps['n']} tarefas"
            with st.expander(rot, expanded=aberto,
                             icon=":material/check_circle:" if ps["pct"] == 100 else ":material/radio_button_unchecked:"):
                dcol, _ = st.columns([1, 3])
                p["duracoes"][ps["id"]] = int(dcol.number_input(
                    "Duração prevista deste passo (dias)", 1, 999, ps["dias"],
                    key=f"dur_{p['id']}_{ps['id']}", on_change=_marcar_sujo))
                tarefas = next(x[3] for x in PR.PASSOS if x[0] == ps["id"])
                for tid, desc in tarefas:
                    reg = p["tarefas"].get(tid, {})
                    c1, c2, c3, c4 = st.columns([3.2, .9, .9, 1.6])
                    c1.checkbox(f"**{tid}** {desc}", value=bool(reg.get("feito")),
                                key=f"tk_{p['id']}_{tid}", on_change=_toggle, args=(tid, p["id"]))
                    if reg.get("feito"):
                        try:
                            _d = datetime.strptime(reg.get("data", ""), PR.FMT).date()
                        except ValueError:
                            _d = date.today()
                        c2.date_input("Data", _d, format="DD/MM/YYYY", key=f"data_{p['id']}_{tid}",
                                      on_change=_obs, args=(tid, p["id"], "data"),
                                      label_visibility="collapsed")
                        c3.caption(reg.get("por", ""))
                    c4.text_input("Observação", reg.get("obs", ""), key=f"obs_{p['id']}_{tid}",
                                  on_change=_obs, args=(tid, p["id"], "obs"),
                                  label_visibility="collapsed", placeholder="observação")
        p["notas"] = st.text_area("Notas gerais do processo (contatos, pendências do proprietário, ofícios…)",
                                  p.get("notas", ""), key=f"notas_{p['id']}", on_change=_marcar_sujo)
        if st.button("Excluir esta ficha", icon=":material/delete:", key=f"del_{p['id']}"):
            procs.remove(p)
            _marcar_sujo()
            st.rerun()

# --- 9. Administrar --------------------------------------------------------
with abas[8]:
    import pandas as pd
    import altair as alt
    st.subheader("Administrar — RPPNs do Instituto Cerrados")
    DADOS = Path(__file__).resolve().parent / "dados"

    # ---- Sincronizar com o SIMRPPN — por qualquer pessoa, de qualquer máquina ----
    import streamlit.components.v1 as components
    from urllib.parse import quote
    import sync_ingest as SI
    SI = importlib.reload(SI)
    _meta = DR.carregar("rppns.json") or {}
    with st.expander("Sincronizar com o SIMRPPN", expanded=False, icon=":material/sync:"):
        if _meta.get("sincronizado_em"):
            st.caption(f"Última sincronização: **{_meta['sincronizado_em']}**"
                       + (f" · por {_meta['por']}" if _meta.get("por") else "")
                       + (f" · coletor v{_meta['coletor_versao']}" if _meta.get("coletor_versao") else ""))
        st.markdown(
            "A leitura do SIMRPPN acontece **no seu próprio navegador**, com o seu login "
            "gov.br — nenhuma senha passa pela plataforma, e nada é navegado à vista: "
            "aparece só uma barra de progresso. Três passos:")

        js_src = (Path(__file__).resolve().parent / "sync_coletor.js").read_text(encoding="utf-8")
        _href = "javascript:" + quote(js_src, safe="")
        st.markdown("**Passo 1 — uma vez só.** Arraste o botão abaixo para a **barra de "
                    "favoritos** do seu navegador (Chrome/Edge: Ctrl+Shift+B mostra a barra).")
        components.html(
            f'<div style="font-family:Montserrat,Segoe UI,Arial,sans-serif;display:flex;'
            f'align-items:center;gap:14px">'
            f'<a href="{_href}" onclick="alert(\'Não clique aqui: arraste este botão para a '
            f'barra de favoritos. Depois use-o na página do SIMRPPN.\');return false;" '
            f'style="display:inline-block;background:{VERDE};color:#fff;padding:10px 18px;'
            f'border-radius:22px;font-weight:700;text-decoration:none;cursor:grab;'
            f'border-bottom:3px solid {MAGENTA}">&#8597; Coletar RPPNs</a>'
            f'<span style="font-size:.85rem;color:#555">← arraste para os favoritos</span></div>',
            height=64)
        with st.expander("Não consegue arrastar? Crie o favorito manualmente"):
            st.markdown("No navegador: **Favoritos → Adicionar**. Nome: `Coletar RPPNs`. "
                        "No campo **URL/endereço**, cole o texto abaixo inteiro:")
            st.text_area("Endereço do favorito", _href, height=90, key="sync_href", label_visibility="collapsed")
        st.markdown(
            "**Passo 2.** Logado(a) no SIMRPPN, na página **Painel de Gestão**, clique no "
            "favorito **Coletar RPPNs**. Uma barra de progresso mostra a sincronização "
            "(≈5 min); ao terminar, um arquivo `sincronizacao_rppns_<data>.json` é baixado.\n\n"
            "**Passo 3.** Envie esse arquivo aqui:")
        up = st.file_uploader("Arquivo de sincronização (.json)", type=["json"], key="sync_up")
        if up is not None:
            try:
                _payload = json.load(up)
            except Exception as e:
                _payload, _erros = None, [f"Não consegui ler o arquivo: {e}"]
            else:
                _erros = SI.validar(_payload)
            if _erros:
                st.error("**Arquivo inválido:**\n\n- " + "\n- ".join(_erros))
            else:
                _por = (st.user.email if _tem_auth and st.user.is_logged_in else "local")
                _geo_antigo = DR.carregar("rppns.geojson")
                _rj, _gj, _st = SI.processar(_payload, por=_por, base_atual=_meta or None,
                                             geo_atual=_geo_antigo)
                _dif = SI.comparar(_meta or None, _rj, _geo_antigo, _gj)
                c1, c2, c3 = st.columns(3)
                c1.metric("RPPNs no arquivo", _st["no_arquivo"])
                c2.metric("Com polígono (após mesclar)", _st["poligonos"])
                c3.metric("Criadas sem polígono", len(_st["criadas_sem_poligono"]))
                if _st["mantidas_nao_vistas"]:
                    st.info(f"**{len(_st['mantidas_nao_vistas'])} RPPN(s) não apareceram no painel de "
                            "quem sincronizou e foram mantidas** como estavam (quem sincroniza vê só "
                            "as RPPNs a que está vinculado no SIMRPPN): "
                            + ", ".join(_st["mantidas_nao_vistas"]))
                linhas = []
                if _dif["novas"]: linhas.append(f"**{len(_dif['novas'])} nova(s):** " + ", ".join(_dif["novas"]))
                if _dif["status_alterados"]: linhas.append("**Status alterado:** " + "; ".join(_dif["status_alterados"]))
                if _dif["poligonos_novos"]: linhas.append(f"**{len(_dif['poligonos_novos'])} polígono(s) novo(s):** " + ", ".join(_dif["poligonos_novos"]))
                if _dif["removidas"]: linhas.append("**Saíram do painel:** " + ", ".join(_dif["removidas"]))
                if _dif["poligonos_perdidos"]: linhas.append("**Polígonos que sumiriam:** " + ", ".join(_dif["poligonos_perdidos"]))
                st.markdown("**O que muda em relação ao publicado:**\n\n- " + "\n- ".join(linhas)
                            if linhas else "Nenhuma diferença em relação ao que já está publicado.")
                if _st["criadas_sem_poligono"]:
                    st.caption("Criadas sem polígono: " + ", ".join(_st["criadas_sem_poligono"]))
                if _st["com_erro_coleta"]:
                    st.warning("Com erro na coleta (confira no SIMRPPN): " + ", ".join(map(str, _st["com_erro_coleta"])))
                if st.button("Confirmar e publicar", type="primary", icon=":material/cloud_upload:",
                             key="sync_pub"):
                    _arqs = {"rppns.json": json.dumps(_rj, ensure_ascii=False, indent=1),
                             "rppns.geojson": json.dumps(_gj, ensure_ascii=False)}
                    if _publicar_arquivos(_arqs, f"Sincroniza RPPNs via plataforma ({_rj['sincronizado_em']}, {_por})"):
                        ss.pop("sync_up", None)
                        st.rerun()

    # cores diversificadas na identidade Jurema/IC
    CORES_STATUS = {"criada": "#004F23", "em trâmite": "#E85718",
                    "em cadastro": "#E00080", "arquivada": "#603010"}
    PALETA_UF = ["#004F23", "#E85718", "#E00080", "#603010", "#B8860B",
                 "#2E7D32", "#DDCCA4"]

    base = _meta
    if not base.get("rppns"):
        st.warning("Ainda não há dados de RPPNs. Use **Sincronizar com o SIMRPPN** acima.")
    else:
        df = pd.DataFrame(base["rppns"])
        for col in ["proprietario", "municipio", "data_criacao",
                    "data_cadastro", "data_ato", "pagina"]:
            if col not in df.columns:
                df[col] = ""
        df[["proprietario", "municipio", "data_criacao", "pagina"]] = \
            df[["proprietario", "municipio", "data_criacao", "pagina"]].fillna("")
        # defesa: município que veio como dropdown gigante (com quebras) -> limpa
        df["municipio"] = df["municipio"].astype(str).apply(
            lambda s: "" if ("\n" in s or len(s) > 50) else s)
        st.caption(f"Fonte: {base.get('fonte','')} · armazenamento: {DR.origem()}.")

        # ---- filtros (card) ----
        with st.container(border=True):
            f1, f2, f3 = st.columns([1, 1.4, 2])
            ufs_l = sorted(df["uf"].dropna().unique().tolist())
            sts_l = sorted(df["status"].dropna().unique().tolist())
            f_uf = f1.multiselect("UF", ufs_l, default=ufs_l, key="adm_uf")
            f_st = f2.multiselect("Status", sts_l, default=sts_l, key="adm_st")
            f_tx = f3.text_input("Buscar por nome, município ou proprietário",
                                 key="adm_busca")
        v = df[df["uf"].isin(f_uf) & df["status"].isin(f_st)]
        if f_tx:
            t = f_tx.lower()
            v = v[v["nome"].str.lower().str.contains(t, na=False) |
                  v["municipio"].str.lower().str.contains(t) |
                  v["proprietario"].str.lower().str.contains(t)]

        # ---- métricas ----
        m = st.columns(4)
        m[0].metric("RPPNs", len(v))
        m[1].metric("Criadas", int((v["status"] == "criada").sum()))
        m[2].metric("Em trâmite/cadastro",
                    int(v["status"].isin(["em trâmite", "em cadastro"]).sum()))
        area_tot = pd.to_numeric(v["area_rppn_ha"], errors="coerce").sum()
        m[3].metric("Área somada (ha)",
                    f"{area_tot:,.2f}".replace(",", "X").replace(".", ",")
                    .replace("X", ".") if area_tot else "—")

        # ---- gráficos: status (barras coloridas) + estado (pizza) ----
        g1, g2 = st.columns(2)
        with g1:
            with st.container(border=True):
                st.markdown("**RPPNs por status**")
                sc = v["status"].value_counts().reset_index()
                sc.columns = ["status", "n"]
                ch = alt.Chart(sc).mark_bar().encode(
                    x=alt.X("n:Q", title="RPPNs"),
                    y=alt.Y("status:N", sort="-x", title=None),
                    color=alt.Color("status:N", legend=None,
                                    scale=alt.Scale(domain=list(CORES_STATUS),
                                                    range=list(CORES_STATUS.values()))),
                    tooltip=[alt.Tooltip("status:N", title="Status"),
                             alt.Tooltip("n:Q", title="RPPNs")]
                ).properties(height=230)
                st.altair_chart(ch, use_container_width=True)
        with g2:
            with st.container(border=True):
                st.markdown("**RPPNs por estado (UF)**")
                uc = v["uf"].value_counts().reset_index()
                uc.columns = ["uf", "n"]
                pie = alt.Chart(uc).mark_arc(innerRadius=45).encode(
                    theta=alt.Theta("n:Q"),
                    color=alt.Color("uf:N", scale=alt.Scale(range=PALETA_UF),
                                    legend=alt.Legend(title="UF")),
                    tooltip=[alt.Tooltip("uf:N", title="UF"),
                             alt.Tooltip("n:Q", title="RPPNs")]
                ).properties(height=230)
                st.altair_chart(pie, use_container_width=True)

        # ---- histograma anual de RPPNs criadas ----
        with st.container(border=True):
            st.markdown("**RPPNs criadas por ano** (data do Ato de Criação)")
            anos = pd.to_datetime(v["data_criacao"], format="%d/%m/%Y",
                                  errors="coerce").dt.year.dropna().astype(int)
            if len(anos):
                hc = anos.value_counts().reset_index()
                hc.columns = ["ano", "n"]
                todos = pd.DataFrame({"ano": range(int(anos.min()),
                                                   int(anos.max()) + 1)})
                hc = todos.merge(hc, on="ano", how="left").fillna(0)
                hc["n"] = hc["n"].astype(int)
                hb = alt.Chart(hc).mark_bar(color=VERDE, size=28).encode(
                    x=alt.X("ano:O", title="Ano"),
                    y=alt.Y("n:Q", title="RPPNs criadas",
                            axis=alt.Axis(tickMinStep=1)),
                    tooltip=[alt.Tooltip("ano:O", title="Ano"),
                             alt.Tooltip("n:Q", title="RPPNs criadas")]
                ).properties(height=240)
                st.altair_chart(hb, use_container_width=True)
            else:
                st.info("Sem datas de criação nos dados atuais. Rode "
                        "`python coletar_rppns.py` (com o Chrome logado) para "
                        "capturar as datas do Ato de Criação.")

        # ---- tabela (card) — cabeçalho verde, no padrão da ferramenta ----
        with st.container(border=True):
            st.markdown("**Lista de RPPNs**")
            st.markdown(_tabela_rppns_html(v), unsafe_allow_html=True)

        # ---- webmap (card) ----
        with st.container(border=True):
            st.markdown("**Webmap das RPPNs** — cor por status "
                        "(verde=criada · laranja=em trâmite · magenta=em cadastro · "
                        "marrom=arquivada)")
            import folium
            from streamlit_folium import st_folium
            madm = folium.Map(location=[-15.5, -48.0], zoom_start=6,
                              control_scale=True, tiles=None)
            folium.TileLayer("OpenStreetMap", name="Mapa (ruas)").add_to(madm)
            folium.TileLayer(
                tiles="https://server.arcgisonline.com/ArcGIS/rest/services/"
                      "World_Imagery/MapServer/tile/{z}/{y}/{x}",
                attr="Esri World Imagery", name="Satélite").add_to(madm)
            gj = DR.carregar("rppns.geojson")
            if gj:
                ids_visiveis = set(v["rppnid"].dropna().astype(int).tolist()) \
                    if "rppnid" in v else set()
                feats_v = [f for f in gj["features"]
                           if not ids_visiveis or
                           f["properties"].get("rppnid") in ids_visiveis]
                if feats_v:
                    capa = folium.GeoJson(
                        {"type": "FeatureCollection", "features": feats_v},
                        name="RPPNs",
                        style_function=lambda f: {
                            "color": CORES_STATUS.get(
                                f["properties"].get("status"), "#004F23"),
                            "weight": 2.5, "fillColor": CORES_STATUS.get(
                                f["properties"].get("status"), "#004F23"),
                            "fillOpacity": .35},
                        tooltip=folium.GeoJsonTooltip(
                            fields=["nome", "uf", "status", "area_rppn_ha"],
                            aliases=["RPPN:", "UF:", "Status:", "Área (ha):"]))
                    capa.add_to(madm)
                    b = capa.get_bounds()
                    if b and b[0][0] is not None:
                        madm.fit_bounds(b)
                n_geo = len(feats_v)
            else:
                n_geo = 0
            folium.LayerControl(collapsed=True).add_to(madm)
            st_folium(madm, use_container_width=True, height=450, key="mapa_adm")
            if n_geo < len(v):
                st.info(f"O mapa mostra {n_geo} polígono(s) de {len(v)} RPPNs "
                        "filtradas — rode o coletor (`python coletar_rppns.py`) com o "
                        "Chrome logado para capturar os polígonos de todas.")
