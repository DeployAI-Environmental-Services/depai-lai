# Leaf Area Index Estimation for Sentinel-2 Images

This repository provides a deep learning model for Leaf Area Index (LAI estimation) from Sentinel-2 satellite images exposed using a webapp.

## Input format

The model assumes that the input images are Geotiff images. The minimum allowed size of these images is $500\times500$. 10 Spectral bands are used for the estimation of LAI, which must be in the following order `['B02','B03','B04','B05','B06','B07','B08','B8A','B11','B12']`.
The input to the model is a list of dictionaries, each dictionary contains the input image path and the offset of the bands for normalization.

```python
[
    {
        "image_path":str,
        "offset":float
    }
]
```

For more details on the format of the input and output for the model, check `model.proto`.

## Local Development

- In a terminal, clone the repository

```powershell
git clone https://github.com/AlbughdadiM/depai-lai.git
```

- Go to the repository directory

```powershell
cd depai-lai
```

- If the files `model_pb2_grpc.py` and `model_pb2.py` are not there, generate them using

```powershell
python3.10 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. model.proto
```

- Build the docker image

```powershell
docker build . -t lai:v0.1
```

- Create a container from the built image

```powershell
docker run --name=test  -v ./test_folder:/data  --env SHARED_FOLDER_PATH=/data -p 8061:8061 -p 8062:8062 lai:v0.1
```

- Run the pytest

```powershell
pytest test_image_processor.py
```

## Container Registry

- Generate a personal access token: Github account settings > Developer settings > Personal access tokens (classic). Generate a token with the `read:package` scope.

- In a terminal, login to container registry using

```powershell
docker login ghcr.io -u USERNAME -p PAT
```

- Pull the image

```powershell
docker pull ghcr.io/albughdadim/depai-lai:v0.1
```

- Create a container

```powershell
docker run --name=test  -v ./test_folder:/data  --env SHARED_FOLDER_PATH=/data -p 8061:8061 -p 8062:8062 ghcr.io/albughdadim/depai-lai:v0.1
```
