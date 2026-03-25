#!/usr/bin/env python3
import sys

from mtk_api_base import init, connect

__all__ = ['init', 'connect']


def main():
    if len(sys.argv)<2:
        print("Usage: python mtk_iot_api.py /dev/ttyUSB0")
        sys.exit(1)
    port = sys.argv[1]
    bytestoread=0x400000
    pos=0
    mtk = init(preloader=None, loader=None,serialport=port)
    mtk.config.iot = True
    offs={}
    with open("dump.bin","wb") as wf:
        while bytestoread>0:
            inited = mtk.preloader.init(directory="")
            if inited:
                data=mtk.preloader.dump_internal_flash(offset=pos,length=bytestoread,step=0x1000,filename="")
                if len(data)==0:
                    if not pos in offs:
                        offs[pos]=0
                    offs[pos]+=1
                    if offs[pos]==2:
                        print(f"Error reading at offset {hex(pos)} ... skipping")
                        wf.write(b"\xFF"*0x1000)
                        bytestoread-=0x1000
                        pos+=0x1000
                if len(data)>0:
                    pos+=len(data)
                    bytestoread-=len(data)
                    wf.write(data)

if __name__ == '__main__':
    main()