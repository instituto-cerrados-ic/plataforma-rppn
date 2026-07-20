# -*- coding: utf-8 -*-
"""
Carga inicial da aba Administrar: dados REAIS capturados do Painel de Gestão do
SIMRPPN (sessão de 16-17/07/2026) — 38 RPPNs (nome/UF/status) e o polígono real
da RPPN 1428 (vértices lidos do editor de limites). O coletor
(coletar_rppns.py) completa/substitui com áreas, municípios e polígonos de todas.
"""
import json
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon

DADOS = Path(__file__).resolve().parent / "dados"
DADOS.mkdir(exist_ok=True)

# (nome, uf, status) — copiado do Painel de Gestão (dados reais)
RPPNS = [
    ("RPPN Santuário Ecológico Mãe Terra", "DF", "criada"),
    ("Acauã", "GO", "em trâmite"),
    ("Bacupari", "GO", "criada"),
    ("Bem Viver", "GO", "criada"),
    ("Biorregional", "GO", "criada"),
    ("Dr. Severiano Abrão Terrestrial Angels", "GO", "arquivada"),
    ("Mimosa", "GO", "criada"),
    ("Murundu", "GO", "criada"),
    ("Recanto do Arco-Íris", "GO", "em trâmite"),
    ("Reserva do Abade", "GO", "em trâmite"),
    ("Rio Almas", "GO", "criada"),
    ("RPPN Acauã", "GO", "criada"),
    ("RPPN Água Santa", "GO", "criada"),
    ("RPPN Amigos da Serra dos Pirineus", "GO", "criada"),
    ("RPPN Avá-Canoeiro", "GO", "criada"),
    ("RPPN Barriguda", "GO", "criada"),
    ("RPPN Campos Úmidos Vochysias", "GO", "criada"),
    ("RPPN Canto da Mata", "GO", "criada"),
    ("RPPN Capão da Onça", "GO", "criada"),
    ("RPPN Flor das Águas do Cerrado", "GO", "criada"),
    ("RPPN Grota das Netas", "GO", "criada"),
    ("RPPN Lavrinhas", "GO", "criada"),
    ("RPPN Nascentes", "GO", "criada"),
    ("RPPN Recanto do Arco-Íris (novo)", "GO", "criada"),
    ("RPPN Reserva Ecológica do Barriguda", "GO", "criada"),
    ("RPPN Sussuarana do Cerrado", "GO", "criada"),
    ("RPPN Vale das Copaíbas", "GO", "criada"),
    ("Santuário Beija Flor", "GO", "arquivada"),
    ("Viver Paz e Bem", "GO", "em trâmite"),
    ("Cachoeira", "MG", "em trâmite"),
    ("Caverna do Tamboril", "MG", "em trâmite"),
    ("RPPN Agnar Domingos João Seu Lico", "MG", "criada"),
    ("RPPN Cacheira do Campo", "MG", "em cadastro"),
    ("RPPN Degraus do Urucuia", "MG", "criada"),
    ("RPPN Gruta do Tamboril", "MG", "criada"),
    ("RPPN Negrinho Divino Eustáquio de Souza", "MG", "criada"),
]

regs = []
for nome, uf, status in RPPNS:
    r = {"rppnid": None, "nome": nome, "uf": uf, "status": status,
         "municipio": "", "proprietario": "", "area_rppn_ha": None,
         "data_criacao": "", "data_cadastro": "", "data_ato": "", "pagina": ""}
    if nome == "RPPN Santuário Ecológico Mãe Terra":
        r.update(rppnid=1428, municipio="Brasília", area_rppn_ha=2.38,
                 proprietario="Dalva Aparecida de Mendonça Fajardo",
                 data_cadastro="28/01/2021", data_ato="29/03/2022",
                 data_criacao="29/03/2022",
                 pagina="https://simrppn.sisicmbio.icmbio.gov.br/RPPNPage/1428")
    regs.append(r)

json.dump({"fonte": "Painel de Gestão SIMRPPN (captura 2026-07-17)",
           "rppns": regs},
          open(DADOS / "rppns.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# polígono REAL da RPPN 1428 (editor de limites, UTM 23S / EPSG:31983)
verts_1428 = [(202809.33, 8275098.37), (202717.73, 8275088.62),
              (202716.23, 8275314.81), (202841.20, 8275313.73)]
gdf = gpd.GeoDataFrame(
    {"rppnid": [1428], "nome": ["RPPN Santuário Ecológico Mãe Terra"],
     "uf": ["DF"], "status": ["criada"], "area_rppn_ha": [2.38]},
    geometry=[Polygon(verts_1428)], crs=31983).to_crs(4326)
gdf.to_file(DADOS / "rppns.geojson", driver="GeoJSON")

print(f"[ok] {DADOS/'rppns.json'}  ({len(regs)} RPPNs)")
print(f"[ok] {DADOS/'rppns.geojson'}  (1 polígono real — 1428)")
