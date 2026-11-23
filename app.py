"""MapToPoster — Streamlit web UI for create_map_poster.py.

Drop this file in the root of a fork of
https://github.com/originalankur/maptoposter (next to
create_map_poster.py, font_management.py, themes/ and fonts/) and deploy
it on Streamlit Community Cloud (share.streamlit.io).

How it works
------------
The repo itself is a command-line script, so this wrapper imports it as a
module and calls its public functions directly — no code in
create_map_poster.py needs to change:

* ``get_available_themes()`` populates the theme dropdown.
* ``get_coordinates()`` geocodes the city via Nominatim.
* ``load_theme()`` + the module-global ``THEME`` select the colours
  (``create_poster`` reads that global, so generation is serialised
  with a lock to keep concurrent sessions from racing on it).
* ``create_poster()`` renders the PNG/SVG/PDF into a temp dir; the
  bytes are kept in ``st.session_state`` so the preview and the download
  button survive Streamlit reruns.

Notes for Streamlit Community Cloud (free tier: 1 vCPU / 1 GB RAM)
-------------------------------------------------------------------
* Each poster fetches live data from OpenStreetMap (Overpass API) at
  generation time, so one poster takes ~30 s to a few minutes. The
  repo's own ``cache/`` pickle cache speeds up repeat generations
  while the app container is alive, but it does not persist across
  reboots — expect a cold start to be slow.
* Keep the default distance modest (10 km). Large radii on big cities
  download a lot of road data and can strain the 1 GB limit.
* ``requirements.txt`` in the repo does not list Streamlit — add a
  ``streamlit`` line (see the ``requirements.txt`` shipped with this
  wrapper) or the Cloud build will fail at import.
"""

import os
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Headless rendering: no display server on Cloud.

# create_map_poster.py resolves themes/, fonts/ and cache/ relative to the
# working directory, so anchor the process there (Streamlit Cloud runs from
# the repo root, but this keeps `streamlit run subdir/app.py` working too).
BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)

import streamlit as st

import create_map_poster as cmp  # noqa: E402  (needs Agg + chdir above)

_GENERATION_LOCK = threading.Lock()

SIZE_PRESETS = {
    "Portrait 12 × 16 in (default)": (12.0, 16.0),
    "Square 12 × 12 in": (12.0, 12.0),
    "Landscape 16 × 12 in": (16.0, 12.0),
    "A4 print 8.3 × 11.7 in": (8.3, 11.7),
    "Instagram post 3.6 × 3.6 in": (3.6, 3.6),
    "HD wallpaper 6.4 × 3.6 in": (6.4, 3.6),
    "4K wallpaper 12.8 × 7.2 in": (12.8, 7.2),
    "Custom…": (12.0, 16.0),
}

FORMAT_MIME = {
    "png": "image/png",
    "svg": "image/svg+xml",
    "pdf": "application/pdf",
}


