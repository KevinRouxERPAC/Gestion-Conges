(function () {
  function initCongeForm() {
    var typeCongeEl = document.getElementById("type_conge");
    if (!typeCongeEl) return;

    var rttHeuresEl = document.getElementById("nb_heures_rtt");
    var rttBlock = rttHeuresEl ? rttHeuresEl.closest("div") : null;

    var blocHeuresExc = document.getElementById("bloc_heures_exceptionnelles");
    var heuresExcEl = document.getElementById("nb_heures_exceptionnelles");

    function isExceptionalType(value) {
      return typeof value === "string" && value.indexOf("EXC:") === 0;
    }

    function refresh() {
      var opt = typeCongeEl.selectedOptions ? typeCongeEl.selectedOptions[0] : null;
      var val = typeCongeEl.value || "";
      var unite = opt ? (opt.getAttribute("data-unite") || "") : "";

      var isRTT = val === "RTT";
      if (rttBlock) {
        rttBlock.classList.toggle("hidden", !isRTT);
      }
      if (rttHeuresEl) {
        rttHeuresEl.required = isRTT;
        if (!isRTT) rttHeuresEl.value = "";
      }

      var isExcHeures = isExceptionalType(val) && unite === "heures";
      if (blocHeuresExc) {
        blocHeuresExc.classList.toggle("hidden", !isExcHeures);
      }
      if (heuresExcEl) {
        heuresExcEl.required = isExcHeures;
        if (!isExcHeures) heuresExcEl.value = "";
      }
    }

    typeCongeEl.addEventListener("change", refresh);
    refresh();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCongeForm);
  } else {
    initCongeForm();
  }
})();
