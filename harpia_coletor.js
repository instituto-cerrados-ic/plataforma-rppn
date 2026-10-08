/*
 * Coletor do HARPIA (IBRAM/DF) — roda DENTRO da aba do Harpia, no navegador
 * da própria pessoa (favorito/bookmarklet), na página "Acompanhamento".
 * Usa a sessão que ela mesma abriu; nada de senha sai do navegador.
 *
 * O Harpia é uma aplicação com estado (Wicket): cada tela tem um id de página
 * e os botões são chamadas AJAX. Por isso a coleta é feita num IFRAME
 * INVISÍVEL que navega pela lista e abre cada solicitação, enquanto a pessoa
 * vê só um painel com barra de progresso. A URL "sem estado" devolve 503 e
 * redireciona para http (bloqueado), então o iframe sempre parte da URL atual
 * (com id de página + uid).
 *
 * Saída: baixa harpia_<data>.json com o texto de cada seção de cada
 * solicitação e os arquivos .zip (shapefiles) em base64. Quem interpreta é
 * a plataforma (harpia_ingest.py): RPPNs, servidões ambientais e polígonos.
 */
(function () {
  var VERSAO = "1.0";

  if (location.hostname.indexOf("harpia.ibram") === -1) {
    alert("Abra primeiro o Harpia (IBRAM), entre em 'Acompanhar Minhas Solicitações' e clique no favorito lá.");
    return;
  }
  if (!/[?&]uid=/.test(location.search)) {
    alert("Abra a tela 'Acompanhamento' (menu Meus Processos → Acompanhamento) e clique no favorito com a lista na tela.");
    return;
  }
  if (window.__icHarpia) { alert("A coleta já está em andamento."); return; }
  window.__icHarpia = true;

  /* ---------- painel de progresso ---------- */
  var ov = document.createElement("div");
  ov.setAttribute("style", "position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:2147483647;" +
    "display:flex;align-items:center;justify-content:center;font-family:Montserrat,Segoe UI,Arial,sans-serif");
  ov.innerHTML =
    '<div style="background:#fff;border-radius:14px;padding:26px 30px;width:min(520px,92vw);' +
    'box-shadow:0 20px 60px rgba(0,0,0,.35);border-top:6px solid #004F23">' +
    '<div style="font-size:1.25rem;font-weight:700;color:#004F23;margin-bottom:4px">Sincronizando Harpia (IBRAM)</div>' +
    '<div style="font-size:.8rem;color:#666;margin-bottom:16px">Instituto Cerrados · Programa Jurema · coletor v' + VERSAO + '</div>' +
    '<div id="ic-h-txt" style="font-size:.95rem;color:#1a1a1a;min-height:1.4em">Preparando…</div>' +
    '<div style="background:#eee;border-radius:8px;height:14px;margin:12px 0 6px;overflow:hidden">' +
    '<div id="ic-h-bar" style="height:100%;width:0%;background:linear-gradient(90deg,#004F23,#2E8B57);transition:width .3s"></div></div>' +
    '<div id="ic-h-sub" style="font-size:.8rem;color:#666;min-height:1.2em"></div>' +
    '<div style="margin-top:16px;display:flex;gap:10px;justify-content:flex-end">' +
    '<button id="ic-h-cancel" style="padding:8px 14px;border:1px solid #bbb;background:#fff;border-radius:8px;cursor:pointer">Cancelar</button>' +
    '<button id="ic-h-close" style="display:none;padding:8px 14px;border:0;background:#004F23;color:#fff;border-radius:8px;cursor:pointer">Fechar</button>' +
    "</div></div>";
  document.body.appendChild(ov);
  var elTxt = document.getElementById("ic-h-txt"), elBar = document.getElementById("ic-h-bar"),
      elSub = document.getElementById("ic-h-sub");
  var cancelado = false;
  document.getElementById("ic-h-cancel").onclick = function () { cancelado = true; };
  document.getElementById("ic-h-close").onclick = function () { ov.remove(); window.__icHarpia = false; };
  function status(t, s) { elTxt.textContent = t; elSub.textContent = s || ""; }
  function barra(i, n) { elBar.style.width = Math.round(100 * i / n) + "%"; }
  function terminar(msg, sub) {
    status(msg, sub); elBar.style.width = "100%";
    document.getElementById("ic-h-cancel").style.display = "none";
    document.getElementById("ic-h-close").style.display = "inline-block";
  }

  /* ---------- utilidades ---------- */
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function T(el) { return el ? (el.textContent || "").replace(/\s+/g, " ").trim() : ""; }
  var LISTA_URL = location.href;

  /* iframe invisível que faz a navegação */
  var fr = document.createElement("iframe");
  fr.setAttribute("style", "position:fixed;left:-20000px;top:0;width:1280px;height:900px;border:0;opacity:0;pointer-events:none");
  document.body.appendChild(fr);
  function D() { try { return fr.contentDocument; } catch (e) { return null; } }
  function carregar(url) {
    return new Promise(function (resolve) {
      var done = false;
      fr.onload = function () { if (!done) { done = true; setTimeout(resolve, 1200); } };
      fr.src = url;
      setTimeout(function () { if (!done) { done = true; resolve(); } }, 20000);
    });
  }
  function esperar(cond, timeoutMs) { // espera até cond(doc) ser verdadeiro
    return new Promise(function (resolve) {
      var t0 = Date.now();
      (function chk() {
        var d = D(), ok = false;
        try { ok = d && d.body && cond(d); } catch (e) { ok = false; }
        if (ok) return resolve(true);
        if (Date.now() - t0 > (timeoutMs || 15000)) return resolve(false);
        setTimeout(chk, 300);
      })();
    });
  }
  function linhas(d) {
    return Array.prototype.map.call(d.querySelectorAll("table tbody tr"), function (tr) {
      var td = tr.querySelectorAll("td");
      return { tr: tr,
        protocolo: T(td[0]), data_envio: T(td[1]), tipo: T(td[2]),
        especificacao: T(td[3]), situacao: T(td[4]), data_situacao: T(td[5]) };
    }).filter(function (r) { return r.protocolo; });
  }
  function abas(d) { // links de aba do formulário (Wicket: href="#", id="id…")
    var seen = {}, out = [];
    Array.prototype.forEach.call(d.querySelectorAll("a[id^=id]"), function (a) {
      if (a.getAttribute("href") !== "#") return;
      var t = T(a);
      if (!t || /notifica|representante/i.test(t) || seen[t]) return;
      if (!a.closest(".nav, ul, .list-group")) return;
      seen[t] = 1; out.push(t);
    });
    return out;
  }
  function abaEl(d, rotulo) {
    return Array.prototype.find.call(d.querySelectorAll("a[id^=id]"), function (a) {
      return a.getAttribute("href") === "#" && T(a) === rotulo && a.closest(".nav, ul, .list-group");
    });
  }
  function textoPrincipal(d) {
    var m = d.querySelector(".tab-content, .card-body, .panel-body") || d.body;
    return (m.innerText || m.textContent || "").trim();
  }
  function links(d) {
    return Array.prototype.map.call(d.querySelectorAll("a[href*='/download/']"), function (a) {
      return { nome: T(a), href: a.getAttribute("href") };
    });
  }
  function baixarB64(href) {
    return fetch(href, { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.arrayBuffer();
    }).then(function (buf) {
      var b = "", u8 = new Uint8Array(buf);
      for (var i = 0; i < u8.length; i += 0x8000) b += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
      return btoa(b);
    });
  }
  async function abrirLista() {
    await carregar(LISTA_URL);
    var ok = await esperar(function (d) { return linhas(d).length > 0; }, 6000);
    if (!ok) { // a lista às vezes só vem depois do clique no menu lateral
      var d = D(), a = d && Array.prototype.find.call(d.querySelectorAll("a"), function (x) { return T(x) === "Acompanhamento"; });
      if (a) a.click();
      ok = await esperar(function (d2) { return linhas(d2).length > 0; }, 12000);
    }
    return ok;
  }

  /* ---------- fluxo principal ---------- */
  (async function () {
    try {
      status("Abrindo a lista de solicitações…");
      if (!(await abrirLista())) throw new Error("Não consegui carregar a lista de solicitações (sessão expirada?).");
      var lista = linhas(D()).map(function (r) {
        return { protocolo: r.protocolo, data_envio: r.data_envio, tipo: r.tipo,
                 especificacao: r.especificacao, situacao: r.situacao, data_situacao: r.data_situacao };
      });
      var n = lista.length, out = [];
      for (var i = 0; i < n; i++) {
        if (cancelado) break;
        var reg = lista[i];
        status("Lendo solicitação " + (i + 1) + " de " + n, reg.protocolo + " · " + reg.especificacao);
        barra(i, n);
        reg.secoes = {}; reg.arquivos = []; reg.erro = "";
        try {
          if (i > 0 && !(await abrirLista())) throw new Error("lista não recarregou");
          var tr = linhas(D()).filter(function (r) { return r.protocolo === reg.protocolo; })[0];
          var olho = tr && tr.tr.querySelector("a i.icon-eye");
          if (!olho) throw new Error("botão Visualizar não encontrado");
          olho.closest("a").click();
          var okForm = await esperar(function (d) { return /rascunhos\/editar/.test(d.location.href) && abas(d).length > 0; }, 20000);
          if (!okForm) throw new Error("formulário não abriu");
          await sleep(800);
          var rot = abas(D()), vistos = {};
          var antes = "";
          for (var k = 0; k < rot.length; k++) {
            var a = abaEl(D(), rot[k]);
            if (a) { // clica e espera a seção trocar de verdade (AJAX), até 8 s
              a.click();
              await esperar(function (d) { var t = textoPrincipal(d); return t && t !== antes; }, 8000);
              await sleep(600);
            }
            antes = reg.secoes[rot[k]] = textoPrincipal(D());
            links(D()).forEach(function (l) { if (!vistos[l.href]) { vistos[l.href] = 1; reg.arquivos.push(l); } });
          }
          for (var z = 0; z < reg.arquivos.length; z++) {
            var arq = reg.arquivos[z];
            if (/\.zip$/i.test(arq.nome)) {
              elSub.textContent = "baixando " + arq.nome;
              try { arq.base64 = await baixarB64(arq.href); } catch (e) { arq.erro = String(e); }
            }
          }
        } catch (e) { reg.erro = String(e && e.message || e); }
        out.push(reg);
      }
      barra(n, n);
      var payload = { versao: VERSAO, origem: "harpia", coletado_em: new Date().toISOString(),
                      total: out.length, solicitacoes: out };
      var nomeArq = "harpia_" + new Date().toISOString().slice(0, 10) + ".json";
      var blob = new Blob([JSON.stringify(payload)], { type: "application/json" });
      var a2 = document.createElement("a"); a2.href = URL.createObjectURL(blob); a2.download = nomeArq;
      document.body.appendChild(a2); a2.click(); a2.remove();
      var comErro = out.filter(function (r) { return r.erro; }).length;
      terminar(cancelado ? "Coleta cancelada (arquivo parcial baixado)." : "Coleta concluída!",
        out.length + " solicitação(ões) lidas" + (comErro ? ", " + comErro + " com erro" : "") +
        ". Arquivo " + nomeArq + " baixado — envie-o na plataforma (aba Administrar → Sincronizar com o Harpia).");
    } catch (e) {
      terminar("Falhou: " + (e && e.message || e), "Confira se está logado e com a tela 'Acompanhamento' aberta e tente de novo.");
    } finally { fr.remove(); }
  })();
})();
