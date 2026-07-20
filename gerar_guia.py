# -*- coding: utf-8 -*-
"""Gera o Guia do Usuário (HTML autocontido, identidade Jurema/IC)."""
import base64
import io
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parent / "assets"
VERDE, BEGE, MAGENTA, MARROM = "#004F23", "#DDCCA4", "#E00080", "#603010"


def logo_b64(nome, largura):
    """Logo redimensionado e BEM comprimido (jpeg q70 / png quantizado)."""
    img = Image.open(ASSETS / nome)
    r = largura / img.width
    img = img.resize((largura, int(img.height * r)))
    buf = io.BytesIO()
    if nome.endswith(".png"):
        img = img.convert("RGBA").quantize(colors=64)   # paleta reduzida
        img.save(buf, "PNG", optimize=True)
    else:
        img.convert("RGB").save(buf, "JPEG", quality=70, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


IC = logo_b64("logo_ic_dark.jpg", 200)
JU = logo_b64("logo_jurema_transparente.png", 150)

HTML = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Guia do Usuário — Plataforma RPPN · Instituto Cerrados / Programa Jurema</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Londrina+Solid:wght@400&family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  :root {{ --verde:{VERDE}; --bege:{BEGE}; --magenta:{MAGENTA}; --marrom:{MARROM}; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:'Montserrat',sans-serif; color:#1a1a1a; margin:0;
         background:#F5F0E3; }}
  .pagina {{ max-width:794px; margin:0 auto; background:#fff; padding:0 0 40px; }}
  header {{ background:var(--verde); color:#fff; padding:28px 36px;
            border-bottom:6px solid var(--magenta); display:flex; gap:20px;
            align-items:center; }}
  header .chip {{ background:#fff; border-radius:12px; padding:8px 10px; }}
  h1 {{ font-family:'Londrina Solid',cursive; font-weight:400; font-size:2rem;
        margin:0; letter-spacing:.5px; }}
  header p {{ margin:4px 0 0; opacity:.92; font-size:.9rem; }}
  main {{ padding:28px 36px; }}
  h2 {{ font-family:'Londrina Solid',cursive; font-weight:400; color:var(--verde);
        font-size:1.5rem; border-bottom:3px solid var(--bege); padding-bottom:4px;
        margin:30px 0 12px; }}
  h3 {{ color:var(--verde); font-size:1.02rem; margin:18px 0 6px; }}
  p, li {{ font-size:.92rem; line-height:1.55; text-align:left; text-indent:0; }}
  .destaque {{ background:#F5F0E3; border-left:5px solid var(--magenta);
               padding:10px 16px; border-radius:6px; margin:10px 0; }}
  .passo {{ display:flex; gap:12px; margin:10px 0; align-items:flex-start; }}
  .passo .n {{ background:var(--verde); color:#fff; font-weight:700; min-width:26px;
               height:26px; border-radius:50%; display:flex; align-items:center;
               justify-content:center; font-size:.85rem; margin-top:2px; }}
  table {{ border-collapse:collapse; width:100%; margin:10px 0; font-size:.88rem; }}
  th {{ background:var(--verde); color:#fff; padding:7px 10px; text-align:left; }}
  td {{ border:1px solid #d9d2bd; padding:6px 10px; vertical-align:top; }}
  tr:nth-child(even) td {{ background:#FAF7EE; }}
  .tag {{ display:inline-block; background:var(--bege); color:#1a1a1a;
          border-radius:10px; padding:1px 10px; font-size:.8rem; font-weight:600; }}
  .acento {{ color:var(--magenta); font-weight:700; }}
  footer {{ background:var(--verde); color:#fff; text-align:center; padding:14px;
            font-size:.8rem; margin-top:34px; }}
  code {{ background:#EFE9D8; padding:1px 6px; border-radius:4px; font-size:.85rem; }}
</style>
</head>
<body>
<div class="pagina">
<header>
  <img src="data:image/jpeg;base64,{IC}" alt="Instituto Cerrados" style="height:64px;border-radius:8px;background:#fff;padding:4px;">
  <div style="flex:1">
    <h1>Guia do Usuário — Plataforma RPPN</h1>
    <p>Programa Jurema · Proteção do Cerrado — Instituto Cerrados</p>
  </div>
  <span class="chip"><img src="data:image/png;base64,{JU}" alt="Jurema" style="height:70px;"></span>
</header>
<main>

<h2>1. O que é a Plataforma RPPN</h2>
<p>A Plataforma RPPN permite que você prepare <b>todo o requerimento da sua Reserva
Particular do Patrimônio Natural</b> — dados cadastrais, perímetro georreferenciado,
mapa técnico e documentos — <b>sem precisar navegar pelo SIMRPPN</b> (o sistema do
ICMBio). Ao final, a plataforma organiza tudo no formato que o SIMRPPN exige.</p>
<div class="destaque">O preenchimento segue as mesmas 7 etapas do SIMRPPN, mas com
ajuda automática: correção de tabelas de coordenadas, validação do perímetro,
aderência de vértices (snapping) e geração do mapa técnico no padrão do Programa
Jurema.</div>

<h2>2. As abas, na ordem</h2>
<table>
<tr><th>Aba</th><th>O que preencher</th></tr>
<tr><td><b>RPPN</b></td><td>Nome da RPPN, área proposta (ha), UF e município.</td></tr>
<tr><td><b>Imóvel</b></td><td>Dados do(s) imóvel(is): nome, áreas, matrícula, endereço,
tipo (rural/urbano), CCIR e código do CAR. Use “Adicionar imóvel” se a RPPN abranger
mais de um.</td></tr>
<tr><td><b>Proprietários</b></td><td>Nome, CPF/CNPJ e contatos de cada proprietário.</td></tr>
<tr><td><b>Resp. Técnico</b></td><td>Profissional habilitado que elaborou as peças
cartográficas: nome, CPF, CREA, título, nº da ART paga e contatos.
<span class="acento">Obrigatório para o memorial descritivo.</span></td></tr>
<tr><td><b>Perímetro / Mapa</b></td><td>O coração da plataforma — ver seções 3 a 6.</td></tr>
<tr><td><b>Documentos</b></td><td>PDFs das certidões e documentos exigidos (seção 7).</td></tr>
<tr><td><b>Revisão</b></td><td>Checagem final de pendências antes do envio.</td></tr>
</table>

<h2>3. Perímetro — as 3 formas de informar</h2>
<div class="destaque"><b>Sempre comece pelo Imóvel (a propriedade).</b> A opção RPPN
só é liberada depois — é ela que permite validar se a RPPN está dentro do imóvel.</div>

<h3>A) Desenhar no mapa</h3>
<div class="passo"><span class="n">1</span><p>Na barra do canto superior esquerdo do
mapa, clique no ícone de <b>polígono</b>.</p></div>
<div class="passo"><span class="n">2</span><p>Clique no mapa para marcar cada
<b>vértice</b> do limite, sobre a imagem de satélite. Feche clicando no primeiro
vértice.</p></div>
<div class="passo"><span class="n">3</span><p>Clique em <b>“Usar polígono desenhado”</b>,
logo abaixo do mapa.</p></div>
<p>Dica: ative <b>“Sobrepor limite do CAR”</b> para digitalizar por cima do limite do
CAR — ajuda muito na conferência.</p>

<h3>B) Enviar arquivo geográfico</h3>
<p>Formatos aceitos: <b>shapefile</b> (envie um <code>.zip</code> com
<code>.shp .shx .dbf .prj</code>), <b>KML</b>, <b>GeoPackage</b> ou <b>GeoJSON</b>,
com um polígono por perímetro. Clique em “Processar arquivo”.</p>

<h3>C) Enviar tabela de vértices (CSV/Excel)</h3>
<p>A plataforma <b>corrige sozinha</b> os erros mais comuns e avisa o que corrigiu:</p>
<table>
<tr><th>Erro na tabela</th><th>Correção automática</th></tr>
<tr><td>Colunas com nomes diferentes (X, E, Este, Longitude…)</td><td>Reconhece por sinônimos</td></tr>
<tr><td>Colunas X/Y trocadas</td><td>Detecta e inverte</td></tr>
<tr><td>Vírgula decimal e separador de milhar</td><td>Converte</td></tr>
<tr><td>Coordenadas geográficas (lat/long)</td><td>Converte para UTM SIRGAS 2000, zona automática</td></tr>
</table>
<p>Se a tabela já estiver em UTM, informe a <b>zona</b> (ex.: 23S).</p>

<h2>4. Ferramentas do mapa — botão por botão</h2>
<p>A barra de ferramentas fica no <b>canto superior esquerdo</b> do mapa (abaixo do
zoom). Ela vale tanto para o polígono do <b>Imóvel</b> quanto para o da <b>RPPN</b> —
o que muda é o alvo selecionado em “Este perímetro é do:”.</p>

<h3>4.1 Desenhar um limite novo</h3>
<table>
<tr><th>Botão / ação</th><th>O que faz</th></tr>
<tr><td><b>Desenhar o limite</b> (ícone de polígono)</td><td>Inicia um polígono novo. Cada
clique no mapa marca um <b>vértice</b>; a área parcial aparece junto ao cursor.
Para fechar, clique sobre o <b>primeiro vértice</b>.</td></tr>
<tr><td><b>Concluir</b></td><td>Fecha o polígono usando os vértices já marcados
(alternativa a clicar no primeiro vértice).</td></tr>
<tr><td><b>Apagar último ponto</b></td><td>Desfaz o <b>último vértice</b> clicado —
use quando errar um clique, sem perder o resto do desenho.</td></tr>
<tr><td><b>Cancelar</b></td><td>Abandona o desenho em andamento (nada é salvo).</td></tr>
</table>

<h3>4.2 Editar um limite existente (arrastar vértices)</h3>
<table>
<tr><th>Botão / ação</th><th>O que faz</th></tr>
<tr><td><b>Editar polígono</b> (ícone de lápis)</td><td>Entra no modo de edição: surgem
<b>alças brancas</b> em cada vértice. Se o limite do alvo já foi definido antes, ele
aparece no mapa <b>pronto para editar</b>.</td></tr>
<tr><td><b>Alças brancas (quadradinhos)</b></td><td><b>Arraste</b> para mover o
vértice.</td></tr>
<tr><td><b>Alças translúcidas (entre vértices)</b></td><td>Arraste para <b>criar um
vértice novo</b> no meio do segmento — útil para detalhar um trecho.</td></tr>
<tr><td><b>Salvar</b></td><td>Confirma as alterações da edição (na barra do
mapa).</td></tr>
<tr><td><b>Cancelar</b></td><td>Descarta as alterações e volta ao limite
anterior.</td></tr>
</table>

<h3>4.3 Apagar</h3>
<table>
<tr><th>Botão / ação</th><th>O que faz</th></tr>
<tr><td><b>Apagar polígono</b> (ícone de lixeira)</td><td>Entra no modo de exclusão: <b>clique no
polígono</b> que deseja remover e confirme em “Salvar”.</td></tr>
<tr><td><b>Apagar tudo</b></td><td>Remove todos os polígonos desenhados no
mapa.</td></tr>
</table>

<h3>4.4 Outros controles do mapa</h3>
<table>
<tr><th>Controle</th><th>O que faz</th></tr>
<tr><td><b>+ / −</b> (canto sup. esquerdo)</td><td>Zoom. Você também pode usar a
rolagem do mouse.</td></tr>
<tr><td><b>Camadas</b> (canto sup. direito)</td><td>Alterna o fundo entre
<b>Satélite</b> (padrão) e <b>Mapa (ruas)</b>, e liga/desliga as camadas
(Imóvel, RPPN, CAR).</td></tr>
<tr><td><b>Escala</b> (canto inferior)</td><td>Escala gráfica de referência do
mapa.</td></tr>
</table>

<div class="destaque"><b>Passo final obrigatório:</b> depois de desenhar <i>ou</i>
editar, clique em <b>“Usar polígono desenhado como Imóvel/RPPN”</b>, logo abaixo do
mapa — é ele que grava o limite na plataforma (e dispara a aderência automática).
Sem esse clique, o desenho fica só na tela.</div>

<h2>5. Aderência de vértices (snapping)</h2>
<p>Como no ArcGIS: vértices próximos “grudam” na geometria de referência —
a <b>RPPN adere ao imóvel</b> e o <b>imóvel adere ao CAR</b> (se carregado).
Evita frestas e sobreposições.</p>
<div class="passo"><span class="n">1</span><p>Deixe o botão <b>“Aderência
(snapping)”</b> ligado e ajuste a <b>tolerância</b>: desenho à mão, use
<b>15–50&nbsp;m</b>; arquivo técnico, <b>1–5&nbsp;m</b>.</p></div>
<div class="passo"><span class="n">2</span><p>Ao concluir um limite, a aderência roda
<b>sozinha</b> e mostra quantos vértices colaram.</p></div>
<div class="passo"><span class="n">3</span><p>Se aparecer “nenhum vértice a até X m”,
<b>aumente a tolerância</b> e clique em <b>“Aplicar aderência agora”</b>.</p></div>

<h2>6. Validação e Mapa técnico</h2>
<p>Com imóvel e RPPN definidos, a plataforma valida: a <b>RPPN precisa estar contida
no imóvel</b> (pode compartilhar trechos de limite). Se parte dela ficar de fora, o
envio é bloqueado e a plataforma informa o percentual fora.</p>
<p>Depois, clique em <span class="tag">Fazer mapa</span>. O mapa técnico sai no padrão
oficial do Programa Jurema: imagem de satélite, grid UTM (SIRGAS 2000), norte, escala
gráfica e absoluta, tabela de vértices (memorial), mapa de contexto na escala do
município, identificação (denominação, proprietário, áreas, responsável técnico),
legenda e datum. Baixe o PNG e os <b>Excel de coordenadas</b> prontos para o SIMRPPN.</p>

<h2>7. Documentos exigidos</h2>
<table>
<tr><th>Documento</th><th>Observação</th></tr>
<tr><td>Cédula de identidade do(s) proprietário(s)</td><td>ou representante legal</td></tr>
<tr><td>Certidão Negativa de Débitos (ITR)</td><td></td></tr>
<tr><td>CCIR</td><td>Certificado de Cadastro do Imóvel Rural</td></tr>
<tr><td>Certidão de Matrícula e Registro</td><td>atualizada</td></tr>
<tr><td>Cadeia Dominial Trintenária</td><td>pode ser a própria matrícula, se contiver</td></tr>
<tr><td>Certidão de ônus reais</td><td>e ações reipersecutórias</td></tr>
<tr><td>ART devidamente paga</td><td>do responsável técnico</td></tr>
<tr><td>Termo de Compromisso assinado</td><td></td></tr>
</table>
<p>As <b>plantas e memoriais descritivos</b> são gerados pelo próprio SIMRPPN a partir
das coordenadas — a plataforma prepara os arquivos de coordenadas para isso.</p>

<h2>8. Perguntas frequentes</h2>
<table>
<tr><th>Situação</th><th>O que fazer</th></tr>
<tr><td>“A opção RPPN não aparece”</td><td>Defina primeiro o perímetro do Imóvel.</td></tr>
<tr><td>“O snapping não moveu nada”</td><td>Aumente a tolerância e clique em “Aplicar
aderência agora”. Desenho à mão costuma pedir 15–50 m.</td></tr>
<tr><td>“A RPPN está fora do imóvel”</td><td>Edite o polígono (seção 4) ou use a
aderência com tolerância maior; a validação precisa ficar verde.</td></tr>
<tr><td>“Minha tabela foi lida errado”</td><td>Confira o aviso de correções aplicadas;
se a zona UTM estiver errada, informe-a manualmente (ex.: 22S).</td></tr>
<tr><td>“O mapa demora a gerar”</td><td>É normal: a plataforma baixa a imagem de
satélite e o limite municipal do IBGE. Acompanhe a animação.</td></tr>
</table>

<h2>9. Envio ao SIMRPPN</h2>
<p>Na fase atual, a plataforma prepara e valida tudo. O <b>envio automático ao
SIMRPPN</b> (com login gov.br) entra na fase 2 — você fará apenas a revisão final e o
clique de “Finalizar requerimento” no próprio SIMRPPN, que é pessoal e
irreversível.</p>

</main>
<footer>Instituto Cerrados · Programa Jurema — Proteção do Cerrado ·
Plataforma RPPN — Guia do Usuário (v1, julho/2026)</footer>
</div>
</body>
</html>
"""

out = Path(__file__).resolve().parent / "guia_usuario.html"
out.write_text(HTML, encoding="utf-8")
print(f"[ok] {out}  ({out.stat().st_size/1024:.0f} KB)")
