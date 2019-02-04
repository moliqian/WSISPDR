from utils import *
from pathlib import Path
from datetime import datetime
from PIL import Image
import cv2


class Predict:
    def __init__(self, net, gpu, root_path, save_path, norm_value=255):
        self.net = net
        self.gpu = gpu

        # self.ori_path = root_path
        self.ori_path = root_path

        self.save_ori_path = save_path / Path("ori")
        self.save_pred_path = save_path / Path("pred")

        self.save_ori_path.mkdir(parents=True, exist_ok=True)
        self.save_pred_path.mkdir(parents=True, exist_ok=True)

        self.norm_value = norm_value

    def pred(self, ori):
        img = (ori.astype(np.float32) / self.norm_value).reshape(
            (1, ori.shape[0], ori.shape[1])
        )
        with torch.no_grad():
            img = torch.from_numpy(img).unsqueeze(0)
            if self.gpu:
                img = img.cuda()
            mask_pred = self.net(img)
        pre_img = mask_pred.detach().cpu().numpy()[0, 0]
        return (pre_img * 255).astype(np.uint8)

    def main(self):
        self.net.eval()
        # path def
        paths = sorted(self.ori_path.glob("*.tif"))
        """Evaluation without the densecrf with the dice coefficient"""
        for i, path in enumerate(paths):
            ori = np.array(Image.open(path))
            pre_img = self.pred(ori)
            cv2.imwrite(str(self.save_pred_path / Path("%05d.tif" % i)), pre_img)
            cv2.imwrite(str(self.save_ori_path / Path("%05d.tif" % i)), ori)


class PredictFmeasure(Predict):
    def __init__(
        self,
        net,
        gpu,
        root_path,
        save_path,
        plot_size,
        peak_thresh=100,
        dist_peak=10,
        dist_threshold=20,
        norm_value=255,
    ):
        super().__init__(net, gpu, root_path, save_path, norm_value=255)
        # self.ori_path = root_path
        self.ori_path = root_path / Path("ori")
        self.gt_path = root_path / Path("{}".format(plot_size))

        self.save_gt_path = save_path / Path("gt")
        self.save_error_path = save_path / Path("error")
        self.save_txt_path = save_path / Path("f-measure.txt")

        self.save_gt_path.mkdir(parents=True, exist_ok=True)
        self.save_error_path.mkdir(parents=True, exist_ok=True)

        self.peak_thresh = peak_thresh
        self.dist_peak = dist_peak
        self.dist_threshold = dist_threshold

        self.tps = 0
        self.fps = 0
        self.fns = 0

    def cal_tp_fp_fn(self, ori, gt_img, pre_img, i):
        gt = target_peaks_gen((gt_img).astype(np.uint8))
        res = local_maxima(pre_img, self.peak_thresh, self.dist_peak)
        associate_id = optimum(gt, res, self.dist_threshold)

        gt_final, no_detected_id = remove_outside_plot(
            gt, associate_id, 0, pre_img.shape
        )
        res_final, overdetection_id = remove_outside_plot(
            res, associate_id, 1, pre_img.shape
        )

        show_res(
            ori,
            gt,
            res,
            no_detected_id,
            overdetection_id,
            path=str(self.save_error_path / Path("%05d.tif" % i)),
        )
        cv2.imwrite(str(self.save_pred_path / Path("%05d.tif" % i)), pre_img)
        cv2.imwrite(str(self.save_ori_path / Path("%05d.tif" % i)), ori)
        cv2.imwrite(str(self.save_gt_path / Path("%05d.tif" % i)), gt_img)

        tp = associate_id.shape[0]
        fn = gt_final.shape[0] - associate_id.shape[0]
        fp = res_final.shape[0] - associate_id.shape[0]
        self.tps += tp
        self.fns += fn
        self.fps += fp

    def main(self):
        self.net.eval()
        # path def
        path_x = sorted(self.ori_path.glob("*.tif"))
        path_y = sorted(self.gt_path.glob("*.tif"))

        z = zip(path_x, path_y)
        """Evaluation without the densecrf with the dice coefficient"""

        for i, b in enumerate(z):
            ori = np.array(Image.open(b[0]))
            gt_img = np.array(Image.open(b[1]))

            pre_img = self.pred(ori)

            self.cal_tp_fp_fn(ori, gt_img, pre_img, i)
        if self.tps == 0:
            f_measure = 0
        else:
            recall = self.tps / (self.tps + self.fns)
            precision = self.tps / (self.tps + self.fps)
            f_measure = (2 * recall * precision) / (recall + precision)

        print(precision, recall, f_measure)
        with self.save_txt_path.open(mode="w") as f:
            f.write("%f,%f,%f" % (precision, recall, f_measure))


if __name__ == "__main__":
    from unet import *

    date = datetime.now().date()
    gpu = True
    plot_size = 6
    key = 1
    models = {1: UNet, 2: UNetCascade, 3: UNetInternalCascade, 4: UnetMultiFixedWeight}

    weight_path = f"../weights/MSELoss/best_{plot_size}.pth"
    root_path = Path("../images/sequ_cut/sequ18")
    save_path = Path("./output/{}/test2/{}".format(date, plot_size))

    net = models[key](n_channels=1, n_classes=1)
    net.cuda()
    net.load_state_dict(torch.load(weight_path, map_location={"cuda:2": "cuda:1"}))

    pred = PredictFmeasure(
        net=net,
        gpu=gpu,
        root_path=root_path,
        save_path=save_path,
        plot_size=plot_size,
        peak_thresh=125,
        dist_peak=2,
        dist_threshold=20,
        norm_value=4096,
    )

    pred.main()
