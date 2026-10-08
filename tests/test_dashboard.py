from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_standalone_dashboard_contains_real_reconciliation_controls():
    dashboard = (ROOT / "dashboard.html").read_text(encoding="utf-8")

    assert "Reconciliation bridge" in dashboard
    assert "Exception review queue" in dashboard
    assert 'id="sourceFilter"' in dashboard
    assert 'id="categoryFilter"' in dashboard
    assert '"adjustedBank":254160.85' in dashboard
    assert '"adjustedBook":254160.85' in dashboard
    assert '"residual":0.0' in dashboard
