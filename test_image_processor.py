import grpc
import pytest
import model_pb2
import model_pb2_grpc


@pytest.fixture(scope="module")
def grpc_stub():
    channel = grpc.insecure_channel("localhost:8061")
    stub = model_pb2_grpc.ImageProcessorStub(channel)
    yield stub
    channel.close()


def test_process_image(grpc_stub):
    request = model_pb2.ImageRequest(  # pylint:disable=E1101 # type: ignore
        images=[
            model_pb2.ImageData(  # pylint:disable=E1101 # type: ignore
                image_path="/data/test_img_10b.tif", offset=-1000
            ),
        ]
    )

    response = grpc_stub.ProcessImage(request)
    assert response.results
    for result in response.results:
        assert result.image_path in [
            "/data/test_img_10b.tif",
            "/data/test_img_10b2.tif",
        ]
        assert result.processed is True
