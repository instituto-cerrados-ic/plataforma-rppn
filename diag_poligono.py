# -*- coding: utf-8 -*-
"""
Diagnóstico (somente leitura): por que algumas RPPNs criadas não têm polígono?
Inspeciona, para rppnids escolhidos: a lista do memorial (links de download,
área/nº de pontos declarados) e o editor de limites (quantas coordenadas
digitadas existem). Rode com o Chrome de depuração logado.

    python diag_poligono.py                 # usa 1341 e 1605
    python diag_poligono.py 1341 1504
"""
import sys
from pathlib import Path

BASE = "https://simrppn.sisicmbio.icmbio.gov.br"
rids = [int(a) for a in sys.argv[1:]] or [1341, 1605]

JS_LISTA = r"""() => {
  const links = [...document.querySelectorAll('a')].map(a => a.innerText.trim())
      .filter(t => /baixar|limite|memorial|enviar/i.test(t));
  const editar = document.querySelector("a[href*='imovelid=']")?.href || '';
  const texto = (document.querySelector('main')?.innerText || '');
  const mArea = texto.match(/Área declarada:\s*([\d.,]+)/g) || [];
  const mPts  = texto.match(/Número de Pontos:\s*(\d+)/g) || [];
  return {links, editar, areas: mArea, pontos: mPts};
}"""

JS_EDITOR = r"""() => {
  const arr = (s) => [...document.querySelectorAll(s)].map(i => i.value).filter(v=>v);
  const sel = (s) => document.querySelector(s)?.value || '';
  return {
    tipo_entrada_imovel: sel("select[name='tipo_entrada_limites']"),
    tipo_entrada_rppn:   sel("select[name='tipo_entrada_limites-rppn1']"),
    n_x_imovel: arr("input[name='longitude-imovel[]']").length,
    n_x_rppn:   arr("input[name='longitude-imovel-rppn1[]']").length,
    limite_rppn: document.querySelector("input[name='limite-rppn']:checked")?.value || '',
  };
}"""


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://localhost:9222")
        ctx = b.contexts[0]
        page = next((pg for pg in ctx.pages if "simrppn" in pg.url),
                    ctx.pages[0] if ctx.pages else ctx.new_page())
        for rid in rids:
            print(f"\n===== RPPN {rid} =====")
            page.goto(f"{BASE}/site/modules/Memorial-descritivo/"
                      f"v_Memorial-descritivo-lista.php?rppnid={rid}&bq=1",
                      wait_until="domcontentloaded")
            page.wait_for_timeout(1200)
            lst = page.evaluate(JS_LISTA)
            print("LISTA:")
            print("  links:", lst["links"])
            print("  áreas declaradas:", lst["areas"])
            print("  nº de pontos:", lst["pontos"])
            print("  link editar:", lst["editar"][:90])
            import re
            m = re.search(r"imovelid=(\d+)", lst["editar"])
            if not m:
                print("  >>> SEM link de editor (imovelid).")
                continue
            page.goto(f"{BASE}/site/modules/Memorial-descritivo/"
                      f"v_Memorial-descritivo-editar.php?rppnid={rid}"
                      f"&imovelid={m.group(1)}&limite=true",
                      wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            ed = page.evaluate(JS_EDITOR)
            print("EDITOR:", ed)


if __name__ == "__main__":
    main()
