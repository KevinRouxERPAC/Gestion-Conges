// ERPAC Gestion des Congés - App JS

// --- Modale confirm / alert (remplace les dialogues natifs) ---
var _erpacModalResolve = null;

function erpacModal() {
    return {
        open: false,
        mode: 'confirm',
        title: '',
        message: '',
        okLabel: 'OK',
        danger: false,
        show(opts) {
            this.title = opts.title || 'Confirmation';
            this.message = opts.message || '';
            this.mode = opts.mode || 'confirm';
            this.okLabel = opts.okLabel || (this.mode === 'alert' ? 'OK' : 'Confirmer');
            this.danger = opts.danger || false;
            this.open = true;
            var self = this;
            this.$nextTick(function() { if (self.$refs.okBtn) self.$refs.okBtn.focus(); });
        },
        ok()     { this.open = false; if (_erpacModalResolve) _erpacModalResolve(true);  _erpacModalResolve = null; },
        cancel() { this.open = false; if (_erpacModalResolve) _erpacModalResolve(false); _erpacModalResolve = null; },
    };
}

function erpacConfirm(message, opts) {
    opts = opts || {};
    return new Promise(function(resolve) {
        _erpacModalResolve = resolve;
        var el = document.getElementById('erpac-modal');
        if (!el || !el.__x) { console.warn('Modal indisponible pour confirmation.'); resolve(false); return; }
        el.__x.$data.show({
            mode: 'confirm',
            title: opts.title || 'Confirmation',
            message: message,
            okLabel: opts.okLabel || 'Confirmer',
            danger: opts.danger !== undefined ? opts.danger : true,
        });
    });
}

function erpacAlert(message, opts) {
    opts = opts || {};
    return new Promise(function(resolve) {
        _erpacModalResolve = resolve;
        var el = document.getElementById('erpac-modal');
        if (!el || !el.__x) { console.warn('Modal indisponible pour alerte:', message); resolve(true); return; }
        el.__x.$data.show({
            mode: 'alert',
            title: opts.title || 'Information',
            message: message,
            okLabel: opts.okLabel || 'OK',
            danger: false,
        });
    });
}

function getCSRFToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}
document.addEventListener('DOMContentLoaded', function() {
    // Interception globale des formulaires avec data-confirm
    document.addEventListener('submit', function(e) {
        var form = e.target;
        var msg = form.getAttribute('data-confirm');
        if (!msg) return;
        if (form._erpacConfirmed) { form._erpacConfirmed = false; return; }
        e.preventDefault();
        erpacConfirm(msg).then(function(ok) {
            if (ok) { form._erpacConfirmed = true; form.submit(); }
        });
    }, true);

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

    // Accessibilite formulaires: lie les erreurs natives aux champs (aria-invalid/aria-describedby)
    function buildFieldErrorId(field) {
        var baseId = field.id || field.name || 'field';
        return String(baseId).replace(/[^a-zA-Z0-9_-]/g, '_') + '-error';
    }

    function ensureFieldId(field) {
        if (!field.id) {
            field.id = String(field.name || 'field').replace(/[^a-zA-Z0-9_-]/g, '_');
        }
    }

    function setFieldInvalid(field, message) {
        if (!field || !field.willValidate) return;
        ensureFieldId(field);
        var errorId = buildFieldErrorId(field);
        var errorEl = document.getElementById(errorId);
        if (!errorEl) {
            errorEl = document.createElement('p');
            errorEl.id = errorId;
            errorEl.className = 'mt-1 text-xs text-red-600';
            field.insertAdjacentElement('afterend', errorEl);
        }
        errorEl.textContent = message || field.validationMessage || 'Valeur invalide.';
        field.setAttribute('aria-invalid', 'true');
        var describedBy = (field.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean);
        if (describedBy.indexOf(errorId) === -1) describedBy.push(errorId);
        field.setAttribute('aria-describedby', describedBy.join(' '));
    }

    function clearFieldInvalid(field) {
        if (!field) return;
        var errorId = buildFieldErrorId(field);
        var errorEl = document.getElementById(errorId);
        if (errorEl) errorEl.remove();
        field.removeAttribute('aria-invalid');
        var describedBy = (field.getAttribute('aria-describedby') || '').split(/\s+/).filter(function(id) {
            return id && id !== errorId;
        });
        if (describedBy.length > 0) field.setAttribute('aria-describedby', describedBy.join(' '));
        else field.removeAttribute('aria-describedby');
    }

    document.querySelectorAll('form').forEach(function(form) {
        form.addEventListener('invalid', function(e) {
            var field = e.target;
            if (!field || !field.matches || !field.matches('input, select, textarea')) return;
            setFieldInvalid(field, field.validationMessage);
        }, true);

        form.querySelectorAll('input, select, textarea').forEach(function(field) {
            field.addEventListener('input', function() {
                if (field.checkValidity()) clearFieldInvalid(field);
                else setFieldInvalid(field, field.validationMessage);
            });
            field.addEventListener('change', function() {
                if (field.checkValidity()) clearFieldInvalid(field);
                else setFieldInvalid(field, field.validationMessage);
            });
        });
    });

    // Web Push : enregistrement du Service Worker et bouton "Activer les alertes"
    if (document.querySelector('.erpac-push-enable')) {
        initWebPush();
    }

    // Rafraîchissement du badge notifications (toutes les 12 s, pause si onglet masqué)
    var badge = document.getElementById('nav-notif-badge') || document.querySelector('.nav-notif-btn .rounded-full');
    var badgeMobile = document.getElementById('nav-notif-badge-mobile');
    if (badge && document.querySelector('.nav-notif-btn')) {
        var prevCount = null;
        var pollTimer = null;
        function updateBadges(c) {
            var text = c > 99 ? '99+' : String(c);
            var hidden = c === 0;
            badge.textContent = text;
            badge.classList.toggle('hidden', hidden);
            if (badgeMobile) {
                badgeMobile.textContent = text;
                badgeMobile.classList.toggle('hidden', hidden);
            }
        }
        function pollNotif() {
            fetch('/notifications/count', { credentials: 'same-origin' })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var c = data.count || 0;
                    if (prevCount !== null && c > prevCount) {
                        var toast = document.createElement('div');
                        toast.setAttribute('role', 'alert');
                        toast.style.cssText = 'position:fixed; top:80px; left:50%; transform:translateX(-50%); z-index:99999; background:#008C3A; color:#fff; padding:14px 24px; border-radius:12px; box-shadow:0 10px 40px rgba(0,0,0,0.2); display:flex; align-items:center; gap:12px; max-width:90%; font-size:15px;';

                        var toastLink = document.createElement('a');
                        toastLink.href = '/notifications/';
                        toastLink.style.color = 'inherit';
                        toastLink.style.textDecoration = 'underline';
                        toastLink.style.fontWeight = '600';
                        toastLink.textContent = 'Nouvelle(s) notification(s) - cliquer pour voir';

                        var closeBtn = document.createElement('button');
                        closeBtn.type = 'button';
                        closeBtn.style.background = 'transparent';
                        closeBtn.style.border = 'none';
                        closeBtn.style.color = 'rgba(255,255,255,0.9)';
                        closeBtn.style.fontSize = '22px';
                        closeBtn.style.lineHeight = '1';
                        closeBtn.style.cursor = 'pointer';
                        closeBtn.style.padding = '0 0 0 8px';
                        closeBtn.setAttribute('aria-label', 'Fermer');
                        closeBtn.textContent = '\u00D7';
                        closeBtn.addEventListener('click', function() {
                            if (toast.parentElement) {
                                toast.remove();
                            }
                        });

                        toast.appendChild(toastLink);
                        toast.appendChild(closeBtn);
                        document.body.appendChild(toast);
                        setTimeout(function() { if (toast.parentElement) toast.remove(); }, 8000);
                    }
                    prevCount = c;
                    updateBadges(c);
                })
                .catch(function() {});
        }
        function startPolling() {
            if (!pollTimer) {
                pollNotif();
                pollTimer = setInterval(pollNotif, 12000);
            }
        }
        function stopPolling() {
            if (pollTimer) {
                clearInterval(pollTimer);
                pollTimer = null;
            }
        }
        startPolling();
        document.addEventListener('visibilitychange', function() {
            if (document.hidden) {
                stopPolling();
            } else {
                startPolling();
            }
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
        erpacAlert('Les notifications ont été bloquées. Autorisez-les dans les paramètres du navigateur pour ce site.', { title: 'Notifications bloquées' });
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
