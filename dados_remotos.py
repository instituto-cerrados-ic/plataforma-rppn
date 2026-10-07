# -*- coding: utf-8 -*-
"""
dados_remotos.py — os dados da plataforma (RPPNs, polígonos, processos) moram
num repositório PRIVADO do GitHub (instituto-cerrados-ic/plataforma-rppn-dados),
lidos e gravados em tempo de execução pela API de conteúdo, com o token de
escopo mínimo dos Secrets. O código fica público; os dados, não.

Sem token (desenvolvimento local) tudo cai na pasta dados/ ao lado do app.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import requests
import streamlit as st

REPO_PADRAO = "instituto-cerrados-ic/plataforma-rppn-dados"
API = "https://api.github.com/repos/{repo}/contents/{caminho}"
DADOS_LOCAL = Path(__file__).resolve().parent / "dados"


def _cfg() -> dict | None:
    """Bloco [github] dos secrets, ou None quando não há token (modo local)."""
    try:
        gh = st.secrets["github"] if "github" in st.secrets else None
    except Exception:
        gh = None
    if not gh or not gh.get("token"):
        return None
    return {"token": gh["token"], "repo": gh.get("repo_dados", REPO_PADRAO),
            "branch": gh.get("branch", "main")}


def remoto() -> bool:
    return _cfg() is not None


def origem() -> str:
    c = _cfg()
    return f"GitHub privado ({c['repo']})" if c else "pasta local dados/"


def _headers(token):
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


@st.cache_data(ttl=120, show_spinner=False)
def _ler_remoto(repo: str, branch: str, nome: str, token: str):
    r = requests.get(API.format(repo=repo, caminho=nome), headers=_headers(token),
                     params={"ref": branch}, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    j = r.json()
    if j.get("encoding") == "base64" and j.get("content"):
        return json.loads(base64.b64decode(j["content"]).decode("utf-8"))
    # arquivos > 1 MB vêm sem conteúdo inline: baixa pelo download_url
    r2 = requests.get(j["download_url"], headers=_headers(token), timeout=60)
    r2.raise_for_status()
    return r2.json()


def carregar(nome: str):
    """Lê `nome` (ex.: 'rppns.json') -> objeto JSON, ou None se não existe."""
    c = _cfg()
    if c:
        return _ler_remoto(c["repo"], c["branch"], nome, c["token"])
    arq = DADOS_LOCAL / nome
    return json.load(open(arq, encoding="utf-8")) if arq.exists() else None


def gravar(arquivos: dict[str, str], mensagem: str) -> str:
    """Grava {nome: conteúdo_texto}. -> descrição de onde foi gravado.
    Levanta RuntimeError se a API do GitHub recusar."""
    c = _cfg()
    if not c:
        DADOS_LOCAL.mkdir(exist_ok=True)
        for nome, conteudo in arquivos.items():
            (DADOS_LOCAL / nome).write_text(conteudo, encoding="utf-8")
        return "gravado na pasta local dados/ (sem token do GitHub)"
    h = _headers(c["token"])
    for nome, conteudo in arquivos.items():
        url = API.format(repo=c["repo"], caminho=nome)
        r = requests.get(url, headers=h, params={"ref": c["branch"]}, timeout=30)
        sha = r.json().get("sha") if r.status_code == 200 else None
        if r.status_code not in (200, 404):
            raise RuntimeError(f"GitHub GET {nome}: HTTP {r.status_code} — {r.text[:200]}")
        body = {"message": mensagem, "branch": c["branch"],
                "content": base64.b64encode(conteudo.encode("utf-8")).decode()}
        if sha:
            body["sha"] = sha
        r = requests.put(url, headers=h, json=body, timeout=60)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"GitHub PUT {nome}: HTTP {r.status_code} — {r.text[:300]}")
    _ler_remoto.clear()          # próxima leitura já vê o que acabou de gravar
    return f"gravado em {c['repo']} (a tela já mostra os dados novos)"
