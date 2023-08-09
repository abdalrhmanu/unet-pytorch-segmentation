import os
import time
from glob import glob 

import torch
from torch.utils.data import DataLoader
import torch.nn as nn

from model.unet import UNet
from model.hyperparameters import get_hparams
from dataset import DriveDataset

from loss import DiceLoss, DiceBCELoss
from utils import seeding, create_dir, epoch_time

from loguru import logger
from tqdm import tqdm


def train(model, train_loader, optimizer, loss_fn, device):
    epoch_loss = 0.0

    model.train()

    for x, y in train_loader:
        x = x.to(device, dtype=torch.float32)  # Move to device
        y = y.to(device, dtype=torch.float32)  # Move to device

        optimizer.zero_grad()

        y_pred = model(x)
        loss = loss_fn(y_pred, y)

        loss.backward()
        optimizer.step()

        epoch_loss += loss.item()
    
    epoch_loss = epoch_loss / len(train_loader)

    return epoch_loss



if __name__ == "__main__":
    seeding(42)

    create_dir("checkpoints")

    # load the dataset
    train_x = sorted(glob(os.path.join(os.getcwd(), 'data/augmented/train/image/*')))[:20]
    train_y = sorted(glob(os.path.join(os.getcwd(), 'data/augmented/train/mask/*')))[:20]
    valid_x = sorted(glob(os.path.join(os.getcwd(), 'data/augmented/test/image/*')))
    valid_y = sorted(glob(os.path.join(os.getcwd(), 'data/augmented/test/mask/*')))
    logger.info(f"train size: {len(train_x)}, valid size: {len(valid_x)}")

    # get model hyperparameters
    hyperparameters = get_hparams()

    # dataset and loader
    train_dataset = DriveDataset(train_x, train_y)
    valid_dataset = DriveDataset(valid_x, valid_y)

    train_loader = DataLoader(
        dataset=train_dataset,
        batch_size=hyperparameters['batch_size'],
        shuffle=True,
        num_workers=2
    )

    valid_loader = DataLoader(
        dataset=valid_dataset,
        batch_size=hyperparameters['batch_size'],
        shuffle=False,
        num_workers=2
    )

    # checking gpu availability and setting up the model
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    if device.type == 'cuda':
        print(torch.cuda.get_device_name(0))
        print('Memory Usage:')
        print('Allocated:', round(torch.cuda.memory_allocated(0)/1024**3,1), 'GB')
        print('Cached:   ', round(torch.cuda.memory_reserved(0)/1024**3,1), 'GB')

        device = torch.device('cuda')

    else:
        device = torch.device('cpu')

    model = UNet()
    model = model.to(device)

    # setting up the optimizer and the lr scheduler
    optimizer = torch.optim.Adam(model.parameters(), lr=hyperparameters['learning_rate'])
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'min', patience=5, verbose=True)

    # setting up the loss function
    loss_fn = DiceBCELoss()

    # training the model
    for epoch in tqdm(range(hyperparameters['n_epochs'])):
        start_time = time.time()

        train_loss = train(model, train_loader, optimizer, loss_fn, device)