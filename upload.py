import os
import zipfile
import grpc
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    send_file,
    session,
    url_for,
    flash,
)
from model_pb2_grpc import ImageProcessorStub
from model_pb2 import ImageRequest, ImageData  # type: ignore # pylint:disable=E0611
from visualize_output import visualize_on_map


data_dir = os.getenv("SHARED_FOLDER_PATH")
print("DATADIR", data_dir)
channel = grpc.insecure_channel("localhost:8061")
stub = ImageProcessorStub(channel)
app = Flask(__name__, static_folder=data_dir)
app.secret_key = "7038c774900b84f40f6cae8927187da2"
app.config["UPLOAD_FOLDER"] = os.path.join(data_dir, "uploads/")  # type: ignore
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024  # Max file size: 16MB


os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

ALLOWED_EXTENSIONS = {"tif"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    map_path = session.get("map_path")  # Retrieve single map path from session
    zip_path = session.get("zip_path")  # Retrieve the zip file path from session
    return render_template("index.html", map_path=map_path, zip_path=zip_path)


@app.route("/download/<filename>")
def download_file(filename):
    # Serve the zip file for download
    zip_filepath = os.path.join(os.path.dirname(app.config["UPLOAD_FOLDER"]), filename)
    return send_file(zip_filepath, as_attachment=True)


@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        flash("No file part")
        return redirect(request.url)

    files = request.files.getlist("file")
    offset = int(request.form.get("offset"))  # type: ignore
    print(files)
    print(offset)

    if not files:
        flash("No selected file")
        return redirect(request.url)
    file_paths = []

    for file in files:
        if file.filename == "":
            flash("No selected file")
            continue

        if allowed_file(file.filename):
            filename = file.filename
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)  # type: ignore
            file.save(file_path)
            file_paths.append(file_path)
        else:
            flash(f"Invalid file type for {file.filename}", "error")

    if file_paths:
        try:
            response = process_images_via_grpc(file_paths, offset)
            # flash(f"Processing results: {response.entries}", "success")
            list_img_paths = []  # Store paths of generated maps
            list_lai_paths = []
            if response.results:
                for result in response.results:
                    img_path = result.image_path
                    lai_path = result.result_path
                    if lai_path is not None:
                        list_img_paths.append(img_path)
                        list_lai_paths.append(lai_path)
                output_map_path = os.path.join(
                    os.path.dirname(lai_path), "map_viz.html"
                )
                zip_filename = "processed_files.zip"
                zip_filepath = os.path.join(os.path.dirname(lai_path), zip_filename)
                with zipfile.ZipFile(zip_filepath, "w") as zipf:
                    for file in list_lai_paths:
                        zipf.write(file, os.path.basename(file))
                visualize_on_map(list_img_paths, list_lai_paths, output_map_path)
                # Provide the paths to the generated maps in the response
                flash("Processing complete. Check the generated maps.", "success")
                session["map_path"] = output_map_path
                session["zip_path"] = zip_filepath
                return redirect(url_for("index"))
        except Exception as e:
            flash(f"Error during processing: {str(e)}", "error")
    return redirect(url_for("index"))


def process_images_via_grpc(list_image_path, offset):
    list_input = []
    for image_path in list_image_path:
        list_input.append(ImageData(image_path=image_path, offset=offset))
    req = ImageRequest(images=list_input)
    response = stub.ProcessImage(req)
    return response


def app_run():
    app.run(host="0.0.0.0", port=8062, debug=False)
