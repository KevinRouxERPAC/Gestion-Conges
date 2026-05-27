"""Tests sécurité : rate limiting login, en-têtes CSP/HSTS/X-Frame, etc."""


class TestSecurityHeaders:
    def test_headers_par_defaut(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200
        assert "Content-Security-Policy" in resp.headers
        csp = resp.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "form-action 'self'" in csp
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("Referrer-Policy") == "same-origin"
        # HSTS absent par défaut (HTTP).
        assert "Strict-Transport-Security" not in resp.headers

    def test_hsts_en_https(self, app, client):
        """Si PREFERRED_URL_SCHEME=https, HSTS est posé."""
        previous = app.config.get("PREFERRED_URL_SCHEME")
        app.config["PREFERRED_URL_SCHEME"] = "https"
        try:
            resp = client.get("/login")
            assert "Strict-Transport-Security" in resp.headers
        finally:
            app.config["PREFERRED_URL_SCHEME"] = previous


class TestRateLimit:
    """Le rate limiter est désactivé en tests via RATELIMIT_ENABLED=False ; on vérifie
    quand même qu'il peut être activé et qu'il bloque comme attendu."""

    def test_rate_limit_actif_bloque(self, app, client):
        from app import limiter
        # Active temporairement le rate limit + reset.
        app.config["RATELIMIT_ENABLED"] = True
        limiter.reset()
        try:
            # 11 tentatives → la 11e dépasse "10 per minute".
            for i in range(10):
                resp = client.post("/login", data={
                    "identifiant": "inexistant",
                    "mot_de_passe": "wrong",
                })
                # 200 (re-render avec erreur de login) ou 302
                assert resp.status_code in (200, 302)
            resp = client.post("/login", data={
                "identifiant": "inexistant",
                "mot_de_passe": "wrong",
            })
            assert resp.status_code == 429
        finally:
            app.config["RATELIMIT_ENABLED"] = False
            limiter.reset()
