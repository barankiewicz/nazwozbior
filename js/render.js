// ── Główny render tabeli imion i paneli kontrolnych ──

"use strict";

// Zmienne do obsługi infinite scroll
var currentLimit = PER_PAGE;
var currentFilteredLength = 0;

// Globalna referencja do wylosowanego imienia (do natychmiastowego wyświetlenia na górze)
var randomHighlight = null;

// Odpowiada za wyświetlenie przefiltrowanych, posortowanych i spaginowanych rekordów w tabeli DOM
function render(append, isRandomClick) {
  if (!isRandomClick) {
    randomHighlight = null;
  }
  
  var all = getSortedFiltered();
  
  if (randomHighlight) {
    // Usuń z oryginalnej pozycji, aby uniknąć duplikatów
    all = all.filter(function (x) {
      return x.imie.toLowerCase() !== randomHighlight.imie.toLowerCase();
    });
    // Wstaw na sam początek
    all.unshift(randomHighlight);
  }
  
  var total = all.length;
  currentFilteredLength = total;
  
  if (!append) {
    currentLimit = PER_PAGE;
  }
  
  var shown = all.slice(0, currentLimit);
  
  countElement.innerHTML = "<b>" + formatNumber(total) + "</b> " + pluralForm(total) + " · pokazano <b>" + formatNumber(shown.length) + "</b>";

  var h = "";
  shown.forEach(function (r, i) {
    var nb = r._g === "nb", uni = r._g === "uni";
    var nx = nb || uni;
    var c3 = nx ? getFmtRejz(r) : getFmtW1(r);
    var c4 = nx ? getFmtRejm(r) : getFmtW2(r);
    var zTotal = r._rzp + r._rzd, mTotal = r._rmp + r._rmd, tCombined = zTotal + mTotal;
    var zPctR = tCombined ? Math.round(zTotal / tCombined * 100) : 0;
    var femalePct = zPctR;
    var malePct = 100 - zPctR;
    var ratioStr = nx 
      ? '<div style="display: inline-flex; flex-direction: column; align-items: flex-end; gap: 3px; vertical-align: middle;">' +
          '<span style="font-size: 11.5px; opacity: 0.85;">' + femalePct + '%\u00A0/\u00A0' + malePct + '%</span>' +
          '<div style="display: flex; width: 60px; height: 4px; border-radius: 2px; overflow: hidden; background: var(--line);">' +
            '<div style="width: ' + femalePct + '%; background: var(--accent);"></div>' +
            '<div style="width: ' + malePct + '%; background: color-mix(in srgb, var(--accent) 35%, var(--surface-2));"></div>' +
          '</div>' +
        '</div>' 
      : '';
    
    var tagTxt = r._sort_pochodzenie;
    if (tagTxt.length > 26) tagTxt = tagTxt.slice(0, 24) + "…";
    
    var unisexBadge = r.unisex && r.unisex >= 0.1 ? ' <span class="unisex-badge" data-tip="Imię unisex (z PESEL): ' + Math.round(r.unisex * 100) + '% nadań to płeć rzadsza (≥10% w obu rejestrach)">⚥</span>' : '';
    
    var isFav = favorites.has(r._sort_imie);
    var favIcon = isFav ? '★' : '☆';
    var favClass = isFav ? 'fav-btn active' : 'fav-btn';
    
    h += '<tr class="main" tabindex="0" data-i="' + i + '" data-imie="' + escapeHtml(r.imie) + '" aria-expanded="false">' +
         '<td class="name"><button type="button" class="' + favClass + '" aria-label="' + (isFav ? 'Usuń z ulubionych' : 'Dodaj do ulubionych') + '" data-fav-imie="' + escapeHtml(r.imie) + '">' + favIcon + '</button>' + escapeHtml(r.imie) + unisexBadge + '</td>' +
         '<td class="num hide">' + r.imie.length + '</td>' +
         '<td><span class="tag ' + getOriginClassCached(r) + '">' + escapeHtml(tagTxt) + '</span></td>' +
         '<td class="num">' + c3 + '</td>' +
         '<td class="num hide">' + c4 + '</td>' +
         (nx ? '<td class="num" data-tip="Stosunek nadań żeńskich do męskich. Im bliżej 50/50, tym bardziej neutralne płciowo imię.">' + ratioStr + '</td>' : '<td class="num"></td>') +
         '<td class="num hide">' + getFmtTotal(r) + '</td>' +
         '<td style="text-align:right"><span class="chev">›</span></td></tr>' +
         '<tr class="detail" data-d="' + i + '"><td colspan="8"><div class="detail-inner" aria-hidden="true"><div><div class="detail-pad">' +
         
         (nb && !r._is_unisex_pesel ? renderNonbinaryDetail(r) :
          (nb && r._is_unisex_pesel) || uni ? renderUnisexPeselDetail(r) :
          '<p class="freq">w PESEL: <b>' + getFmtW1(r) + '</b> os. jako imię pierwsze, ' +
          '<b>' + getFmtW2(r) + '</b> jako drugie' +
          (r.pochodzenie ? (' · pochodzenie <b>' + getOriginLabel(r.pochodzenie) + '</b>' + originSource(r)) : '') + '</p>' +
          trendSparkline(r.trend) +
          baseRelationLinks(r) +
          suggestSecondNames(r.imie, r._g, r.pochodzenie) +
          ("opis_html" in r
            ? ('<div class="opis">' + (r.opis_html || DESCRIPTION_MISSING) + '</div>' +
               (r.opis_html ? '<p class="src">' + getDescriptionSourceLink(r.imie) + '</p>' : ''))
            : ('<div class="opis" data-opis-imie="' + escapeHtml(r.imie) + '">' + DESCRIPTION_LOADING + '</div>' +
               '<p class="src" data-src-imie="' + escapeHtml(r.imie) + '" style="display:none"></p>'))) +
         
         '</div></div></div></td></tr>';
  });
  
  tableBody.innerHTML = h || '<tr><td colspan="8"><div class="empty">Nic z tego nie pasuje - poluzuj trochę filtry.<span class="shrug">¯\\_(ツ)_/¯</span></div></td></tr>';
  
  markSortHeader();
  saveState();
  updateFacets();
}

