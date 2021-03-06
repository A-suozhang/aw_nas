# -*- coding: utf-8 -*-

import torch
from torch import nn

from aw_nas.utils.torch_utils import accuracy
from aw_nas.objective.base import BaseObjective

class ClassificationObjective(BaseObjective):
    NAME = "classification"

    def __init__(self, search_space, label_smooth=None):
        super(ClassificationObjective, self).__init__(search_space)
        self.label_smooth = label_smooth
        self._criterion = nn.CrossEntropyLoss() if not self.label_smooth \
                          else CrossEntropyLabelSmooth(self.label_smooth)

    @classmethod
    def supported_data_types(cls):
        return ["image"]

    def perf_names(self):
        return ["acc"]

    def get_perfs(self, inputs, outputs, targets, cand_net):
        """
        Get top-1 acc.
        """
        return [float(accuracy(outputs, targets)[0]) / 100]

    def get_reward(self, inputs, outputs, targets, cand_net):
        return self.get_perfs(inputs, outputs, targets, cand_net)[0]

    def get_loss(self, inputs, outputs, targets, cand_net,
                 add_controller_regularization=True, add_evaluator_regularization=True):
        """
        Get the cross entropy loss *tensor*, optionally add regluarization loss.

        Args:
            outputs: logits
            targets: labels
        """
        return self._criterion(outputs, targets)

class CrossEntropyLabelSmooth(nn.Module):
    def __init__(self, epsilon):
        super(CrossEntropyLabelSmooth, self).__init__()
        self.epsilon = epsilon
        self.logsoftmax = nn.LogSoftmax(dim=1)

    def forward(self, inputs, targets):
        num_classes = int(inputs.shape[-1])
        log_probs = self.logsoftmax(inputs)
        targets = torch.zeros_like(log_probs).scatter_(1, targets.unsqueeze(1), 1)
        targets = (1 - self.epsilon) * targets + self.epsilon / num_classes
        loss = (-targets * log_probs).mean(0).sum()
        return loss
