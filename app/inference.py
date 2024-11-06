import uuid
import logging
import os
from typing import Dict, List
import numpy as np
from osgeo import gdal
from app.lai_unet import NeuralNetwork
from app.utils import create_directory


def lai_estimate(list_images: List[str]) -> List[Dict]:
    task_id = str(uuid.uuid4())
    logging.info("Initialization LAI Model")
    g_min_max = np.load("./app/weights/global_min_max_v2.npy")
    model = NeuralNetwork("./app/weights", g_min_max)
    model.load_model()
    temp_path = os.path.join(os.path.dirname(list_images[0]["image_path"]), task_id)  # type: ignore
    create_directory(temp_path)
    processing_status = []
    for image in list_images:
        image_path = image["image_path"]  # type: ignore
        offset = image["offset"]  # type: ignore
        img_filename = os.path.basename(image_path)
        res_output = {
            "image_path": image_path,
            "processed": False,
            "result_path": None,
        }
        dataset = gdal.Open(image_path)
        del dataset
        prediction_output_path = os.path.join(
            temp_path, img_filename.split(".")[0] + "_LAI.tif"
        )
        model.predict_lai(image_path, offset, prediction_output_path)
        if os.path.exists(prediction_output_path):
            res_output = {
                "image_path": image_path,
                "processed": True,
                "result_path": prediction_output_path,
            }
        processing_status.append(res_output)
    # clean_temp_directory(temp_path)
    return processing_status
