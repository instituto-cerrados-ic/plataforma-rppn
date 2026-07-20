# -*- coding: utf-8 -*-
"""
gerar_coordenadas.py
====================
Converte um polígono (Shapefile / KML / GeoPackage / GeoJSON) no
"Arquivo Excel Padronizado com PONTO, X, Y e Descrição" que o SIMRPPN
(Memorial Descritivo > editor de limites) aceita como entrada de dados.

- Reprojeta para UTM SIRGAS 2000, escolhendo a zona automaticamente pelo
  centróide (ou forçada via --zona).
- Gera as colunas exatamente na ordem esperada: PONTO, X, Y, Descrição.
- Imprime também qual opção do dropdown "Projeção" selecionar no site.

Uso:
    python gerar_coordenadas.py entrada.shp -o saida.xlsx
    python gerar_coordenadas.py imovel.kml -o imovel_coords.xlsx --prefixo P
    python gerar_coordenadas.py area.gpkg --camada rppn --zona 23S

Requisitos: geopandas, pyproj, shapely, openpyxl (já instalados no ambiente).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon

# ---------------------------------------------------------------------------
# Mapeamento zona UTM SIRGAS 2000 -> EPSG e -> opção do dropdown do SIMRPPN
# Dropdown "Projeção": Geográfica=1, UTM-18S=2, 19S=3, 20S=4, 21S=5, 22S=6,
#                      23S=7, 24S=8, 25S=9, 20N=10, 21N=11, 22N=12
# ---------------------------------------------------------------------------
EPSG_SUL = {z: 31960 + z for z in range(17, 26)}   # 17S..25S -> 31977..31985
EPSG_NORTE = {z: 31948 + z for z in range(17, 26)}  # 17N..25N -> 31965..31973

DROPDOWN = {
    "18S": ("UTM - 18 S", 2), "19S": ("UTM - 19 S", 3), "20S": ("UTM - 20 S", 4),
    "21S": ("UTM - 21 S", 5), "22S": ("UTM - 22 S", 6), "23S": ("UTM - 23 S", 7),
    "24S": ("UTM - 24 S", 8), "25S": ("UTM - 25 S", 9),
    "20N": ("UTM - 20 N", 10), "21N": ("UTM - 21 N", 11), "22N": ("UTM - 22 N", 12),
}


def epsg_da_zona(zona: str) -> int:
    """'23S' -> 31983 ; '20N' -> 31968."""
    zona = zona.upper().strip()
    num, hemi = int(zona[:-1]), zona[-1]
    if hemi == "S":
        return EPSG_SUL[num]
    if hemi == "N":
        return EPSG_NORTE[num]
    raise ValueError(f"Hemisfério inválido em '{zona}' (use N ou S)")


def zona_pelo_centroide(lon: float, lat: float) -> str:
    """Deduz a zona UTM ('23S') a partir de lon/lat geográficos."""
    num = int((lon + 180) // 6) + 1
    hemi = "S" if lat < 0 else "N"
    return f"{num}{hemi}"


def carregar_poligono(caminho: Path, camada: str | None) -> gpd.GeoDataFrame:
    kwargs = {}
    if camada:
        kwargs["layer"] = camada
    gdf = gpd.read_file(caminho, **kwargs)
    if gdf.empty:
        raise SystemExit(f"[erro] Nenhuma feição em {caminho}")
    # mantém só polígonos
    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])]
    if gdf.empty:
        raise SystemExit(f"[erro] {caminho} não contém polígonos.")
    if gdf.crs is None:
        print("[aviso] Arquivo sem CRS definido; assumindo SIRGAS 2000 geográfico (EPSG:4674).")
        gdf = gdf.set_crs(4674)
    return gdf


def maior_poligono(gdf: gpd.GeoDataFrame) -> Polygon:
    """Une tudo e devolve o maior anel exterior (dissolve multipartes)."""
    geom = gdf.geometry.union_all() if hasattr(gdf.geometry, "union_all") else gdf.geometry.unary_union
    if isinstance(geom, MultiPolygon):
        geom = max(geom.geoms, key=lambda g: g.area)
    return geom


def extrair_vertices(poly: Polygon, fechar: bool) -> list[tuple[float, float]]:
    """Vértices do anel externo. Por padrão remove o ponto de fechamento
    (shapefile repete o 1º=último); use fechar=True para mantê-lo."""
    coords = list(poly.exterior.coords)
    if not fechar and len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    return coords


def gerar(
    caminho: Path,
    saida: Path,
    camada: str | None = None,
    zona: str | None = None,
    prefixo: str = "P",
    descricao_fixa: str = "",
    fechar: bool = False,
) -> dict:
    gdf = carregar_poligono(caminho, camada)

    # centróide em geográfico para deduzir a zona
    cen = gdf.to_crs(4674).geometry.union_all().centroid if hasattr(
        gdf.geometry, "union_all") else gdf.to_crs(4674).unary_union.centroid
    zona_final = (zona or zona_pelo_centroide(cen.x, cen.y)).upper()
    if zona_final not in DROPDOWN:
        raise SystemExit(
            f"[erro] Zona {zona_final} fora das opções do SIMRPPN "
            f"({', '.join(DROPDOWN)}).")

    epsg = epsg_da_zona(zona_final)
    gdf_utm = gdf.to_crs(epsg)
    poly = maior_poligono(gdf_utm)
    vertices = extrair_vertices(poly, fechar)

    # --- escreve o Excel padronizado ---
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "coordenadas"
    ws.append(["PONTO", "X", "Y", "Descrição"])  # 1ª linha é ignorada pelo sistema
    largura = len(str(len(vertices)))
    for i, (x, y) in enumerate(vertices, start=1):
        ponto = f"{prefixo}-{i:0{max(2, largura)}d}"
        ws.append([ponto, round(x, 2), round(y, 2), descricao_fixa])
    for col, w in zip("ABCD", (10, 16, 16, 30)):
        ws.column_dimensions[col].width = w
    saida.parent.mkdir(parents=True, exist_ok=True)
    wb.save(saida)

    rotulo, valor_dropdown = DROPDOWN[zona_final]
    area_ha = poly.area / 10_000.0
    info = {
        "arquivo_saida": str(saida),
        "n_pontos": len(vertices),
        "zona": zona_final,
        "epsg": epsg,
        "dropdown_projecao": rotulo,
        "dropdown_valor": valor_dropdown,
        "area_ha": round(area_ha, 4),
    }
    return info


def main(argv=None):
    ap = argparse.ArgumentParser(description="Gera o Excel PONTO,X,Y,Descrição do SIMRPPN.")
    ap.add_argument("entrada", type=Path, help="Shapefile/KML/GPKG/GeoJSON do polígono")
    ap.add_argument("-o", "--saida", type=Path, help="xlsx de saída (padrão: <entrada>_coords.xlsx)")
    ap.add_argument("--camada", help="Nome da camada (para GPKG/KML multi-camada)")
    ap.add_argument("--zona", help="Forçar zona UTM, ex.: 23S, 22S, 20N (padrão: automático)")
    ap.add_argument("--prefixo", default="P", help="Prefixo do nome do ponto (padrão: P)")
    ap.add_argument("--descricao", default="", help="Texto fixo na coluna Descrição")
    ap.add_argument("--fechar", action="store_true", help="Manter o vértice de fechamento (1º=último)")
    args = ap.parse_args(argv)

    saida = args.saida or args.entrada.with_name(args.entrada.stem + "_coords.xlsx")
    info = gerar(
        args.entrada, saida, camada=args.camada, zona=args.zona,
        prefixo=args.prefixo, descricao_fixa=args.descricao, fechar=args.fechar,
    )

    print("\n=== Excel de coordenadas gerado ===")
    print(f"  Arquivo ......... {info['arquivo_saida']}")
    print(f"  Nº de pontos .... {info['n_pontos']}")
    print(f"  Área do polígono  {info['area_ha']} ha")
    print(f"  Zona UTM ........ {info['zona']}  (EPSG:{info['epsg']}, SIRGAS 2000)")
    print("\n  No SIMRPPN, no campo 'Projeção' selecione:")
    print(f"    -> \"{info['dropdown_projecao']}\"  (opção {info['dropdown_valor']})")
    print("  E em 'Tipo de Entrada de Dados' selecione:")
    print("    -> \"Arquivo Excel Padronizado com PONTO, X, Y e Descrição\" (opção 3)")
    print("=" * 36)


if __name__ == "__main__":
    main()
