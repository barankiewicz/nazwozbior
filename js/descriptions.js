// ── Leniwe ładowanie opisów znaczeń imion ──

"use strict";

// Przestrzenie nazw na opisy dynamicznie ładowane z folderu opisy/
var DESCRIPTIONS = window.NZ_OPISY = window.NZ_OPISY || {};
var DESCRIPTION_STATE = {};
var DESCRIPTION_SOURCES = window.NZ_OPISY_SRC = window.NZ_OPISY_SRC || {};

// Ładuje asynchronicznie skrypt ze słownikiem dla danej litery, jeśli go jeszcze nie ma
function ensureDescription(name, cb) {
  var k = getShardKey(name);
  var st = DESCRIPTION_STATE[k];
  
  if (st === 'ok') {
    cb();
    return;
  }
  
  if (st) {
    st.push(cb);
    return;
  }
  
  DESCRIPTION_STATE[k] = [cb];
  var sc = document.createElement('script');
  sc.src = 'opisy/' + k + '.js';
  
  sc.onload = sc.onerror = function () {
    var q = DESCRIPTION_STATE[k];
    DESCRIPTION_STATE[k] = 'ok';
    (q || []).forEach(function (f) { f(); });
  };
  
  document.head.appendChild(sc);
}

// Pobiera treść opisu dla danego imienia (po jego załadowaniu)
function getDescription(name) {
  return (DESCRIPTIONS[getShardKey(name)] || {})[name] || "";
}

// Pobiera informację o źródle z jakiego został pobrany dany opis
function getDescriptionSource(name) {
  return (DESCRIPTION_SOURCES[getShardKey(name)] || {})[name] || "";
}

// Wstawia opis do elementu DOM w rozwiniętym wierszu tabeli
function fillDescription(scope, name) {
  var d = scope.querySelector('[data-opis-imie="' + escapeHtml(name) + '"]');
  if (!d) return;
  
  var o = getDescription(name);
  d.innerHTML = o || DESCRIPTION_MISSING;
  
  var sp = scope.querySelector('[data-src-imie="' + escapeHtml(name) + '"]');
  if (sp) {
    if (o) {
      sp.innerHTML = getDescriptionSourceLink(name);
      sp.style.display = "";
    } else {
      sp.style.display = "none";
    }
  }
}
