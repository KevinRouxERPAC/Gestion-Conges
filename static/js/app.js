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

    // Confirmation ERPAC accessible pour les actions destructives ou longues.
    var confirmDialog = document.getElementById('erpac-confirm');
    var confirmMessage = document.getElementById('erpac-confirm-message');
    var confirmPanel = confirmDialog ? confirmDialog.querySelector('[role="dialog"]') : null;
    var confirmForm = null;
    var confirmTrigger = null;
    function closeConfirm() {
        if (!confirmDialog) return;
        confirmDialog.hidden = true;
        confirmDialog.setAttribute('aria-hidden', 'true');
        if (confirmTrigger) confirmTrigger.focus();
        confirmForm = null;
    }
    function openConfirm(form) {
        if (!confirmDialog || !confirmPanel) return false;
        confirmForm = form;
        confirmTrigger = document.activeElement;
        confirmMessage.textContent = form.getAttribute('data-confirm') || 'Confirmer cette action ?';
        confirmDialog.hidden = false;
        confirmDialog.setAttribute('aria-hidden', 'false');
        confirmPanel.focus();
        return true;
    }
    document.addEventListener('submit', function(e) {
        var form = e.target;
        if (!form || !form.hasAttribute || !form.hasAttribute('data-confirm') || form.dataset.confirmed === 'true') return;
        e.preventDefault();
        e.stopPropagation();
        openConfirm(form);
    }, true);
    if (confirmDialog) {
        confirmDialog.querySelector('[data-confirm-ok]').addEventListener('click', function() {
            if (!confirmForm) return;
            confirmForm.dataset.confirmed = 'true';
            closeConfirm();
            confirmForm.requestSubmit();
        });
        confirmDialog.querySelectorAll('[data-confirm-cancel]').forEach(function(el) { el.addEventListener('click', closeConfirm); });
        confirmDialog.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') { e.preventDefault(); closeConfirm(); return; }
            if (e.key !== 'Tab') return;
            var focusables = confirmDialog.querySelectorAll('button:not([disabled])');
            if (!focusables.length) return;
            var first = focusables[0];
            var last = focusables[focusables.length - 1];
            if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
            else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
        });
    }

    // CSP : navigation de ligne via data-row-href (remplace onclick/onkeydown inline sur <tr>).
    // Un clic sur un lien/bouton interne (cellule "Actions") ne déclenche pas la navigation.
    document.addEventListener('click', function(e) {
        var row = e.target.closest('[data-row-href]');
        if (!row) return;
        if (e.target.closest('a, button, input, label')) return;
        window.location.href = row.getAttribute('data-row-href');
    });
    document.addEventListener('keydown', function(e) {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        var row = e.target.closest('[data-row-href]');
        if (row && e.target === row) {
            e.preventDefault();
            window.location.href = row.getAttribute('data-row-href');
        }
    });

    document.querySelectorAll('[data-progress]').forEach(function (bar) {
        var value = Math.max(0, Math.min(100, Number(bar.getAttribute('data-progress')) || 0));
        bar.style.setProperty('--erp-progress', value + '%');
    });

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

    // PWA : enregistrement du Service Worker pour le cache hors-ligne, sur toutes les pages.
    // Le SW gère aussi le Web Push : on s'assure qu'il est actif même sans bouton push présent.
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', function () {
            navigator.serviceWorker.register('/sw.js').catch(function (err) {
                console.warn('SW registration failed', err);
            });
        });
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
                        toast.className = 'erpac-live-toast';
                        toast.innerHTML = '<a href="/notifications/">Nouvelle(s) notification(s) – cliquer pour voir</a><button type="button" aria-label="Fermer">&times;</button>';
                        // CSP : pas de onclick inline ; on attache l'écouteur de fermeture programmatiquement.
                        var tClose = toast.querySelector('button');
                        if (tClose) { tClose.addEventListener('click', function() { toast.remove(); }); }
                        document.body.appendChild(toast);
                        setTimeout(function() { if (toast.parentElement) toast.remove(); }, 8000);
                    }
                    prevCount = c;
                    badge.textContent = c > 99 ? '99+' : c;
                    badge.classList.toggle('hidden', c === 0);
                })
                .catch(function() {});
        }
        var pollTimer;
        function schedulePoll() {
            if (pollTimer) clearTimeout(pollTimer);
            if (document.visibilityState === 'visible') {
                pollTimer = setTimeout(function () { pollNotif(); schedulePoll(); }, 12000);
            }
        }
        pollNotif();
        schedulePoll();
        document.addEventListener('visibilitychange', function () {
            if (document.visibilityState === 'visible') { pollNotif(); schedulePoll(); }
        });
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

    // Réutilise l'enregistrement SW déjà fait par app.js (PWA) plutôt qu'un doublon.
    navigator.serviceWorker.ready
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
