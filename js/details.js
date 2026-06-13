// ── Renderowanie paneli szczegółów, wykresów trendu i nagłówków tabeli ──

"use strict";

// Tworzy wewnętrzny link-odsyłacz w szczegółach imienia do innego imienia
function xrefLink(name) {
  return '<a href="#" class="xref" data-imie="' + escapeHtml(name) + '">' + escapeHtml(name) + '</a>';
}

// Tworzy dodatkowy opis pochodzenia i odsyłacz do zewnętrznej bazy (np. Wikipedii)
function originSource(r) {
  if (!r.pochodzenie || !r.zrodlo) return "";
  var n = encodeURIComponent(r.imie), lab = null, url = null;
  
  switch (r.zrodlo) {
    case "PL": lab = "polskiej Wikipedii"; url = "https://pl.wikipedia.org/wiki/" + n; break;
    case "EN": lab = "angielskiej Wikipedii"; url = "https://en.wikipedia.org/wiki/" + n; break;
    case "WD": case "WDD": lab = "Wikidanych"; url = "https://www.wikidata.org/w/index.php?search=" + n; break;
    case "WIKT-PL": lab = "Wikisłownika"; url = "https://pl.wiktionary.org/wiki/" + r.imie; break;
    case "WIKT-EN": lab = "angielskiego Wikisłownika"; url = "https://en.wiktionary.org/wiki/" + r.imie; break;
    case "ODZ": return r.zrodlo_baza ? ' <span class="origin-src">(odziedziczone po imieniu ' + xrefLink(r.zrodlo_baza) + ')</span>' : ' <span class="origin-src">(odziedziczone po imieniu bazowym)</span>';
    case "MORF": return r.zrodlo_baza ? ' <span class="origin-src">(wnioskowane od imienia ' + xrefLink(r.zrodlo_baza) + ')</span>' : "";
    case "TRANS": return r.zrodlo_baza ? ' <span class="origin-src">(transliteracja od ' + xrefLink(r.zrodlo_baza) + ')</span>' : "";
    case "UK": lab = "ukraińskiej Wikipedii"; url = "https://uk.wikipedia.org/wiki/" + n; break;
    case "RU": lab = "rosyjskiej Wikipedii"; url = "https://ru.wikipedia.org/wiki/" + n; break;
    case "VI": lab = "wietnamskiej Wikipedii"; url = "https://vi.wikipedia.org/wiki/" + n; break;
    case "RMY": lab = "romskiej Wikipedii"; url = "https://rmy.wikipedia.org/wiki/" + n; break;
    case "WIKT-CAT": lab = "en.Wiktionary (kategorie)"; url = "https://en.wiktionary.org/wiki/" + n; break;
    case "WAR": return r.zrodlo_baza ? ' <span class="origin-src">(wnioskowane od imienia ' + xrefLink(r.zrodlo_baza) + ')</span>' : "";
    case "EN-TL": lab = "angielskiej Wikipedii (tłum.)"; url = "https://en.wikipedia.org/wiki/" + n; break;
    case "UK-TL": lab = "ukraińskiej Wikipedii (tłum.)"; url = "https://uk.wikipedia.org/wiki/" + n; break;
    case "RU-TL": lab = "rosyjskiej Wikipedii (tłum.)"; url = "https://ru.wikipedia.org/wiki/" + n; break;
    case "VI-TL": lab = "wietnamskiej Wikipedii (tłum.)"; url = "https://vi.wikipedia.org/wiki/" + n; break;
    default: return "";
  }
  return ' <span class="origin-src">(wg <a href="' + url + '" target="_blank" rel="noopener noreferrer">' + lab + '</a>)</span>';
}

