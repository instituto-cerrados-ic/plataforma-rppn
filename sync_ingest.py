# -*- coding: utf-8 -*-
"""
sync_ingest.py — recebe o arquivo gerado pelo coletor no navegador
(sincronizacao_rppns_*.json), transforma em dados/rppns.json + dados/rppns.geojson
(reprojetando os vértices UTM SIRGAS 2000 → WGS84), compara com o que está
publicado e grava — no GitHub (token nos secrets; o Streamlit Cloud republica
sozinho) ou localmente (dev).
"""
from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path

import gerar_coordenadas as gc

# valor do <select> de projeção do SIMRPPN -> zona UTM (1 = geográfica)
VAL2ZONA = {2: "18S", 3: "19S", 4: "20S", 5: "21S", 6: "22S", 7: "23S",
            8: "24S", 9: "25S", 10: "20N", 11: "21N", 12: "22N"}
CAMPOS = ["rppnid", "nome", "uf", "status", "municipio", "proprietario",
          "area_rppn_ha", "data_criacao", "data_cadastro", "data_ato", "pagina"]


def _num(v):
    try:
        s = str(v).strip()
        return float(s.replace(".", "").replace(",", ".")) if "," in s else float(s)
    except (TypeError, ValueError):
        return None


def _poligono(pts, zona_val):
    """Lista [[x,y],...] + valor do select -> (shapely Polygon em WGS84) ou None."""
    from shapely.geometry import Polygon
    import geopandas as gpd
    coords = [(_num(x), _num(y)) for x, y in pts]
    coords = [(x, y) for x, y in coords if x is not None and y is not None]
    if len(coords) < 3:
        return None
    zona = VAL2ZONA.get(int(zona_val or 0))
    epsg = gc.epsg_da_zona(zona) if zona else 4674
    poly = Polygon(coords)
    if not poly.is_valid:
        poly = poly.buffer(0)
    return gpd.GeoSeries([poly], crs=epsg).to_crs(4326).iloc[0]


def validar(payload) -> list[str]:
    """Erros estruturais do arquivo (lista vazia = ok)."""
    erros = []
    if not isinstance(payload, dict):
        return ["O arquivo não é um JSON de sincronização."]
    if "rppns" not in payload or not isinstance(payload["rppns"], list):
        erros.append("Campo 'rppns' ausente — não é um arquivo do coletor.")
    elif not payload["rppns"]:
        erros.append("O arquivo não contém nenhuma RPPN.")
    else:
        sem_id = sum(1 for r in payload["rppns"] if not r.get("rppnid"))
        if sem_id:
            erros.append(f"{sem_id} registro(s) sem rppnid.")
    return erros


