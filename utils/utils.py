import numpy as np
from skimage import measure
from PIL import Image, ImageDraw
import json
from statistics import mean
import cv2
from pathlib import Path
import matplotlib.pyplot as plt


def hwc_to_chw(img):
    return np.transpose(img, axes=[2, 0, 1])


def normalize(x):
    return x / 255


def batch(iterable, batch_size):
    """Yields lists by batch"""
    b = []
    for i, t in enumerate(iterable):
        b.append(t)
        if (i + 1) % batch_size == 0:
            yield b
            b = []

    if len(b) > 0:
        yield b


def original_add_pred():
    # original 画像に　外線を加える
    input_path = sorted(
        Path(
            "/home/kazuya/weakly_supervised_instance_segmentation/outputs/pred/sophisticated_pred/"
        ).glob("*.tif")
    )
    original_path = sorted(Path("./images/test/ori").glob("*.tif"))
    for i, path in enumerate(input_path):
        img = cv2.imread(str(path), 0)
        # img = cv2.imread("./outputs/2019-01-18/test/mask_pred/00000.tif", 0)
        mask = np.zeros(img.shape, dtype=np.uint8)
        plt.imshow(img > 0.5), plt.show()
        for label in range(1, img.max() + 1):
            contours = measure.find_contours(img, 0.5)
            for contour in contours:
                for x, y in contour:
                    mask[int(x), int(y)] = 255
        # img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        # mask_color = np.zeros(img.shape)
        # mask_color[:, :, 0] = mask
        original = cv2.imread(str(original_path[i]), -1)
        # original = cv2.imread("./images/test/exp1_F0002-00300.tif", -1)
        original = (original / 4096 * 255).astype(np.uint8)
        original = cv2.cvtColor(original, cv2.COLOR_GRAY2BGR)
        mask_color = np.zeros(original.shape, dtype=np.uint8)
        mask_color[:, :, 2] = mask
        img = cv2.addWeighted(original, 0.8, mask_color, 0.2, 1)
        plt.imshow(img), plt.show()

        cv2.imwrite(f"out{i:05d}.png", img)


def make_ground_truth(file_path, save_path):
    with open(file_path) as f:
        df = json.load(f)
        im = Image.new("I", (1392, 1040), 0)
        draw = ImageDraw.Draw(im)
        for i, label in enumerate(df["shapes"]):
            plots = []
            for x, y in label["points"]:
                plots.append((x, y))
            draw.polygon(tuple(plots), fill=i + 1)
        mask = np.array(im)
        cv2.imwrite(save_path, mask)



