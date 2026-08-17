# Wildfire EO Portal

Wildfire severity assessment tool using Sentinel-2 imagery and Google Earth Engine.

[Live app](https://wildfire-eo-app.streamlit.app/)

The dashboard computes burn severity from pre/post-fire Sentinel-2 composites and reports burned area by severity class and land cover type. Built around three wildfire events in Greece, with support for arbitrary custom areas of interest.

## Demo

Pre-configured historical scenarios:

![Demo cases](assets/democases1.gif)

Custom AOI drawing tool:

![Interactive tool](assets/interactivetool1.gif)
![Interactive tool](assets/interactivetool2.gif)

## Features

- Automated Sentinel-2 L2A retrieval with cloud masking
- dNBR-based burn severity classification
- Burned area statistics by burn severity and land cover (ESA WorldCover)
- Interactive polygon/rectangle drawing for custom AOIs
- Pre-configured scenarios for wildfire events
