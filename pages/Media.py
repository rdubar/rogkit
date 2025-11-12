"""
Streamlit page for media library visualization.

Displays Plex media library as DataFrame with charts showing movies by year, decade, and genre.
"""
import pandas as pd  # type: ignore
import streamlit as st  # type: ignore

from rogkit_package.media.media import detect_db_path
from rogkit_package.media.media_cache import (
    load_cached_records,
    ensure_cache_table,
)

st.set_page_config(page_title="RogKit", page_icon=":tools:")

st.header("Roger's Fast Media Library")

db_path = detect_db_path()
if db_path is None:
    st.error(
        "No media database detected. Run `media --update` or `media --update-plex` "
        "to build the local cache before loading this dashboard."
    )
    st.stop()

ensure_cache_table(db_path)
records = load_cached_records(db_path)

if not records:
    st.warning("The media cache is empty. Run `media` first to populate it.")
    st.stop()

df_full = pd.DataFrame(records)
columns_to_display = [
    "title",
    "year",
    "metadata_type",
    "summary",
    "size_bytes",
    "disk",
    "source",
    "file_path",
    "added_at",
]

available_columns = [col for col in columns_to_display if col in df_full.columns]
df_display = df_full[available_columns].copy()

if "year" in df_display.columns:
    df_display["year"] = df_display["year"].fillna(0).astype(int).replace(0, pd.NA)
    df_display["year_display"] = df_display["year"].astype("Int64").astype(str).replace("<NA>", "")

st.write(df_display)

if "year" in df_display.columns:
    year_series = df_display["year"].dropna().astype(int)
    if not year_series.empty:
        st.subheader("Items by Year")
        st.bar_chart(year_series.value_counts().sort_index())

        st.subheader("Items by Decade")
        decades = (year_series // 10) * 10
        st.bar_chart(decades.value_counts().sort_index())
else:
    st.info("Year metadata is unavailable in the current cache.")

# TODO: Restore genre/actor-based visualisations once genre metadata is cached again.

