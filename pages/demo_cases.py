import sys
from pathlib import Path

src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)

import streamlit as st
import json
import datetime as dt
import folium
from folium import plugins
import pandas as pd
from streamlit_folium import st_folium
import data_loader
import indices
import classify
import stats
import importlib


st.set_page_config(
    page_title="Demo Cases", 
    page_icon=":material/collections_bookmark:", 
    layout="wide"
)

with open('data/demo_scenarios.json', 'r') as f:
       config = json.load(f)
project_id = st.secrets["earth_engine"]["project_id"]

@st.cache_resource
def init_gee():
    data_loader.init_ee_smart()

init_gee()


# --- main page ---
st.title("Pre-Configured Demo Scenarios")
st.caption("Historical Wildfire Event Analysis & Burn Severity Evaluation")

st.divider()

# --- sidebar  ---
with st.sidebar:
    st.markdown("**Scenario Selection**")
    scenario_names = list(config['demo_scenarios'].keys())
    
    selected_scenario = st.selectbox(
        "Select Demo Area", 
        scenario_names,
        help="Select a historical wildfire event to load pre-configured parameters."
    )
    selected = config['demo_scenarios'][selected_scenario]

    # Quick Metadata Display
    st.caption(f":material/event: **Fire Event:** {selected.get('start_date')} — {selected.get('end_date')}")

    st.divider()

    st.markdown("**Acquisition Windows**")

    pre_fire = (
        dt.date.fromisoformat(selected['pre-fire']['start']),
        dt.date.fromisoformat(selected['pre-fire']['end'])
    )
    post_fire = (
        dt.date.fromisoformat(selected['post-fire']['start']),
        dt.date.fromisoformat(selected['post-fire']['end'])
    )

    # Το ένα κάτω από το άλλο
    pre_dates = st.date_input("Pre-fire Date Range", value=pre_fire)
    post_dates = st.date_input("Post-fire Date Range", value=post_fire)

    run = st.button(
        "Run Analysis", 
        type="primary", 
        use_container_width=True,
        icon=":material/play_arrow:"
    )


def get_center_from_aoi(aoi):
    coords = aoi.centroid().getInfo()['coordinates']
    return [coords[1], coords[0]]


