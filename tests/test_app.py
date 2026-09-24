from streamlit.testing.v1 import AppTest
from pathlib import Path


def test_app_renders_without_exception():
    entrypoint = Path(__file__).resolve().parents[1] / "streamlit_app.py"
    app = AppTest.from_file(entrypoint, default_timeout=15).run()
    assert not app.exception
    assert app.title


def test_all_pages_render_without_exception():
    entrypoint = Path(__file__).resolve().parents[1] / "streamlit_app.py"
    for page in ("app_pages/product_radar.py", "app_pages/fulfillment.py", "app_pages/insights.py"):
        app = AppTest.from_file(entrypoint, default_timeout=15).run()
        app.switch_page(page).run()
        assert not app.exception, page
