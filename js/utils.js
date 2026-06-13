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
  return r._g === "nb" || r._g === "uni"
    ? (r._rzp + r._rzd + r._rmp + r._rmd)
    : ((r.wystapienia_pierwsze || 0) + (r.wystapienia_drugie || 0));
}

// Zwraca wartość danego rekordu dla wybranego klucza sortowania
function getSortValue(r, key) {
  if (key === "dlugosc") return r.imie.length;
  if (key === "imie") return r.imie.toLowerCase();
  if (key === "pochodzenie") return (r._g === "nb" || r._g === "uni") ? getNbOriginLabel(r) : getOriginLabel(r.pochodzenie);
  if (key === "wystapienia_razem") return totalCount(r);
  if (key === "rejz") return r._rzp + r._rzd;
  if (key === "rejm") return r._rmp + r._rmd;
  if (key === "ratio_nb") {
    var z = r._rzp + r._rzd, m = r._rmp + r._rmd, t = z + m;
    return t ? z / t : 0;
  }
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
