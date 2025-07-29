from mock_img import mock_graphics_image_loader 

class MockImgFactory:
    def __init__(self):
        pass

    def __call__(self, path, size=None, keep_aspect=False, interpolation=None):
        return mock_graphics_image_loader(path, size, keep_aspect)

    def read(self, path, size=None, keep_aspect=False):
        return mock_graphics_image_loader(path, size, keep_aspect)