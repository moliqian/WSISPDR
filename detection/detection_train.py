from tqdm import tqdm
from torch import optim
from .detection_eval import *
from utils import get_imgs_and_masks, get_imgs_and_masks2, batch
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np


class _TrainBase:
    def __init__(
        self,
        net,
        epochs,
        batch_size,
        lr,
        gpu,
        plot_size,
        train_path,
        weight_path,
        save_path=None,
        val_path=None,
    ):
        if isinstance(train_path, list):
            self.ori_path = []
            self.mask_path = []
            for path in train_path:
                self.ori_path.append(path.joinpath("ori"))
                self.mask_path.append(path.joinpath("{}".format(plot_size)))
        else:
            self.ori_path = train_path / Path("ori")
            self.mask_path = train_path / Path("{}".format(plot_size))
        if val_path is not None:
            self.val_path = val_path / Path("ori")
            self.val_mask_path = val_path / Path("{}".format(plot_size))
        else:
            self.val_path = None
            self.val_mask_path = None
        self.save_weight_path = weight_path
        self.save_weight_path.parent.mkdir(parents=True, exist_ok=True)
        self.save_weight_path.parent.joinpath("epoch_weight").mkdir(
            parents=True, exist_ok=True
        )
        if save_path is not None:
            self.save_path = save_path
            self.save_path.mkdir(parents=True, exist_ok=True)
        print(
            "Starting training:\nEpochs: {}\nBatch size: {} \nLearning rate: {}\ngpu:{}\n"
            "plot_size:{}\n".format(epochs, batch_size, lr, gpu, plot_size)
        )

        self.net = net

        self.train = None
        self.val = None

        self.N_train = None
        self.optimizer = optim.Adam(net.parameters(), lr=lr)
        self.epochs = epochs
        self.batch_size = batch_size
        self.gpu = gpu
        self.plot_size = plot_size
        self.criterion = nn.MSELoss()
        self.losses = []
        self.val_losses = []
        self.evals = []
        self.epoch_loss = 0
        self.bad = 0

    def show_graph(self):
        print("f-measure={}".format(max(self.evals)))
        x = list(range(len(self.losses)))
        plt.plot(x, self.losses)
        plt.plot(x, self.val_losses)
        plt.show()
        plt.plot(x, self.evals)
        plt.show()

    def validation(self, number_of_train_data, epoch):
        loss = self.epoch_loss / (number_of_train_data + 1)
        print("Epoch finished ! Loss: {}".format(loss))

        self.losses.append(loss)
        if epoch % 10 == 0:
            torch.save(
                self.net.state_dict(),
                str(
                    self.save_weight_path.parent.joinpath(
                        "epoch_weight/{:05d}.pth".format(epoch)
                    )
                ),
            )

        if loss < 0.01:
            fmeasure, val_loss = eval_net(self.net, self.val, gpu=self.gpu)
            print("f-measure: {}".format(fmeasure))
            print("val_loss: {}".format(val_loss))
            try:
                update_or_not = max(self.evals) < fmeasure
                if update_or_not:
                    print("update best")
                    print("{}".format(update_or_not))
                    torch.save(self.net.state_dict(), str(self.save_weight_path))
                    self.bad = 0
                elif min(self.val_losses) > val_loss:
                    print("stay")
                    pass
                else:
                    self.bad += 1
                    print("bad ++")
            except ValueError:
                torch.save(self.net.state_dict(), str(self.save_weight_path))
            self.evals.append(fmeasure)
            self.val_losses.append(val_loss)
        else:
            print("loss is too large. Continue train")
            val_loss = eval_net(self.net, self.val, gpu=self.gpu, only_loss=True)
            self.evals.append(0)
            self.val_losses.append(val_loss)
        print("bad = {}".format(self.bad))
        self.epoch_loss = 0


class TrainNet(_TrainBase):
    def load(self):
        self.net.train()
        # reset the generators
        if isinstance(self.ori_path, list):
            ori_paths = []
            mask_paths = []
            for paths in zip(self.ori_path, self.mask_path):
                ori_paths.extend(sorted(list(paths[0].glob("*.tif"))))
                mask_paths.extend(sorted(list(paths[1].glob("*.tif"))))
            assert len(ori_paths) == len(mask_paths), "path のデータ数が正しくない"
            ori_paths = np.array(ori_paths)
            mask_paths = np.array(mask_paths)
            self.N_train = len(ori_paths)
            self.train = get_imgs_and_masks2(ori_paths, mask_paths)
        else:
            self.train = get_imgs_and_masks(
                self.ori_path, self.mask_path
            )
            self.N_train = len(list(self.ori_path.glob("*.tif")))
        if self.val_path is not None:
            self.val = get_imgs_and_masks(
                self.val_path, self.val_mask_path
            )

    def loss_calculate(self, masks_probs_flat, true_masks_flat):
        return self.criterion(masks_probs_flat, true_masks_flat)

    def main(self):
        for epoch in range(self.epochs):
            print("Starting epoch {}/{}.".format(epoch + 1, self.epochs))
            self.load()

            pbar = tqdm(total=self.N_train)
            for i, b in enumerate(batch(self.train, self.batch_size)):
                imgs = np.array([i[0] for i in b])
                true_masks = np.array([i[1] for i in b])

                imgs = torch.from_numpy(imgs)
                true_masks = torch.from_numpy(true_masks)

                if self.gpu:
                    imgs = imgs.cuda()
                    true_masks = true_masks.cuda()

                masks_pred = self.net(imgs)

                masks_probs_flat = masks_pred.view(-1)
                true_masks_flat = true_masks.view(-1)

                loss = self.loss_calculate(masks_probs_flat, true_masks_flat)
                self.epoch_loss += loss.item()

                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()

                pbar.update(self.batch_size)
            pbar.close()
            if self.val_path is not None:
                self.validation(i, epoch)
            else:
                torch.save(
                    self.net.state_dict(),
                    str(
                        self.save_weight_path.parent.joinpath(
                            "epoch_weight/{:05d}.pth".format(epoch)
                        )
                    ),
                )

            if self.bad >= 50:
                print("stop running")
                break
        self.show_graph()
