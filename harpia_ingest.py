# -*- coding: utf-8 -*-
"""
harpia_ingest.py — interpreta o arquivo gerado pelo coletor do Harpia
(harpia_<data>.json): identifica solicitações de RPPN distrital (IBRAM/DF),
servidões ambientais e polígonos (shapefile dentro do .zip anexado), e
mescla tudo em rppns.json / rppns.geojson ao lado das RPPNs federais.

Identificação das RPPNs do Harpia: rppnid NEGATIVO derivado do protocolo
(as federais têm ids positivos do SIMRPPN), campo orgao = "IBRAM".
"""
from __future__ import annotations

import base64
import io
import re
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

SITUACAO2STATUS = {"processo peticionado": "em trâmite", "deferido": "criada",
                   "indeferido": "arquivada", "arquivado": "arquivada", "cancelado": "arquivada"}


def _id(protocolo: str) -> int:
    dig = re.sub(r"\D", "", protocolo or "")
    return -int(dig) if dig else 0


def _num(s):
    try:
        return float(str(s).replace(".", "").replace(",", "."))
    except (TypeError, ValueError):
        return None


def _apos(texto: str, rotulo: str) -> str:
    """Linha seguinte ao rótulo (campos do Harpia vêm como 'Rótulo\\nValor')."""
    m = re.search(re.escape(rotulo) + r"\s*\n+\s*([^\n]+)", texto or "")
    return m.group(1).strip() if m else ""


def _secao(sol: dict, *nomes) -> str:
    for n in nomes:
        for k, v in (sol.get("secoes") or {}).items():
            if n.lower() in k.lower():
                return v or ""
    return ""


def validar(payload) -> list[str]:
    if not isinstance(payload, dict) or payload.get("origem") != "harpia":
        return ["Não é um arquivo do coletor do Harpia."]
    if not isinstance(payload.get("solicitacoes"), list) or not payload["solicitacoes"]:
        return ["O arquivo não contém solicitações."]
    return []


def interpretar(sol: dict) -> dict:
    """Uma solicitação do Harpia -> registro interpretado."""
    todo = "\n".join((sol.get("secoes") or {}).values())
    prop = _secao(sol, "Propriedade")
    req = _secao(sol, "Requerimento")
    r = {"protocolo": sol.get("protocolo", ""), "data_envio": sol.get("data_envio", ""),
         "tipo": sol.get("tipo", ""), "especificacao": sol.get("especificacao", ""),
         "situacao": sol.get("situacao", ""), "data_situacao": sol.get("data_situacao", ""),
         "erro_coleta": sol.get("erro", "")}
    r["eh_rppn"] = "Informações da RPPN" in prop
    r["menciona_rppn"] = bool(re.search(r"\bRPPN\b|Reserva Particular", todo))
    r["nome_rppn"] = _apos(prop, "Nome da RPPN")
    r["motivo"] = _apos(prop, "Motivo da Criação")
    r["configuracao"] = _apos(prop, "Configuração da RPPN")
    m = re.search(r"Área Total \(Propriedades\):\s*([\d.,]+)", prop)
    r["area_imovel_ha"] = _num(m.group(1)) if m else None
    m = re.search(r"Área Total \(RPPN\):\s*([\d.,]+)", prop)
    r["area_rppn_ha"] = _num(m.group(1)) if m else None
    # proprietário: 1ª linha da tabela "NOME ... AÇÕES\n\nNome\n\nMatrícula\n\nTipo\n\nSim/Não"
    m = re.search(r"AÇÕES\s*\n+\s*([^\n]+)\n+\s*(\d+)\n+\s*([^\n]+)\n+\s*(Sim|Não)", prop)
    r["proprietario"], r["matricula"], r["tipo_imovel"] = (m.group(1).strip(), m.group(2), m.group(3).strip()) if m else ("", "", "")
    m = re.search(r"LATITUDE\s+LONGITUDE\s*\n+\s*\d+\s*\n+\s*(-?[\d,\.]+)\s*\n+\s*(-?[\d,\.]+)", prop)
    r["lat"], r["lon"] = (float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))) if m else (None, None)
    sv = _apos(prop, "Há proposta de servidão ambiental no empreendimento?")
    r["servidao_proposta"] = sv.lower().startswith("sim")
    m = re.search(r"Servidão Ambiental(.*)$", prop, re.S)
    r["servidao_texto"] = m.group(1).strip()[:2000] if m and r["servidao_proposta"] else ""
    # campos do requerimento: procura em todas as seções (a aba pode ter sido
    # capturada antes de renderizar e o texto vir sob outro rótulo)
    r["processo_sei"] = _apos(req, "Número do processo:") or _apos(todo, "Número do processo:")
    r["assunto"] = _apos(req, "Assunto") or _apos(todo, "Assunto")
    r["zips"] = [a for a in (sol.get("arquivos") or []) if str(a.get("nome", "")).lower().endswith(".zip")]
    r["anexos"] = [a.get("nome", "") for a in (sol.get("arquivos") or [])]
    return r


