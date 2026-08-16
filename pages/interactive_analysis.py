import sys
from pathlib import Path
import json
import datetime as dt

src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

import streamlit as st
import ee
import folium
import folium.plugins as plugins
import pandas as pd
from streamlit_folium import st_folium

import indices
import classify
import stats
import data_loader

st.set_page_config(
    page_title="Interactive Analysis", 
    page_icon=":material/analytics:", 
    layout="wide"
)

with open('data/demo_scenarios.json', 'r') as f:
       config = json.load(f)
project_id = st.secrets["earth_engine"]["project_id"]

# --- header ---
st.title("Interactive Custom AOI Analysis")
st.caption("Define Custom Regions of Interest & Execute Multi-Temporal Spectral Evaluation")

st.divider()

# --- sidebar ---
with st.sidebar:
    st.subheader("Temporal Parameters", anchor=False)
    today = dt.date.today()

    st.markdown("**Pre-Fire Window**")
    col_pre1, col_pre2 = st.columns(2)
    with col_pre1:
        pre_start = st.date_input("Start", value=today - dt.timedelta(days=365), key="pre_start")
    with col_pre2:
        pre_end = st.date_input("End", value=today - dt.timedelta(days=330), key="pre_end")

    st.markdown("**Post-Fire Window**")
    col_post1, col_post2 = st.columns(2)
    with col_post1:
        post_start = st.date_input("Start", value=today - dt.timedelta(days=30), key="post_start")
    with col_post2:
        post_end = st.date_input("End", value=today, key="post_end")

    st.divider()

    btn_load_fc = st.button(
        "Fetch Imagery", 
        type="primary", 
        use_container_width=True,
        icon=":material/satellite_alt:"
    )

# --- draw aoi ---
st.subheader("Define Area of Interest (AOI)")
st.caption("Use the drawing tools (Polygon or Rectangle) on the top-left of the map to enclose your target region.")

m_draw = folium.Map(location=[38.0, 23.7], zoom_start=8, tiles="OpenStreetMap")
m_draw.get_root().html.add_child(
    folium.Element("<style>.leaflet-control-attribution { display: none !important; }</style>")
)

plugins.Draw(
    export=False, position="topleft",
    draw_options={
        "polyline": False, 
        "circle": False, 
        "circlemarker": False, 
        "marker": False, 
        "polygon": True, 
        "rectangle": True
    },
    edit_options={"edit": True, "remove": True}
).add_to(m_draw)

map_data = st_folium(m_draw, width="stretch", height=380, key="draw_map")
if map_data and map_data.get("all_drawings"):
    st.session_state["last_drawn_geometry"] = map_data["all_drawings"][-1]["geometry"]

# --- false-color image ---
if btn_load_fc:
    if "last_drawn_geometry" not in st.session_state:
        st.warning("Please draw an Area of Interest on the map before fetching imagery.", icon=":material/warning:")
    else:
        try:
            with st.spinner("Fetching Sentinel-2 composites via Google Earth Engine..."):
                geom_data = st.session_state["last_drawn_geometry"]
                coords, gtype = geom_data["coordinates"], geom_data["type"]
                aoi_ee = ee.Geometry.Polygon(coords) if gtype == "Polygon" else ee.Geometry.MultiPolygon(coords)

                max_cloud = config['sentinel2']['max_cloud']

                before_img = data_loader.get_median_composite(aoi_ee, pre_start.isoformat(), pre_end.isoformat(), max_cloud)
                before_img = indices.add_ndvi(before_img)
                before_img = indices.add_nbr(before_img)

                after_img = data_loader.get_median_composite(aoi_ee, post_start.isoformat(), post_end.isoformat(), max_cloud)
                after_img = indices.add_ndvi(after_img)
                after_img = indices.add_nbr(after_img)

                vis_fc = {"bands": ["B12", "B8A", "B2"], "min": 0, "max": 3000}

                st.session_state["fc_results"] = {
                    "before_vis_fc": before_img.getMapId(vis_fc),
                    "after_vis_fc": after_img.getMapId(vis_fc),
                    "center": [aoi_ee.centroid().coordinates().getInfo()[1], aoi_ee.centroid().coordinates().getInfo()[0]],
                    "before_img": before_img, 
                    "after_img": after_img, 
                    "aoi_ee": aoi_ee
                }
                st.session_state.pop("analysis_results", None)
                st.success("Sentinel-2 imagery composites loaded successfully.", icon=":material/check_circle:")
        except Exception as e:
            st.error(f"Error retrieving imagery: {e}", icon=":material/error:")