// Aktualizuje przeliczone wartości na przyciskach podziału oraz dostępne pochodzenia
function updateFacets() {
  var filterFn = getMatchFilter();
  
  var maleCount = 0;
  for (var i = 0; i < maleNames.length; i++) {
    if (filterFn(maleNames[i], false)) maleCount++;
  }
  
  var femaleCount = 0;
  for (var i = 0; i < femaleNames.length; i++) {
    if (filterFn(femaleNames[i], false)) femaleCount++;
  }
  
  var nbCount = 0;
  for (var i = 0; i < nonbinaryPool.length; i++) {
    if (filterFn(nonbinaryPool[i], false)) nbCount++;
  }
  
  var uniCount = 0;
  for (var i = 0; i < unisexNames.length; i++) {
    if (filterFn(unisexNames[i], false)) uniCount++;
  }
  
  var allCount = maleCount + femaleCount;
  
  var seg = document.getElementById("seg-gender");
  var b = seg.querySelectorAll("button");
  b[0].innerHTML = 'żeńskie <span class="facet-num">' + formatNumber(femaleCount) + '</span>';
  b[1].innerHTML = 'męskie <span class="facet-num">' + formatNumber(maleCount) + '</span>';
  b[2].innerHTML = 'unisex <span class="gend-tip" data-tip="Imiona z rejestru PESEL występujące w obu rejestrach (co najmniej 10% nadań rzadszej płci). Obliczane przez Nazwozbiór.">?</span> <span class="facet-num">' + formatNumber(uniCount) + '</span>';
  b[3].innerHTML = 'niebinarne <span class="gend-tip" data-tip="Imiona neutralne płciowo z zaimki.pl, zebrane przez kolektyw „Rada Języka Neutralnego” (zaimki.pl/imiona).">?</span> <span class="facet-num">' + formatNumber(nbCount) + '</span>';
  b[4].innerHTML = 'wszystkie <span class="facet-num">' + formatNumber(allCount) + '</span>';
  b[3].style.display = nonbinaryNames.length ? "" : "none";

  var originCounts = {}, originKeys = [];
  var pool = getPool();
  for (var i = 0; i < pool.length; i++) {
    var r = pool[i];
    if (!filterFn(r, true)) continue;
    var o = r.pochodzenie || "__none__";
    if (!originCounts[o]) {
      originCounts[o] = 0;
      originKeys.push(o);
    }
    originCounts[o]++;
  }
  
  originKeys.sort(function (a, b) {
    if (a === "__none__") return 1;
    if (b === "__none__") return -1;
    if (originCounts[b] !== originCounts[a]) return originCounts[b] - originCounts[a];
    return getOriginLabel(a).localeCompare(getOriginLabel(b), "pl");
  });
  
  var h = '<option value="all">dowolne</option>';
  originKeys.forEach(function (k) {
    h += '<option value="' + k + '">' + (k === "__none__" ? "nieokreślone" : getOriginLabel(k)) + ' (' + formatNumber(originCounts[k]) + ')</option>';
  });
  
  var pv = originSelect.value;
  originSelect.innerHTML = h;
  if (originSelect.querySelector('option[value="' + pv + '"]')) originSelect.value = pv;
  else { state.origin = "all"; originSelect.value = "all"; }
}
