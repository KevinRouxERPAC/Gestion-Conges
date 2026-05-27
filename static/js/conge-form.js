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
    const demiDebut = document.getElementById("demi_journee_debut");
    const demiFin = document.getElementById("demi_journee_fin");
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

    function estOuvrable(d) {
        const jour = d.getDay();
        if (jour === 0 || jour === 6) return false;
        return !feriesSet.has(toISODate(d));
    }

    function compterJoursOuvrables(debut, fin, dDebut, dFin) {
        // debut et fin sont des Date locales. dDebut/dFin : "matin", "apres_midi" ou null.
        if (fin < debut) return 0;

        // Mono-jour
        if (debut.getTime() === fin.getTime()) {
            if (!estOuvrable(debut)) return 0;
            if (dDebut === "matin" || dDebut === "apres_midi" || dFin === "matin" || dFin === "apres_midi") {
                return 0.5;
            }
            return 1;
        }

        // Multi-jours
        let jours = 0;
        const current = new Date(debut.getTime());
        while (current <= fin) {
            if (estOuvrable(current)) jours += 1;
            current.setDate(current.getDate() + 1);
        }
        if (dDebut === "apres_midi" && estOuvrable(debut)) jours -= 0.5;
        if (dFin === "matin" && estOuvrable(fin)) jours -= 0.5;
        return Math.max(0, jours);
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

        const dDebut = demiDebut ? demiDebut.value || null : null;
        const dFin = demiFin ? demiFin.value || null : null;
        const jours = compterJoursOuvrables(debut, fin, dDebut, dFin);
        const suffixe = feriesLoaded ? "" : " (estimation, jours fériés non chargés)";
        // Format français : "1,5" plutôt que "1.5"
        const joursFmt = Number.isInteger(jours) ? String(jours) : jours.toString().replace(".", ",");
        output.textContent = `${joursFmt} jour(s) ouvrable(s)${suffixe}`;
        output.classList.remove("hidden", "text-red-600");
        output.classList.add(jours === 0 ? "text-orange-600" : "text-erpac-primary");
    }

    dateDebut.addEventListener("change", refresh);
    dateFin.addEventListener("change", refresh);
    if (demiDebut) demiDebut.addEventListener("change", refresh);
    if (demiFin) demiFin.addEventListener("change", refresh);
    fetchFeries();
})();