// Generuje listę powiązań między imionami (bazowe / pochodne)
function baseRelationLinks(r) {
  var parts = [];
  (r.bazowe || []).forEach(function (b) {
    parts.push(escapeHtml(b.relacja) + ' imienia ' + xrefLink(b.imie));
  });
  if (r.pochodne && r.pochodne.length) {
    parts.push((r.pochodne.length === 1 ? 'pochodne imię: ' : 'pochodne imiona: ') + r.pochodne.map(xrefLink).join(", "));
  }
  return parts.length ? '<p class="xrefs">' + parts.join(' · ') + '</p>' : '';
}

// Generuje graficzny wykres trendu w formacie SVG ze znacznikami
function trendSparkline(trend) {
  if (!trend) return "";
  var pts = [], k, yr, v;
  for (k in trend) {
    if (trend.hasOwnProperty(k)) {
      yr = +k;
      v = +trend[k];
      if (yr && !isNaN(v)) pts.push([yr, v]);
    }
  }
  if (pts.length < 2) return "";
  pts.sort(function (a, b) { return a[0] - b[0]; });
  
  var first = pts[0], last = pts[pts.length - 1], y0 = first[0], y1 = last[0];
  var vmax = 0, peak = first, i;
  for (i = 0; i < pts.length; i++) {
    if (pts[i][1] > vmax) vmax = pts[i][1];
    if (pts[i][1] > peak[1]) peak = pts[i];
  }
  if (!vmax) return "";

  function nice(x) {
    var e = Math.floor(Math.log(x) / Math.LN10);
    var f = x / Math.pow(10, e);
    return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * Math.pow(10, e);
  }
  function nfk(n) {
    if (n >= 1000) {
      var t = n / 1000;
      return (t % 1 ? t.toFixed(1).replace(".", ",") : t) + " tys.";
    }
    return "" + n;
  }
  
  var step = nice(vmax / 3);
  var vtop = Math.ceil(vmax / step) * step;
  var W = 560, H = 100, padL = 42, padR = 12, padT = 12, padB = 16;
  var iw = W - padL - padR, ih = H - padT - padB, base = padT + ih;
  
  function sx(y) { return padL + (y1 === y0 ? 0 : (y - y0) / (y1 - y0) * iw); }
  function sy(val) { return padT + (1 - val / vtop) * ih; }
  function xy(p) { return sx(p[0]).toFixed(1) + "," + sy(p[1]).toFixed(1); }
  
  var g = "";

  for (var t = 0; t <= vtop + 0.5; t += step) {
    var gy = sy(t).toFixed(1);
    g += '<line class="' + (t === 0 ? "trend-axis" : "trend-grid") + '" x1="' + padL + '" y1="' + gy + '" x2="' + (W - padR) + '" y2="' + gy + '"/>';
    g += '<text class="trend-tick" x="' + (padL - 6) + '" y="' + gy + '" text-anchor="end" dominant-baseline="middle">' + nfk(t) + '</text>';
  }

  var runs = [[first]];
  for (i = 1; i < pts.length; i++) {
    if (pts[i][0] - pts[i - 1][0] > 1) runs.push([pts[i]]);
    else runs[runs.length - 1].push(pts[i]);
  }

  g += '<polygon class="trend-area" points="' + sx(y0).toFixed(1) + "," + base + " " +
       pts.map(xy).join(" ") + " " + sx(y1).toFixed(1) + "," + base + '"/>';

  for (i = 1; i < runs.length; i++) {
    var a = runs[i - 1][runs[i - 1].length - 1], b = runs[i][0];
    g += '<line class="trend-gap" x1="' + sx(a[0]).toFixed(1) + '" y1="' + sy(a[1]).toFixed(1) +
         '" x2="' + sx(b[0]).toFixed(1) + '" y2="' + sy(b[1]).toFixed(1) + '"/>';
  }

  runs.forEach(function (run) {
    if (run.length > 1) g += '<polyline class="trend-line" points="' + run.map(xy).join(" ") + '"/>';
  });

  g += '<circle class="trend-dot" cx="' + sx(first[0]).toFixed(1) + '" cy="' + sy(first[1]).toFixed(1) + '" r="3"/>';
  g += '<circle class="trend-dot" cx="' + sx(last[0]).toFixed(1) + '" cy="' + sy(last[1]).toFixed(1) + '" r="3"/>';
  g += '<circle class="trend-peak" cx="' + sx(peak[0]).toFixed(1) + '" cy="' + sy(peak[1]).toFixed(1) + '" r="3.6"/>';

  var yspan = y1 - y0, ystep = yspan > 20 ? 5 : yspan > 8 ? 2 : 1, yticks = [y0], yy;
  for (yy = Math.ceil((y0 + 1) / ystep) * ystep; yy < y1; yy += ystep) { if (y1 - yy >= 2) yticks.push(yy); }
  yticks.push(y1);
  
  yticks.forEach(function (yv) {
    var xx = sx(yv), anc = yv === y0 ? "start" : (yv === y1 ? "end" : "middle");
    g += '<line class="trend-grid" x1="' + xx.toFixed(1) + '" y1="' + base + '" x2="' + xx.toFixed(1) + '" y2="' + (base + 3) + '"/>';
    g += '<text class="trend-lbl" x="' + xx.toFixed(1) + '" y="' + (base + 13) + '" text-anchor="' + anc + '">' + yv + '</text>';
  });

  pts.forEach(function (p) {
    g += '<circle class="trend-hit" cx="' + sx(p[0]).toFixed(1) + '" cy="' + sy(p[1]).toFixed(1) + '" r="10" data-y="' + p[0] + '" data-v="' + formatNumber(p[1]) + '"/>';
  });
  g += '<line class="trend-v-line" x1="0" y1="' + padT + '" x2="0" y2="' + base + '" style="display:none; stroke: var(--accent); stroke-width: 1; stroke-dasharray: 2 2; pointer-events: none; opacity: 0.7;"/>';
  g += '<circle class="trend-cursor" r="4" cx="0" cy="0" style="display:none"/>';

  var change = first[1] ? Math.round((last[1] - first[1]) / first[1] * 100) : null;
  var up = change >= 0, col = up ? 'var(--teal)' : 'var(--magenta)';
  var foot = '<div class="trend-foot">' +
    '<span>szczyt: <b>' + peak[0] + '</b> (' + formatNumber(peak[1]) + ')</span>' +
    '<span>' + last[0] + ': <b>' + formatNumber(last[1]) + '</b></span>' +
    (change === null ? '' : '<span style="color:' + col + ';font-weight:700">' + (up ? '↗ +' : '↘ ') + change + '% od ' + first[0] + '</span>') +
    '</div>';

  return '<div class="trend">' +
    '<svg viewBox="0 0 ' + W + ' ' + H + '" class="trend-svg" role="img" aria-label="Trend nadań imienia od ' + y0 + ' do ' + y1 + ', szczyt w ' + peak[0] + '">' + g + '</svg>' +
    foot + '</div>';
}

