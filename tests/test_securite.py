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


class TestSessionCookie:
    """Durcissement du cookie de session (R2) : HttpOnly / SameSite / Secure."""

    def _set_cookie_session(self, resp):
        """Retourne l'en-tête Set-Cookie du cookie de session, ou None."""
        for header, value in resp.headers.items():
            if header == "Set-Cookie" and value.startswith("session="):
                return value
        return None

    def test_httponly_et_samesite_toujours_presents(self, client, users):
        from tests.conftest import login
        resp = login(client, "rh1", "rh123")
        # follow_redirects → on relit le Set-Cookie sur la réponse finale ;
        # à défaut, on déclenche une nouvelle pose de cookie.
        cookie = self._set_cookie_session(resp)
        if cookie is None:
            resp = client.get("/login")
            cookie = self._set_cookie_session(resp)
        assert cookie is not None
        assert "HttpOnly" in cookie
        assert "SameSite=Lax" in cookie

    def test_secure_pose_quand_https(self, app, client, users):
        from tests.conftest import login
        previous = app.config.get("SESSION_COOKIE_SECURE")
        app.config["SESSION_COOKIE_SECURE"] = True
        try:
            resp = login(client, "rh1", "rh123")
            cookie = self._set_cookie_session(resp)
            assert cookie is not None
            assert "Secure" in cookie
        finally:
            app.config["SESSION_COOKIE_SECURE"] = previous

    def test_config_secure_indexe_sur_scheme(self):
        """SESSION_COOKIE_SECURE doit suivre PREFERRED_URL_SCHEME (HTTPS only)."""
        from config import Config
        assert Config.SESSION_COOKIE_SECURE == (Config.PREFERRED_URL_SCHEME == "https")
        assert Config.SESSION_COOKIE_HTTPONLY is True
        assert Config.SESSION_COOKIE_SAMESITE == "Lax"


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
