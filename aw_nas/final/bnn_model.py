# from __future__ import print_function
# import six
# import numpy as np
# import torch
from torch import nn
# 
from aw_nas import ops, utils
from aw_nas.final.cnn_model import CNNGenotypeModel

class BNNGenotypeModel(CNNGenotypeModel):
    NAME="bnn_final_model"
    def __init__(self, *args, **kwargs):
        super(BNNGenotypeModel, self).__init__(*args, **kwargs)
        self.bi_flops = 0

    def _hook_intermediate_feature(self, module, inputs, outputs):
        if not self._flops_calculated:
            if isinstance(module, nn.Conv2d):
                self.total_flops += 2* inputs[0].size(1) * outputs.size(1) * \
                                    module.kernel_size[0] * module.kernel_size[1] * \
                                    outputs.size(2) * outputs.size(3) / module.groups
            elif isinstance(module, ops.XNORConv2d):
                self.bi_flops += 2* inputs[0].size(1) * outputs.size(1) * \
                                    module.kernel_size * module.kernel_size * \
                                    outputs.size(2) * outputs.size(3) / (module.groups)  # the 1-bit conv
            elif isinstance(module, nn.Linear):
                self.total_flops += 2 * inputs[0].size(1) * outputs.size(1)
        else:
            pass

