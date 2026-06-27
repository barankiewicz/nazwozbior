// ── Funkcje pomocnicze i narzędziowe ──

"use strict";

// Formatowanie liczby według polskiego formatu (np. 1 234 567)
function formatNumber(n) {
  return (n || 0).toLocaleString("pl-PL");
}

// Zabezpieczenie przed atakami XSS poprzez ucieczkę znaków HTML
function escapeHtml(s) {
  return String(s).replace(/[&<>]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c];
  });
}

// Określenie odpowiedniej polskiej formy rzeczownika "imię" dla danej liczby
function pluralForm(n) {
  var a = n % 10, b = n % 100;
  if (n === 1) return "imię";
  if (a >= 2 && a <= 4 && !(b >= 12 && b <= 14)) return "imiona";
  return "imion";
}

// Pobranie etykiety pochodzenia (zwraca nazwę z konfiguracji lub "nieokreślone")
function getOriginLabel(o) {
  return o ? (ORIGIN_LABELS[o] || o) : "nieokreślone";
}

// Przypisanie klasy CSS na podstawie skrótu pochodzenia (do celów kolorowania)
function getOriginClass(o) {
  if (!o) return "o-none";
  var s = 0;
  for (var i = 0; i < o.length; i++) s += o.charCodeAt(i);
  return "o" + (s % 6);
}

// Pobranie etykiety pochodzenia dla imion niebinarnych (obsługuje opis z bazy)
function getNbOriginLabel(r) {
  return r.pochodzenie ? getOriginLabel(r.pochodzenie) : (r.pochodzenie_opis || "nieokreślone");
}

// Obliczenie łącznej liczby wystąpień imienia w PESEL (jako pierwsze i drugie)
function totalCount(r) {
  return r._sort_wystapienia_razem || 0;
}

// Zoptymalizowane cache'owanie klasy CSS pochodzenia
function getOriginClassCached(r) {
  if (r._originClass === undefined) {
    r._originClass = getOriginClass(r.pochodzenie);
  }
  return r._originClass;
}

// Zoptymalizowane cache'owanie sformatowanych liczb
function getFmtRejz(r) {
  if (r._fmt_rejz === undefined) {
    r._fmt_rejz = formatNumber(r._rzp + r._rzd);
  }
  return r._fmt_rejz;
}

function getFmtRejm(r) {
  if (r._fmt_rejm === undefined) {
    r._fmt_rejm = formatNumber(r._rmp + r._rmd);
  }
  return r._fmt_rejm;
}

function getFmtW1(r) {
  if (r._fmt_w1 === undefined) {
    r._fmt_w1 = formatNumber(r.wystapienia_pierwsze || 0);
  }
  return r._fmt_w1;
}

function getFmtW2(r) {
  if (r._fmt_w2 === undefined) {
    r._fmt_w2 = formatNumber(r.wystapienia_drugie || 0);
  }
  return r._fmt_w2;
}

function getFmtTotal(r) {
  if (r._fmt_total === undefined) {
    r._fmt_total = formatNumber(totalCount(r));
  }
  return r._fmt_total;
}

// Zwraca wartość danego rekordu dla wybranego klucza sortowania
function getSortValue(r, key) {
  var k = "_sort_" + key;
  if (k in r) return r[k];
  if (key === "wystapienia_razem") return totalCount(r);
  return r[key] || 0;
}

// Wyznaczenie klucza sharda (pierwszej litery) dla leniwego ładowania opisu
function getShardKey(name) {
  var c = (name[0] || '_').toLowerCase();
  c = SHARD_MAP[c] || c;
  return /^[a-z]$/.test(c) ? c : '_';
}

// Generowanie linku do zewnętrznego źródła na podstawie pochodzenia rekordu opisowego
function getDescriptionSourceLink(name) {
  var src = getDescriptionSource(name);
  var n = encodeURIComponent(name);
  if (src === "EN") return 'źródło: <a href="https://en.wikipedia.org/wiki/' + n + '" target="_blank" rel="noopener noreferrer">angielska Wikipedia</a> <span style="opacity:.6">(tłum. automatyczne)</span>';
  if (src === "UK") return 'źródło: <a href="https://uk.wikipedia.org/wiki/' + n + '" target="_blank" rel="noopener noreferrer">ukraińska Wikipedia</a> <span style="opacity:.6">(tłum. automatyczne)</span>';
  if (src === "RU") return 'źródło: <a href="https://ru.wikipedia.org/wiki/' + n + '" target="_blank" rel="noopener noreferrer">rosyjska Wikipedia</a> <span style="opacity:.6">(tłum. automatyczne)</span>';
  if (src === "VI") return 'źródło: <a href="https://vi.wikipedia.org/wiki/' + n + '" target="_blank" rel="noopener noreferrer">wietnamska Wikipedia</a> <span style="opacity:.6">(tłum. automatyczne)</span>';
  return 'źródło: <a href="https://pl.wikipedia.org/wiki/' + n + '" target="_blank" rel="noopener noreferrer">polska Wikipedia</a>';
}
