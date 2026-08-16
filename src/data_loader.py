import ee
import json
import indices
import classify
import stats
import streamlit as st


with open('data/demo_scenarios.json', 'r') as f:
       config = json.load(f)
project_id = st.secrets["earth_engine"]["project_id"]

def init_ee(project_id):
    
    try:
        ee.Initialize(project=project_id)
    except Exception:
        ee.Authenticate(auth_mode="localhost")
        ee.Initialize(project=project_id)
    print("ee initialized successfully")


def init_ee_smart():

    if "gcp_service_account" in st.secrets:
        credentials = ee.ServiceAccountCredentials(
            email=st.secrets["gcp_service_account"]["client_email"],
            key_data=json.dumps(dict(st.secrets["gcp_service_account"]))
        )
        ee.Initialize(credentials)
    else:
        init_ee(st.secrets["earth_engine"]["project_id"])
 
def get_s2_collection(aoi, start_date, end_date, max_cloud_pct=5):
    
    return(
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_pct))
        .map(mask_s2_clouds)
    )


def geometry_from_config(scenario_config):
    
    geom = scenario_config['geometry']
    
    if geom['type'] == 'bbox':
        return ee.Geometry.Rectangle([geom['west'], geom['south'], geom['east'], geom['north']])
    elif geom['type'] == 'point_buffer':
        return ee.Geometry.Point([geom['lon'], geom['lat']]).buffer(geom['buffer_m'])
    else:
        raise ValueError(f"unknown geometry type: {geom['type']}")


def mask_s2_clouds(image):
    
    qa = image.select("QA60")
    
    cloud_mask = qa.bitwiseAnd(1 << 10).eq(0)
    cirrus_mask = qa.bitwiseAnd(1 << 11).eq(0)
    combined_masks = cloud_mask.And(cirrus_mask)
    
    return image.updateMask(combined_masks)
    

def get_median_composite(aoi, start_date, end_date, max_cloud_pct=5):
    
    collection = get_s2_collection(aoi, start_date, end_date, max_cloud_pct)
    img = collection.median()
    img = img.clip(aoi)
    return img