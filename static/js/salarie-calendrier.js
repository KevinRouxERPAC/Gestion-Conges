document.addEventListener("DOMContentLoaded", function () {
  var cb = document.getElementById("voir-tous");
  if (cb) {
    cb.addEventListener("change", function () {
      window.location.href = this.checked ? this.dataset.urlTous : this.dataset.urlMoi;
    });
  }

  var dataEl = document.getElementById("calendar-events-data");
  var eventsData = dataEl ? JSON.parse(dataEl.textContent) : [];

  var typeColors = {
    CP: "#008C3A",
    "Sans solde": "#f59e0b",
    RTT: "#9333ea",
    default: "#6b7280",
  };

  function getDisplayType(type) {
    return type === "CP" ? "Congés" : type;
  }

  function mapToCalendarEvents(list) {
    return list.map(function (e) {
      var endDate = new Date(e.end);
      endDate.setDate(endDate.getDate() + 1);

      var isEnAttente = e.statut === "en_attente_responsable" || e.statut === "en_attente_rh";
      var color = typeColors[e.type] || typeColors.default;
      var displayType = getDisplayType(e.type);

      var isRTT = e.type === "RTT";
      var unitTextValide = isRTT ? (e.heures_rtt || 0) + " h" : e.jours + " jour(s)";
      var unitTextAttente = isRTT ? (e.heures_rtt || 0) + " h" : e.jours + " j";

      var baseTitle = isEnAttente
        ? displayType + " - " + unitTextAttente + " (en attente)"
        : displayType + " - " + unitTextValide;

      var title = e.salarie ? e.salarie + " - " + baseTitle : baseTitle;

      return {
        title: title,
        start: e.start,
        end: endDate.toISOString().split("T")[0],
        backgroundColor: isEnAttente ? "#fef3c7" : color,
        borderColor: isEnAttente ? "#f59e0b" : color,
        textColor: isEnAttente ? "#92400e" : "#fff",
        extendedProps: { type: e.type, jours: e.jours, heures_rtt: e.heures_rtt, statut: e.statut || "valide" },
      };
    });
  }

  var calendarEl = document.getElementById("calendar-salarie");
  if (!calendarEl || typeof FullCalendar === "undefined") return;

  var yearEl = document.getElementById("calendar-year");
  var requestedYear = yearEl ? parseInt(yearEl.textContent, 10) : new Date().getFullYear();
  var currentYear = new Date().getFullYear();
  var initialDate = currentYear === requestedYear ? new Date() : new Date(requestedYear, 0, 1);

  var calendar = new FullCalendar.Calendar(calendarEl, {
    initialView: "dayGridMonth",
    locale: "fr",
    firstDay: 1,
    headerToolbar: {
      left: "prev,next today",
      center: "title",
      right: "dayGridMonth",
    },
    buttonText: {
      today: "Aujourd'hui",
      month: "Mois",
    },
    events: [],
    initialDate: initialDate,
    height: "auto",
    eventClick: function (info) {
      info.jsEvent.preventDefault();
    },
  });

  calendar.render();

  var typeInputs = Array.from(document.querySelectorAll('input[name="type_filter"]'));
  function getSelectedTypes() {
    var selected = new Set();
    typeInputs.forEach(function (el) {
      if (el.checked) selected.add(el.value);
    });
    return selected;
  }

  function applyTypeFilters() {
    var selected = getSelectedTypes();
    var selectedSize = selected.size;

    document.querySelectorAll("tr[data-type]").forEach(function (row) {
      var t = row.getAttribute("data-type");
      row.hidden = selectedSize > 0 ? !selected.has(t) : true;
    });

    var filteredEvents = selectedSize > 0 ? eventsData.filter(function (e) { return selected.has(e.type); }) : [];
    calendar.removeAllEvents();
    calendar.addEventSource(mapToCalendarEvents(filteredEvents));
  }

  typeInputs.forEach(function (el) {
    el.addEventListener("change", applyTypeFilters);
  });
  applyTypeFilters();
});
