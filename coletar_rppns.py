# -*- coding: utf-8 -*-
"""
coletar_rppns.py — captura os dados de TODAS as RPPNs do Painel de Gestão do
SIMRPPN (nome, status, UF, município, área, rppnid) + o POLÍGONO de cada uma
(vértices do editor de limites), e grava dados/rppns.json + dados/rppns.geojson
para a aba "Administrar" da plataforma.

Uso (com o Chrome de depuração aberto e logado — abrir_chrome_debug.bat):
    python coletar_rppns.py                 # todas
    python coletar_rppns.py --limit 5       # só as 5 primeiras (teste)

Não altera NADA no SIMRPPN — somente leitura.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gerar_coordenadas as gc  # noqa: E402

BASE = "https://simrppn.sisicmbio.icmbio.gov.br"
DADOS = Path(__file__).resolve().parent / "dados"
DADOS.mkdir(exist_ok=True)

# valor do select 'sistema_de_coordenadasid' -> zona UTM (1=Geográfica)
VAL2ZONA = {2: "18S", 3: "19S", 4: "20S", 5: "21S", 6: "22S", 7: "23S",
            8: "24S", 9: "25S", 10: "20N", 11: "21N", 12: "22N"}

JS_PAINEL = """() => {
  const linhas = [];
  document.querySelectorAll('table tr').forEach(tr => {
    const tds = tr.querySelectorAll('td');
    if (!tds.length) return;
    const editar = tr.querySelector("a[href*='rppnid=']");
    if (!editar) return;
    const m = editar.href.match(/rppnid=(\\d+)/);
    const pagina = tr.querySelector("a[href*='RPPNPage']");
    linhas.push({
      rppnid: m ? parseInt(m[1]) : null,
      nome: tds[0] ? tds[0].innerText.trim().split('\\n')[0] : '',
      uf: tds[1] ? tds[1].innerText.trim() : '',
      status: tds[2] ? tds[2].innerText.trim() : '',
      pagina: pagina ? pagina.href : '',
    });
  });
  return linhas;
}"""

JS_RPPN = """() => {
  // município = o rótulo no formato "Nome (UF)" — ignora o <select> gigante
  // de municípios (RPPNs em cadastro mostram a lista editável inteira).
  const muni = () => {
    const els = document.querySelectorAll('main label, main span, main p, main td');
    for (const el of els) {
      const t = (el.innerText || '').trim();
      if (/^[^\\n]{1,50}\\([A-Z]{2}\\)$/.test(t)) return t;
    }
    return '';
  };
  return {
    nome: document.querySelector("input[name='nome']")?.value || '',
    area: document.querySelector("input[name='area']")?.value || '',
    municipio: muni(),
  };
}"""

JS_PROP = """() => {
  const nomes = [];
  document.querySelectorAll('main table tr').forEach(tr => {
    const td = tr.querySelector('td');
    if (td && td.innerText.trim()) nomes.push(td.innerText.trim());
  });
  return nomes;
}"""

JS_RESUMO = """() => {
  const val = (label) => {
    let best = null, len = 1e9;
    document.querySelectorAll('main *').forEach(el => {
      const t = el.textContent || '';
      if (t.includes(label)) {
        const m = t.match(/(\\d{2}\\/\\d{2}\\/\\d{4})/);
        if (m && t.length < len) { best = m[1]; len = t.length; }
      }
    });
    return best;
  };
  return { cadastro: val('Data de cadastro'), ato: val('Data da publicação') };
}"""

JS_EDITOR = """() => {
  const arr = (sel) => [...document.querySelectorAll(sel)].map(i => i.value);
  const zona = (sel) => parseInt(document.querySelector(sel)?.value || '0');
  const limite = document.querySelector("input[name='limite-rppn']:checked")?.value || '';
  return {
    limite_tipo: limite,
    zona_imovel: zona("select[name='sistema_de_coordenadasid']"),
    x_imovel: arr("input[name='longitude-imovel[]']"),
    y_imovel: arr("input[name='latitude-imovel[]']"),
    zona_rppn: zona("select[name='sistema_de_coordenadasid-rppn1']"),
    x_rppn: arr("input[name='longitude-imovel-rppn1[]']"),
    y_rppn: arr("input[name='latitude-imovel-rppn1[]']"),
  };
}"""


def _num(v):
    try:
        return float(str(v).replace(".", "").replace(",", ".")) \
            if "," in str(v) else float(v)
    except Exception:
        return None


def poligono_de(xs, ys, zona_val):
    from shapely.geometry import Polygon
    pts = [(_num(x), _num(y)) for x, y in zip(xs, ys)]
    pts = [(x, y) for x, y in pts if x is not None and y is not None]
    if len(pts) < 3:
        return None, None
    zona = VAL2ZONA.get(zona_val)
    if zona is None:                      # geográfica: lat/long direto
        return Polygon([(x, y) for x, y in pts]), 4674
    return Polygon(pts), gc.epsg_da_zona(zona)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="máx. de RPPNs (0 = todas)")
    ap.add_argument("--cdp", default="http://localhost:9222")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright
    import geopandas as gpd

    with sync_playwright() as p:
        try:
            b = p.chromium.connect_over_cdp(args.cdp)
        except Exception:
            sys.exit("[erro] Chrome de depuração não encontrado.\n"
                     "       Abra com abrir_chrome_debug.bat, faça o login gov.br "
                     "e rode de novo.")
        ctx = b.contexts[0]
        # prefere uma aba já no SIMRPPN; senão, a primeira
        page = None
        for pg in ctx.pages:
            if "simrppn" in pg.url:
                page = pg
                break
        page = page or (ctx.pages[0] if ctx.pages else ctx.new_page())

        print("[1/3] Lendo o Painel de Gestão...")
        page.goto(f"{BASE}/Painel-de-gestao", wait_until="domcontentloaded")
        try:
            page.wait_for_selector("a[href*='rppnid=']", timeout=12000)
        except Exception:
            pass
        page.wait_for_timeout(800)
        print(f"      URL: {page.url}")
        corpo = page.evaluate("() => document.body.innerText || ''")
        if ("Entrar com" in corpo or "/Login" in page.url
                or page.url.rstrip("/").endswith("icmbio.gov.br")):
            sys.exit(
                "[erro] O SIMRPPN pediu LOGIN nesta janela do Chrome de depuração\n"
                "       (perfil .chrome_perfil — separado do seu Chrome normal).\n"
                "       1) Vá até a janela aberta pelo abrir_chrome_debug.bat;\n"
                "       2) Faça o login gov.br NELA (até ver o Painel de Gestão);\n"
                "       3) Rode 'python coletar_rppns.py' de novo.")
        linhas = page.evaluate(JS_PAINEL)
        # dedup por rppnid (o painel tem links repetidos por linha)
        vistos, rppns = set(), []
        for l in linhas:
            if l["rppnid"] and l["rppnid"] not in vistos:
                vistos.add(l["rppnid"])
                rppns.append(l)
        if not rppns:
            sys.exit("[erro] nenhuma RPPN no painel — confira se está logado.")
        print(f"      {len(rppns)} RPPNs encontradas.")
        if args.limit:
            rppns = rppns[: args.limit]

        print("[2/3] Coletando detalhes e polígonos (somente leitura)...")
        feats = []
        for i, r in enumerate(rppns, 1):
            rid = r["rppnid"]
            try:
                page.goto(f"{BASE}/Rppn?rppnid={rid}&bq=1",
                          wait_until="domcontentloaded")
                page.wait_for_timeout(600)
                det = page.evaluate(JS_RPPN)
                r["area_rppn_ha"] = _num(det["area"])
                r["municipio"] = re.sub(r"\s*\([A-Z]{2}\)$", "",
                                        det["municipio"]).strip()
                # proprietário(s)
                page.goto(f"{BASE}/Proprietario?rppnid={rid}&bq=1",
                          wait_until="domcontentloaded")
                page.wait_for_timeout(400)
                nomes = page.evaluate(JS_PROP)
                r["proprietario"] = nomes[0] if nomes else ""
                if len(nomes) > 1:
                    r["proprietario"] += f" (+{len(nomes) - 1})"
                # datas (Resumo): cadastro e ato de criação
                page.goto(f"{BASE}/Resumo?rppnid={rid}&bq=1",
                          wait_until="domcontentloaded")
                page.wait_for_timeout(400)
                dts = page.evaluate(JS_RESUMO)
                r["data_cadastro"] = dts.get("cadastro") or ""
                r["data_ato"] = dts.get("ato") or ""
                r["data_criacao"] = r["data_ato"] or r["data_cadastro"]
                # imovelid -> editor -> vértices
                page.goto(f"{BASE}/site/modules/Memorial-descritivo/"
                          f"v_Memorial-descritivo-lista.php?rppnid={rid}&bq=1",
                          wait_until="domcontentloaded")
                page.wait_for_timeout(600)
                href = page.evaluate(
                    "() => document.querySelector(\"a[href*='imovelid=']\")?.href || ''")
                m = re.search(r"imovelid=(\d+)", href)
                if m:
                    page.goto(f"{BASE}/site/modules/Memorial-descritivo/"
                              f"v_Memorial-descritivo-editar.php?rppnid={rid}"
                              f"&imovelid={m.group(1)}&limite=true",
                              wait_until="domcontentloaded")
                    # a tabela de coordenadas é preenchida via JS; insiste até os
                    # pontos certos aparecerem (imóvel, ou RPPN se limite parcial)
                    ed = {"x_imovel": [], "y_imovel": [], "x_rppn": [], "y_rppn": [],
                          "zona_imovel": 0, "zona_rppn": 0, "limite_tipo": ""}
                    for _try in range(5):
                        page.wait_for_timeout(700)
                        ed = page.evaluate(JS_EDITOR)
                        parcial = ed.get("limite_tipo") == "parcial"
                        ok_i = len([x for x in ed["x_imovel"] if x]) >= 3
                        ok_r = len([x for x in ed["x_rppn"] if x]) >= 3
                        if (ok_r if parcial else ok_i):
                            break
                    # RPPN parcial tem vértices próprios; senão usa os do imóvel
                    if len([x for x in ed["x_rppn"] if x]) >= 3:
                        poly, epsg = poligono_de(ed["x_rppn"], ed["y_rppn"],
                                                 ed["zona_rppn"])
                    else:
                        poly, epsg = poligono_de(ed["x_imovel"], ed["y_imovel"],
                                                 ed["zona_imovel"])
                    if poly is not None:
                        g = gpd.GeoSeries([poly], crs=epsg).to_crs(4326).iloc[0]
                        feats.append({"rppnid": rid, "nome": r["nome"],
                                      "uf": r["uf"], "status": r["status"],
                                      "area_rppn_ha": r["area_rppn_ha"],
                                      "geometry": g})
                tem_poly = bool(feats and feats[-1]["rppnid"] == rid)
                n_pts = feats[-1]["geometry"].exterior.coords.__len__() - 1 \
                    if tem_poly else 0
                print(f"   [{i}/{len(rppns)}] {r['nome']} — ok"
                      + (f" ({n_pts} pts)" if tem_poly else " (SEM polígono)"))
            except Exception as e:
                print(f"   [{i}/{len(rppns)}] {r['nome']} — FALHOU: "
                      f"{str(e).splitlines()[0]}")

        print("[3/3] Gravando dados/...")
        json.dump({"fonte": "SIMRPPN — coleta automática", "rppns": rppns},
                  open(DADOS / "rppns.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        if feats:
            gdf = gpd.GeoDataFrame(feats, crs=4326)
            gdf.to_file(DADOS / "rppns.geojson", driver="GeoJSON")
        print(f"[ok] rppns.json ({len(rppns)}) + rppns.geojson ({len(feats)} polígonos)")
        print(">> Recarregue a aba Administrar da plataforma (F5).")


if __name__ == "__main__":
    main()
