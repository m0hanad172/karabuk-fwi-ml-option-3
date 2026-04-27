import os
import numpy as np
from fastapi import FastAPI, UploadFile, File, Query, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
import ee
import folium
import requests
from folium import raster_layers
import geemap
from utils import (
    start_auto_save_thread, predict_region, detect_fire_from_image,
    start_drone, stop_drone, drone_feed_stream,
    detect_fire_from_drone, get_all_predictions, get_parameters
)
from cameras import start_camera, stop_camera, get_camera_frame_generator, get_notifications
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from config import OPENWEATHER_API_KEY, EE_ASSET_PATH, EE_Project_ID

app = FastAPI()

os.makedirs("uploads/notifications", exist_ok=True)
app.mount("/static/notifications", StaticFiles(directory="uploads/notifications"), name="notifications")

#
# Authenticate once when the server starts
# ee.Initialize()
@app.on_event("startup")
def init_ee():
    ee.Initialize(project=EE_Project_ID)


# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def start_auto_save():
    start_auto_save_thread()


@app.get("/predict/{region}")
def predict(region: str):
    return predict_region(region)


@app.post("/detect_fire/")
async def detect_fire(file: UploadFile = File(...)):
    return await detect_fire_from_image(file)


@app.post("/start_drone")
async def start_drone_route():
    return start_drone()


@app.post("/stop_drone")
async def stop_drone_route():
    return stop_drone()


@app.get("/drone_feed")
async def drone_feed():
    return drone_feed_stream()

@app.post("/start_camera/{cam_id}")
async def start_camera_route(cam_id: str):
    success = start_camera(cam_id)
    return {"status": "started" if success else "already_running_or_invalid"}

@app.post("/stop_camera/{cam_id}")
async def stop_camera_route(cam_id: str):
    success = stop_camera(cam_id)
    return {"status": "stopped" if success else "not_running"}

