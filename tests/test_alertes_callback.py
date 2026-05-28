"""T003/T004 — alertes : build_alert_table + render_alertes scaffold."""
from dash import html


def test_render_alertes_returns_placeholder():
    from ui.tabs.alertes import render_alertes
    result = render_alertes()
    # Doit retourner un Div contenant alertes-container
    assert isinstance(result, html.Div)
    ids = _collect_ids(result)
    assert "alertes-container" in ids


def test_render_alertes_no_data_argument():
    """render_alertes() ne doit plus accepter de data dict."""
    import inspect
    from ui.tabs.alertes import render_alertes
    sig = inspect.signature(render_alertes)
    assert len(sig.parameters) == 0


def test_build_alert_table_empty():
    from ui.tabs.alertes import build_alert_table
    result = build_alert_table([])
    assert isinstance(result, html.Div)


def test_build_alert_table_with_rows():
    from ui.tabs.alertes import build_alert_table
    rows = [{"Alerte": "test", "Date": "2026-01-01"}]
    result = build_alert_table(rows)
    assert isinstance(result, html.Div)


def test_render_alertes_contains_seuil_inputs():
    from ui.tabs.alertes import render_alertes
    result = render_alertes()
    ids = _collect_ids(result)
    assert "seuil-battery" in ids
    assert "seuil-ending"  in ids


# ── helpers ───────────────────────────────────────────────────────────────────

def _collect_ids(component):
    ids = set()
    if hasattr(component, "id") and component.id:
        ids.add(component.id)
    children = getattr(component, "children", None)
    if children is None:
        return ids
    if isinstance(children, list):
        for c in children:
            ids |= _collect_ids(c)
    elif hasattr(children, "children"):
        ids |= _collect_ids(children)
    return ids
