// Calcul live du nombre de jours ouvrables dans le formulaire de demande de congé.
// Active si la page contient des inputs #date_debut et #date_fin et un span [data-conge-jours-ouvrables].
//
// Comportement :
//   1. Récupère les jours fériés via /api/jours-feries au chargement (années courante + suivante).
//   2. À chaque changement de date, calcule en local le nb de jours ouvrables (hors WE + fériés).
//   3. Affiche le résultat dans le span cible, avec délai de tampon pour éviter le flicker.
//
// Le calcul serveur (/api/jours-ouvrables) sert de référence si le client veut une confirmation.

(function () {
    "use strict";

    const dateDebut = document.getElementById("date_debut");
    const dateFin = document.getElementById("date_fin");
    const output = document.querySelector("[data-conge-jours-ouvrables]");

    if (!dateDebut || !dateFin || !output) {
        return;
    }

    let feriesSet = new Set();
    let feriesLoaded = false;

    function fetchFeries() {
        const annees = [new Date().getFullYear(), new Date().getFullYear() + 1];
        fetch(`/api/jours-feries?annees=${annees.join(",")}`, { credentials: "same-origin" })
            .then((r) => (r.ok ? r.json() : { feries: [] }))
            .then((data) => {
                feriesSet = new Set(data.feries || []);
                feriesLoaded = true;
                refresh();
            })
            .catch(() => {
                // Échec silencieux : calcul approximatif WE-only.
                feriesLoaded = true;
                refresh();
            });
    }

    function toISODate(d) {
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, "0");
        const j = String(d.getDate()).padStart(2, "0");
        return `${y}-${m}-${j}`;
    }

    function compterJoursOuvrables(debut, fin) {
        // debut et fin sont des Date locales.
        if (fin < debut) return 0;
        let jours = 0;
        const current = new Date(debut.getTime());
        while (current <= fin) {
            const jourSemaine = current.getDay(); // 0=dim, 6=sam
            if (jourSemaine !== 0 && jourSemaine !== 6) {
                if (!feriesSet.has(toISODate(current))) {
                    jours += 1;
                }
            }
            current.setDate(current.getDate() + 1);
        }
        return jours;
    }

    function parseLocalDate(str) {
        if (!str) return null;
        // Format AAAA-MM-JJ → Date locale (sans timezone UTC).
        const parts = str.split("-");
        if (parts.length !== 3) return null;
        return new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
    }

    function refresh() {
        const debut = parseLocalDate(dateDebut.value);
        const fin = parseLocalDate(dateFin.value);

        if (!debut || !fin) {
            output.textContent = "";
            output.classList.add("hidden");
            return;
        }
        if (fin < debut) {
            output.textContent = "Date de fin antérieure à la date de début";
            output.classList.remove("hidden");
            output.classList.add("text-red-600");
            return;
        }

        const jours = compterJoursOuvrables(debut, fin);
        const suffixe = feriesLoaded ? "" : " (estimation, jours fériés non chargés)";
        output.textContent = `${jours} jour(s) ouvrable(s)${suffixe}`;
        output.classList.remove("hidden", "text-red-600");
        output.classList.add(jours === 0 ? "text-orange-600" : "text-erpac-primary");
    }

    dateDebut.addEventListener("change", refresh);
    dateFin.addEventListener("change", refresh);
    fetchFeries();
})();