// Renderuje panel szczegółów dla imion unisex wprost z rejestru PESEL
function renderUnisexPeselDetail(r) {
  var src = r._src || {};
  var freq = 'w PESEL: <b>' + formatNumber(r._rzp + r._rzd) + '</b> os. w rej. żeńskim, <b>' + formatNumber(r._rmp + r._rmd) + '</b> w męskim' +
    (src.pochodzenie ? (' · pochodzenie <b>' + getOriginLabel(src.pochodzenie) + '</b>' + originSource(src)) : '');
  
  return '<p class="freq">' + freq + '</p>' +
    trendSparkline(src.trend) +
    baseRelationLinks(src) +
    ("opis_html" in src
      ? ('<div class="opis">' + (src.opis_html || DESCRIPTION_MISSING) + '</div>' +
        (src.opis_html ? '<p class="src">' + getDescriptionSourceLink(r.imie) + '</p>' : ''))
      : ('<div class="opis" data-opis-imie="' + escapeHtml(r.imie) + '"><span style="color:var(--faint)">wczytuję znaczenie…</span></div>' +
        '<p class="src" data-src-imie="' + escapeHtml(r.imie) + '" style="display:none"></p>'));
}

// Formatuje pojedynczy atrybut informacji o imieniu niebinarnym
function nonbinaryField(label, val, allowHtml) {
  if (!val) return "";
  return '<div class="nb-row"><dt>' + label + '</dt><dd>' + (allowHtml ? val : escapeHtml(val)) + '</dd></div>';
}

