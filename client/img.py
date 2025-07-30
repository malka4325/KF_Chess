import pathlib
from typing import Union, Tuple

import cv2
import numpy as np


class Img:
    def __init__(self):
        self.img = None
    
    @classmethod
    def create_blank(cls, width: int, height: int, color: Tuple[int, int, int, int] = (0, 0, 0, 255)):
        """Create a blank RGBA image of specified size and color."""
        new_img = cls()
        new_img.img = np.full((height, width, 4), color, dtype=np.uint8)
        return new_img

    def read(self, path: Union[str, pathlib.Path],
             size: Union[Tuple[int, int], None] = None,
             keep_aspect: bool = False,
             interpolation: int = cv2.INTER_AREA):
        """
        Load `path` into self.img and **optionally resize**.

        Parameters
        ----------
        path : str | Path
            Image file to load.
        size : (width, height) | None
            Target size in pixels.  If None, keep original.
        keep_aspect : bool
            • False  → resize exactly to `size`
            • True   → shrink so the *longer* side fits `size` while
                       preserving aspect ratio (no cropping).
        interpolation : OpenCV flag
            E.g.  `cv2.INTER_AREA` for shrink, `cv2.INTER_LINEAR` for enlarge.

        Returns
        -------
        Img
            `self`, so you can chain:  `sprite = Img().read("foo.png", (64,64))`
        """
        path = str(path)
        self.img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if self.img is None:
            raise FileNotFoundError(f"Cannot load image: {path}")

        # If image has 3 channels, convert to 4 for consistency (alpha=255)
        if self.img.shape[2] == 3:
            self.img = cv2.cvtColor(self.img, cv2.COLOR_BGR2BGRA)

        if size is not None:
            target_w, target_h = size
            h, w = self.img.shape[:2]

            if keep_aspect:
                scale = min(target_w / w, target_h / h)
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))
            else:
                new_w, new_h = target_w, target_h

            self.img = cv2.resize(self.img, (new_w, new_h), interpolation=interpolation)
            if self.img.shape[0] == 0 or self.img.shape[1] == 0:
                raise ValueError(f"Invalid resized image: {self.img.shape} from {path}")

            # print(f"[DEBUG] Resized {path} to {self.img.shape}") # Commented out for cleaner output

        return self

    def copy(self):
        new_img = Img()
        new_img.img = self.img.copy()
        return new_img

    def draw_on(self, other_img, x, y):
        if self.img is None or other_img.img is None:
            raise ValueError("Both images must be loaded before drawing.")

        # Ensure consistent channel count for alpha blending
        src_img_rgba = self.img
        if src_img_rgba.shape[2] == 3: # If source is BGR, convert to BGRA (alpha=255)
            src_img_rgba = cv2.cvtColor(self.img, cv2.COLOR_BGR2BGRA)

        h, w = src_img_rgba.shape[:2]
        H, W = other_img.img.shape[:2]

        if h == 0 or w == 0:
            # print(f"[WARN] Skipping draw: source image has 0 size: {self.img.shape}") # Commented out
            return

        # Check boundaries
        if y < 0 or x < 0 or y + h > H or x + w > W:
            # print(f"[WARN] Skipping draw at ({x},{y}): roi size {(h, w)} exceeds board {(H, W)}") # Commented out
            return

        # Get region of interest on the destination image
        roi = other_img.img[y:y + h, x:x + w]

        # Split source image into channels and get alpha mask
        b, g, r, a = cv2.split(src_img_rgba)
        mask = a / 255.0

        # Perform alpha blending for each color channel
        for c in range(3): # BGR channels
            roi[..., c] = (1 - mask) * roi[..., c] + mask * src_img_rgba[..., c]
        
        # Also blend the alpha channel if the destination has one
        if other_img.img.shape[2] == 4:
            other_img.img[y:y+h, x:x+w, 3] = (1 - mask) * other_img.img[y:y+h, x:x+w, 3] + mask * src_img_rgba[..., 3]


    def put_text(self, txt, x, y, font_size, color=(255, 255, 255, 255), thickness=1):
        if self.img is None:
            raise ValueError("Image not loaded.")
        
        # Ensure the color is BGR or BGRA depending on the image channels for putText
        display_color = color
        if self.img.shape[2] == 3 and len(color) == 4:
            display_color = color[:3] # Use only BGR channels if destination is BGR
        elif self.img.shape[2] == 4 and len(color) == 3:
            display_color = (*color, 255) # Add alpha channel if destination is BGRA and color is BGR

        cv2.putText(self.img, txt, (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX, font_size,
                    display_color, thickness, cv2.LINE_AA)

    def show(self):
        if self.img is None:
            raise ValueError("Image not loaded.")
        cv2.imshow("Image", self.img)
        cv2.waitKey(1)

    def draw_rect(self, x1, y1, x2, y2, color):
        cv2.rectangle(self.img, (x1, y1), (x2, y2), color, 2)