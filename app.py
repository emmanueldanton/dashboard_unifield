import dash

from ui.layout import create_layout
from callbacks import register_all_callbacks

app = dash.Dash(
    __name__,
    title="CAD.42 — UNIFIELD Dashboard",
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    assets_folder="assets",
)
server = app.server

app.layout = create_layout()
register_all_callbacks(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860)
