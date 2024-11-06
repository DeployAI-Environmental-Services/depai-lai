import glob
import os
import subprocess
import time
import logging
import keras
import geopandas as gpd
import numpy as np
import tifffile as tiff
from osgeo import gdal, osr
from app.utils import (
    clean_temp_directory,
    create_directory,
    create_fishnet,
    stretch_n,
)
from app.config import ISZ, N_CLS, N_CHANNELS
from app.utils import array2raster


class NeuralNetwork:
    def __init__(self, model_folder, min_max):
        keras.utils.clear_session()
        self.model_folder = model_folder
        self.min_max = min_max
        self.model = None

    def load_model(self, weights_file_name="unet_lai_keras3_tf2_16_1.keras"):
        weights_path = os.path.join(self.model_folder, weights_file_name)
        self.model = keras.saving.load_model(weights_path)

    @classmethod
    def make_prediction_cropped(
        cls,
        model,
        x_train,
        initial_size=(572, 572),
        final_size=(388, 388),
        num_channels=10,
        num_masks=1,
    ):
        shift = int((initial_size[0] - final_size[0]) / 2)
        height = x_train.shape[1]
        width = x_train.shape[2]

        if height % final_size[1] == 0:
            num_h_tiles = int(height / final_size[1])
        else:
            num_h_tiles = int(height / final_size[1]) + 1

        if width % final_size[1] == 0:
            num_w_tiles = int(width / final_size[1])
        else:
            num_w_tiles = int(width / final_size[1]) + 1

        rounded_height = num_h_tiles * final_size[0]
        rounded_width = num_w_tiles * final_size[0]

        padded_height = rounded_height + 2 * shift
        padded_width = rounded_width + 2 * shift

        padded = np.zeros((num_channels, padded_height, padded_width))

        padded[:, shift : shift + height, shift : shift + width] = x_train

        # add mirror reflections to the padded areas
        up = padded[:, shift : 2 * shift, shift:-shift][:, ::-1]
        padded[:, :shift, shift:-shift] = up

        lag = padded.shape[1] - height - shift
        bottom = padded[:, height + shift - lag : shift + height, shift:-shift][:, ::-1]
        padded[:, height + shift :, shift:-shift] = bottom

        left = padded[:, :, shift : 2 * shift][:, :, ::-1]
        padded[:, :, :shift] = left

        lag = padded.shape[2] - width - shift
        right = padded[:, :, width + shift - lag : shift + width][:, :, ::-1]

        padded[:, :, width + shift :] = right

        h_start = range(0, padded_height, final_size[0])[:-1]
        assert len(h_start) == num_h_tiles

        w_start = range(0, padded_width, final_size[0])[:-1]
        assert len(w_start) == num_w_tiles

        temp = []
        for h in h_start:
            for w in w_start:
                temp += [padded[:, h : h + initial_size[0], w : w + initial_size[0]]]
        temp = np.array(temp)
        temp = np.transpose(temp, (0, 3, 2, 1))

        prediction = model.predict(np.array(temp))
        prediction = np.transpose(prediction, (0, 3, 2, 1))
        predicted_mask = np.zeros((num_masks, rounded_height, rounded_width))

        for j_h, h in enumerate(h_start):
            for j_w, w in enumerate(w_start):
                i = len(w_start) * j_h + j_w
                predicted_mask[:, h : h + final_size[0], w : w + final_size[0]] = (
                    prediction[i]
                )

        return predicted_mask[:, :height, :width]

    def predict_lai(self, image_path, offset, output_path):
        temp_path = os.path.dirname(output_path)
        fishnet_temp_directory = os.path.join(temp_path, "fishnet")
        tiles_temp_directory = os.path.join(temp_path, "tiles")
        predictions_temp_directory = os.path.join(temp_path, "predictions")
        create_directory(fishnet_temp_directory)
        create_directory(tiles_temp_directory)
        create_directory(predictions_temp_directory)
        fishnet_output_path = os.path.join(
            fishnet_temp_directory, os.path.basename(image_path).split(".")[0] + ".shp"
        )
        start_time = time.time()
        print("Start prediction")
        src = gdal.Open(image_path)
        ulx, xres, _, uly, _, yres = src.GetGeoTransform()
        lrx = ulx + (src.RasterXSize * xres)
        lry = uly + (src.RasterYSize * yres)
        proj = osr.SpatialReference(wkt=src.GetProjection())
        prj = proj.GetAttrValue("AUTHORITY", 1)
        del src
        create_fishnet(fishnet_output_path, ulx, lrx, lry, uly, 500, 500, prj, 20)
        gdf = gpd.read_file(fishnet_output_path)
        exploded_gdf = gdf.explode(index_parts=False)
        del gdf
        for i in range(0, len(exploded_gdf)):
            output_patch = os.path.join(
                tiles_temp_directory, "patch_" + str(i) + ".tif"
            )
            predicted_output_patch = os.path.join(
                predictions_temp_directory, "patch_" + str(i) + ".tif"
            )
            part_gd = exploded_gdf.loc[i]
            coords = part_gd.geometry.exterior.coords.xy
            x_min = str(np.amin(coords[0]))
            x_max = str(np.amax(coords[0]))
            y_min = str(np.amin(coords[1]))
            y_max = str(np.amax(coords[1]))
            gdal_cmd = [
                "gdalwarp",
                "-te",
                x_min,
                y_min,
                x_max,
                y_max,
                image_path,
                output_patch,
            ]
            subprocess.call(gdal_cmd)
            img_arr = tiff.imread(output_patch)
            img_arr = stretch_n(img_arr, self.min_max, offset=offset)
            img_arr = np.transpose(img_arr, (2, 1, 0))
            predicted_mask = self.make_prediction_cropped(
                self.model,
                img_arr,
                initial_size=(ISZ, ISZ),
                final_size=(ISZ - 32, ISZ - 32),
                num_masks=N_CLS,
                num_channels=N_CHANNELS,
            )
            predicted_mask = np.transpose(predicted_mask, (2, 1, 0))
            predicted_mask = np.squeeze(predicted_mask)
            dataset = gdal.Open(output_patch)
            array2raster(predicted_output_patch, dataset, predicted_mask, "Float32")
            del dataset
            os.remove(output_patch)
        clean_temp_directory(tiles_temp_directory)
        clean_temp_directory(fishnet_temp_directory)
        file_list = glob.glob(os.path.join(predictions_temp_directory, "*.tif"))
        files_string = " ".join(file_list)
        gdal_merge_cmd = (
            "python3 ./app/gdal_merge.py -o "
            + output_path
            + " -of gtiff "
            + files_string
        )
        os.system(gdal_merge_cmd)
        clean_temp_directory(predictions_temp_directory)
        end_time = time.time()
        execution_time = end_time - start_time
        logging.info("Prediction time for image %s", str(execution_time))
