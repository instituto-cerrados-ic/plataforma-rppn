# -*- coding: utf-8 -*-
"""
testar_fluxos.py — testes de fluxo da Plataforma RPPN com o AppTest do Streamlit
(sem navegador, sem login: roda contra a pasta local dados/).

Cada teste simula o que uma pessoa faria e confere o resultado na tela.
Uso: python testar_fluxos.py            (código de saída 1 se algum fluxo falhar)
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from streamlit.testing.v1 import AppTest  # noqa: E402

resultados = []
REAL_ANTES = json.loads((AQUI / "dados" / "processos.json").read_text(encoding="utf-8"))


def teste(nome):
    def deco(fn):
        def run():
            try:
                fn()
                resultados.append((nome, True, ""))
            except Exception as e:  # noqa: BLE001
                resultados.append((nome, False, f"{type(e).__name__}: {e}"))
        run.__name__ = fn.__name__
        return run
    return deco


def app(**query):
    at = AppTest.from_file(str(AQUI / "app.py"), default_timeout=240)
    for k, v in query.items():
        at.query_params[k] = v
    at.run()
    assert not at.exception, f"exceção na carga: {[str(e.value)[:200] for e in at.exception]}"
    return at


def _labels(seq):
    return [getattr(x, "label", "") for x in seq]


@teste("1. Abre sem erro e mostra as 9 abas na ordem")
def t_abas():
    at = app()
    labels = [t.label.split(" ", 1)[-1] for t in at.tabs]
    assert labels == ["RPPN", "Imóvel", "Proprietários", "Resp. Técnico", "Perímetro / Mapa",
                      "Documentos", "Revisão", "Processos", "Administrar"], labels


@teste("2. Guia do usuário abre pela rota ?guia=1 (não depende de arquivo estático)")
def t_guia():
    at = app(guia="1")
    assert "Baixar o guia (HTML)" in _labels(at.get("download_button"))
    html = (AQUI / "static" / "guia_usuario.html").read_text(encoding="utf-8")
    for trecho in ("Processos", "Administrar", "Sincronizar", "Harpia", "Gravar alterações", "@cerrados.org"):
        assert trecho in html, f"guia sem o trecho '{trecho}'"
    assert "Londrina" not in html, "guia ainda usa Londrina Solid"


@teste("3. Aba RPPN: campos obrigatórios aparecem e Revisão lista pendências quando vazio")
def t_revisao_vazia():
    at = app()
    assert "Nome da RPPN *" in _labels(at.text_input)
    avisos = " ".join(w.value for w in at.warning)
    assert "Pendências" in avisos or "pendência" in avisos.lower(), "Revisão não listou pendências"


@teste("4. Aba RPPN: preencher nome e área reflete na Revisão")
def t_preencher():
    at = app()
    at.text_input(key="rppn_nome").input("RPPN Teste Fluxo").run()
    at.text_input(key="rppn_area").input("2,5").run()
    assert not at.exception
    avisos = " ".join(w.value for w in at.warning)
    assert "Nome da RPPN" not in avisos, "nome preenchido ainda consta como pendência"


@teste("5. Administrar: painel carrega dados, filtro por órgão e métricas coerentes")
def t_administrar():
    at = app()
    org = [m for m in at.multiselect if m.label == "Órgão"]
    assert org, "filtro Órgão ausente"
    assert set(org[0].value) <= {"ICMBio", "IBRAM"}
    met = {m.label: m.value for m in at.metric}
    assert "RPPNs" in met and int(met["RPPNs"]) > 0, met
    base = json.loads((AQUI / "dados" / "rppns.json").read_text(encoding="utf-8"))
    assert int(met["RPPNs"]) == len(base["rppns"]), "métrica RPPNs difere do arquivo"
    # filtra só IBRAM e confere que a contagem cai
    org[0].set_value(["IBRAM"]).run()
    met2 = {m.label: m.value for m in at.metric}
    n_ibram = sum(1 for r in base["rppns"] if (r.get("orgao") or "ICMBio") == "IBRAM")
    assert int(met2["RPPNs"]) == n_ibram, (met2["RPPNs"], n_ibram)


@teste("6. Administrar: as duas sincronizações estão disponíveis (SIMRPPN e Harpia)")
def t_sync_ui():
    at = app()
    ups = _labels(at.get("file_uploader"))
    assert any("sincroniza" in u.lower() for u in ups), ups
    assert any("harpia" in u.lower() for u in ups), ups


@teste("7. Processos: fichas carregam, métricas e gráficos presentes")
def t_processos():
    at = app()
    met = {m.label: m.value for m in at.metric}
    assert "Processos ativos" in met, met
    sel = [s for s in at.selectbox if s.label == "Ficha do processo"]
    assert sel, "selectbox da ficha ausente"
    assert len(at.checkbox) >= 30, "checklist de tarefas não renderizou"


@teste("8. Processos: marcar uma tarefa deixa alteração pendente e gravar persiste (em cópia)")
def t_processos_gravar():
    # roda numa CÓPIA da pasta dados/ (PLATAFORMA_DADOS_DIR) para não sujar o arquivo real
    import os
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "dados"
        shutil.copytree(AQUI / "dados", tmp)
        os.environ["PLATAFORMA_DADOS_DIR"] = str(tmp)
        try:
            at = AppTest.from_file(str(AQUI / "app.py"), default_timeout=240).run()
        finally:
            os.environ.pop("PLATAFORMA_DADOS_DIR", None)
        assert not at.exception
        antes = json.loads((tmp / "processos.json").read_text(encoding="utf-8"))
        cb = [c for c in at.checkbox if not c.value and c.key and c.key.startswith("tk_")]
        assert cb, "nenhuma tarefa pendente para marcar"
        cb[0].check().run()
        assert any("não gravadas" in w.value for w in at.warning), "aviso de pendência não apareceu"
        btn = [b for b in at.button if b.label == "Gravar alterações"]
        assert btn and not btn[0].disabled, "botão Gravar indisponível"
        os.environ["PLATAFORMA_DADOS_DIR"] = str(tmp)
        try:
            btn[0].click().run()
        finally:
            os.environ.pop("PLATAFORMA_DADOS_DIR", None)
        depois = json.loads((tmp / "processos.json").read_text(encoding="utf-8"))
        real = json.loads((AQUI / "dados" / "processos.json").read_text(encoding="utf-8"))
        assert real == REAL_ANTES, "o teste alterou o arquivo REAL dados/processos.json"
        feitas = lambda d: sum(1 for p in d["processos"] for t in p["tarefas"].values() if t.get("feito"))
        assert feitas(depois) == feitas(antes) + 1, (feitas(antes), feitas(depois))
        assert depois.get("por"), "gravação sem autor"


@teste("9. Sincronização é aditiva (SIMRPPN parcial não apaga nada)")
def t_sync_aditiva():
    import sync_ingest as SI
    base = json.loads((AQUI / "dados" / "rppns.json").read_text(encoding="utf-8"))
    geo = json.loads((AQUI / "dados" / "rppns.geojson").read_text(encoding="utf-8"))
    um = [r for r in base["rppns"] if (r.get("orgao") or "ICMBio") == "ICMBio"][0]
    payload = {"versao": "t", "rppns": [{"rppnid": um["rppnid"], "nome": um["nome"], "uf": um["uf"],
                                          "status": um["status"], "pts_rppn": [], "pts_imovel": []}]}
    novo, gnovo, st = SI.processar(payload, "teste", base, geo)
    assert len(novo["rppns"]) == len(base["rppns"]), "RPPNs sumiram"
    assert len(gnovo["features"]) == len(geo["features"]), "polígonos sumiram"
    assert novo.get("harpia_sincronizado_em") == base.get("harpia_sincronizado_em"), "metadado do Harpia perdido"


if __name__ == "__main__":
    for fn in [t_abas, t_guia, t_revisao_vazia, t_preencher, t_administrar, t_sync_ui,
               t_processos, t_processos_gravar, t_sync_aditiva]:
        fn()
    falhas = 0
    for nome, okk, msg in resultados:
        print(f"[{'OK' if okk else 'FALHA'}] {nome}" + (f" — {msg}" if msg else ""))
        falhas += (not okk)
    print(f"\n{len(resultados) - falhas}/{len(resultados)} fluxos OK")
    sys.exit(1 if falhas else 0)
