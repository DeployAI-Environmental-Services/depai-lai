# Use Ubuntu 22.04 as the base image
FROM ubuntu:22.04

ENV GDAL_VERSION=3.4.1
ENV GDAL_CONFIG=/usr/bin/gdal-config
# Update package lists and install dependencies
RUN apt-get -y update \
    && apt-get install -y --no-install-recommends \
    software-properties-common \
    wget \
    gdal-bin \
    libgdal-dev \
    libspatialindex-dev \
    gcc \
    g++ \
    python3-dev \
    python3-pip \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for GDAL
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

RUN mkdir /lai

# COPY . /lai/

COPY . /lai/

# Set the working directory
WORKDIR /lai

# Install Python dependencies
RUN pip uninstall -y blinker numpy
RUN pip install --upgrade pip \
    && pip install --upgrade --ignore-installed -r requirements.txt \
    && pip install GDAL==${GDAL_VERSION} rasterio==1.3.5 \
    && pip install numpy==1.26.4

RUN gdown --id 1VREu4kPKB3hp0TpvVAXmy45W89GqYDx5 --output /lai/app/weights/unet_lai_keras3_tf2_16_1.keras


# Set the command to run the application
CMD ["python3", "serve.py"]