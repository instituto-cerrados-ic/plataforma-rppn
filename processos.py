# -*- coding: utf-8 -*-
"""
processos.py — gestão do andamento de cada processo de criação de RPPN.

Segue o documento "Processo de Criação de RPPNs" (IC, vigente a partir de
07/10/2026): 6 passos, cada um com as suas tarefas. Cada processo guarda, por
tarefa, se está feita, quando, por quem e uma observação; e, por passo, a
duração prevista (dias corridos) para estimar quanto falta.

Persistência: dados/processos.json (mesmo caminho da sincronização: commit no
GitHub pelo token dos secrets, ou gravação local em desenvolvimento).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

VERSAO = "1.0"

# (id, título, duração prevista em dias, [(id_tarefa, descrição), ...])
PASSOS = [
    ("1", "Verificar os documentos da propriedade", 15, [
        ("1.1", "Certidão de matrícula e registro do imóvel (no nome do proprietário)"),
        ("1.2", "CCIR atualizado (SNCR/INCRA), conferido com a matrícula"),
        ("1.3", "Certidão Negativa de Débitos de Imóvel Rural (NIRF), conferida"),
        ("1.4", "Retificações/atualizações orientadas ao proprietário (se houve divergência)"),
    ]),
    ("2", "Definir o limite da RPPN", 30, [
        ("2.1", "Análise prévia: imagens de satélite e bases topográficas"),
        ("2.2", "Visita de campo com GPS (quando há recurso)"),
        ("2.3", "Limite definido em consenso com o proprietário (sem áreas agrícolas/construídas)"),
        ("2.4", "ART do georreferenciamento emitida no portal CREA-DF"),
        ("2.5", "Boleto da ART enviado ao Financeiro (administracao@cerrados.org)"),
    ]),
    ("3", "Montar o processo (PDF único)", 30, [
        ("3.1", "Requerimento de criação assinado por todos os proprietários"),
        ("3.2", "Mapa com polígonos e vértices da RPPN e do imóvel"),
        ("3.3", "Identidade autenticada / CNH digital dos proprietários (e atos constitutivos, se PJ)"),
        ("3.4", "Procuração autenticada (quando há representante)"),
        ("3.5", "Certidão de matrícula dentro da validade"),
        ("3.6", "CCIR"),
        ("3.7", "Certidão Negativa de Débitos de Imóvel Rural"),
        ("3.8", "ART do georreferenciamento do imóvel"),
        ("3.9", "ART do georreferenciamento da RPPN"),
        ("3.10", "Memorial descritivo do imóvel assinado pelo responsável técnico"),
        ("3.11", "Memorial descritivo da RPPN assinado pelo responsável técnico"),
        ("3.12", "Termo de compromisso assinado pelo proprietário/representante"),
        ("3.13", "PDF único montado e conferido (PDF24)"),
    ]),
    ("4", "Preencher o requerimento do SIMRPPN", 10, [
        ("4.1", "Requerimento aberto no SIMRPPN (dados do imóvel, proprietário e RPPN)"),
        ("4.2", "Memorial descritivo do imóvel gerado (Excel padronizado)"),
        ("4.3", "Memorial descritivo da RPPN gerado (Excel padronizado)"),
        ("4.4", "Requerimento finalizado no SIMRPPN"),
        ("4.5", "E-mail ao ICMBio com o PDF e o Termo de Compromisso (Word)"),
    ]),
    ("5", "Acompanhar o processo no ICMBio", 180, [
        ("5.1", "Análise técnica concluída"),
        ("5.2", "Consulta pública realizada"),
        ("5.3", "Vistoria técnica realizada"),
        ("5.4", "Certidão de ônus reais e cadeia dominial enviadas (docs 13 e 14)"),
        ("5.5", "Análise jurídica concluída"),
    ]),
    ("6", "Solicitar a averbação da RPPN", 60, [
        ("6.1", "Ofício e Termo de Compromisso recebidos do ICMBio"),
        ("6.2", "Orientações e documentos repassados ao proprietário/procurador"),
        ("6.3", "Certidão de averbação e termo autenticado recebidos"),
        ("6.4", "Documentos enviados à DIMAN (assessoriadiman@icmbio.gov.br)"),
        ("6.5", "Portaria de criação publicada no DOU"),
        ("6.6", "Comunicação acionada para divulgação"),
        ("6.7", "Ressarcimento de custos cartoriais encaminhado (se o projeto prevê)"),
    ]),
]
DURACAO_PADRAO = {p[0]: p[2] for p in PASSOS}
FMT = "%d/%m/%Y"

# Roteiro DISTRITAL (IBRAM/DF, sistema Harpia) — RASCUNHO baseado na IN IBRAM
# nº 18/2020 e no que o formulário do Harpia pede; a equipe valida e ajusta.
PASSOS_IBRAM = [
    ("1", "Verificar os documentos da propriedade", 15, PASSOS[0][3]),
    ("2", "Definir o limite da RPPN", 30, PASSOS[1][3]),
    ("3", "Montar o processo (documentos da IN IBRAM 18/2020)", 30, [
        ("3.1", "Requerimento de criação assinado pelo proprietário/representante"),
        ("3.2", "Mapa e arquivos vetoriais (shapefile) do imóvel e da RPPN"),
        ("3.3", "Documentos pessoais / atos constitutivos (se PJ) e procuração (se representante)"),
        ("3.4", "Certidão de matrícula dentro da validade"),
        ("3.5", "CCIR e Certidão Negativa de Débitos de Imóvel Rural"),
        ("3.6", "ART do georreferenciamento e memoriais descritivos assinados"),
        ("3.7", "Termo de compromisso / termo de parceria assinado"),
    ]),
    ("4", "Protocolar no Harpia (IBRAM)", 10, [
        ("4.1", "Proprietário/representante cadastrado como usuário externo no SEI-GDF"),
        ("4.2", "Requerimento preenchido no Harpia (interessado, propriedade, RPPN, shapefile)"),
        ("4.3", "Solicitação enviada — protocolo gerado"),
        ("4.4", "Documentos assinados no SEI pelo proprietário/representante"),
    ]),
    ("5", "Acompanhar o processo no IBRAM", 180, [
        ("5.1", "Análise técnica (SUCON) concluída"),
        ("5.2", "Vistoria técnica realizada"),
        ("5.3", "Exigências/diligências do IBRAM atendidas"),
        ("5.4", "Parecer técnico favorável emitido"),
        ("5.5", "Análise jurídica (Procuradoria) concluída"),
    ]),
    ("6", "Criação e averbação da RPPN", 60, [
        ("6.1", "Portaria/decreto de criação publicado no DODF"),
        ("6.2", "Termo de compromisso assinado e registrado"),
        ("6.3", "Averbação à margem da matrícula feita (certidão recebida)"),
        ("6.4", "Certidão de averbação enviada ao IBRAM"),
        ("6.5", "Comunicação acionada para divulgação"),
    ]),
]
ROTEIROS = {"ICMBio": PASSOS, "IBRAM": PASSOS_IBRAM}


def passos_de(p: dict) -> list:
    """Roteiro do processo conforme o órgão (ICMBio = federal, IBRAM = distrital)."""
    return ROTEIROS.get(p.get("orgao") or "ICMBio", PASSOS)


# ----------------------------------------------------------------- modelo
def novo_processo(nome: str, uf: str = "", municipio: str = "", rppnid=None,
                  proprietario: str = "", responsavel: str = "", inicio: str = "",
                  orgao: str = "ICMBio") -> dict:
    roteiro = ROTEIROS.get(orgao, PASSOS)
    return {"id": f"p{int(datetime.now().timestamp() * 1000)}", "nome": nome, "uf": uf,
            "municipio": municipio, "rppnid": rppnid, "proprietario": proprietario,
            "responsavel": responsavel, "orgao": orgao,   # ICMBio (federal) | IBRAM (distrital)
            "inicio": inicio or date.today().strftime(FMT),
            "situacao": "ativo",                   # ativo | concluído | arquivado
            "duracoes": {x[0]: x[2] for x in roteiro},   # dias previstos por passo (editável)
            "tarefas": {},                          # id_tarefa -> {feito, data, por, obs}
            "notas": ""}


def carregar(arq: Path) -> dict:
    if arq.exists():
        return json.load(open(arq, encoding="utf-8"))
    return {"versao": VERSAO, "atualizado_em": "", "por": "", "processos": []}


def serializar(base: dict, por: str = "") -> str:
    base = dict(base)
    base["versao"] = VERSAO
    base["atualizado_em"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    base["por"] = por
    return json.dumps(base, ensure_ascii=False, indent=1)


def gravar_local(arq: Path, base: dict, por: str = ""):
    arq.parent.mkdir(exist_ok=True)
    arq.write_text(serializar(base, por), encoding="utf-8")


# -------------------------------------------------------------- situação
def resumo(p: dict) -> dict:
    """Progresso do processo: % por passo, fase atual, o que falta e previsão."""
    t = p.get("tarefas", {})
    passos, fase, concl_tot, n_tot = [], None, 0, 0
    for pid, titulo, _d, tarefas in passos_de(p):
        feitas = sum(1 for tid, _ in tarefas if t.get(tid, {}).get("feito"))
        n = len(tarefas)
        concl_tot += feitas
        n_tot += n
        pend = [desc for tid, desc in tarefas if not t.get(tid, {}).get("feito")]
        passos.append({"id": pid, "titulo": titulo, "feitas": feitas, "n": n,
                       "pct": round(100 * feitas / n), "pendentes": pend,
                       "dias": int(p.get("duracoes", {}).get(pid, DURACAO_PADRAO[pid]))})
        if fase is None and feitas < n:
            fase = pid
    if fase is None:
        fase = "6"
    completude = round(100 * concl_tot / n_tot) if n_tot else 0
    # dias que faltam: proporcional no passo atual + passos inteiros seguintes
    dias_rest = 0.0
    for ps in passos:
        if ps["id"] < fase:
            continue
        frac = 1 - ps["feitas"] / ps["n"] if ps["n"] else 0
        dias_rest += ps["dias"] * frac
    dias_rest = int(round(dias_rest))
    # último registro de data concluída (para "parado há X dias")
    datas = []
    for v in t.values():
        if v.get("feito") and v.get("data"):
            try:
                datas.append(datetime.strptime(v["data"], FMT).date())
            except ValueError:
                pass
    ultimo = max(datas) if datas else None
    try:
        ini = datetime.strptime(p.get("inicio", ""), FMT).date()
    except ValueError:
        ini = None
    return {"passos": passos, "fase": fase,
            "fase_titulo": next(ps["titulo"] for ps in passos if ps["id"] == fase),
            "completude": completude, "concluidas": concl_tot, "total": n_tot,
            "dias_restantes": dias_rest,
            "previsao": (date.today() + timedelta(days=dias_rest)).strftime(FMT),
            "ultimo_registro": ultimo.strftime(FMT) if ultimo else "",
            "parado_ha": (date.today() - ultimo).days if ultimo else None,
            "dias_decorridos": (date.today() - ini).days if ini else None,
            "proximas": next((ps["pendentes"] for ps in passos if ps["id"] == fase), [])}


def a_partir_do_simrppn(rppns: list[dict], existentes: list[dict]) -> list[dict]:
    """Sugere processos para RPPNs 'em trâmite/cadastro' do SIMRPPN que ainda não
    têm ficha de processo (vinculadas pelo rppnid)."""
    ids = {p.get("rppnid") for p in existentes if p.get("rppnid")}
    out = []
    for r in rppns:
        if r.get("status") in ("em trâmite", "em cadastro") and r.get("rppnid") not in ids:
            orgao = r.get("orgao") or "ICMBio"
            sistema = "Harpia" if orgao == "IBRAM" else "SIMRPPN"
            p = novo_processo(r.get("nome", ""), r.get("uf", ""), r.get("municipio", ""),
                              r.get("rppnid"), r.get("proprietario", ""),
                              inicio=r.get("data_cadastro") or "", orgao=orgao)
            # já está no sistema do órgão: passos 1 a 3 e a abertura presumidos feitos — a equipe confere
            for pid, _t, _d, tarefas in passos_de(p)[:3]:
                for tid, _ in tarefas:
                    p["tarefas"][tid] = {"feito": True, "data": r.get("data_cadastro") or "",
                                         "por": f"{sistema} (presumido)", "obs": ""}
            if orgao == "IBRAM":
                for tid in ("4.2", "4.3"):
                    p["tarefas"][tid] = {"feito": True, "data": r.get("data_cadastro") or "",
                                         "por": sistema, "obs": f"protocolo {r.get('protocolo', '')}"}
            else:
                p["tarefas"]["4.1"] = {"feito": True, "data": r.get("data_cadastro") or "",
                                       "por": sistema, "obs": ""}
                if r.get("status") == "em trâmite":
                    p["tarefas"]["4.4"] = {"feito": True, "data": r.get("data_cadastro") or "",
                                           "por": sistema, "obs": ""}
            out.append(p)
    return out
