# Plataforma RPPN — Instituto Cerrados / Programa Jurema

Aplicativo Streamlit para preparar o requerimento de uma RPPN (Reserva Particular
do Patrimônio Natural) sem entrar no SIMRPPN: dados cadastrais, perímetro
georreferenciado (desenho no mapa, arquivo ou tabela de vértices, com aderência
de vértices e validação topológica), mapa técnico no padrão Jurema/IC, documentos
e um painel de administração das RPPNs.

## Rodar localmente
```
pip install -r requirements.txt
streamlit run app.py
```

## Estrutura
- `app.py` — aplicativo (7 abas + Administrar)
- `geo_utils.py` — leitura/validação de geometria, tabela de vértices, aderência
- `gerar_coordenadas.py` — polígono → Excel PONTO,X,Y em UTM SIRGAS 2000
- `mapa_tecnico.py` — layout do mapa técnico (satélite, grid, memorial, contexto)
- `gerar_guia.py` / `static/guia_usuario.html` — Guia do Usuário
- `coletar_rppns.py` — coletor (local) dos dados das RPPNs do SIMRPPN
- `assets/` — logos e malhas (IBGE)

## Notas de deploy (Streamlit Community Cloud)
- `requirements.txt` com `numpy` pinado (evita segfault em rebuild).
- `.streamlit/config.toml` sem porta fixa; `enableStaticServing` ligado (Guia).
- `dados/` (dados das RPPNs, com nomes de proprietários) fica FORA do repositório
  enquanto o app é público; entra na Fase 2 junto com o login.

Instituto Cerrados · Programa Jurema — Proteção do Cerrado.
