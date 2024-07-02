import errno
import logging
from math import ceil
import os
import shutil
import numpy as np
import geopandas as gpd
from osgeo import gdal, osr, ogr
from app.config import NODATAVALUE


def clean_temp_directory(folder_name: str):
    try:
        shutil.rmtree(folder_name)
    except OSError as e:
        logging.error("Error: %s - %s.", e.filename, e.strerror)


def create_directory(folder_name: str):
    if not os.path.exists(folder_name):
        try:
            os.mkdir(folder_name)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise


def array2raster(
    new_raster_fn,
    dataset,
    array,
    dtype,
    nodatavalue=NODATAVALUE,
    add_colortable=False,
    colortable=None,
):
    cols = array.shape[1]
    rows = array.shape[0]
    origin_x, pixel_width, b, origin_y, _, pixel_height = dataset.GetGeoTransform()
    driver = gdal.GetDriverByName("GTiff")
    gdt_dtype = gdal.GDT_Unknown
    if dtype == "Byte":
        gdt_dtype = gdal.GDT_Byte
    elif dtype == "Float32":
        gdt_dtype = gdal.GDT_Float32
    else:
        print("Not supported data type.")
    if array.ndim == 2:
        band_num = 1
    else:
        band_num = array.shape[2]

    out_raster = driver.Create(new_raster_fn, cols, rows, band_num, gdt_dtype)
    out_raster.SetGeoTransform((origin_x, pixel_width, 0, origin_y, 0, pixel_height))
    for b in range(band_num):
        outband = out_raster.GetRasterBand(b + 1)
        if band_num == 1:
            outband.WriteArray(array)
        else:
            outband.WriteArray(array[:, :, b])

    prj = dataset.GetProjection()
    out_raster_srs = osr.SpatialReference(wkt=prj)
    out_raster.SetProjection(out_raster_srs.ExportToWkt())
    out_raster.GetRasterBand(1).SetNoDataValue(nodatavalue)
    if add_colortable:
        colors = gdal.ColorTable()
        for i in range(colortable.GetCount()):
            s_entry = colortable.GetColorEntry(i)
            colors.SetColorEntry(i + 1, s_entry)
        out_raster.GetRasterBand(1).SetRasterColorTable(colors)
        out_raster.GetRasterBand(1).SetRasterColorInterpretation(gdal.GCI_PaletteIndex)
    outband.FlushCache()


def stretch_n(bands, min_max, offset=None):
    out = np.zeros_like(bands, dtype=np.float32)
    n = bands.shape[2]
    if n == 11:
        n = n - 1
    for i in range(n):
        a = 0  # np.min(band)
        b = 1  # np.max(band)
        c = min_max[i, 0]
        d = min_max[i, 1]
        if offset:
            bands[:, :, i] = bands[:, :, i] + offset
        t = a + (bands[:, :, i] + -c) * (b - a) / (d - c)
        t[t < a] = a
        t[t > b] = b
        out[:, :, i] = t
    return out.astype(np.float32)


def create_fishnet(
    output_grid_fn: str,
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
    grid_height: int,
    grid_width: int,
    prj: str,
    pixel_size: float,
):
    # pylint: disable = C0103
    # convert sys.argv to float
    xmin = float(xmin)
    xmax = float(xmax)
    ymin = float(ymin)
    ymax = float(ymax)
    grid_width = ceil(float(grid_width) * pixel_size)
    grid_height = ceil(float(grid_height) * pixel_size)
    #     get rows
    rows = ceil((ymax - ymin) / grid_height)
    # get columns
    cols = ceil((xmax - xmin) / grid_width)
    # start grid cell envelope
    ringXleftOrigin = xmin
    ringXrightOrigin = xmin + grid_width
    ringYtopOrigin = ymax
    ringYbottomOrigin = ymax - grid_height

    # create output file
    outDriver = ogr.GetDriverByName("ESRI Shapefile")
    if os.path.exists(output_grid_fn):
        os.remove(output_grid_fn)
    outDataSource = outDriver.CreateDataSource(output_grid_fn)
    outLayer = outDataSource.CreateLayer(output_grid_fn, geom_type=ogr.wkbPolygon)
    featureDefn = outLayer.GetLayerDefn()

    # create grid cells
    countcols = 0
    while countcols < cols:
        countcols += 1

        # reset envelope for rows
        ringYtop = ringYtopOrigin
        ringYbottom = ringYbottomOrigin
        countrows = 0

        while countrows < rows:
            countrows += 1
            ring = ogr.Geometry(ogr.wkbLinearRing)
            ring.AddPoint(ringXleftOrigin, ringYtop)
            ring.AddPoint(ringXrightOrigin, ringYtop)
            ring.AddPoint(ringXrightOrigin, ringYbottom)
            ring.AddPoint(ringXleftOrigin, ringYbottom)
            ring.AddPoint(ringXleftOrigin, ringYtop)
            poly = ogr.Geometry(ogr.wkbPolygon)
            poly.AddGeometry(ring)

            # add new geom to layer
            outFeature = ogr.Feature(featureDefn)
            outFeature.SetGeometry(poly)
            outLayer.CreateFeature(outFeature)
            outFeature = None

            # new envelope for next poly
            ringYtop = ringYtop - grid_height
            ringYbottom = ringYbottom - grid_height

        # new envelope for next poly
        ringXleftOrigin = ringXleftOrigin + grid_width
        ringXrightOrigin = ringXrightOrigin + grid_width

    # Save and close DataSources
    outDataSource = None
    gdf = gpd.read_file(output_grid_fn)
    gdf.crs = {"init": "epsg:" + str(prj)}
    gdf.to_file(output_grid_fn)
