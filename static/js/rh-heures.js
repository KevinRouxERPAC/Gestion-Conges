(function () {
  var form = document.getElementById("weekly-hours-form");
  if (!form) return;

  var inputs = Array.from(document.querySelectorAll(".grid-input"));
  var errorCountEl = document.getElementById("error-count");
  var filledCountEl = document.getElementById("filled-count");
  var confirmCheckbox = document.getElementById("confirm-validate-checkbox");
  var confirmValidateInput = document.getElementById("confirm_validate_input");
  var validateBtn = document.getElementById("validate-btn");

  function parseVal(input) {
    if (!input || input.value.trim() === "") return 0;
    return Number(input.value.replace(",", ".")) || 0;
  }

  function validateRows() {
    var rows = Array.from(document.querySelectorAll("tr[data-user-row]"));
    var errorRows = 0;
    var filledRows = 0;

    rows.forEach(function (row) {
      var prevuesInput = row.querySelector('input[name$="_heures_prevues"]');
      var travailleesInput = row.querySelector('input[name$="_heures_travaillees"]');
      var supInput = row.querySelector('input[name$="_heures_sup"]');
      var trajetInput = row.querySelector('input[name$="_heures_trajet"]');
      var absenceInput = row.querySelector('input[name$="_heures_absence"]');

      var values = {
        prevues: parseVal(prevuesInput),
        travaillees: parseVal(travailleesInput),
        sup: parseVal(supInput),
        trajet: parseVal(trajetInput),
        absence: parseVal(absenceInput),
      };

      var isFilled = values.travaillees > 0 || values.sup > 0 || values.trajet > 0 || values.absence > 0;
      if (isFilled) filledRows += 1;

      // Calcul auto H sup côté front (option A)
      // H sup auto = H travaillées - 34,65 (peut être négatif)
      // On recalcule si le champ est vide ou vaut 0/0,00 (valeur par défaut non modifiée).
      if (travailleesInput && supInput) {
        var baseHebdo = 34.65;
        var currentRaw = (supInput.value || "").trim();
        var isDefaultZero =
          currentRaw === "" ||
          currentRaw === "0" ||
          currentRaw === "0,00" ||
          currentRaw === "0.0";
        if (isDefaultZero) {
          var autoSup = values.travaillees - baseHebdo;
          supInput.value = (Math.round(autoSup * 100) / 100).toFixed(2);
          values.sup = parseVal(supInput);
        }
      }

      var hasNegative = Object.values(values).some(function (v) { return v < 0; });
      var overflow = Object.values(values).some(function (v) { return v > 80; });
      var incoherent = (values.travaillees + values.absence) > (values.prevues + values.sup + 1);
      var isError = hasNegative || overflow || incoherent;

      row.classList.toggle("bg-red-50", isError);
      row.classList.toggle("border-red-200", isError);
      if (isError) errorRows += 1;

      var ecart = (values.travaillees + values.absence) - (values.prevues + values.sup);
      var ecartCell = row.querySelector(".row-ecart");
      if (ecartCell) {
        ecartCell.textContent = (Math.round(ecart * 100) / 100).toFixed(2);
        ecartCell.classList.toggle("text-red-600", ecart > 1);
        ecartCell.classList.toggle("text-green-700", ecart <= 1);
      }
    });

    if (errorCountEl) errorCountEl.textContent = String(errorRows);
    if (filledCountEl) filledCountEl.textContent = String(filledRows);
    if (validateBtn) validateBtn.disabled = errorRows > 0;
    return errorRows;
  }

  inputs.forEach(function (input) {
    input.addEventListener("input", validateRows);
    input.addEventListener("keydown", function (e) {
      if (!["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)) return;
      var active = document.activeElement;
      var all = inputs.filter(function (x) { return !x.disabled; });
      var index = all.indexOf(active);
      if (index < 0) return;
      e.preventDefault();
      var cols = 5;
      var nextIndex = index;
      if (e.key === "ArrowRight") nextIndex = Math.min(all.length - 1, index + 1);
      if (e.key === "ArrowLeft") nextIndex = Math.max(0, index - 1);
      if (e.key === "ArrowDown") nextIndex = Math.min(all.length - 1, index + cols);
      if (e.key === "ArrowUp") nextIndex = Math.max(0, index - cols);
      all[nextIndex].focus();
      all[nextIndex].select();
    });
  });

  form.addEventListener("submit", function (e) {
    var submitter = e.submitter;
    if (!submitter) return;
    var action = submitter.value;
    var errors = validateRows();
    if (errors > 0) {
      e.preventDefault();
      erpacAlert("Corrigez les lignes en erreur avant de continuer.", { title: "Erreur de saisie" });
      return;
    }
    if (action === "validate") {
      var confirmed = Boolean(confirmCheckbox && confirmCheckbox.checked);
      if (!confirmed) {
        e.preventDefault();
        erpacAlert("Cochez la confirmation pour valider et verrouiller la semaine.", { title: "Confirmation requise" });
        return;
      }
      if (confirmValidateInput) confirmValidateInput.value = "1";
    }
  });

  validateRows();
})();
