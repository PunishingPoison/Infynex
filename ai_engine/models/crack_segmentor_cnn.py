"""
INFYNEX PyTorch Deep Learning Damage Detection Model
Deep Convolutional Neural Network for structural defect detection (cracks & spalling).
Implements multi-scale convolutional feature extraction, batch normalization,
and dual classification & bounding-box regression heads.
"""

import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import List, Dict, Any, Tuple


class ConvBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2, stride=2)
        )

    def forward(self, x):
        return self.conv(x)


class StructuralDamageCNN(nn.Module):
    """
    Convolutional Neural Network for detecting structural concrete defects.
    Outputs:
    - class_logits: 4 classes [Background, Vertical Crack, Spalling, Diagonal Shear]
    - bbox_reg: [dx, dy, dw, dh] bounding box regression offsets
    """
    def __init__(self, num_classes: int = 4):
        super().__init__()
        self.num_classes = num_classes

        # Feature Extractor Backbone
        self.layer1 = ConvBlock(3, 32)    # -> 360 x 640
        self.layer2 = ConvBlock(32, 64)   # -> 180 x 320
        self.layer3 = ConvBlock(64, 128)  # -> 90 x 160
        self.layer4 = ConvBlock(128, 256) # -> 45 x 80

        # Global Feature Pooling
        self.adaptive_pool = nn.AdaptiveAvgPool2d((4, 4))
        
        # Classification Head
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(256 * 4 * 4, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(256, num_classes)
        )

        # Bounding Box Regression Head
        self.bbox_head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(256 * 4 * 4, 128),
            nn.ReLU(inplace=True),
            nn.Linear(128, 4),
            nn.Sigmoid() # Normalized [xmin, ymin, xmax, ymax]
        )

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        f1 = self.layer1(x)
        f2 = self.layer2(f1)
        f3 = self.layer3(f2)
        f4 = self.layer4(f3)

        pooled = self.adaptive_pool(f4)
        logits = self.classifier(pooled)
        bboxes = self.bbox_head(pooled)
        return logits, bboxes
