# -*- coding: utf-8 -*-
"""
complementos.py — dados informados À MÃO pela equipe (polígono ou campos que faltam
nos sistemas oficiais), guardados em complementos.json, SEPARADOS do que vem das
sincronizações. Por isso nenhuma sincronização os apaga: eles são aplicados por cima
dos dados oficiais na hora de mostrar o painel e o mapa.

Regras de precedência:
- campos: o valor manual prevalece sobre o oficial enquanto o complemento existir;
- polígono: o oficial (SIMRPPN/Harpia) prevalece quando existe, salvo se a pessoa marcou
  "prevalece" no complemento; quando não há oficial, o manual é usado.
"""
from __future__ import annotations

import hashlib
from datetime import datetime

ARQ = "complementos.json"
CAMPOS = ["nome", "uf", "municipio", "proprietario", "status", "area_rppn_ha",
          "data_criacao", "data_ato", "data_cadastro", "pagina"]


def vazio() -> dict:
    return {"versao": "1.0", "atualizado_em": "", "por": "", "itens": {}}


def id_manual(nome: str) -> int:
    """RPPN que não está em nenhum sistema: id negativo estável derivado do nome
    (faixa −9.000.000… para não colidir com os ids do Harpia)."""
    h = int(hashlib.sha1(nome.strip().lower().encode("utf-8")).hexdigest(), 16) % 1_000_000
    return -(9_000_000 + h)


def definir(comp: dict, rppnid: int, campos: dict | None = None, poligono: dict | None = None,
            prevalece: bool = False, por: str = "", obs: str = "", nome_poligono: str = "") -> dict:
    itens = comp.setdefault("itens", {})
    it = itens.get(str(rppnid), {"campos": {}, "poligono": None})
    for k, v in (campos or {}).items():
        if v in (None, ""):
            it["campos"].pop(k, None)
        else:
            it["campos"][k] = v
    if poligono is not None:
        it["poligono"] = poligono
        it["poligono_arquivo"] = nome_poligono
    it["prevalece"] = bool(prevalece)
    it["obs"] = obs or it.get("obs", "")
    it["por"] = por
    it["em"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    itens[str(rppnid)] = it
    comp["atualizado_em"] = it["em"]
    comp["por"] = por
    return comp


def remover(comp: dict, rppnid: int, por: str = "") -> dict:
    comp.setdefault("itens", {}).pop(str(rppnid), None)
    comp["atualizado_em"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    comp["por"] = por
    return comp


def aplicar(rppns_json: dict | None, geojson: dict | None, comp: dict | None) -> tuple[dict, dict, dict]:
    """Dados oficiais + complementos -> (rppns_json, geojson, info) para exibição.
    Não altera os objetos de entrada."""
    import copy
    rj = copy.deepcopy(rppns_json or {"rppns": []})
    gj = copy.deepcopy(geojson or {"type": "FeatureCollection", "features": []})
    itens = (comp or {}).get("itens", {}) or {}
    info = {"campos": [], "poligonos_manuais": [], "poligonos_sobrepostos": [], "rppns_manuais": []}
    por_id = {r.get("rppnid"): r for r in rj["rppns"]}
    for sid, it in itens.items():
        rid = int(sid)
        r = por_id.get(rid)
        if r is None:                       # RPPN que só existe à mão
            r = {"rppnid": rid, "nome": "", "uf": "", "status": "em cadastro", "municipio": "",
                 "proprietario": "", "area_rppn_ha": None, "data_criacao": "", "data_cadastro": "",
                 "data_ato": "", "pagina": "", "orgao": it.get("campos", {}).get("orgao", "ICMBio")}
            rj["rppns"].append(r)
            por_id[rid] = r
            info["rppns_manuais"].append(it.get("campos", {}).get("nome", sid))
        for k, v in (it.get("campos") or {}).items():
            if v not in (None, ""):
                r[k] = v
                info["campos"].append((r.get("nome") or sid, k))
        r["complemento"] = True
        if it.get("poligono"):
            feats = [f for f in gj["features"] if f["properties"].get("rppnid") == rid]
            if not feats or it.get("prevalece"):
                gj["features"] = [f for f in gj["features"] if f["properties"].get("rppnid") != rid]
                gj["features"].append({"type": "Feature", "geometry": it["poligono"],
                                       "properties": {"rppnid": rid, "nome": r.get("nome", ""),
                                                      "uf": r.get("uf", ""), "status": r.get("status", ""),
                                                      "area_rppn_ha": r.get("area_rppn_ha"),
                                                      "orgao": r.get("orgao", "ICMBio"), "fonte": "manual"}})
                (info["poligonos_sobrepostos"] if feats else info["poligonos_manuais"]).append(r.get("nome") or sid)
    return rj, gj, info


def serializar(comp: dict) -> str:
    import json
    return json.dumps(comp, ensure_ascii=False, indent=1)
