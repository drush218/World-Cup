import os
import time

import streamlit as st

# Pull Streamlit Cloud secrets into env vars before app.py reads them at import time.
# On Streamlit Cloud: set FOOTBALL_API_KEY and ADMIN_PASSWORD in the Secrets panel.
# Locally: set them as env vars, or add a .streamlit/secrets.toml (see secrets.toml.example).
for _k in ("FOOTBALL_API_KEY", "ADMIN_PASSWORD", "SECRET_KEY"):
    try:
        if _k not in os.environ:
            os.environ[_k] = st.secrets[_k]
    except (KeyError, FileNotFoundError):
        pass

from datetime import datetime

import streamlit.components.v1 as components
from jinja2 import Environment, FileSystemLoader

from app import PLAYERS, TEAM_CODE, _cache, compute_scores, load_awards

st.set_page_config(
    page_title="The Table – WC2026 Sweepstake",
    layout="centered",
)

# Hide Streamlit chrome so the leaderboard fills the page cleanly
st.markdown(
    "<style>#MainMenu,header,footer{visibility:hidden;}"
    ".block-container{padding:0!important;max-width:100%!important}</style>",
    unsafe_allow_html=True,
)

with st.spinner("Loading…"):
    scores, team_fixtures, matchday_info = compute_scores()
    awards = load_awards()

if _cache["ts"]:
    delta = time.time() - _cache["ts"]
    last_updated = (
        "just now" if delta < 60
        else f"{int(delta / 60)}m ago" if delta < 3600
        else datetime.fromtimestamp(_cache["ts"]).strftime("%H:%M")
    )
else:
    last_updated = "—"

env = Environment(loader=FileSystemLoader("templates"))
html = env.get_template("index.html").render(
    scores=scores,
    team_fixtures=team_fixtures,
    matchday_info=matchday_info,
    awards=awards,
    last_updated=last_updated,
    num_players=len(PLAYERS),
    team_code=TEAM_CODE,
)

components.html(html, height=2600, scrolling=True)