def generate_poster(
    city,
    country,
    theme,
    dist,
    width,
    height,
    output_format="png",
    latitude=None,
    longitude=None,
    country_label=None,
    display_city=None,
    display_country=None,
    font_family=None,
):
    """Generate one poster and return ``(file_bytes, filename, (lat, lon))``.

    Raises ``ValueError`` for bad input (unknown city, bad coordinates)
    and ``RuntimeError`` when the street network cannot be retrieved.
    """
    city = (city or "").strip()
    country = (country or "").strip()
    if not city or not country:
        raise ValueError("Please enter both a city and a country.")
    if width > 20 or height > 20:
        raise ValueError("Width and height are capped at 20 inches.")
    if (latitude is None) != (longitude is None):
        raise ValueError("Latitude and longitude must be given together.")

    with _GENERATION_LOCK:
        # Coordinates: explicit override, else geocode via Nominatim.
        if latitude is not None and longitude is not None:
            from lat_lon_parser import parse

            point = (parse(str(latitude)), parse(str(longitude)))
        else:
            point = cmp.get_coordinates(city, country)

        # Custom Google Font (downloaded + cached by font_management.py).
        fonts = None
        if font_family and font_family.strip().lower() != "roboto":
            from font_management import load_fonts

            fonts = load_fonts(font_family.strip())
            if not fonts:
                st.warning(
                    f"Could not load font '{font_family}' — falling back to Roboto."
                )

        # create_poster() reads the module-global THEME.
        cmp.THEME = cmp.load_theme(theme)

        slug = city.lower().replace(" ", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{slug}_{theme}_{timestamp}.{output_format}"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, filename)
            cmp.create_poster(
                city,
                country,
                point,
                dist,
                output_file,
                output_format,
                width,
                height,
                country_label=country_label or None,
                display_city=display_city or None,
                display_country=display_country or None,
                fonts=fonts,
            )
            with open(output_file, "rb") as f:
                data = f.read()

    return data, filename, point


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------

st.set_page_config(page_title="MapToPoster", page_icon="🗺️", layout="centered")
st.title("🗺️ MapToPoster")
st.markdown(
    "Turn any city into a beautiful minimalist map poster, powered by "
    "OpenStreetMap. Pick a city and a theme — the poster renders live "
    "and downloads as a print-ready file."
)

themes = cmp.get_available_themes()
default_theme_idx = themes.index("terracotta") if "terracotta" in themes else 0

with st.form("poster_form"):
    col_city, col_country = st.columns(2)
    city = col_city.text_input("City", value="Paris")
    country = col_country.text_input("Country", value="France")

    theme = st.selectbox("Theme", options=themes, index=default_theme_idx)

    dist = st.slider(
        "Map radius (metres)",
        min_value=2000,
        max_value=30000,
        value=10000,
        step=1000,
        help="Smaller radii suit dense old centres (Venice, Amsterdam); "
        "larger radii suit sprawling metros (Tokyo, Mumbai). A smaller "
        "radius also generates faster.",
    )

    preset = st.selectbox("Poster size", options=list(SIZE_PRESETS))
    preset_w, preset_h = SIZE_PRESETS[preset]
    if preset == "Custom…":
        col_w, col_h = st.columns(2)
        width = col_w.number_input(
            "Width (inches)", min_value=1.0, max_value=20.0, value=12.0, step=0.5
        )
        height = col_h.number_input(
            "Height (inches)", min_value=1.0, max_value=20.0, value=16.0, step=0.5
        )
    else:
        width, height = preset_w, preset_h
        st.caption(f"Size: {width} × {height} in at 300 DPI (PNG).")

    output_format = st.radio(
        "File format", options=["png", "svg", "pdf"], horizontal=True
    )

    with st.expander("Advanced options"):
        col_lat, col_lon = st.columns(2)
        latitude = col_lat.text_input("Latitude override (optional)", value="")
        longitude = col_lon.text_input("Longitude override (optional)", value="")
        country_label = st.text_input(
            "Country label override (optional)",
            value="",
            help="Text printed under the city name instead of the country.",
        )
        col_dc, col_dco = st.columns(2)
        display_city = col_dc.text_input("Display city name (optional)", value="")
        display_country = col_dco.text_input(
            "Display country name (optional)", value=""
        )
        font_family = st.text_input(
            "Google Font family (optional)",
            value="",
            help='e.g. "Noto Sans JP" for Japanese city names. '
            "Downloaded on first use and cached.",
        )

    submitted = st.form_submit_button("Generate poster", type="primary")

if submitted:
    try:
        with st.spinner(
            "Fetching OpenStreetMap data and rendering — this can take "
            "30 seconds to a few minutes…"
        ):
            started = time.time()
            data, filename, point = generate_poster(
                city=city,
                country=country,
                theme=theme,
                dist=dist,
                width=float(width),
                height=float(height),
                output_format=output_format,
                latitude=latitude.strip() or None,
                longitude=longitude.strip() or None,
                country_label=country_label.strip() or None,
                display_city=display_city.strip() or None,
                display_country=display_country.strip() or None,
                font_family=font_family.strip() or None,
            )
            elapsed = time.time() - started
        st.session_state["poster"] = {
            "data": data,
            "filename": filename,
            "mime": FORMAT_MIME[output_format],
            "format": output_format,
            "coords": point,
            "city": city,
            "country": country,
            "theme": theme,
            "elapsed": elapsed,
        }
        st.success(f"Done in {elapsed:.0f} s — poster centred on {point[0]:.4f}, {point[1]:.4f}.")
    except Exception as exc:  # noqa: BLE001 — show any failure in the UI
        st.error(f"Generation failed: {exc}")
        st.caption(
            "Common causes: the city could not be geocoded (check the "
            "spelling), or the OpenStreetMap Overpass API timed out — "
            "try again, or try a smaller radius."
        )

poster = st.session_state.get("poster")
if poster:
    st.divider()
    st.subheader(f"{poster['city']}, {poster['country']} — {poster['theme']}")
    if poster["format"] == "png":
        st.image(poster["data"], caption=poster["filename"])
    else:
        st.info(f"Preview is only available for PNG — download the {poster['format'].upper()} below.")
    st.download_button(
        label=f"⬇️ Download {poster['filename']}",
        data=poster["data"],
        file_name=poster["filename"],
        mime=poster["mime"],
    )

st.divider()
st.caption(
    "Map data © OpenStreetMap contributors. Geocoding by Nominatim and map "
    "data by the Overpass API — please be patient with them, they are free "
    "community services with rate limits."
)
