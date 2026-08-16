# classify.py
import ee

SEVERITY_THRESHOLDS = {
    "Unburned":  (-1.0, 0.099),
    "Low":       (0.10, 0.269),
    "Moderate":  (0.27, 0.439),
    "High":      (0.44, 0.659),
    "Very High": (0.66, 1.300),
}

SEVERITY_VALUES = {
    "Unburned": 0, "Low": 1, "Moderate": 2, "High": 3, "Very High": 4,
}


def get_non_burnable_mask(aoi, exclude_cropland=True):
    """
    Returns a mask where 1 = vegetation (forests/shrublands/grasslands),
    0 = Water (80), Built-up (50), Cropland (40).
    """
    landcover = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
    
    not_water = landcover.neq(80)
    not_builtup = landcover.neq(50)
    valid_land = not_water.And(not_builtup)
    
    if exclude_cropland:
        not_cropland = landcover.neq(40) # Class 40 = Cropland
        valid_land = valid_land.And(not_cropland)

    return valid_land


def detect_burned_area(dnbr, after_img=None, threshold=0.10, min_pixels=10, exclude_cropland=True):

    burned = dnbr.select("dNBR").gte(threshold)

    land_mask = get_non_burnable_mask(dnbr.geometry(), exclude_cropland=exclude_cropland)
    burned = burned.updateMask(land_mask)

    if after_img is not None:
        bands = after_img.bandNames().getInfo()
        
        if "NBR" in bands:
            post_nbr = after_img.select("NBR")
            burned = burned.updateMask(post_nbr.lt(0.05))
            
        if "B12" in bands:
            swir2 = after_img.select("B12")
            burned = burned.updateMask(swir2.gt(1200))

    pixel_count = burned.connectedPixelCount(maxSize=100, eightConnected=True)
    min_area_mask = pixel_count.gte(min_pixels)
    burned = burned.updateMask(min_area_mask)

    return burned.rename("burned").selfMask()


def classify_dnbr(dnbr, after_img=None, mask_to_burned_only=True, threshold=0.10, min_pixels=10, exclude_cropland=True):

    severity = ee.Image(0).rename("severity")

    for name, (lo, hi) in SEVERITY_THRESHOLDS.items():
        if name == "Unburned":
            continue
        class_value = SEVERITY_VALUES[name]
        mask = dnbr.gte(lo).And(dnbr.lt(hi))
        severity = severity.where(mask, class_value)

    # Clean burned mask
    clean_burned_mask = detect_burned_area(
        dnbr, 
        after_img=after_img, 
        threshold=threshold, 
        min_pixels=min_pixels,
        exclude_cropland=exclude_cropland
    )

    if mask_to_burned_only:
        severity = severity.updateMask(clean_burned_mask)

    return severity.rename("severity")


def get_filled_burned_mask(burned_mask):

    clean = burned_mask.updateMask(burned_mask.connectedPixelCount(50, True).gte(10))
    filled = clean.focalMax(90, 'circle', 'meters').focalMin(90, 'circle', 'meters')
    return filled


def get_burned_landcover(filled_mask, aoi=None):

    landcover = ee.Image("ESA/WorldCover/v200/2021").select("Map")
    landcover_no_water = landcover.updateMask(landcover.neq(80))
    masked_lc = landcover_no_water.updateMask(filled_mask)
    
    if aoi is not None:
        return masked_lc.clip(aoi)
    return masked_lc