def processar(payload: dict, por: str = "", base_atual: dict | None = None,
              geo_atual: dict | None = None) -> tuple[dict, dict, dict]:
    """-> (rppns_json, geojson, estatisticas).

    MESCLA com o que já está publicado: quem sincroniza pode ser uma
    colaboradora que só vê parte das RPPNs no painel dela (vínculo no SIMRPPN).
    RPPNs que não apareceram no arquivo são MANTIDAS; polígonos já publicados
    são mantidos quando a coleta não trouxe um novo para aquela RPPN.
    """
    regs, feats, falhas = [], [], []
    for r in payload["rppns"]:
        reg = {k: r.get(k, "") for k in CAMPOS}
        reg["rppnid"] = int(reg["rppnid"])
        reg["area_rppn_ha"] = _num(reg["area_rppn_ha"])
        reg["pagina"] = reg["pagina"] or f"https://simrppn.sisicmbio.icmbio.gov.br/RPPNPage/{reg['rppnid']}"
        # defesa: município que veio como dropdown
        if "\n" in str(reg["municipio"]) or len(str(reg["municipio"])) > 50:
            reg["municipio"] = ""
        regs.append(reg)
        try:
            pts_r, pts_i = r.get("pts_rppn") or [], r.get("pts_imovel") or []
            geom = (_poligono(pts_r, r.get("zona_rppn")) if len(pts_r) >= 3
                    else _poligono(pts_i, r.get("zona_imovel")))
            if geom is not None:
                feats.append({"type": "Feature", "geometry": geom.__geo_interface__,
                              "properties": {"rppnid": reg["rppnid"], "nome": reg["nome"],
                                             "uf": reg["uf"], "status": reg["status"],
                                             "area_rppn_ha": reg["area_rppn_ha"]}})
        except Exception as e:  # polígono inválido não derruba a sincronização
            falhas.append(f"{reg['nome']}: {e}")
    # --- mesclagem com a base publicada ---
    vistos = {r["rppnid"] for r in regs}
    mantidas = []
    for r in (base_atual or {}).get("rppns", []):
        if r.get("rppnid") and r["rppnid"] not in vistos:
            regs.append(r)
            mantidas.append(r.get("nome", ""))
    ids_feat = {f["properties"]["rppnid"] for f in feats}
    poligonos_mantidos = 0
    for f in (geo_atual or {}).get("features", []):
        if f["properties"].get("rppnid") not in ids_feat:
            feats.append(f)
            poligonos_mantidos += 1

    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    rppns_json = {"fonte": "SIMRPPN — sincronização pela plataforma",
                  "sincronizado_em": agora, "por": por,
                  "coletor_versao": payload.get("versao", ""),
                  "coletado_em": payload.get("coletado_em", ""), "rppns": regs}
    geojson = {"type": "FeatureCollection", "features": feats}
    ids_poly = {f["properties"]["rppnid"] for f in feats}
    stats = {"total": len(regs), "poligonos": len(feats),
             "no_arquivo": len(vistos), "mantidas_nao_vistas": mantidas,
             "poligonos_mantidos": poligonos_mantidos,
             "criadas_sem_poligono": [x["nome"] for x in regs
                                      if x["status"] == "criada" and x["rppnid"] not in ids_poly],
             "falhas": falhas, "com_erro_coleta": [x.get("nome") for x in payload["rppns"] if x.get("erro")]}
    return rppns_json, geojson, stats


def comparar(antigo: dict | None, novo: dict, geo_antigo: dict | None, geo_novo: dict) -> dict:
    """O que mudou em relação ao que está publicado."""
    a = {r["rppnid"]: r for r in (antigo or {}).get("rppns", []) if r.get("rppnid")}
    n = {r["rppnid"]: r for r in novo["rppns"]}
    pa = {f["properties"].get("rppnid") for f in (geo_antigo or {}).get("features", [])}
    pn = {f["properties"].get("rppnid") for f in geo_novo["features"]}
    return {
        "novas": [n[i]["nome"] for i in n if i not in a],
        "removidas": [a[i]["nome"] for i in a if i not in n],
        "status_alterados": [f"{n[i]['nome']}: {a[i].get('status')} → {n[i]['status']}"
                             for i in n if i in a and a[i].get("status") != n[i]["status"]],
        "poligonos_novos": [n[i]["nome"] for i in (pn - pa) if i in n],
        "poligonos_perdidos": [a[i]["nome"] for i in (pa - pn) if i in a],
    }


# ---------------------------------------------------------------- gravação
def gravar_local(dados_dir: Path, rppns_json: dict, geojson: dict):
    dados_dir.mkdir(exist_ok=True)
    (dados_dir / "rppns.json").write_text(json.dumps(rppns_json, ensure_ascii=False, indent=1), encoding="utf-8")
    (dados_dir / "rppns.geojson").write_text(json.dumps(geojson, ensure_ascii=False), encoding="utf-8")


def gravar_github(token: str, repo: str, branch: str, arquivos: dict[str, str], mensagem: str) -> list[str]:
    """Faz commit de cada arquivo via API de conteúdo do GitHub. -> URLs dos commits."""
    import requests
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    urls = []
    for caminho, conteudo in arquivos.items():
        url = f"https://api.github.com/repos/{repo}/contents/{caminho}"
        sha = None
        r = requests.get(url, headers=h, params={"ref": branch}, timeout=30)
        if r.status_code == 200:
            sha = r.json().get("sha")
        elif r.status_code != 404:
            raise RuntimeError(f"GitHub GET {caminho}: HTTP {r.status_code} — {r.text[:200]}")
        body = {"message": mensagem, "branch": branch,
                "content": base64.b64encode(conteudo.encode("utf-8")).decode()}
        if sha:
            body["sha"] = sha
        r = requests.put(url, headers=h, json=body, timeout=60)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"GitHub PUT {caminho}: HTTP {r.status_code} — {r.text[:300]}")
        urls.append(r.json().get("commit", {}).get("html_url", ""))
    return urls