@app.get("/camera_feed/{cam_id}")
async def camera_feed(cam_id: str):
    return StreamingResponse(
        get_camera_frame_generator(cam_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.get("/notifications")
async def notifications_route():
    return get_notifications()


@app.get("/detect_fire_drone/")
async def detect_fire_drone_route():
    return await detect_fire_from_drone()


@app.get("/get_predictions")
def get_predictions():
    return get_all_predictions()


@app.get("/map", response_class=HTMLResponse)
def get_fire_map(
    city: str = Query("Karabuk"),
    beforeStart: str = Query("2025-06-01"),
    beforeEnd: str = Query("2025-06-25"),
    afterStart: str = Query("2025-07-25"),
    afterEnd: str = Query("2025-08-05")
):
    provinces = ee.FeatureCollection("FAO/GAUL_SIMPLIFIED_500m/2015/level1")
    region = provinces.filter(ee.Filter.eq('ADM1_NAME', city))

    # --- Sentinel-2 data ---
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
        .filterBounds(region) \
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
        .select(['B2','B3','B4','B8','B11','B12'])

    before = s2.filterDate(beforeStart, beforeEnd).median().clip(region)
    after = s2.filterDate(afterStart, afterEnd).median().clip(region)

    # --- Indices ---
    def savi(img):
        return img.expression(
            '((NIR - RED) / (NIR + RED + 0.5)) * 1.5',
            {'NIR': img.select('B8'), 'RED': img.select('B4')}
        ).rename('SAVI')

    def bsi(img):
        return img.expression(
            '((SWIR + RED) - (NIR + BLUE)) / ((SWIR + RED) + (NIR + BLUE))',
            {'SWIR': img.select('B11'), 'RED': img.select('B4'),
            'NIR': img.select('B8'), 'BLUE': img.select('B2')}
        ).rename('BSI')

    def addIndices(img):
        ndvi = img.normalizedDifference(['B8','B4']).rename('NDVI')
        nbr  = img.normalizedDifference(['B8','B12']).rename('NBR')
        return img.addBands([ndvi, nbr, savi(img), bsi(img)])

    beforeIdx = addIndices(before)
    afterIdx  = addIndices(after)

    # --- Difference features ---
    dNBR = beforeIdx.select('NBR').subtract(afterIdx.select('NBR')).rename('dNBR')
    dBSI = beforeIdx.select('BSI').subtract(afterIdx.select('BSI')).rename('dBSI')
    dNDVI = beforeIdx.select('NDVI').subtract(afterIdx.select('NDVI')).rename('dNDVI')
    dNBR_div_NDVI = dNBR.divide(dNDVI).rename('dNBR_NDVI_ratio')

    # --- Terrain features ---
    srtm = ee.Image('USGS/SRTMGL1_003').clip(region).rename('elevation')
    slope = ee.Terrain.slope(srtm).rename('slope')
    tpi = srtm.subtract(
        srtm.reduceNeighborhood(ee.Reducer.mean(), ee.Kernel.circle(radius=3))
    ).rename('TPI')

    # --- LST (MODIS) ---
    lst = ee.ImageCollection('MODIS/061/MOD11A1') \
        .filterBounds(region) \
        .filterDate(beforeStart, afterEnd) \
        .select('LST_Day_1km') \
        .mean() \
        .multiply(0.02) \
        .rename('LST')

    # --- Post-fire Sentinel-2 bands ---
    postBands = after.select(['B8','B11']).rename(['post_B8','post_B11'])

    # --- Final stack (all 10 input bands) ---
    stack_region = ee.Image.cat([
        postBands, dNBR, dNBR_div_NDVI, dBSI, dNDVI,
        srtm, slope, tpi, lst
    ]).toFloat().clip(region)

    # --- Classify ---
    model = ee.Classifier.load(EE_ASSET_PATH)
    classified = stack_region.classify(model)
    
    ########################
    weather_url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}"
    weather = requests.get(weather_url).json()

    wind_deg = weather["wind"]["deg"]
    wind_speed = weather["wind"]["speed"]
    
    ########################

    # --- Visualization ---
    center = region.geometry().centroid().coordinates().getInfo()[::-1]
    m = folium.Map(location=center, zoom_start=9)
    ########################
    # Wind Arrow Marker
    icon_html = f"""
    <div style="transform: rotate({wind_deg}deg); font-size: 28px;">
        ➤
    </div>
    """

    folium.Marker(
        location=center,
        icon=folium.DivIcon(html=icon_html),
        tooltip=f"Wind Speed: {wind_speed} m/s, Direction: {wind_deg}°"
    ).add_to(m)
    ########################

    visRGB = {'bands': ['B4','B3','B2'], 'min': 0, 'max': 3000}
    rgb_before_id = before.visualize(**visRGB).getMapId()['tile_fetcher'].url_format
    rgb_after_id  = after.visualize(**visRGB).getMapId()['tile_fetcher'].url_format

    burned_only = classified.eq(1).selfMask()
    burned_id = burned_only.visualize(**{'palette':'#FF0000'}).getMapId()['tile_fetcher'].url_format
    classified_id = classified.visualize(**{'min':0, 'max':1, 'palette':['#00FF00','#FF0000']}).getMapId()['tile_fetcher'].url_format

    # Add attr parameter to each layer
    raster_layers.TileLayer(
        tiles=rgb_before_id,
        name='Before RGB',
        attr='Map data © Google Earth Engine'
    ).add_to(m)

    raster_layers.TileLayer(
        tiles=rgb_after_id,
        name='After RGB',
        attr='Map data © Google Earth Engine'
    ).add_to(m)

    raster_layers.TileLayer(
        tiles=burned_id,
        name='Burned Only',
        attr='Map data © Google Earth Engine'
    ).add_to(m)

    raster_layers.TileLayer(
        tiles=classified_id,
        name='All Classes',
        attr='Map data © Google Earth Engine'
    ).add_to(m)

    folium.LayerControl().add_to(m)

    return m._repr_html_()