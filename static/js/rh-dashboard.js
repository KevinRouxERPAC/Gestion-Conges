document.addEventListener("DOMContentLoaded", function () {
  var dataEl = document.getElementById("calendar-events-data-rh");
  var eventsData = dataEl ? JSON.parse(dataEl.textContent) : [];

  var typeColors = {
    CP: "#008C3A",
    RTT: "#9333ea",
    Maladie: "#ef4444",
    Anciennete: "#16a34a",
    default: "#6b7280",
  };

  var calendarEvents = eventsData.map(function (e) {
    var endDate = new Date(e.end);
    endDate.setDate(endDate.getDate() + 1);
    return {
      title: e.user + " - " + e.type_conge,
      start: e.start,
      end: endDate.toISOString().split("T")[0],
      backgroundColor: typeColors[e.type_conge] || typeColors.default,
      borderColor: typeColors[e.type_conge] || typeColors.default,
      extendedProps: { user: e.user, type: e.type_conge },
    };
  });

  var calendarEl = document.getElementById("calendar-rh");
  if (!calendarEl || typeof FullCalendar === "undefined") return;

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
    events: calendarEvents,
    height: "auto",
  });
  calendar.render();
});
