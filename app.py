import streamlit as st

st.set_page_config(
    page_title="Wildfire Earth Observation Portal", 
    page_icon=":material/satellite_alt:", 
    layout="wide"
)


st.markdown("""
    <style>
        /* Overview, Demo Cases, Interactive Analysis font */
        [data-testid="stSidebarNavItems"] span,
        [data-testid="stSidebarNavItems"] p {
            font-size: 15px !important;
            font-weight: 500 !important;
        }

        /* Analytics font */
        [data-testid="stSidebarNav"] div:first-child span {
            font-size: 16px !important;
            font-weight: 600 !important;
        }

        /* icon font */
        [data-testid="stSidebarNavItems"] span[data-testid="stIconMaterial"] {
            font-size: 22px !important;
        }
    </style>
""", unsafe_allow_html=True)


# --- DASHBOARD ---
def show_dashboard():
    st.title("Wildfire Impact & Severity Assessment")
    st.caption("Automated Sentinel-2 & Google Earth Engine Analysis Pipeline")

    st.divider()

    # --- DEMO ---
    st.subheader("Platform Demonstration")

    col_vid1, col_vid2 = st.columns(2)

    with col_vid1:
        try:
            st.video("assets/democases1.mp4", autoplay=True, loop=True, muted=True)
        except Exception:
            st.info("Place `democases1.mp4` inside `assets/` folder.", icon=":material/info:")

    with col_vid2:
        try:
            st.video("assets/interactivetool1.mp4", autoplay=True, loop=True, muted=True)
        except Exception:
            st.info("Place `interactivetool1.mp4` inside `assets/` folder.", icon=":material/info:")

    # --- MODULE OVERVIEW ---

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        #### Pre-Configured Scenarios
        * **Historic Case Studies:** Evaluate predefined wildfire events across key historical regions.
        * **Dual-Spectral Comparison:** Compare True Color (RGB) and False Color composites.
        * **Spectral Index Classification:** View automated Burn Severity classes and affected land cover classes.
        """)

    with col2:
        st.markdown("""
        #### Custom AOI Analysis
        * **Interactive Area Analysis:** Define custom Polygons and Rectangles directly on the basemap.
        * **Flexible Temporal Windows:** Specify custom Pre-Fire and Post-Fire acquisition dates.
        * **Two-Stage Processing:** Preview cloud-filtered composites prior to running full statistical analytics.
        """)


# --- PAGE DEFINITIONS ---
dashboard_page = st.Page(
    show_dashboard, 
    title="Overview", 
    icon=":material/dashboard:", 
    default=True
)

demo_cases_page = st.Page(
    "pages/demo_cases.py", 
    title="Demo Cases", 
    icon=":material/collections_bookmark:"
)

interactive_analysis_page = st.Page(
    "pages/interactive_analysis.py", 
    title="Interactive Analysis", 
    icon=":material/analytics:"
)

pg = st.navigation(
    {
        "Analytics": [dashboard_page, demo_cases_page, interactive_analysis_page]
    }
)

pg.run()

st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {
            margin-bottom: auto;
        }
    </style>
""", unsafe_allow_html=True)

with st.sidebar.expander("About & Credits", icon=":material/info:"):
    st.markdown("""
    **Developer:** Ioanna Tselka  
    **Frameworks:** Streamlit, Google Earth Engine, Folium  
    **Data Sources:** ESA Copernicus Sentinel-2, ESA WorldCover  
    
    [GitHub Repository](https://github.com/ioannatselka)  
    [LinkedIn Profile](https://www.linkedin.com/in/ioanna-tselka/)
    """)