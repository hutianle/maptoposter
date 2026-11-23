# Deploying MapToPoster on Streamlit Community Cloud

## What you need

- A GitHub account (free).
- A fork of https://github.com/originalankur/maptoposter with two added
  files from this folder:
  - `app.py` — the Streamlit wrapper (place in the repo root, next to
    `create_map_poster.py`).
  - `requirements.txt` — use `requirements-cloud.txt` from this folder
    (the upstream `requirements.txt` plus a `streamlit` line) and
    rename it to `requirements.txt` in your fork. Without the
    `streamlit` line the Cloud build fails at `import streamlit`.

## Steps

1. **Fork** https://github.com/originalankur/maptoposter.
2. **Add the two files** to your fork (GitHub web UI → Add file →
   Upload files — or `git clone` your fork, copy them in, push).
3. Go to **https://share.streamlit.io** → **New app** (or
   **Create app**).
4. Pick **your fork**, branch `main`, main file path `app.py` → **Deploy**.
5. Wait for the build. The first install (osmnx, geopandas, scipy…)
   takes several minutes — that is normal.
6. Test with the defaults (**Paris, France, terracotta, 10 km**). The
   first poster takes 30 s to a few minutes while it fetches live
   OpenStreetMap data.

## What to expect on the free tier

- **Resources:** 1 vCPU / 1 GB RAM. Generation is CPU- and
  memory-hungry; keep the radius modest (10 km default). Very large
  radii on big cities can run out of memory.
- **Sleep:** the app sleeps after a period with no traffic and takes
  a while to wake up.
- **Cache:** the repo's `cache/` pickle cache speeds up repeat
  generations while the container is alive, but it does **not**
  survive a reboot — a cold start always re-downloads the map data.
- **Rate limits:** geocoding (Nominatim) and map data (Overpass API)
  are free community services. If a generation fails with a timeout,
  just retry, or try a smaller radius.
- **No secrets needed.** No API keys are involved.

## If Streamlit Cloud struggles

Hugging Face Spaces (huggingface.co/spaces) is the closest free
alternative: create a Space with the **Streamlit** SDK, upload the
same files, and it will build the same way — with more generous free
resources. A Docker-based deploy (Fly.io / Render / Railway) also
works: the same `app.py` runs under `streamlit run app.py`.
