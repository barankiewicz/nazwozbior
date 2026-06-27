// ── Eksport danych w formacie CSV ──

"use strict";

// Generowanie pliku CSV dla aktualnie widocznych wyników wyszukiwania i filtrów
document.getElementById("csv-btn").addEventListener("click", function () {
  var all = getSortedFiltered();
  if (!all.length) return;
  
  var shown = showAll ? all : all.slice(currentPage * PER_PAGE, currentPage * PER_PAGE + PER_PAGE);
  var nb = state.g === "nb", uni = state.g === "uni";
  
  // Wstawienie BOM (Byte Order Mark) ułatwia aplikacjom rozpoznanie kodowania UTF-8
  var csv = nb || uni 
    ? "\uFEFFimię,długość,pochodzenie,znaczenie,rejestr żeński,rejestr męski,ż%,m%\n"
    : "\uFEFFimię,długość,pochodzenie,pierwsze,drugie,łącznie\n";
    
  shown.forEach(function (r) {
    if (nb || uni) {
      var zCsv = r._rzp + r._rzd, mCsv = r._rmp + r._rmd, tCsv = zCsv + mCsv;
      var zPctCsv = tCsv ? Math.round(zCsv / tCsv * 100) : 0;
      csv += '"' + r.imie + '",' + r.imie.length + ',"' + getNbOriginLabel(r).replace(/"/g, '""') + '","' + (r.znaczenie || "").replace(/"/g, '""') + '",' + zCsv + "," + mCsv + "," + zPctCsv + "," + (100 - zPctCsv) + "\n";
      return;
    }
    var o = getOriginLabel(r.pochodzenie);
    csv += '"' + r.imie + '",' + r.imie.length + ',"' + o + '",' + (r.wystapienia_pierwsze || 0) + "," + (r.wystapienia_drugie || 0) + "," + ((r.wystapienia_pierwsze || 0) + (r.wystapienia_drugie || 0)) + "\n";
  });
  
  var blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "nazwozbior.csv";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
});
