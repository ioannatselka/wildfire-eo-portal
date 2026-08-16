import ee
import importlib
import classify

SEVERITY_COLORS = {
    "Low": "#FFFF00",        
    "Moderate": "#FFA500",   
    "High": "#FF0000",       
    "Very High": "#800000"   
}

LANDCOVER_COLORS = {
    "Tree cover":" ""#006400",
    "Shrubland": "#ffbb22",
    "Grassland": "#ffff4c",
    "Cropland": "#f096ff",
    "Built-up": "#fa0000",
    "Bare / sparse vegetation": "#b4b4b4",
    "Water": "#0064c8",
    "Herbaceous wetland": "#0096a0", 
    "Snow and ice": "#ffffff",       
    "Mangroves": "#00cf75",          
    "Moss and lichen": "#fae6a0"     
}

LANDCOVER_CLASSES = {
    10: "Tree cover",
    20: "Shrubland",
    30: "Grassland",
    40: "Cropland",
    50: "Built-up",
    60: "Bare / sparse vegetation",
    70: "Snow and ice",
    80: "Water",
    90: "Herbaceous wetland",
    95: "Mangroves",
    100: "Moss and lichen"
}

def burned_area_hectares(burned_mask, aoi, scale=10):
    area_image = burned_mask.multiply(ee.Image.pixelArea())
    stats = area_image.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=aoi,
        scale=scale,
        maxPixels=1e9        
    )
    total_area_m2 = stats.get("burned")
    if total_area_m2 is None:
        return 0.0
    return total_area_m2.getInfo() / 10_000


def burned_area_by_severity(severity_image, aoi, scale=10):
    hist = severity_image.reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(),
        geometry=aoi,
        scale=scale,
        maxPixels=1e9
    ).get("severity").getInfo()

    if not hist:
        return []

    pixel_area_m2 = scale * scale  
    value_to_name = {v: k for k, v in classify.SEVERITY_VALUES.items()}

    result = []
    for value_str, pixel_count in hist.items():
        val = int(float(value_str))
        if val == 0:
            continue
        class_name = value_to_name.get(val, f"Class_{val}")
        sqm = pixel_count * pixel_area_m2
        ha = round(sqm / 10_000, 2)
        sqkm = round(sqm / 1_000_000, 2)
        result.append({"Severity Level": class_name, "Area (ha)": ha, "Area (km²)": sqkm})

    return result


def burned_area_by_landcover(filled_mask, aoi, scale=30):

    landcover = ee.Image("ESA/WorldCover/v200/2021").select("Map")
    landcover_no_water = landcover.updateMask(landcover.neq(80))
    
    area_image = ee.Image.pixelArea().updateMask(filled_mask)
    combined = area_image.addBands(landcover_no_water)

    landcover_sum = combined.reduceRegion(
        reducer=ee.Reducer.sum().group(groupField=1, groupName="landcover_class"),
        geometry=aoi,
        scale=scale,    
        maxPixels=1e9,
        tileScale=4     
    ).get("groups").getInfo()

    if not landcover_sum:
        return []

    result = []
    for group in landcover_sum:
        code = int(group["landcover_class"])
        if code == 80:
            continue
        name = LANDCOVER_CLASSES.get(code, f"Class_{code}")
        sqm = group["sum"]
        ha = round(sqm / 10_000, 2)    
        sqkm = round(sqm / 1_000_000, 2)
        if ha > 0:
            result.append({"Land Cover Type": name, "Area (ha)": ha, "Area (km²)": sqkm})

    return result


def create_html_legend(title, legend_dict):
    """Generates floating HTML Legend for Folium Maps."""
    html = f"""
    <div style="
        position: fixed; 
        bottom: 30px; left: 30px; width: 180px; height: auto; 
        background-color: rgba(255, 255, 255, 0.45);
        z-index:9999; font-size:12px;
        border:2px solid grey; border-radius: 5px;
        padding: 10px;
    ">
    <b>{title}</b><br>
    """
    for name, color in legend_dict.items():
        html += f"""
        <div style="display: flex; align-items: center; margin-top: 3px;">
            <div style="background-color: {color}; width: 15px; height: 15px; margin-right: 8px; border: 1px solid #000;"></div>
            <span>{name}</span>
        </div>
        """
    html += "</div>"
    return html