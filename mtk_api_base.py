#!/usr/bin/env python3
# MTK Flash Client (c) B.Kerler 2018-2025.
# Licensed under GPLv3 License
#
# Shared API functions used by mtk_api.py and mtk_iot_api.py
import logging
import os

from mtkclient.Library.DA.mtk_da_handler import DaHandler
from mtkclient.Library.mtk_class import Mtk
from mtkclient.config.mtk_config import MtkConfig


def init(preloader, loader, serialport=None):
    loglevel = logging.INFO
    config = MtkConfig(loglevel=loglevel, gui=None, guiprogress=None)
    config.loader = loader
    if preloader is not None:
        if os.path.exists(preloader):
            config.preloader_filename = preloader
            with open(config.preloader_filename, "rb") as f:
                config.preloader = f.read()
    mtk = Mtk(config=config, loglevel=loglevel, serialportname=serialport)
    return mtk


def connect(mtk, directory=".", loglevel=logging.INFO):
    da_handler = DaHandler(mtk, loglevel)
    mtk = da_handler.connect(mtk, directory)
    if mtk is None:
        return None, None
    mtk = da_handler.configure_da(mtk)
    return mtk, da_handler
