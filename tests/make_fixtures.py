# -*- coding: utf-8 -*-
"""Test dosyalarını (fixtures/) üretir. Sadece geliştirici içindir: Pillow, ffmpeg ve exiftool gerekir.
Üretilen küçük dosyalar pakete dahildir; testleri çalıştırmak için bu betik gerekmez."""
import os, shutil, subprocess, sys
from pathlib import Path
from PIL import Image

F = Path(__file__).parent / "fixtures"
if F.exists():
    shutil.rmtree(F)


def photo(rel, make=None, model=None, dt=None, serial=None, comment=None, color=(0, 0, 0), fmt=None):
    p = F / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", (8, 8), color)
    ex = Image.Exif()
    if make: ex[0x010f] = make
    if model: ex[0x0110] = model
    if dt:
        ex[0x0132] = dt
        ex.get_ifd(0x8769)[0x9003] = dt
    if serial: ex.get_ifd(0x8769)[0xA431] = serial          # BodySerialNumber
    if comment: ex.get_ifd(0x8769)[0x9286] = b"ASCII\0\0\0" + comment.encode()
    im.save(p, format=fmt, exif=ex) if (make or model or dt or serial or comment) else im.save(p, format=fmt)
    return p


def video(rel, args):
    p = F / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=16x16:d=0.2", str(p)], check=True)
    if args:
        subprocess.run(["exiftool", "-q", "-overwrite_original", *args, str(p)], check=True)


# 1) temel adlandırma + aynı saniye (kaynak sırası: IMG_2 < IMG_3 < IMG_10)
photo("temel/kart/IMG_2.jpg", "Canon", "Canon EOS R6", "2026:11:20 10:00:00", color=(1, 0, 0))
photo("temel/kart/IMG_3.jpg", "Canon", "Canon EOS R6", "2026:11:20 10:00:00", color=(2, 0, 0))
photo("temel/kart/IMG_10.jpg", "Canon", "Canon EOS R6", "2026:11:20 10:00:00", color=(3, 0, 0))
photo("temel/kart/IMG_11.jpg", "Canon", "Canon EOS R6", "2026:11:20 10:05:00", color=(4, 0, 0))
photo("temel/kart/IMG_11.tif", "Canon", "Canon EOS R6", "2026:11:20 10:05:00", color=(4, 0, 0))  # JPG+RAW çifti yerine
photo("temel/nikon/DSC_1.jpg", "NIKON CORPORATION", "NIKON Z 6", "2026:11:20 09:59:00")
photo("temel/eksik/tarihsiz.jpg", "SONY", "ILCE-7M3")
photo("temel/eksik/cihazsiz.jpg", dt="2026:11:21 08:00:00")
photo("temel/eksik/WhatsApp.jpg")
(F / "temel/notlar.txt").write_text("fotoğraf değil")

# 2) aynı model iki gövde (seri no)
photo("govde/a.jpg", "Canon", "Canon EOS R6", "2026:11:22 10:00:00", serial="11111234")
photo("govde/b.jpg", "Canon", "Canon EOS R6", "2026:11:22 10:01:00", serial="22225678")

# 3) cihaz adı eşleştirme
photo("esleme/a.jpg", "realme", "realme 5i", "2021:01:01 10:00:00")
photo("esleme/b.jpg", "realme", "RMX2030", "2021:01:01 10:00:05")
photo("esleme/c.jpg", "samsung", "SM-A515F", "2022:01:01 10:00:00")
photo("esleme/d.jpg", "samsung", "Galaxy A51", "2022:01:01 11:00:00")

# 4) ekran görüntüleri
photo("ekran/IMG_1142.PNG", dt="2024:06:18 15:18:58", comment="Screenshot", fmt="PNG")
photo("ekran/Ekran görüntüsü 2025-05-25 005223.png", fmt="PNG")
photo("ekran/RobloxScreenShot20250525_005219337.png", fmt="PNG")
photo("ekran/Screenshot_20210102-181538.jpg")
photo("ekran/cv.png", fmt="PNG")
photo("ekran/iphone_foto.jpg", "Apple", "iPhone 14", "2024:06:18 15:00:00")

# 5) videolar (exiftool gerekir)
video("video/iphone.mov", ["-Keys:Make=Apple", "-Keys:Model=iPhone 14", "-Keys:CreationDate=2026:11:20 18:30:00+03:00",
                           "-QuickTime:CreateDate=2026:11:20 15:30:00"])
video("video/tokyo.mov", ["-Keys:Make=Apple", "-Keys:Model=iPhone 14", "-QuickTime:CreateDate=2026:11:20 01:00:00",
                          "-Keys:GPSCoordinates#=35.68 139.69 0"])
video("video/utc_gpssiz.mov", ["-Keys:Make=Apple", "-Keys:Model=iPhone 14", "-QuickTime:CreateDate=2026:11:20 07:00:00"])
photo("video/sony/DSC0.jpg", "SONY", "ILCE-7M3", "2026:11:20 13:00:00")
photo("video/sony/DSC1.jpg", "SONY", "ILCE-7M3", "2026:11:20 13:02:00")
video("video/sony/C0001.mp4", ["-Make=Sony", "-Model=ILCE-7M3", "-QuickTime:CreateDate=2026:11:20 10:01:00"])
video("video/bilgisiz.mp4", [])
print("ok", sum(1 for _ in F.rglob("*") if _.is_file()), "dosya")