# --- false color & run analysis ---
if "fc_results" in st.session_state:
    fc_res = st.session_state["fc_results"]
    st.divider()

    st.subheader("False-Color Comparison (Pre / Post)")
    m2 = folium.Map(location=fc_res["center"], zoom_start=11, tiles=None)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr="Esri", name="Esri Basemap").add_to(m2)

    m2.get_root().html.add_child(
        folium.Element("<style>.leaflet-control-attribution { display: none !important; }</style>")
    )
    
    left = folium.TileLayer(tiles=fc_res["before_vis_fc"]["tile_fetcher"].url_format, attr="GEE", name="Pre-fire SWIR")
    right = folium.TileLayer(tiles=fc_res["after_vis_fc"]["tile_fetcher"].url_format, attr="GEE", name="Post-fire SWIR")
    left.add_to(m2)
    right.add_to(m2)
    
    plugins.SideBySideLayers(left, right).add_to(m2)
    folium.LayerControl().add_to(m2)
    st_folium(m2, width="stretch", height=480, key="fc_map", returned_objects=[])

    st.divider()
    
    st.subheader("Burn Severity & Land Cover Assessment")
    
    if st.button("Run Comprehensive Analysis", type="primary", icon=":material/analytics:"):
        try:
            with st.spinner("Computing dNBR indices and generating land cover impact statistics..."):
                before, after, aoi = fc_res["before_img"], fc_res["after_img"], fc_res["aoi_ee"]
                dnbr = indices.compute_dnbr(before, after)
                
                threshold_val = 0.15

                burned_mask = classify.detect_burned_area(
                    dnbr, after_img=after, threshold=threshold_val, min_pixels=15, exclude_cropland=True
                )
                filled_mask = classify.get_filled_burned_mask(burned_mask)

                sev_img = classify.classify_dnbr(
                    dnbr, after_img=after, mask_to_burned_only=True, threshold=threshold_val, min_pixels=15, exclude_cropland=True
                )
                sev_img = sev_img.updateMask(filled_mask)

                burned_landcover = classify.get_burned_landcover(filled_mask, aoi)

                by_severity = stats.burned_area_by_severity(sev_img, aoi)
                by_landcover = stats.burned_area_by_landcover(filled_mask, aoi)

                total_ha = sum(item["Area (ha)"] for item in by_severity) if by_severity else 0.0

                st.session_state["analysis_results"] = {
                    "sev_mapid": sev_img.getMapId({"min": 1, "max": 4, "palette": ["yellow", "orange", "red", "darkred"]}),
                    "lc_mapid": burned_landcover.getMapId({"min": 10, "max": 100, "palette": ["006400", "ffbb22", "ffff4c", "f096ff", "fa0000", "b4b4b4", "ffffff", "0064c8", "0096a0", "00cf75", "fae6a0"]}),
                    "total_ha": total_ha,
                    "by_severity": by_severity,
                    "by_landcover": by_landcover
                }
                st.success("Processing complete.", icon=":material/check_circle:")
        except Exception as e:
            st.error(f"Error executing analysis pipeline: {e}", icon=":material/error:")