def _poligono_do_zip(b64: str):
    """Shapefile(s) dentro do zip -> shapely Polygon (WGS84) da RPPN, ou None."""
    import geopandas as gpd
    raw = base64.b64decode(b64)
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            z.extractall(td)
        shps = sorted(Path(td).rglob("*.shp"))
        if not shps:
            return None
        # preferir a camada cujo nome fala em RPPN; senão a de menor área (a RPPN cabe no imóvel)
        cands = []
        for shp in shps:
            try:
                g = gpd.read_file(shp)
            except Exception:
                continue
            g = g[g.geometry.notna()]
            if g.empty:
                continue
            if g.crs is None:
                g = g.set_crs(4674)
            g = g[g.geom_type.isin(["Polygon", "MultiPolygon"])]   # ignora camadas de vértices
            if g.empty:
                continue
            geom = g.to_crs(4326).union_all() if hasattr(g, "union_all") else g.to_crs(4326).unary_union
            cands.append((("rppn" in shp.name.lower()), geom.area, geom))
        if not cands:
            return None
        cands.sort(key=lambda c: (not c[0], c[1]))
        return cands[0][2]


def processar(payload: dict, por: str = "", base_atual: dict | None = None,
              geo_atual: dict | None = None) -> tuple[dict, dict, dict, list[dict]]:
    """-> (rppns_json mesclado, geojson mesclado, estatísticas, registros interpretados)."""
    regs = [interpretar(s) for s in payload["solicitacoes"]]
    novos, feats, falhas = [], [], []
    for r in regs:
        if not r["eh_rppn"]:
            continue
        rid = _id(r["protocolo"])
        status = SITUACAO2STATUS.get(r["situacao"].lower(), "em trâmite")
        novos.append({"rppnid": rid, "nome": r["nome_rppn"] or f"RPPN (protocolo {r['protocolo']})",
                      "uf": "DF", "status": status, "municipio": "Brasília",
                      "proprietario": r["proprietario"], "area_rppn_ha": r["area_rppn_ha"],
                      "data_criacao": "", "data_cadastro": r["data_envio"][:10], "data_ato": "",
                      "pagina": "https://harpia.ibram.df.gov.br/", "orgao": "IBRAM",
                      "protocolo": r["protocolo"], "processo_sei": r["processo_sei"],
                      "situacao_harpia": r["situacao"], "data_situacao": r["data_situacao"],
                      "matricula": r["matricula"], "area_imovel_ha": r["area_imovel_ha"],
                      "servidao_proposta": r["servidao_proposta"], "servidao_texto": r["servidao_texto"],
                      "lat": r["lat"], "lon": r["lon"]})
        geom = None
        for z in r["zips"]:
            if z.get("base64"):
                try:
                    geom = _poligono_do_zip(z["base64"])
                except Exception as e:
                    falhas.append(f"{r['nome_rppn']}: {z.get('nome')}: {e}")
            if geom is not None:
                break
        if geom is not None:
            feats.append({"type": "Feature", "geometry": geom.__geo_interface__,
                          "properties": {"rppnid": rid, "nome": novos[-1]["nome"], "uf": "DF",
                                         "status": status, "area_rppn_ha": r["area_rppn_ha"],
                                         "orgao": "IBRAM"}})
    # mesclagem: substitui só as RPPNs do IBRAM vistas; mantém tudo o mais
    vistos = {x["rppnid"] for x in novos}
    regs_base = [x for x in (base_atual or {}).get("rppns", []) if x.get("rppnid") not in vistos]
    feats_base = [f for f in (geo_atual or {}).get("features", []) if f["properties"].get("rppnid") not in vistos]
    ids_poly_novos = {f["properties"]["rppnid"] for f in feats}
    # RPPN do IBRAM sem polígono novo mantém o antigo, se havia
    for f in (geo_atual or {}).get("features", []):
        if f["properties"].get("rppnid") in vistos and f["properties"]["rppnid"] not in ids_poly_novos:
            feats.append(f)
    rppns_json = dict(base_atual or {})
    rppns_json.update({"rppns": regs_base + novos,
                       "harpia_sincronizado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
                       "harpia_por": por, "harpia_coletor_versao": payload.get("versao", "")})
    rppns_json.setdefault("fonte", "SIMRPPN + Harpia (IBRAM)")
    geojson = {"type": "FeatureCollection", "features": feats_base + feats}
    stats = {"solicitacoes": len(regs), "rppns": len(novos), "poligonos": len(ids_poly_novos),
             "servidoes": [x["nome"] for x in novos if x["servidao_proposta"]],
             "relacionadas": [f"{r['protocolo']} — {r['assunto'] or r['especificacao']}"
                              for r in regs if r["menciona_rppn"] and not r["eh_rppn"]],
             "outras": [f"{r['protocolo']} — {r['assunto'] or r['especificacao']}"
                        for r in regs if not r["menciona_rppn"]],
             "falhas": falhas, "com_erro_coleta": [r["protocolo"] for r in regs if r["erro_coleta"]]}
    return rppns_json, geojson, stats, regs
