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

    // Web Push : enregistrement du Service Worker et bouton "Activer les alertes"
    if (document.querySelector('.erpac-push-enable')) {
        initWebPush();
    }
});

function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

function initWebPush() {
    const btn = document.querySelector('.erpac-push-enable');
    if (!btn || !('serviceWorker' in navigator) || !('PushManager' in window)) {
        if (btn) btn.style.display = 'none';
        return;
    }

    navigator.serviceWorker.register('/sw.js')
        .then(function(reg) {
            window._erpacSwReg = reg;
            btn.addEventListener('click', function() { subscribeUser(reg); });
            checkExistingSubscription(reg);
        })
        .catch(function() {
            if (btn) btn.style.display = 'none';
        });
}

function checkExistingSubscription(reg) {
    reg.pushManager.getSubscription().then(function(sub) {
        var btn = document.querySelector('.erpac-push-enable');
        if (sub && btn) btn.style.display = 'none';
    });
}

function subscribeUser(reg) {
    var btn = document.querySelector('.erpac-push-enable');
    if (!btn) return;
    if (Notification.permission === 'denied') {
        alert('Les notifications ont été bloquées. Autorisez-les dans les paramètres du navigateur pour ce site.');
        return;
    }
    if (Notification.permission === 'granted') {
        doSubscribe(reg, btn);
        return;
    }
    Notification.requestPermission().then(function(perm) {
        if (perm === 'granted') {
            doSubscribe(reg, btn);
        } else if (perm === 'denied' && btn) {
            btn.textContent = 'Notifications bloquées';
        }
    });
}

function doSubscribe(reg, btn) {
    fetch('/notifications/vapid-public')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var vapidKey = data.vapid_public_key;
            if (!vapidKey) {
                if (btn) btn.textContent = 'Alertes non configurées';
                return;
            }
            return reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(vapidKey)
            });
        })
        .then(function(subscription) {
            if (!subscription) return;
            var body = {
                endpoint: subscription.endpoint,
                keys: {
                    p256dh: btoa(String.fromCharCode.apply(null, new Uint8Array(subscription.getKey('p256dh')))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''),
                    auth: btoa(String.fromCharCode.apply(null, new Uint8Array(subscription.getKey('auth')))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
                }
            };
            return fetch('/notifications/push-subscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
                credentials: 'same-origin'
            }).then(function(res) {
                if (res.ok && btn) {
                    btn.textContent = 'Alertes activées';
                    btn.style.display = 'none';
                }
            });
        })
        .catch(function(err) {
            if (btn) btn.textContent = 'Erreur, réessayez';
            console.warn('Web Push subscribe error', err);
        });
}
