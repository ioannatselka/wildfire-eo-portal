import ee

def add_ndvi(image):
    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
    return image.addBands(ndvi)


def add_nbr(image):
    nbr = image.normalizedDifference(["B8A", "B12"]).rename("NBR")
    return image.addBands(nbr)

def compute_dnbr(nbr_before, nbr_after):
    
    before_nbr = nbr_before.select("NBR")
    after_nbr = nbr_after.select("NBR")

    diff = before_nbr.subtract(after_nbr)
    diff = diff.rename("dNBR")

    return diff


def get_s2_composite(aoi, start_date, end_date):
    """Fetches median Sentinel-2 SR composite for an AOI and adds NBR band."""
    img = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(start_date.isoformat(), end_date.isoformat())
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
        .median()
        .clip(aoi)
    )
    return add_nbr(img)