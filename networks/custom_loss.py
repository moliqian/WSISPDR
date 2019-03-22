import torch.nn as nn
import torch
import torch.nn.functional as F


class BoundaryEnhancedCrossEntropyLoss(nn.Module):
    def __init__(self, weight=1.3, alf = 0.5, beta = 0.8):
        super().__init__()
        self.weight = weight
        self.alf= alf
        self.beta = beta
        self.sigma = 0.0001

    def forward(self, inputs, boundaries, targets):
        boundary_enhance = self.alf * torch.clamp(self.beta - boundaries, max=0)
        loss = (1 + boundary_enhance) * targets * torch.log(inputs + self.sigma) + self.weight * (
            1 - targets
        ) * torch.log(1 - inputs + self.sigma)
        return -torch.mean(loss)


class CrossEntropy(nn.Module):
    def forward(self, inputs, targets):
        loss = targets * torch.log(inputs) + (1 - targets) * torch.log(1 - inputs)
        return -torch.mean(loss)


class SignMseLoss(nn.Module):
    def __init__(self, plus_weight=1.3, minus_weight=0.7):
        super(SignMseLoss, self).__init__()
        self.plus = plus_weight
        self.minus = -minus_weight

    def forward(self, input, target):
        loss_plus = self.plus * (torch.sign(input - target) + 1) * ((input - target) ** 2)
        loss_minus = self.minus * (torch.sign(input - target) - 1) * ((input - target) ** 2)
        loss_plus = loss_plus.sum() / input.data.nelement()
        loss_minus = loss_minus.sum() / input.data.nelement()
        loss = loss_plus + loss_minus
        return loss


class MseLoss(nn.Module):
    def __init__(self, plus_weight=0.7, minus_weight=0.3):
        super(MseLoss, self).__init__()
        self.plus = plus_weight
        self.minus = -minus_weight

    def forward(self, input, target):
        return ((input - target) ** 2).sum() / input.data.nelement()


if __name__ == "__main__":
    a = torch.zeros(3, dtype=torch.float32)
    a[1] = 1
    b = torch.zeros(3, dtype=torch.float32)
    b[0] = 0.228
    b[1] = 0.619
    b[2] = 0.153
    b = torch.zeros(3, dtype=torch.float32)
    b[0] = 0.228
    b[1] = 0.619
    b[2] = 0.153
    criterion = BoundaryEnhancedCrossEntropyLoss()
    loss = criterion(b,b, a)
    print(loss)
    # criterion = nn.CrossEntropyLoss()
    # loss = criterion(a, b)
    criterion = nn.BCELoss()
    loss = criterion(b, a)
    print(loss)
    F.binary_cross_entropy(b, a)
