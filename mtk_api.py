#!/usr/bin/env python3
from mtk_api_base import init, connect


def main():
    mtk=init(preloader=None, loader=None)
    mtk, da_handler = connect(mtk=mtk, directory=".")
    data=da_handler.da_rs(start=0,sectors=0x4000,filename="",parttype="user",display=False)
    print(data.hex())


if __name__ == '__main__':
    main()
