import logging
import os
import folium
import numpy as np
import rasterio
import matplotlib
from PIL import Image, ImageDraw
from rasterio.io import MemoryFile
from rasterio.warp import Resampling, calculate_default_transform, reproject


def normalize(array, min_value, max_value):
    return (array - min_value) / (max_value - min_value)


def apply_colormap(image, cmap_name="viridis"):
    cmap = matplotlib.colormaps.get_cmap(cmap_name)  # type: ignore
    colored_image = cmap(image)
    return (colored_image[:, :, :3] * 255).astype(np.uint8)


def reproject_to_wgs84(src, bands):
    dst_crs = "EPSG:4326"
    transform, width, height = calculate_default_transform(
        src.crs, dst_crs, src.width, src.height, *src.bounds
    )
    reprojected_bands = [
        np.empty((height, width), dtype=src.read(1).dtype) for _ in bands  # type: ignore
    ]
    for i, band in enumerate(bands):
        reproject(
            source=rasterio.band(src, band),
            destination=reprojected_bands[i],
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=dst_crs,
            resampling=Resampling.nearest,
        )
    return reprojected_bands, transform


def calculate_map_center(bounds_list):
    min_lat = float("inf")
    min_lon = float("inf")
    max_lat = float("-inf")
    max_lon = float("-inf")
    for bounds in bounds_list:
        bottom_left = bounds[0]
        top_right = bounds[1]
        min_lat = min(min_lat, bottom_left[0])
        min_lon = min(min_lon, bottom_left[1])
        max_lat = max(max_lat, top_right[0])
        max_lon = max(max_lon, top_right[1])
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2
    return center_lat, center_lon


def visualize_on_map(list_img_path, list_lai_path, output_map_path):
    image_list = []
    lai_list = []
    bounds_list = []
    name_list = []
    for img_path, lai_path in zip(list_img_path, list_lai_path):
        with rasterio.open(img_path) as dataset:
            rgb_bands, transform = reproject_to_wgs84(dataset, bands=[3, 2, 1])
            red_band = normalize(rgb_bands[0], min_value=0, max_value=7000)
            green_band = normalize(rgb_bands[1], min_value=0, max_value=7000)
            blue_band = normalize(rgb_bands[2], min_value=0, max_value=7000)
            rgb_image = np.dstack((red_band, green_band, blue_band))
            rgb_image[rgb_image < 0] = 0
            rgb_image[rgb_image > 1] = 1
            rgb_image = rgb_image * 5.5
            bounds = rasterio.transform.array_bounds(  # type: ignore
                rgb_bands[0].shape[0], rgb_bands[0].shape[1], transform
            )
        with rasterio.open(lai_path) as dataset:
            lai_image, _ = reproject_to_wgs84(dataset, bands=[1])
            lai_normalized = normalize(lai_image[0], min_value=0, max_value=8)
            colored_lai_image = apply_colormap(lai_normalized, cmap_name="RdYlGn")

        nodata_mask = np.all(rgb_image == 0, axis=-1)
        rgba_image = np.dstack((rgb_image, ~nodata_mask * 255))
        rgba_lai_image = np.dstack((colored_lai_image, ~nodata_mask * 255))
        image_list.append(rgba_image)
        lai_list.append(rgba_lai_image)
        bounds_list.append([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
        name_list.append(os.path.basename(img_path).split(".")[0])

    map_center = calculate_map_center(bounds_list)
    m = folium.Map(location=map_center, zoom_start=12)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
        name="Esri Satellite",
        overlay=False,
        control=True,
    ).add_to(m)
    for img, lai, bound, name in zip(image_list, lai_list, bounds_list, name_list):
        folium.raster_layers.ImageOverlay(  # type: ignore
            image=img,
            bounds=bound,
            opacity=1,
            name=name,
        ).add_to(m)
        folium.raster_layers.ImageOverlay(  # type: ignore
            image=lai,
            bounds=bound,
            opacity=1,
            name=name + "_LAI",
        ).add_to(m)
    folium.LayerControl().add_to(m)
    m.save(output_map_path)
