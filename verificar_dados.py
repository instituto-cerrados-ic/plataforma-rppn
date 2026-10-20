# -*- coding: utf-8 -*-
"""
verificar_dados.py — checagem de integridade do "banco" da Plataforma RPPN
(os três JSON do repositório privado instituto-cerrados-ic/plataforma-rppn-dados).

Uso:
  python verificar_dados.py                 # lê a pasta local dados/
  python verificar_dados.py --remoto        # clona o repositório privado (precisa de git com acesso)
  python verificar_dados.py --pasta <dir>   # qualquer pasta com os 3 arquivos
  python verificar_dados.py --simular-sync <arquivo_do_coletor.json>
        # prova de aditividade: aplica a sincronização em memória e confere que nada
        # que estava na base some (RPPNs, polígonos, metadados, processos)

Saída: lista de [OK]/[AVISO]/[ERRO] e código de saída 1 se houver ERRO.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
REPO_DADOS = "https://github.com/instituto-cerrados-ic/plataforma-rppn-dados.git"
STATUS_OK = {"criada", "em trâmite", "em cadastro", "arquivada"}
ORGAOS = {"ICMBio", "IBRAM"}
UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB",
       "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}
BBOX_BR = (-74.0, -34.0, -34.0, 5.5)   # lon_min, lat_min, lon_max, lat_max

achados: list[tuple[str, str]] = []


def ok(m): achados.append(("OK", m))
def aviso(m): achados.append(("AVISO", m))
def erro(m): achados.append(("ERRO", m))


def _data(s):
    try:
        return datetime.strptime(s, "%d/%m/%Y")
    except Exception:
        return None


def carregar(pasta: Path):
    out = {}
    for nome in ("rppns.json", "rppns.geojson", "processos.json"):
        p = pasta / nome
        if not p.exists():
            erro(f"{nome}: arquivo ausente em {pasta}")
            out[nome] = None
            continue
        try:
            out[nome] = json.loads(p.read_text(encoding="utf-8"))
            ok(f"{nome}: JSON válido ({p.stat().st_size/1024:.0f} KB)")
        except Exception as e:
            erro(f"{nome}: JSON inválido — {e}")
            out[nome] = None
    return out


def checar_rppns(rj):
    if not rj:
        return set()
    regs = rj.get("rppns")
    if not isinstance(regs, list) or not regs:
        erro("rppns.json: lista 'rppns' vazia ou ausente")
        return set()
    ids = [r.get("rppnid") for r in regs]
    dup = [i for i, n in Counter(ids).items() if n > 1]
    if dup:
        erro(f"rppns.json: rppnid duplicado: {dup}")
    else:
        ok(f"rppns.json: {len(regs)} RPPNs, ids únicos")
    sem_id = [r.get("nome") for r in regs if not isinstance(r.get("rppnid"), int) or r.get("rppnid") == 0]
    if sem_id:
        erro(f"rppns.json: registros sem rppnid inteiro: {sem_id}")
    for r in regs:
        nome = r.get("nome") or f"id {r.get('rppnid')}"
        if not r.get("nome"):
            aviso(f"rppns.json: id {r.get('rppnid')} sem nome")
        if r.get("status") not in STATUS_OK:
            erro(f"rppns.json: '{nome}' com status fora do padrão: {r.get('status')!r}")
        if r.get("uf") not in UFS:
            erro(f"rppns.json: '{nome}' com UF inválida: {r.get('uf')!r}")
        org = r.get("orgao") or "ICMBio"
        if org not in ORGAOS:
            erro(f"rppns.json: '{nome}' com órgão desconhecido: {org!r}")
        if org == "IBRAM" and not (isinstance(r.get("rppnid"), int) and r["rppnid"] < 0):
            erro(f"rppns.json: '{nome}' é IBRAM mas o rppnid não é negativo ({r.get('rppnid')})")
        if org == "ICMBio" and isinstance(r.get("rppnid"), int) and r["rppnid"] < 0:
            erro(f"rppns.json: '{nome}' é ICMBio mas tem rppnid negativo")
        a = r.get("area_rppn_ha")
        if a is not None and not (isinstance(a, (int, float)) and 0 < a < 1_000_000):
            aviso(f"rppns.json: '{nome}' com área suspeita: {a!r}")
        m = str(r.get("municipio") or "")
        if "\n" in m or len(m) > 50:
            erro(f"rppns.json: '{nome}' com município corrompido (dropdown capturado)")
        for campo in ("data_criacao", "data_cadastro", "data_ato"):
            v = r.get(campo)
            if v and not _data(v):
                aviso(f"rppns.json: '{nome}' campo {campo} fora do formato dd/mm/aaaa: {v!r}")
        if r.get("status") == "criada" and not r.get("data_criacao"):
            aviso(f"rppns.json: '{nome}' criada sem data_criacao")
    crit = [r["nome"] for r in regs if r.get("status") == "criada"]
    ok(f"rppns.json: {len(crit)} criadas, {sum(1 for r in regs if r.get('status')=='em trâmite')} em trâmite, "
       f"{sum(1 for r in regs if (r.get('orgao') or 'ICMBio')=='IBRAM')} do IBRAM")
    for meta in ("sincronizado_em", "por"):
        if not rj.get(meta):
            aviso(f"rppns.json: metadado '{meta}' ausente (última sincronização não registrada)")
    return set(ids)


def checar_geojson(gj, ids_rppn):
    if not gj:
        return
    feats = gj.get("features")
    if gj.get("type") != "FeatureCollection" or not isinstance(feats, list):
        erro("rppns.geojson: não é um FeatureCollection")
        return
    try:
        from shapely.geometry import shape
    except ImportError:
        aviso("shapely não instalado: geometria não validada")
        shape = None
    ids = []
    for f in feats:
        p = f.get("properties") or {}
        rid, nome = p.get("rppnid"), p.get("nome") or f"id {p.get('rppnid')}"
        ids.append(rid)
        if rid not in ids_rppn:
            erro(f"rppns.geojson: polígono de '{nome}' (id {rid}) sem RPPN correspondente em rppns.json")
        g = f.get("geometry") or {}
        if g.get("type") not in ("Polygon", "MultiPolygon"):
            erro(f"rppns.geojson: '{nome}' não é polígono ({g.get('type')})")
            continue
        if shape:
            try:
                s = shape(g)
            except Exception as e:
                erro(f"rppns.geojson: '{nome}' geometria ilegível — {e}")
                continue
            if not s.is_valid:
                aviso(f"rppns.geojson: '{nome}' geometria inválida (auto-interseção?)")
            if s.is_empty or s.area == 0:
                erro(f"rppns.geojson: '{nome}' geometria vazia")
            x0, y0, x1, y1 = s.bounds
            if not (BBOX_BR[0] <= x0 and x1 <= BBOX_BR[2] and BBOX_BR[1] <= y0 and y1 <= BBOX_BR[3]):
                erro(f"rppns.geojson: '{nome}' fora do Brasil (bounds {s.bounds}) — coordenadas trocadas ou zona UTM errada?")
            if (x1 - x0) > 1.0 or (y1 - y0) > 1.0:
                aviso(f"rppns.geojson: '{nome}' muito extenso (>1°) — conferir")
    dup = [i for i, n in Counter(ids).items() if n > 1]
    if dup:
        erro(f"rppns.geojson: rppnid duplicado entre polígonos: {dup}")
    ok(f"rppns.geojson: {len(feats)} polígonos; {len(ids_rppn - set(ids))} RPPNs sem polígono")


def checar_processos(pj, ids_rppn):
    if not pj:
        return
    procs = pj.get("processos")
    if not isinstance(procs, list):
        erro("processos.json: lista 'processos' ausente")
        return
    try:
        sys.path.insert(0, str(AQUI))
        import processos as PR
    except Exception as e:
        aviso(f"processos.py não importável ({e}); checagem estrutural apenas")
        PR = None
    ids = [p.get("id") for p in procs]
    dup = [i for i, n in Counter(ids).items() if n > 1]
    if dup:
        erro(f"processos.json: id de processo duplicado: {dup}")
    rids = [p.get("rppnid") for p in procs if p.get("rppnid")]
    dupr = [i for i, n in Counter(rids).items() if n > 1]
    if dupr:
        erro(f"processos.json: mais de uma ficha para a mesma RPPN (rppnid {dupr})")
    for p in procs:
        nome = p.get("nome") or p.get("id")
        if p.get("rppnid") and p["rppnid"] not in ids_rppn:
            aviso(f"processos.json: '{nome}' aponta para rppnid {p['rppnid']} que não existe em rppns.json")
        if p.get("situacao", "ativo") not in ("ativo", "concluído", "arquivado"):
            erro(f"processos.json: '{nome}' com situação inválida {p.get('situacao')!r}")
        if (p.get("orgao") or "ICMBio") not in ORGAOS:
            erro(f"processos.json: '{nome}' com órgão inválido {p.get('orgao')!r}")
        if p.get("inicio") and not _data(p["inicio"]):
            aviso(f"processos.json: '{nome}' data de início inválida {p['inicio']!r}")
        if PR:
            validas = {tid for _p, _t, _d, tarefas in PR.passos_de(p) for tid, _ in tarefas}
            estranhas = set(p.get("tarefas", {})) - validas
            if estranhas:
                erro(f"processos.json: '{nome}' tem tarefas fora do roteiro {p.get('orgao','ICMBio')}: {sorted(estranhas)}")
            for pid in p.get("duracoes", {}):
                if pid not in {x[0] for x in PR.passos_de(p)}:
                    aviso(f"processos.json: '{nome}' duração para passo inexistente {pid}")
            for tid, t in p.get("tarefas", {}).items():
                if t.get("feito") and t.get("data") and not _data(t["data"]):
                    aviso(f"processos.json: '{nome}' tarefa {tid} com data inválida {t['data']!r}")
            r = PR.resumo(p)
            if r["dias_restantes"] < 0:
                erro(f"processos.json: '{nome}' dias restantes negativos")
    ok(f"processos.json: {len(procs)} fichas ({sum(1 for p in procs if p.get('situacao','ativo')=='ativo')} ativas)"
       + (f" · última gravação {pj.get('atualizado_em')} por {pj.get('por')}" if pj.get("atualizado_em") else ""))


def simular_sync(dados, arquivo: Path):
    """Aplica a sincronização em memória e prova que ela é ADITIVA."""
    sys.path.insert(0, str(AQUI))
    payload = json.loads(arquivo.read_text(encoding="utf-8"))
    base, geo = dados["rppns.json"], dados["rppns.geojson"]
    if payload.get("origem") == "harpia":
        import harpia_ingest as HI
        novo, gnovo, st, _ = HI.processar(payload, "simulação", base, geo)
    else:
        import sync_ingest as SI
        novo, gnovo, st = SI.processar(payload, "simulação", base, geo)
    antes = {r["rppnid"]: r for r in base["rppns"]}
    depois = {r["rppnid"]: r for r in novo["rppns"]}
    sumiram = set(antes) - set(depois)
    if sumiram:
        erro(f"SYNC NÃO ADITIVA: {len(sumiram)} RPPN(s) sumiriam: {[antes[i]['nome'] for i in sumiram]}")
    else:
        ok(f"sync: nenhuma RPPN some ({len(antes)} → {len(depois)})")
    pa = {f["properties"]["rppnid"] for f in geo["features"]}
    pd_ = {f["properties"]["rppnid"] for f in gnovo["features"]}
    perd = pa - pd_
    if perd:
        erro(f"SYNC NÃO ADITIVA: polígonos perdidos: {[antes.get(i, {}).get('nome', i) for i in perd]}")
    else:
        ok(f"sync: nenhum polígono some ({len(pa)} → {len(pd_)})")
    for k in ("harpia_sincronizado_em", "sincronizado_em"):
        if base.get(k) and not novo.get(k):
            erro(f"SYNC NÃO ADITIVA: metadado '{k}' sumiria")
    mudaram = [antes[i]["nome"] for i in antes if i in depois and antes[i] != depois[i]]
    ok(f"sync: {len(set(depois) - set(antes))} novas, {len(mudaram)} atualizadas (a coleta prevalece para as vistas)")
    ok("processos.json não é tocado pela sincronização (arquivo separado)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--remoto", action="store_true")
    ap.add_argument("--pasta")
    ap.add_argument("--simular-sync")
    args = ap.parse_args()
    if args.remoto:
        td = Path(tempfile.mkdtemp())
        subprocess.run(["git", "clone", "-q", "--depth", "5", REPO_DADOS, str(td / "d")], check=True)
        pasta = td / "d"
        log = subprocess.run(["git", "-C", str(pasta), "log", "--format=%h %ad %an %s", "--date=short", "-5"],
                             capture_output=True, text=True).stdout.strip()
        ok("repositório privado clonado; últimos commits:\n      " + log.replace("\n", "\n      "))
    else:
        pasta = Path(args.pasta) if args.pasta else AQUI / "dados"
    dados = carregar(pasta)
    ids = checar_rppns(dados["rppns.json"])
    checar_geojson(dados["rppns.geojson"], ids)
    checar_processos(dados["processos.json"], ids)
    if args.simular_sync:
        simular_sync(dados, Path(args.simular_sync))
    n_err = sum(1 for t, _ in achados if t == "ERRO")
    for t, m in achados:
        print(f"[{t}] {m}")
    print(f"\n{'TUDO EM ORDEM' if not n_err else f'{n_err} ERRO(S)'} — "
          f"{sum(1 for t,_ in achados if t=='AVISO')} aviso(s)")
    sys.exit(1 if n_err else 0)


if __name__ == "__main__":
    main()
