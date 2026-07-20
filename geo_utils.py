# -*- coding: utf-8 -*-
"""
geo_utils.py — motor de geometria da Plataforma RPPN.

- parse_tabela_vertices(): lê CSV/Excel de vértices e CORRIGE erros comuns:
  nomes de coluna errados, colunas trocadas (X/Y), vírgula decimal, separador
  de milhar, e converte coordenadas geográficas -> UTM SIRGAS 2000 (zona auto).
- validar_topologia(): confere se a RPPN está DENTRO do imóvel (ou compartilha
  limite) — condição para aceitar.
- gerar_excel_coords(): grava o Excel PONTO,X,Y,Descrição do SIMRPPN.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gerar_coordenadas as gc  # EPSG/zona/DROPDOWN reaproveitados

# bounding box aproximado do Brasil (para detectar eixos trocados em geográficas)
BR_LON = (-74.5, -33.0)
BR_LAT = (-34.5, 6.5)

SIN_X = {"x", "e", "este", "leste", "utme", "utm_e", "coordx", "coord_x", "coord e",
         "long", "longitude", "lon", "lng", "long.", "x(m)", "x_m", "easting"}
SIN_Y = {"y", "n", "norte", "utmn", "utm_n", "coordy", "coord_y", "coord n",
         "lat", "latitude", "y(m)", "y_m", "northing"}
SIN_P = {"ponto", "pt", "p", "id", "vertice", "vertices", "num", "numero", "no",
         "n_ponto", "estaca", "marco"}
SIN_D = {"descricao", "desc", "obs", "observacao", "observacoes", "nome", "label",
         "comentario"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return s.strip().lower()


def _num(v):
    """'8.275.358,88' / '202847,89' / '-15,58' -> float. Robusto a milhar/vírgula."""
    if v is None:
        return None
    s = str(v).strip().replace(" ", "")
    if s == "" or s.lower() in ("nan", "none"):
        return None
    # se tem vírgula E ponto: ponto = milhar, vírgula = decimal
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    s = re.sub(r"[^0-9.\-+eE]", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def _mapear_colunas(cols):
    """Casa cada coluna a um papel (x/y/ponto/desc) por sinônimo normalizado."""
    papel = {}
    for c in cols:
        n = _norm(c)
        if n in SIN_X:
            papel[c] = "x"
        elif n in SIN_Y:
            papel[c] = "y"
        elif n in SIN_P:
            papel[c] = "ponto"
        elif n in SIN_D:
            papel[c] = "desc"
    return papel


def parse_tabela_vertices(arquivo, zona_forcada=None):
    """
    Lê um CSV/XLS/XLSX de vértices e devolve (df_utm, meta).
    df_utm: colunas PONTO, X, Y, Descrição (X/Y em UTM SIRGAS 2000, metros).
    meta: dict com 'zona', 'epsg', 'dropdown', 'correcoes' (lista de textos),
          'crs_origem' ('geografica'|'utm'), 'poligono' (shapely em UTM).
    """
    arquivo = Path(arquivo)
    correcoes = []
    if arquivo.suffix.lower() in (".xls", ".xlsx"):
        raw = pd.read_excel(arquivo, dtype=str)
    else:
        # tenta separadores e encodings comuns de planilhas BR
        raw = None
        for sep in (";", ",", "\t"):
            try:
                tmp = pd.read_csv(arquivo, sep=sep, dtype=str, encoding="utf-8-sig")
                if tmp.shape[1] >= 2:
                    raw = tmp
                    break
            except Exception:
                continue
        if raw is None:
            raw = pd.read_csv(arquivo, dtype=str, encoding="latin-1")

    raw = raw.dropna(how="all")
    papel = _mapear_colunas(raw.columns)
    col_x = next((c for c, p in papel.items() if p == "x"), None)
    col_y = next((c for c, p in papel.items() if p == "y"), None)
    col_p = next((c for c, p in papel.items() if p == "ponto"), None)
    col_d = next((c for c, p in papel.items() if p == "desc"), None)

    # colunas não reconhecidas -> usa as duas primeiras numéricas como X, Y
    if col_x is None or col_y is None:
        numericas = [c for c in raw.columns
                     if raw[c].map(_num).notna().mean() > 0.6]
        if len(numericas) < 2:
            raise ValueError("Não encontrei duas colunas de coordenadas na tabela.")
        col_x, col_y = numericas[0], numericas[1]
        correcoes.append(f"Colunas de coordenada não nomeadas — assumi "
                         f"'{col_x}'→X e '{col_y}'→Y (2 primeiras numéricas).")

    xs = raw[col_x].map(_num)
    ys = raw[col_y].map(_num)
    val = xs.notna() & ys.notna()
    xs, ys = list(xs[val]), list(ys[val])
    if len(xs) < 3:
        raise ValueError("Menos de 3 pontos válidos após a limpeza.")
    if any("," in str(v) for v in raw[col_x].tolist() + raw[col_y].tolist()):
        correcoes.append("Vírgula decimal convertida para ponto.")

    # geográfica ou UTM? (magnitude)
    geografica = max(abs(min(xs)), abs(max(xs))) <= 180 and \
        max(abs(min(ys)), abs(max(ys))) <= 90

    def _dentro_brasil(lon, lat):
        return (BR_LON[0] <= lon <= BR_LON[1]) and (BR_LAT[0] <= lat <= BR_LAT[1])

    if geografica:
        # detecta eixos trocados: qual atribuição cai dentro do Brasil?
        ok_normal = sum(_dentro_brasil(x, y) for x, y in zip(xs, ys))
        ok_troca = sum(_dentro_brasil(y, x) for x, y in zip(xs, ys))
        if ok_troca > ok_normal:
            xs, ys = ys, xs
            correcoes.append("Colunas X/Y trocadas — corrigido (lon/lat).")
        lon, lat = xs, ys
        # centróide -> zona -> converte p/ UTM SIRGAS 2000
        cx, cy = sum(lon) / len(lon), sum(lat) / len(lat)
        zona = (zona_forcada or gc.zona_pelo_centroide(cx, cy)).upper()
        epsg = gc.epsg_da_zona(zona)
        from pyproj import Transformer
        tr = Transformer.from_crs(4674, epsg, always_xy=True)  # SIRGAS2000 geo -> UTM
        xs, ys = zip(*[tr.transform(a, b) for a, b in zip(lon, lat)])
        xs, ys = list(xs), list(ys)
        correcoes.append(f"Coordenadas geográficas convertidas para UTM {zona} "
                        f"(SIRGAS 2000, EPSG:{epsg}).")
        crs_origem = "geografica"
    else:
        # UTM: easting ~1e5-9e5, northing ~ até 1e7. Detecta troca por magnitude.
        if (sum(1 for v in xs if abs(v) > 1_000_000) > len(xs) / 2 and
                sum(1 for v in ys if abs(v) < 1_000_000) > len(ys) / 2):
            xs, ys = ys, xs
            correcoes.append("Colunas X/Y trocadas — corrigido (UTM E/N).")
        cx = sum(xs) / len(xs)
        # deduz zona pelo easting não dá; exige zona informada ou assume centro-BR
        zona = (zona_forcada or "23S").upper()
        epsg = gc.epsg_da_zona(zona)
        if not zona_forcada:
            correcoes.append(f"Zona UTM não informada — assumi {zona}; confirme.")
        crs_origem = "utm"

    if col_p is not None:
        pontos = [str(p) for p in raw[col_p][val].tolist()]
    else:
        pontos = [f"P-{i:02d}" for i in range(1, len(xs) + 1)]
    descr = [str(d) if d is not None else "" for d in
             (raw[col_d][val].tolist() if col_d is not None else [""] * len(xs))]

    df_utm = pd.DataFrame({"PONTO": pontos, "X": [round(x, 2) for x in xs],
                           "Y": [round(y, 2) for y in ys], "Descrição": descr})
    poly = Polygon(list(zip(xs, ys)))
    rotulo, valor = gc.DROPDOWN[zona]
    meta = {"zona": zona, "epsg": epsg, "dropdown": rotulo, "dropdown_valor": valor,
            "correcoes": correcoes, "crs_origem": crs_origem, "poligono": poly,
            "area_ha": round(abs(poly.area) / 10_000, 4), "n_pontos": len(xs)}
    return df_utm, meta


def validar_topologia(imovel: Polygon, rppn: Polygon):
    """
    Confere a relação RPPN×imóvel. Aceita só se a RPPN estiver contida no imóvel
    (permitindo compartilhar trechos de limite).
    Retorna (ok: bool, status: str, detalhe: str).
    """
    if imovel is None or rppn is None:
        return False, "incompleto", "Falta o polígono do imóvel ou da RPPN."
    if not imovel.is_valid:
        imovel = imovel.buffer(0)
    if not rppn.is_valid:
        rppn = rppn.buffer(0)
    compartilha = rppn.boundary.intersection(imovel.boundary).length > 0
    if rppn.covered_by(imovel):
        if compartilha:
            return True, "dentro_com_limite_comum", \
                "RPPN dentro do imóvel, compartilhando trecho(s) de limite. OK."
        return True, "dentro", "RPPN totalmente dentro do imóvel. OK."
    # quanto vaza para fora?
    fora = rppn.difference(imovel)
    pct = 100 * fora.area / rppn.area if rppn.area else 0
    return False, "fora", (f"A RPPN NÃO está contida no imóvel: {pct:.1f}% da área "
                           f"da RPPN fica fora do perímetro da propriedade.")


def aderir_vertices(poly: Polygon, guias, tol_m: float = 5.0):
    """
    'Cola' os vértices de `poly` aos vértices/bordas de uma ou mais geometrias-guia
    (mesmo CRS, metros) dentro da tolerância. Primeiro tenta vértice da guia; se não
    houver, projeta na borda da guia. Retorna (poly_novo, n_movidos).
    """
    from math import hypot
    from shapely.geometry import Point
    if guias is None:
        return poly, 0
    if not isinstance(guias, (list, tuple)):
        guias = [guias]
    # coleta vértices-guia e as bordas
    vert_guia = []
    bordas = []
    for g in guias:
        if g is None:
            continue
        if not g.is_valid:
            g = g.buffer(0)
        bordas.append(g.boundary)
        gg = g.geoms if g.geom_type == "MultiPolygon" else [g]
        for part in gg:
            vert_guia.extend(list(part.exterior.coords))

    novos = []
    movidos = 0
    for x, y in list(poly.exterior.coords)[:-1]:
        alvo = None
        melhor = tol_m
        for gx, gy in vert_guia:            # 1) vértice mais próximo
            d = hypot(x - gx, y - gy)
            if d <= melhor:
                melhor, alvo = d, (gx, gy)
        if alvo is None:                    # 2) senão, projeta na borda
            p = Point(x, y)
            for b in bordas:
                proj = b.interpolate(b.project(p))
                if p.distance(proj) <= tol_m:
                    alvo = (proj.x, proj.y)
                    break
        if alvo is not None and (alvo[0] != x or alvo[1] != y):
            novos.append(alvo)
            movidos += 1
        else:
            novos.append((x, y))
    novo_poly = Polygon(novos)
    if not novo_poly.is_valid:
        novo_poly = novo_poly.buffer(0)
    return novo_poly, movidos


def gerar_excel_coords(df_utm: pd.DataFrame, caminho: Path):
    """Grava o Excel padronizado PONTO,X,Y,Descrição (1ª linha = cabeçalho)."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "coordenadas"
    ws.append(["PONTO", "X", "Y", "Descrição"])
    for _, r in df_utm.iterrows():
        ws.append([r["PONTO"], float(r["X"]), float(r["Y"]), r.get("Descrição", "")])
    for col, w in zip("ABCD", (10, 16, 16, 28)):
        ws.column_dimensions[col].width = w
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    wb.save(caminho)
    return caminho
