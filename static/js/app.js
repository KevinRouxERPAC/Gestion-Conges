// ERPAC Gestion des Congés - App JS
document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss flash messages after 5 seconds
    const alerts = document.querySelectorAll('[x-data="{ show: true }"]');
    // Handled by Alpine.js

    // Date validation on forms
    const dateDebut = document.getElementById('date_debut');
    const dateFin = document.getElementById('date_fin');

    if (dateDebut && dateFin) {
        dateDebut.addEventListener('change', function() {
            dateFin.min = this.value;
            if (dateFin.value && dateFin.value < this.value) {
                dateFin.value = this.value;
            }
        });
    }
});
