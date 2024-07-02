import time
import grpc
from concurrent import futures
import model_pb2
import model_pb2_grpc
from app.inference import lai_estimate


class ImageProcessorServicer(model_pb2_grpc.ImageProcessorServicer):
    def ProcessImage(self, request, context):
        list_images = []
        for image in request.images:
            image_dict = {"image_path": image.image_path, "offset": image.offset}
            list_images.append(image_dict)

        result = self.run_model(list_images)

        results = []
        for res in result:
            processed_image = model_pb2.ImageResponse.ProcessedImage(
                image_path=res["image_path"],
                processed=res["processed"],
                result_path=res["result_path"],
            )
            results.append(processed_image)

        return model_pb2.ImageResponse(results=results)

    def run_model(self, list_images):
        results = lai_estimate(list_images)
        return results


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    model_pb2_grpc.add_ImageProcessorServicer_to_server(
        ImageProcessorServicer(), server
    )
    server.add_insecure_port("[::]:8061")
    server.start()
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    serve()