# --- analysis results ---
if "analysis_results" in st.session_state:
    res = st.session_state["analysis_results"]
    center = st.session_state["fc_results"]["center"]

    st.divider()

    # --- metrics ---
    m_col1, m_col2, m_col3 = st.columns(3)
    with m_col1:
        st.metric("Total Burned Area", f"{res['total_ha']:.2f} ha")
    with m_col2:
        st.metric("Total Burned Area (km²)", f"{(res['total_ha'] / 100.0):.2f} km²")
    with m_col3:
        severity_count = len(res['by_severity']) if res['by_severity'] else 0
        st.metric("Severity Classes Detected", f"{severity_count}")

    st.divider()

    # --- BURN SEVERITY ---
    st.subheader("Burn Severity Assessment")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        m3 = folium.Map(location=center, zoom_start=11, tiles=None)
        folium.TileLayer(
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", 
            attr="Esri", 
            name="Esri Basemap"
        ).add_to(m3)
        folium.TileLayer(
            tiles=res["sev_mapid"]["tile_fetcher"].url_format, 
            attr="GEE", 
            name="Severity"
        ).add_to(m3)

        m3.get_root().html.add_child(
            folium.Element("<style>.leaflet-control-attribution { display: none !important; }</style>")
        )
        m3.get_root().html.add_child(
            folium.Element(stats.create_html_legend("Burn Severity", stats.SEVERITY_COLORS))
        )
        folium.LayerControl().add_to(m3)
        st_folium(m3, width="stretch", height=450, key="severity_map", returned_objects=[])

    with col2:
        st.markdown("### Burn Severity Breakdown")
        if res["by_severity"]:
            df_sev = pd.DataFrame(res["by_severity"])
            st.dataframe(
                df_sev.style.map(
                    lambda v: f"background-color: {stats.SEVERITY_COLORS.get(v, '#fff')}; color: {'black' if v in ['Low', 'Moderate'] else 'white'}; font-weight: bold;", 
                    subset=["Severity Level"]
                ),
                column_config={
                    "Severity Level": "Severity Level",
                    "Area (ha)": st.column_config.NumberColumn("Area (ha)", format="%.2f"),
                    "Area (km²)": st.column_config.NumberColumn("Area (km²)", format="%.2f"),
                },
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.info("No burned pixels detected within the defined AOI.", icon=":material/info:")

    st.divider()

    # --- LAND COVER ---
    st.subheader("Land Cover Affected (ESA WorldCover)")
    col3, col4 = st.columns([2, 1])

    with col3:
        m4 = folium.Map(location=center, zoom_start=11, tiles=None)
        folium.TileLayer(
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", 
            attr="Esri", 
            name="Esri Basemap"
        ).add_to(m4)
        folium.TileLayer(
            tiles=res["lc_mapid"]["tile_fetcher"].url_format, 
            attr="GEE", 
            name="Land Cover"
        ).add_to(m4)

        m4.get_root().html.add_child(
            folium.Element("<style>.leaflet-control-attribution { display: none !important; }</style>")
        )
        m4.get_root().html.add_child(
            folium.Element(stats.create_html_legend("Land Cover", stats.LANDCOVER_COLORS))
        )
        folium.LayerControl().add_to(m4)
        st_folium(m4, width="stretch", height=450, key="landcover_map", returned_objects=[])

    with col4:
        st.markdown("### Land Cover Statistics")
        if res["by_landcover"]:
            df_lc = pd.DataFrame(res["by_landcover"])
            st.dataframe(
                df_lc.style.map(
                    lambda v: f"background-color: {stats.LANDCOVER_COLORS.get(v, '#fff')}; color: black; font-weight: bold;", 
                    subset=["Land Cover Type"]
                ),
                column_config={
                    "Land Cover Type": "Land Cover Type",
                    "Area (ha)": st.column_config.NumberColumn("Area (ha)", format="%.2f"),
                    "Area (km²)": st.column_config.NumberColumn("Area (km²)", format="%.2f"),
                },
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.info("No land cover data detected within the affected area.", icon=":material/info:")