# --- main pipeline ---
if run:
    with st.spinner("Processing Sentinel-2 imagery via Google Earth Engine..."):


        aoi = data_loader.geometry_from_config(selected)

        before_img = data_loader.get_median_composite(
            aoi, pre_dates[0].isoformat(), pre_dates[1].isoformat(),
            config['sentinel2']['max_cloud']
        )
        before_img = indices.add_ndvi(before_img)
        before_img = indices.add_nbr(before_img)

        after_img = data_loader.get_median_composite(
            aoi, post_dates[0].isoformat(), post_dates[1].isoformat(),
            config['sentinel2']['max_cloud']
        )
        after_img = indices.add_ndvi(after_img)
        after_img = indices.add_nbr(after_img)

        dnbr = indices.compute_dnbr(before_img, after_img)

        # detect burned area & classify burn severity
        burned_mask = classify.detect_burned_area(
            dnbr, 
            after_img=after_img, 
            threshold=0.10, 
            min_pixels=5,
            exclude_cropland=True
        )

        severity_image = classify.classify_dnbr(
            dnbr, 
            after_img=after_img, 
            mask_to_burned_only=True, 
            threshold=0.10, 
            min_pixels=5,
            exclude_cropland=True
        )

        total_ha = stats.burned_area_hectares(burned_mask, aoi)
        center = get_center_from_aoi(aoi)

            
    # --- 1. rgb comparison ---
    st.subheader("True-Color RGB Comparison (Pre / Post)")
    vis_params = {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000}

    m1 = folium.Map(location=center, zoom_start=11, tiles=None)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr="Esri", name="Esri Basemap").add_to(m1)

    m1.get_root().html.add_child(
        folium.Element("<style>.leaflet-control-attribution { display: none !important; }</style>")
    )

    left1 = folium.TileLayer(tiles=before_img.getMapId(vis_params)["tile_fetcher"].url_format, attr="GEE", name="Pre-fire RGB")
    right1 = folium.TileLayer(tiles=after_img.getMapId(vis_params)["tile_fetcher"].url_format, attr="GEE", name="Post-fire RGB")
    
    left1.add_to(m1); right1.add_to(m1)
    plugins.SideBySideLayers(left1, right1).add_to(m1)
    folium.LayerControl().add_to(m1)
    
    st_folium(m1, width="stretch", height=480, key="true_color_map", returned_objects=[])
    st.metric("Total Burned Area", f"{total_ha:.1f} ha ({total_ha / 100:.2f} km²)")

    st.divider()

    # --- 2. false-color ---
    st.subheader("False-Color Mapping (Pre / Post)")
    vis_params_fc = {"bands": ["B12", "B8A", "B2"], "min": 0, "max": 3000}

    m2 = folium.Map(location=center, zoom_start=11, tiles=None)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr="Esri", name="Esri Basemap").add_to(m2)

    m2.get_root().html.add_child(
        folium.Element("<style>.leaflet-control-attribution { display: none !important; }</style>")
    )

    left2 = folium.TileLayer(tiles=before_img.getMapId(vis_params_fc)["tile_fetcher"].url_format, attr="GEE", name="Pre-fire False Color")
    right2 = folium.TileLayer(tiles=after_img.getMapId(vis_params_fc)["tile_fetcher"].url_format, attr="GEE", name="Post-fire False Color")

    left2.add_to(m2); right2.add_to(m2)
    plugins.SideBySideLayers(left2, right2).add_to(m2)
    folium.LayerControl().add_to(m2)

    st_folium(m2, width="stretch", height=480, key="false_color_map", returned_objects=[])

    st.divider()

    # --- 3. burn severity ---
    st.subheader("Burn Severity Assessment")
    col_map3, col_stats3 = st.columns([2, 1])

    with col_map3:
        sev_vis = {"min": 1, "max": 4, "palette": ["yellow", "orange", "red", "darkred"]}
        m3 = folium.Map(location=center, zoom_start=11, tiles=None)
        folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr="Esri", name="Esri Basemap").add_to(m3)
        folium.TileLayer(tiles=severity_image.getMapId(sev_vis)["tile_fetcher"].url_format, attr="GEE", name="Severity").add_to(m3)

        m3.get_root().html.add_child(
            folium.Element("<style>.leaflet-control-attribution { display: none !important; }</style>")
        )

        m3.get_root().html.add_child(folium.Element(stats.create_html_legend("Burn Severity", stats.SEVERITY_COLORS)))
        folium.LayerControl().add_to(m3)
        st_folium(m3, width="stretch", height=450, key="severity_map", returned_objects=[])

    with col_stats3:
        st.markdown("### Burn Severity Breakdown")
        by_severity = stats.burned_area_by_severity(severity_image, aoi)
        
        if by_severity:
            df_sev = pd.DataFrame(by_severity)
            st.dataframe(
                df_sev.style.map(
                    lambda v: f"background-color: {stats.SEVERITY_COLORS.get(v, '#ffffff')}; color: {'black' if v in ['Low', 'Moderate'] else 'white'}; font-weight: bold;", 
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
            st.info("No burned areas detected.", icon=":material/info:")

    st.divider()

# --- 4. land cover ---
    st.subheader("Land Cover Affected (ESA WorldCover)")
    col_map4, col_stats4 = st.columns([2, 1])

    filled_mask = classify.get_filled_burned_mask(burned_mask)
    burned_landcover = classify.get_burned_landcover(filled_mask, aoi)

    with col_map4:
        lc_vis = {
            "min": 10, "max": 100,
            "palette": ["006400", "ffbb22", "ffff4c", "f096ff", "fa0000", "b4b4b4", "ffffff", "0064c8", "0096a0", "00cf75", "fae6a0"]
        }
        m4 = folium.Map(location=center, zoom_start=11, tiles=None)
        folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr="Esri", name="Esri Basemap").add_to(m4)
        folium.TileLayer(tiles=burned_landcover.getMapId(lc_vis)["tile_fetcher"].url_format, attr="GEE", name="Land Cover").add_to(m4)

        m4.get_root().html.add_child(
            folium.Element("<style>.leaflet-control-attribution { display: none !important; }</style>")
        )

        m4.get_root().html.add_child(folium.Element(stats.create_html_legend("Land Cover", stats.LANDCOVER_COLORS)))
        folium.LayerControl().add_to(m4)
        st_folium(m4, width="stretch", height=450, key="landcover_map", returned_objects=[])

    with col_stats4:
        st.markdown("### Land Cover Statistics")
        with st.spinner("Calculating Land Cover statistics..."):
            by_landcover = stats.burned_area_by_landcover(filled_mask, aoi)      
        if by_landcover:
            df_lc = pd.DataFrame(by_landcover)
            st.dataframe(
                df_lc.style.map(
                    lambda v: f"background-color: {stats.LANDCOVER_COLORS.get(v, '#ffffff')}; color: black; font-weight: bold;", 
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
            st.info("No land cover data detected in burned region.", icon=":material/info:")

else:
    st.info("Select a demo scenario from the sidebar and click Run Analysis to execute.", icon=":material/arrow_back:")