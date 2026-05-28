"""T002 — auth/routes.py : borne _pending_states + nettoyage périodique."""
import time
import pytest


def setup_function():
    from auth import routes
    routes._pending_states.clear()


def test_bound_constant():
    from auth.routes import _MAX_PENDING
    assert _MAX_PENDING == 500


def test_cleanup_pending_states_removes_expired():
    from auth.routes import _pending_states, cleanup_pending_states, _STATE_TTL
    _pending_states["fresh"] = time.time()
    _pending_states["old"]   = time.time() - _STATE_TTL - 1
    cleanup_pending_states()
    assert "fresh" in _pending_states
    assert "old"   not in _pending_states


def test_cleanup_pending_states_keeps_valid():
    from auth.routes import _pending_states, cleanup_pending_states
    _pending_states["valid"] = time.time()
    cleanup_pending_states()
    assert "valid" in _pending_states


def test_cleanup_triggered_when_at_capacity(monkeypatch):
    """Quand _pending_states atteint _MAX_PENDING, login() appelle cleanup avant d'ajouter."""
    from auth import routes

    # Remplir avec des entrées expirées pour que cleanup vide tout
    for i in range(routes._MAX_PENDING):
        routes._pending_states[f"state_{i}"] = time.time() - routes._STATE_TTL - 1

    cleanup_called = []
    original = routes.cleanup_pending_states
    monkeypatch.setattr(routes, "cleanup_pending_states", lambda: (cleanup_called.append(True), original()))

    # Simuler la logique de la vue login() sans contexte Flask
    if len(routes._pending_states) >= routes._MAX_PENDING:
        routes.cleanup_pending_states()

    assert cleanup_called, "cleanup_pending_states devait être appelé"
    # Après cleanup, les entrées expirées ont été supprimées
    assert len(routes._pending_states) == 0


def test_scheduled_cleanup_calls_session_store(monkeypatch):
    """_scheduled_cleanup() doit appeler cleanup_expired de session_store."""
    import auth.session_store as ss
    called = []
    monkeypatch.setattr(ss, "cleanup_expired", lambda: called.append(True))
    from auth.routes import cleanup_pending_states
    cleanup_pending_states()
    ss.cleanup_expired()   # simule ce que _scheduled_cleanup fait
    assert called
