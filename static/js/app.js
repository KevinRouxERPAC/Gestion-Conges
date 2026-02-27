// ERPAC Gestion des Congés - App JS

function getCSRFToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}
document.addEventListener('DOMContentLoaded', function() {
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

    // Anti double-soumission : désactive le bouton après le premier clic
    document.querySelectorAll('form').forEach(function(form) {
        form.addEventListener('submit', function() {
            var btns = form.querySelectorAll('button[type="submit"], input[type="submit"]');
            btns.forEach(function(btn) {
                btn.disabled = true;
                btn.classList.add('opacity-50', 'cursor-not-allowed');
            });
            setTimeout(function() {
                btns.forEach(function(btn) { btn.disabled = false; btn.classList.remove('opacity-50', 'cursor-not-allowed'); });
            }, 5000);
        });
    });

    // Web Push : enregistrement du Service Worker et bouton "Activer les alertes"
    if (document.querySelector('.erpac-push-enable')) {
        initWebPush();
    }

    // Rafraîchissement du badge notifications (toutes les 12 s) pour voir les nouvelles demandes sans recharger
    var badge = document.getElementById('nav-notif-badge') || document.querySelector('.nav-notif-btn .rounded-full');
    if (badge && document.querySelector('.nav-notif-btn')) {
        var prevCount = null;
        function pollNotif() {
            fetch('/notifications/count', { credentials: 'same-origin' })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var c = data.count || 0;
                    if (prevCount !== null && c > prevCount) {
                        var toast = document.createElement('div');
                        toast.setAttribute('role', 'alert');
                        toast.style.cssText = 'position:fixed; top:80px; left:50%; transform:translateX(-50%); z-index:99999; background:#008C3A; color:#fff; padding:14px 24px; border-radius:12px; box-shadow:0 10px 40px rgba(0,0,0,0.2); display:flex; align-items:center; gap:12px; max-width:90%; font-size:15px;';
                        toast.innerHTML = '<a href="/notifications/" style="color:inherit; text-decoration:underline; font-weight:600;">Nouvelle(s) notification(s) – cliquer pour voir</a><button type="button" style="background:transparent; border:none; color:rgba(255,255,255,0.9); font-size:22px; line-height:1; cursor:pointer; padding:0 0 0 8px;" onclick="this.parentElement.remove()" aria-label="Fermer">&times;</button>';
                        document.body.appendChild(toast);
                        setTimeout(function() { if (toast.parentElement) toast.remove(); }, 8000);
                    }
                    prevCount = c;
                    badge.textContent = c > 99 ? '99+' : c;
                    badge.classList.toggle('hidden', c === 0);
                })
                .catch(function() {});
        }
        pollNotif();
        setInterval(pollNotif, 12000);
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
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken() },
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
