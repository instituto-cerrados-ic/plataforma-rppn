/*
 * Coletor de RPPNs — roda DENTRO da aba do SIMRPPN, no navegador da própria
 * pessoa (favorito/bookmarklet). Usa a sessão que ela mesma abriu; nada de
 * senha ou sessão sai do navegador. Nenhuma página é navegada à vista: as
 * leituras são requisições em segundo plano e um iframe invisível (para a
 * tela do editor, que monta as coordenadas por script). O que a pessoa vê é
 * só um painel com barra de progresso.
 *
 * Saída: baixa o arquivo sincronizacao_rppns_<data>.json, que a plataforma
 * (aba Administrar → Sincronizar) transforma em dados + polígonos e publica.
 *
 * Este arquivo é a FONTE legível. O app embute uma versão compactada dele no
 * favorito "Coletar RPPNs". VERSAO abaixo aparece no painel e no arquivo.
 */
(function () {
  var VERSAO = "1.0";
  var BASE = "https://simrppn.sisicmbio.icmbio.gov.br";

  if (location.hostname.indexOf("simrppn") === -1) {
    alert("Abra primeiro o SIMRPPN (Painel de Gestão) e clique no favorito lá.");
    return;
  }
  if (window.__icSync) { alert("A sincronização já está em andamento."); return; }
  window.__icSync = true;

  /* ---------- painel de progresso ---------- */
  var ov = document.createElement("div");
  ov.setAttribute("style", "position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:2147483647;" +
    "display:flex;align-items:center;justify-content:center;font-family:Montserrat,Segoe UI,Arial,sans-serif");
  ov.innerHTML =
    '<div style="background:#fff;border-radius:14px;padding:26px 30px;width:min(520px,92vw);' +
    'box-shadow:0 20px 60px rgba(0,0,0,.35);border-top:6px solid #004F23">' +
    '<div style="font-size:1.25rem;font-weight:700;color:#004F23;margin-bottom:4px">Sincronizando RPPNs</div>' +
    '<div style="font-size:.8rem;color:#666;margin-bottom:16px">Instituto Cerrados · Programa Jurema · coletor v' + VERSAO + '</div>' +
    '<div id="ic-s-txt" style="font-size:.95rem;color:#1a1a1a;min-height:1.4em">Preparando…</div>' +
    '<div style="background:#eee;border-radius:8px;height:14px;margin:12px 0 6px;overflow:hidden">' +
    '<div id="ic-s-bar" style="height:100%;width:0%;background:linear-gradient(90deg,#004F23,#2E8B57);transition:width .3s"></div></div>' +
    '<div id="ic-s-sub" style="font-size:.8rem;color:#666;min-height:1.2em"></div>' +
    '<div style="margin-top:16px;display:flex;gap:10px;justify-content:flex-end">' +
    '<button id="ic-s-cancel" style="padding:8px 14px;border:1px solid #bbb;background:#fff;border-radius:8px;cursor:pointer">Cancelar</button>' +
    '<button id="ic-s-close" style="display:none;padding:8px 14px;border:0;background:#004F23;color:#fff;border-radius:8px;cursor:pointer">Fechar</button>' +
    "</div></div>";
  document.body.appendChild(ov);
  var elTxt = document.getElementById("ic-s-txt"), elBar = document.getElementById("ic-s-bar"),
      elSub = document.getElementById("ic-s-sub");
  var cancelado = false;
  document.getElementById("ic-s-cancel").onclick = function () { cancelado = true; };
  document.getElementById("ic-s-close").onclick = function () { ov.remove(); window.__icSync = false; };
  function status(t, s) { elTxt.textContent = t; elSub.textContent = s || ""; }
  function barra(i, n) { elBar.style.width = Math.round(100 * i / n) + "%"; }
  function terminar(msg, sub) {
    status(msg, sub); elBar.style.width = "100%";
    document.getElementById("ic-s-cancel").style.display = "none";
    document.getElementById("ic-s-close").style.display = "inline-block";
  }

  /* ---------- utilidades ---------- */
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function fetchDoc(url) {
    return fetch(url, { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status + " em " + url);
      return r.text();
    }).then(function (h) { return new DOMParser().parseFromString(h, "text/html"); });
  }
  function T(el) { return el ? (el.textContent || "").replace(/\s+/g, " ").trim() : ""; }
  function vals(doc, sel) {
    return Array.prototype.map.call(doc.querySelectorAll(sel), function (i) { return i.value; })
      .filter(function (v) { return v && v.trim(); });
  }
  function dataPerto(doc, rotulo) { // menor elemento que contém o rótulo e uma data dd/mm/aaaa
    var best = null, len = 1e9;
    Array.prototype.forEach.call(doc.querySelectorAll("main *"), function (el) {
      var t = el.textContent || "";
      if (t.indexOf(rotulo) !== -1) {
        var m = t.match(/(\d{2}\/\d{2}\/\d{4})/);
        if (m && t.length < len) { best = m[1]; len = t.length; }
      }
    });
    return best || "";
  }

  /* ---------- leitura das telas ---------- */
  function lerPainel(doc) {
    var out = [], vistos = {};
    Array.prototype.forEach.call(doc.querySelectorAll("table tr"), function (tr) {
      var tds = tr.querySelectorAll("td"); if (!tds.length) return;
      var a = tr.querySelector("a[href*='rppnid=']"); if (!a) return;
      var m = a.getAttribute("href").match(/rppnid=(\d+)/); if (!m) return;
      var id = parseInt(m[1], 10); if (vistos[id]) return; vistos[id] = 1;
      out.push({ rppnid: id, nome: T(tds[0]).split("\n")[0], uf: T(tds[1]), status: T(tds[2]),
                 pagina: BASE + "/RPPNPage/" + id });
    });
    return out;
  }
  function lerRppn(doc) {
    var muni = "";
    Array.prototype.some.call(doc.querySelectorAll("main label, main span, main p, main td"), function (el) {
      var t = T(el); if (/^[^\n]{1,50}\([A-Z]{2}\)$/.test(t)) { muni = t; return true; } return false;
    });
    var a = doc.querySelector("input[name='area']");
    return { area: a ? a.value : "", municipio: muni.replace(/\s*\([A-Z]{2}\)$/, "") };
  }
  function lerProp(doc) {
    var nomes = [];
    Array.prototype.forEach.call(doc.querySelectorAll("main table tr"), function (tr) {
      var td = tr.querySelector("td"); if (td && T(td)) nomes.push(T(td));
    });
    return nomes;
  }
  function lerResumo(doc) {
    return { cadastro: dataPerto(doc, "Data de cadastro"), ato: dataPerto(doc, "Data da publicação") };
  }
  function lerLista(doc) {
    var a = doc.querySelector("a[href*='imovelid=']"), m = a ? a.getAttribute("href").match(/imovelid=(\d+)/) : null;
    var txt = T(doc.querySelector("main")), pts = [], re = /Número de Pontos:\s*(\d+)/g, x;
    while ((x = re.exec(txt))) pts.push(parseInt(x[1], 10));
    return { imovelid: m ? m[1] : null, nptsImovel: pts[0] || 0, nptsRppn: pts[1] || 0 };
  }
  // Editor de limites: as coordenadas são montadas por script → iframe INVISÍVEL,
  // esperando até os pontos esperados aparecerem (ou 25 s).
  function lerEditor(url, espImovel, espRppn) {
    return new Promise(function (resolve) {
      var f = document.createElement("iframe");
      f.setAttribute("style", "position:fixed;left:-9999px;top:0;width:2px;height:2px;opacity:0;pointer-events:none");
      f.src = url; document.body.appendChild(f);
      var t0 = Date.now();
      function extrair(d) {
        var sel = function (s) { var e = d.querySelector(s); return e ? parseInt(e.value || "0", 10) : 0; };
        var chk = d.querySelector("input[name='limite-rppn']:checked");
        return {
          limite_tipo: chk ? chk.value : "",
          zona_imovel: sel("select[name='sistema_de_coordenadasid']"),
          zona_rppn: sel("select[name='sistema_de_coordenadasid-rppn1']"),
          x_imovel: vals(d, "input[name='longitude-imovel[]']"), y_imovel: vals(d, "input[name='latitude-imovel[]']"),
          x_rppn: vals(d, "input[name='longitude-imovel-rppn1[]']"), y_rppn: vals(d, "input[name='latitude-imovel-rppn1[]']")
        };
      }
      (function check() {
        var d = null; try { d = f.contentDocument; } catch (e) {}
        if (d && d.readyState === "complete" && d.querySelector("select[name='sistema_de_coordenadasid']")) {
          var e = extrair(d), parcial = e.limite_tipo === "parcial";
          var okR = e.x_rppn.length >= 3 && e.x_rppn.length >= espRppn;
          var okI = e.x_imovel.length >= 3 && e.x_imovel.length >= espImovel;
          if ((parcial ? okR : okI) || Date.now() - t0 > 25000) { f.remove(); resolve(e); return; }
        } else if (Date.now() - t0 > 25000) { f.remove(); resolve(null); return; }
        setTimeout(check, 400);
      })();
    });
  }

  /* ---------- fluxo principal ---------- */
  (async function () {
    try {
      status("Lendo o Painel de Gestão…");
      var docPainel = /Painel-de-gestao/i.test(location.pathname) ? document : await fetchDoc(BASE + "/Painel-de-gestao");
      var lista = lerPainel(docPainel);
      if (!lista.length) {
        terminar("Nenhuma RPPN encontrada.", "Confira se você está logado(a) e no Painel de Gestão, e tente de novo.");
        return;
      }
      var res = [], comPoly = 0, n = lista.length;
      for (var i = 0; i < n; i++) {
        if (cancelado) { terminar("Cancelado.", "Nada foi enviado."); return; }
        var r = lista[i], base = BASE, rid = r.rppnid;
        status("Sincronizando RPPN " + (i + 1) + " de " + n + " — " + r.nome, "lendo dados cadastrais…");
        barra(i, n);
        try {
          var dR = await fetchDoc(base + "/Rppn?rppnid=" + rid + "&bq=1");
          var info = lerRppn(dR); r.area_rppn_ha = info.area; r.municipio = info.municipio;
          var nomes = lerProp(await fetchDoc(base + "/Proprietario?rppnid=" + rid + "&bq=1"));
          r.proprietario = nomes[0] || ""; if (nomes.length > 1) r.proprietario += " (+" + (nomes.length - 1) + ")";
          var dt = lerResumo(await fetchDoc(base + "/Resumo?rppnid=" + rid + "&bq=1"));
          r.data_cadastro = dt.cadastro; r.data_ato = dt.ato; r.data_criacao = dt.ato || dt.cadastro;
          elSub.textContent = "lendo o perímetro…";
          var li = lerLista(await fetchDoc(base + "/site/modules/Memorial-descritivo/v_Memorial-descritivo-lista.php?rppnid=" + rid + "&bq=1"));
          if (li.imovelid) {
            var ed = await lerEditor(base + "/site/modules/Memorial-descritivo/v_Memorial-descritivo-editar.php?rppnid=" +
                                     rid + "&imovelid=" + li.imovelid + "&limite=true", li.nptsImovel, li.nptsRppn);
            if (ed) {
              r.limite_tipo = ed.limite_tipo; r.zona_imovel = ed.zona_imovel; r.zona_rppn = ed.zona_rppn;
              r.pts_imovel = ed.x_imovel.map(function (x, k) { return [x, ed.y_imovel[k]]; });
              r.pts_rppn = ed.x_rppn.map(function (x, k) { return [x, ed.y_rppn[k]]; });
              if (r.pts_rppn.length >= 3 || r.pts_imovel.length >= 3) comPoly++;
            }
          }
        } catch (e) { r.erro = String(e && e.message || e); }
        res.push(r);
        await sleep(150);
      }
      barra(n, n);
      status("Gerando o arquivo…");
      var payload = { versao: VERSAO, coletado_em: new Date().toISOString(), origem: BASE, total: res.length, rppns: res };
      var nomeArq = "sincronizacao_rppns_" + new Date().toISOString().slice(0, 10) + ".json";
      var blob = new Blob([JSON.stringify(payload)], { type: "application/json" });
      var a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = nomeArq;
      document.body.appendChild(a); a.click(); a.remove();
      terminar("Concluído: " + res.length + " RPPNs, " + comPoly + " com perímetro.",
               "O arquivo " + nomeArq + " foi baixado. Agora envie-o na plataforma (Administrar → Sincronizar).");
    } catch (e) {
      terminar("Não foi possível concluir.", String(e && e.message || e));
    }
  })();
})();