// Renderuje panel z informacjami z bazy imion niebinarnych (zaimki.pl)
function renderNonbinaryDetail(r) {
  var freq = 'w PESEL: <b>' + formatNumber(r._rzp + r._rzd) + '</b> w rejestrze żeńskim, <b>' + formatNumber(r._rmp + r._rmd) + '</b> w męskim';
  
  if (r._war.length > 1) {
    freq += ' · ' + r._war.map(function (v) {
      var z = v.z ? (v.z.wystapienia_pierwsze || 0) + (v.z.wystapienia_drugie || 0) : 0;
      var m = v.m ? (v.m.wystapienia_pierwsze || 0) + (v.m.wystapienia_drugie || 0) : 0;
      return escapeHtml(v.w) + ": ż " + formatNumber(z) + " / m " + formatNumber(m);
    }).join(", ");
  }
  
  var linki = (r.linki || []).map(function (u) {
    var dom;
    try { dom = new URL(u).hostname.replace(/^www\./, ""); } catch (e) { dom = u; }
    return '<a href="' + escapeHtml(u) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(dom) + '</a>';
  }).join(" · ");
  
  var imieniny = (r.imieniny || []).join(", ") + (r.imieniny_kom ? " (" + r.imieniny_kom + ")" : "");
  
  return '<p class="freq">' + freq + '</p><dl class="nb-info">' +
    nonbinaryField("znaczenie", r.znaczenie) +
    nonbinaryField("pochodzenie", r.pochodzenie_opis) +
    nonbinaryField("używane", r.uzycie) +
    nonbinaryField("w rejestrach", r.prawnie) +
    nonbinaryField("za", r.plusy) +
    nonbinaryField("przeciw", r.minusy) +
    nonbinaryField("imieniny", imieniny) +
    nonbinaryField("znane osoby", r.znane_osoby_html, true) +
    nonbinaryField("więcej", linki, true) +
    '</dl><p class="src">źródło: <a href="https://zaimki.pl/imiona" target="_blank" rel="noopener noreferrer">zaimki.pl</a></p>';
}

// Ustawia odpowiednie nagłówki tabeli zależnie od rodzaju (niebinarne/unisex posiadają inną kolumnę)
function updateHeader() {
  var nb = state.g === "nb" || state.g === "uni";
  headerRow.innerHTML = nb ? HEADER_NONBINARY : HEADER_BINARY;
  
  if (nb) {
    if (state.sort === "wystapienia_pierwsze") state.sort = "rejz";
    if (state.sort === "wystapienia_drugie") state.sort = "rejm";
  } else {
    if (state.sort === "rejz") state.sort = "wystapienia_pierwsze";
    if (state.sort === "rejm") state.sort = "wystapienia_drugie";
    if (state.sort === "ratio_nb") state.sort = "wystapienia_razem";
  }
}

// Aktualizuje wskaźnik i klasy sortowania w nagłówku tabeli
function markSortHeader() {
  [].forEach.call(headerRow.querySelectorAll("th[data-key]"), function (th) {
    var on = th.getAttribute("data-key") === state.sort;
    th.setAttribute("data-active", on ? "1" : "0");
    th.setAttribute("aria-sort", on ? (state.dir === 1 ? "ascending" : "descending") : "none");
    var arr = th.querySelector(".arr");
    if (arr) arr.textContent = on ? (state.dir === 1 ? "▲" : "▼") : "▲";
  });
}
