// ── Główny render tabeli imion i paneli kontrolnych ──

"use strict";

// Odpowiada za wyświetlenie przefiltrowanych, posortowanych i spaginowanych rekordów w tabeli DOM
function render() {
  var all = getSorted(getFiltered());
  var total = all.length;
  
  if (randomOffset >= total) randomOffset = 0;
  var totalPages = Math.max(1, Math.ceil((total - randomOffset) / PER_PAGE));
  if (currentPage >= totalPages) currentPage = Math.max(0, totalPages - 1);
  
  viewAllButton.style.display = "";
  var shown, start;
  
  if (showAll) {
    shown = all;
    prevButton.style.display = "none";
    nextButton.style.display = "none";
    pageInfo.textContent = "";
    viewAllButton.textContent = "pokaż po stronie";
    countElement.innerHTML = "<b>" + formatNumber(total) + "</b> " + pluralForm(total);
  } else {
    start = randomOffset + currentPage * PER_PAGE;
    shown = all.slice(start, start + PER_PAGE);
    prevButton.style.display = currentPage > 0 ? "inline-block" : "none";
    nextButton.style.display = currentPage < totalPages - 1 ? "inline-block" : "none";
    pageInfo.textContent = "strona " + (currentPage + 1) + " z " + totalPages;
    viewAllButton.textContent = "pokaż wszystkie";
    countElement.innerHTML = "<b>" + formatNumber(total) + "</b> " + pluralForm(total) + " · <b>" + formatNumber(start + 1) + "</b>–<b>" + formatNumber(Math.min(start + PER_PAGE, total)) + "</b>";
  }

  var h = "";
  shown.forEach(function (r, i) {
    var nb = r._g === "nb", uni = r._g === "uni";
    var nx = nb || uni;
    var c3 = nx ? formatNumber(r._rzp + r._rzd) : formatNumber(r.wystapienia_pierwsze);
    var c4 = nx ? formatNumber(r._rmp + r._rmd) : formatNumber(r.wystapienia_drugie);
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
    
    var tagTxt = nb ? getNbOriginLabel(r) : getOriginLabel(r.pochodzenie);
    if (tagTxt.length > 26) tagTxt = tagTxt.slice(0, 24) + "…";
    
    var unisexBadge = r.unisex && r.unisex >= 0.1 ? ' <span class="unisex-badge" data-tip="Imię unisex (z PESEL): ' + Math.round(r.unisex * 100) + '% nadań to płeć rzadsza (≥10% w obu rejestrach)">⚥</span>' : '';
    
    h += '<tr class="main" tabindex="0" data-i="' + i + '" data-imie="' + escapeHtml(r.imie) + '" aria-expanded="false">' +
         '<td class="name">' + escapeHtml(r.imie) + unisexBadge + '</td>' +
         '<td class="num hide">' + r.imie.length + '</td>' +
         '<td><span class="tag ' + getOriginClass(r.pochodzenie) + '">' + escapeHtml(tagTxt) + '</span></td>' +
         '<td class="num">' + c3 + '</td>' +
         '<td class="num hide">' + c4 + '</td>' +
         (nx ? '<td class="num" data-tip="Stosunek nadań żeńskich do męskich. Im bliżej 50/50, tym bardziej neutralne płciowo imię.">' + ratioStr + '</td>' : '<td class="num"></td>') +
         '<td class="num hide">' + formatNumber(totalCount(r)) + '</td>' +
         '<td style="text-align:right"><span class="chev">›</span></td></tr>' +
         '<tr class="detail" data-d="' + i + '"><td colspan="8"><div class="detail-inner" aria-hidden="true"><div class="detail-pad">' +
         
         (nb && !r._is_unisex_pesel ? renderNonbinaryDetail(r) :
          (nb && r._is_unisex_pesel) || uni ? renderUnisexPeselDetail(r) :
          '<p class="freq">w PESEL: <b>' + formatNumber(r.wystapienia_pierwsze) + '</b> os. jako imię pierwsze, ' +
          '<b>' + formatNumber(r.wystapienia_drugie) + '</b> jako drugie' +
          (r.pochodzenie ? (' · pochodzenie <b>' + getOriginLabel(r.pochodzenie) + '</b>' + originSource(r)) : '') + '</p>' +
          trendSparkline(r.trend) +
          baseRelationLinks(r) +
          ("opis_html" in r
            ? ('<div class="opis">' + (r.opis_html || DESCRIPTION_MISSING) + '</div>' +
               (r.opis_html ? '<p class="src">' + getDescriptionSourceLink(r.imie) + '</p>' : ''))
            : ('<div class="opis" data-opis-imie="' + escapeHtml(r.imie) + '"><span style="color:var(--faint)">wczytuję znaczenie…</span></div>' +
               '<p class="src" data-src-imie="' + escapeHtml(r.imie) + '" style="display:none"></p>'))) +
         
         '</div></div></td></tr>';
  });
  
  tableBody.innerHTML = h || '<tr><td colspan="8"><div class="empty">Nic z tego nie pasuje - poluzuj trochę filtry.<span class="shrug">¯\\_(ツ)_/¯</span></div></td></tr>';
  
  markSortHeader();
  saveState();
  updateFacets();
}

// Aktualizuje przeliczone wartości na przyciskach podziału oraz dostępne pochodzenia
function updateFacets() {
  function match(r, skipOrigin) {
    var L = r.imie.length;
    if (L < state.min || L > state.max) return false;
    
    var t = totalCount(r);
    if (state.minUse > 0 && t < state.minUse) return false;
    if (state.maxUse > 0 && t > state.maxUse) return false;
    
    if (!nameMatches(r.imie)) return false;
    
    if (!skipOrigin) {
      if (state.origin === "all") {
        // brak
      } else if (state.origin === "__none__") {
        if (r.pochodzenie) return false;
      } else if (r.pochodzenie !== state.origin) {
        return false;
      }
    }
    return true;
  }
  
  var maleCount = maleNames.filter(function (r) { return match(r, false); }).length;
  var femaleCount = femaleNames.filter(function (r) { return match(r, false); }).length;
  var nbCount = nonbinaryNames.filter(function (r) { return match(r, false); }).length;
  
  var uSeenBi = {}, uniCount = 0;
  maleNames.concat(femaleNames).forEach(function (r) {
    if (!r.unisex || r.unisex < 0.1) return;
    var k = r.imie.toLowerCase();
    if (!uSeenBi[k] && match(r, false)) {
      uSeenBi[k] = true;
      uniCount++;
    }
  });
  
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
  getPool().forEach(function (r) {
    if (!match(r, true)) return;
    var o = r.pochodzenie || "__none__";
    if (!originCounts[o]) {
      originCounts[o] = 0;
      originKeys.push(o);
    }
    originCounts[o]++;
  });
  
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
