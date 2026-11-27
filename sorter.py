# -*- coding: utf-8 -*-
"""Fotoğraf ve videoları cihaza, türe ve çekim zamanına göre düzenleyen çekirdek mantık.

İki aşamalı çalışır:
  1) scan()     : dosyaları okur (yavaş kısım)
  2) finalize() : kullanıcının seçimlerine göre (saat dilimi, aynı model ayırma) yeni adları belirler
Komut satırından deneme:  python sorter.py KAYNAK HEDEF [--move] [--run] [--no-exiftool]
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Callable, Optional

import logging

import exifread

logging.getLogger("exifread").setLevel(logging.CRITICAL)  # 'PNG file does not have exif data' gibi uyarıları gizle

try:
    from hachoir.core import config as _hachoir_config
    from hachoir.metadata import extractMetadata
    from hachoir.parser import createParser
    _hachoir_config.quiet = True
    HAS_HACHOIR = True
except Exception:  # pragma: no cover
    HAS_HACHOIR = False

try:
    from zoneinfo import ZoneInfo, available_timezones
    available_timezones()  # Windows'ta tzdata paketi gerekir
    HAS_ZONEINFO = True
except Exception:  # pragma: no cover
    HAS_ZONEINFO = False

try:
    from timezonefinder import TimezoneFinder
    _TF = TimezoneFinder()
except Exception:  # pragma: no cover
    _TF = None

# ----------------------------------------------------------------- ayarlar
PHOTO_EXT = {
    ".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp",
    ".cr2", ".cr3", ".nef", ".nrw", ".arw", ".srf", ".sr2", ".dng", ".orf",
    ".rw2", ".raf", ".pef", ".srw", ".3fr", ".gif", ".bmp",
}
VIDEO_EXT = {
    ".mp4", ".mov", ".m4v", ".avi", ".mts", ".m2ts", ".3gp", ".mkv", ".wmv",
    ".mpg", ".mpeg", ".insv", ".lrv",
}

# Klasör adları dile göre. Hedefte daha önce hangi dil kullanıldıysa o dil korunur (detect_folder_lang).
FOLDERS = {
    "tr": {"photo": "Fotoğraflar", "video": "Videolar", "missing": "_Eksik Bilgi", "no_date": "Tarih Yok",
           "no_device": "Cihaz Yok", "no_both": "Tarih ve Cihaz Yok", "screenshots": "Ekran Görüntüleri",
           "duplicates": "_Kopyalar"},
    "en": {"photo": "Photos", "video": "Videos", "missing": "_Missing Info", "no_date": "No Date",
           "no_device": "No Device", "no_both": "No Date or Device", "screenshots": "Screenshots",
           "duplicates": "_Duplicates"},
}
# Rapor ve notlar
TEXT = {
    "tr": {"utc": "UTC → {tz}", "shift": "saat {v}", "dup": "kopya: {name}", "exists": "hedefte aynı içerik zaten var",
           "photo": "Fotoğraf", "video": "Video", "unsupported": "desteklenmeyen dosya, dokunulmadı",
           "cols": ["Kaynak", "Yeni konum", "Tür", "Çekim zamanı", "Cihaz", "Dosyada yazan cihaz", "Seri no",
                    "Kopyası olduğu dosya", "Not", "Durum"],
           "status": {}},
    "en": {"utc": "UTC → {tz}", "shift": "clock {v}", "dup": "duplicate of: {name}", "exists": "same content already in target",
           "photo": "Photo", "video": "Video", "unsupported": "unsupported file, left untouched",
           "cols": ["Source", "New location", "Type", "Taken at", "Device", "Device as written in file", "Serial no",
                    "Duplicate of", "Note", "Status"],
           "status": {"bekliyor": "pending", "zaten var": "already there", "kopyalandı": "copied",
                      "taşındı": "moved", "hata": "error"}},
}


def status_text(status: str, lang: str) -> str:
    m = TEXT.get(lang, TEXT["tr"])["status"]
    if status.startswith("hata") and "hata" in m:
        return m["hata"] + status[4:]
    return m.get(status, status)


def detect_folder_lang(target) -> Optional[str]:
    """Hedefte önceki bir çalıştırmadan kalan klasörlerin dili (yoksa None)."""
    target = Path(target)
    if not target.is_dir():
        return None
    names = set()
    try:
        for d in target.iterdir():
            if d.is_dir():
                names.add(d.name)
                try:
                    names.update(x.name for x in d.iterdir() if x.is_dir())
                except OSError:
                    pass
    except OSError:
        return None
    for lang, f in FOLDERS.items():
        if names & set(f.values()):
            return lang
    return None


JOURNAL_DIR = "_islem_gecmisi"           # geri alma için yapılan işlemlerin kaydı
DATE_FMT = "%Y-%m-%d_%H-%M-%S"
DEFAULT_TZ = "Europe/Istanbul"
UNKNOWN_DEVICE = "(cihaz bilinmiyor)"

MAKE_ALIASES = {
    "nikon corporation": "Nikon", "nikon": "Nikon", "canon": "Canon", "sony": "Sony",
    "fujifilm": "Fujifilm", "olympus imaging corp.": "Olympus", "olympus corporation": "Olympus",
    "om digital solutions": "OM System", "panasonic": "Panasonic", "pentax corporation": "Pentax",
    "ricoh imaging company, ltd.": "Ricoh", "samsung": "Samsung", "apple": "Apple",
    "google": "Google", "xiaomi": "Xiaomi", "huawei": "Huawei", "gopro": "GoPro", "dji": "DJI",
    "leica camera ag": "Leica",
}
# Videoda saati genelde UTC yazan markalar (telefonlar, aksiyon kameraları). Diğerleri çoğunlukla yerel yazar.
UTC_BRANDS = ("apple", "samsung", "google", "xiaomi", "huawei", "oneplus", "oppo", "vivo",
              "realme", "motorola", "gopro", "dji", "insta360")

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


# ----------------------------------------------------------------- veri
@dataclass
class MediaInfo:
    date: Optional[datetime] = None   # saat dilimsiz "duvar saati"
    date_kind: str = "local"          # local: zaten yerel | utc: UTC olabilir, çevrilmesi gerekebilir
    device: Optional[str] = None
    serial: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    raw_device: Optional[str] = None  # dosyada yazan ad (eşleştirmeden önce)
    comment: str = ""                 # EXIF UserComment (iPhone ekran görüntülerinde "Screenshot")
    screenshot: bool = False


@dataclass
class Action:
    src: Path
    kind: str                     # "photo" | "video"
    info: MediaInfo
    date: Optional[datetime] = None      # son hali (çevrilmiş)
    device: Optional[str] = None         # son hali (gerekirse seri no ile)
    dest: Optional[Path] = None
    status: str = "bekliyor"
    note: str = ""
    dup_of: Optional["Action"] = None    # içerik olarak aynısı kaynakta daha önce geçiyorsa


@dataclass
class Options:
    tz_name: str = DEFAULT_TZ                         # GPS yoksa kullanılacak konum
    video_utc: dict = field(default_factory=dict)     # cihaz -> True (UTC, çevir) / False (yerel)
    split_models: set = field(default_factory=set)    # seri numarasına göre ayrılacak cihazlar
    clock_offsets: dict = field(default_factory=dict)  # cihaz -> dakika (makinenin saati yanlışsa, ör. +120)
    lang: str = "tr"                                   # rapor/not dili ve yeni klasör adlarının dili


@dataclass
class Plan:
    source: Path
    target: Path
    actions: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    scan_seconds: float = 0.0
    used_exiftool: bool = False
    folder_lang: str = "tr"
    lang: str = "tr"

    def counts(self) -> dict:
        c = {"toplam": len(self.actions), "tam": 0, "tarih_yok": 0, "cihaz_yok": 0,
             "ikisi_yok": 0, "zaten_var": 0, "desteklenmeyen": len(self.skipped)}
        for a in self.actions:
            c["zaten_var"] += a.status == "zaten var"
            d, v = a.info.date, a.info.device
            c["tam" if d and v else "tarih_yok" if v else "cihaz_yok" if d else "ikisi_yok"] += 1
        c["ekran_goruntusu"] = sum(1 for a in self.actions if a.info.screenshot)
        c["kopya"] = sum(1 for a in self.actions if a.dup_of is not None and a.status == "bekliyor")
        c["yeni"] = sum(1 for a in self.actions if a.status == "bekliyor")
        return c


# ----------------------------------------------------------------- yardımcılar
def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def _file_order(name: str):
    """Klasör içi sıra: önce uzantısız ada göre doğal sıra. Böylece 'DSC_1.jpg', 'DSC_1 (1).jpg'den önce gelir
    (aynı içerikli dosyalarda asıl kabul edilen ilk dosyadır)."""
    stem, ext = os.path.splitext(name)
    return natural_key(stem), ext.lower()


def clean_name(s: str) -> str:
    s = _INVALID.sub("", s).strip().rstrip(".")
    return re.sub(r"\s+", " ", s)


def make_device(make, model) -> Optional[str]:
    make = str(make or "").strip().strip("\x00")
    model = str(model or "").strip().strip("\x00")
    if make:
        make = MAKE_ALIASES.get(make.lower(), make)
    if model and make:
        first = make.split()[0].lower()
        name = model if model.lower().startswith(first) else f"{make} {model}"
    else:
        name = model or make
    return clean_name(name) or None


_DATE_RE = re.compile(
    r"(\d{4})[:\-/](\d{2})[:\-/](\d{2})[ T](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?\s*(Z|[+\-]\d{2}:?\d{2})?")


def parse_date(value):
    """(tarih, saat_dilimi_var_mı) döner. Saat dilimi yazılıysa o andaki yerel saat alınır."""
    if value is None:
        return None, False
    if isinstance(value, datetime):
        dt, has_tz = value.replace(tzinfo=None), False
    else:
        m = _DATE_RE.search(str(value))
        if not m:
            return None, False
        try:
            dt = datetime(*map(int, m.groups()[:6]))
        except ValueError:
            return None, False
        has_tz = bool(m.group(7)) and m.group(7) != "Z"
    if dt.year < 1990 or dt.year > 2100:      # 0000:00:00, 1904 (boş MP4) vb.
        return None, False
    return dt.replace(microsecond=0), has_tz


def _ratio_to_float(tag) -> Optional[float]:
    try:
        d, m, s = [float(x.num) / float(x.den) if x.den else 0.0 for x in tag.values]
        return d + m / 60 + s / 3600
    except Exception:
        return None


def _find_exiftool() -> Optional[str]:
    bases = [getattr(sys, "_MEIPASS", None), Path(sys.executable).parent, Path(__file__).resolve().parent]
    for b in bases:
        if not b:
            continue
        for name in ("exiftool.exe", "exiftool(-k).exe"):
            p = Path(b) / name
            if p.exists():
                return str(p.resolve())    # göreli ad Popen'da başlatılamıyor
    return shutil.which("exiftool")


EXIFTOOL = _find_exiftool()


# ----------------------------------------------------------------- Python ile okuma
def _exif_segment_only(path: Path) -> Optional[bytes]:
    """JPEG içindeki EXIF (APP1) bölümünü tek başına küçük bir JPEG olarak döner.

    Bazı dosyalarda EXIF'ten önce başka bölümler (ör. C2PA/JUMBF "içerik kimlik bilgisi", APP11) bulunur
    ve exifread bunları geçemez. EXIF bölümünü ayırıp tekrar okumak bu durumu çözer."""
    try:
        with open(path, "rb") as f:
            head = f.read(1 << 20)
    except OSError:
        return None
    if not head.startswith(b"\xff\xd8"):
        return None
    i = 2
    while i + 4 <= len(head) and head[i] == 0xFF:
        marker, length = head[i + 1], int.from_bytes(head[i + 2:i + 4], "big")
        if marker == 0xDA:      # görüntü verisi başladı
            break
        if marker == 0xE1 and head[i + 4:i + 10] == b"Exif\x00\x00":
            return b"\xff\xd8" + head[i:i + 2 + length] + b"\xff\xd9"
        i += 2 + length
    return None


def read_photo_python(path: Path) -> MediaInfo:
    info = MediaInfo()
    # PNG'de UserComment ("Screenshot") ancak details=True ile okunuyor; PNG'ler küçük ve az olduğu için sorun değil.
    details = path.suffix.lower() == ".png"
    try:
        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=details)
        if not tags:
            seg = _exif_segment_only(path)
            if seg:
                import io
                tags = exifread.process_file(io.BytesIO(seg), details=details)
    except Exception:
        return info
    for key in ("EXIF DateTimeOriginal", "EXIF DateTimeDigitized", "Image DateTime"):
        if key in tags:
            info.date, _ = parse_date(tags[key])
            if info.date:
                break
    info.device = make_device(tags.get("Image Make"), tags.get("Image Model"))
    if "EXIF UserComment" in tags:
        try:
            info.comment = str(tags["EXIF UserComment"]).strip("\x00 ")
        except Exception:
            pass
    for key in ("EXIF BodySerialNumber", "MakerNote SerialNumber", "Image CameraSerialNumber"):
        if key in tags and str(tags[key]).strip("\x00 "):
            info.serial = str(tags[key]).strip("\x00 ")
            break
    lat, lon = _ratio_to_float(tags.get("GPS GPSLatitude")), _ratio_to_float(tags.get("GPS GPSLongitude"))
    if lat is not None and lon is not None and (lat or lon):
        if str(tags.get("GPS GPSLatitudeRef", "N")).startswith("S"):
            lat = -lat
        if str(tags.get("GPS GPSLongitudeRef", "E")).startswith("W"):
            lon = -lon
        info.lat, info.lon = lat, lon
    return info


def read_video_python(path: Path) -> MediaInfo:
    info = MediaInfo(date_kind="utc")
    if not HAS_HACHOIR:
        return info
    try:
        parser = createParser(str(path))
        if not parser:
            return info
        with parser:
            md = extractMetadata(parser)
        if md:
            for key in ("creation_date", "date_time_original"):
                if md.has(key):
                    info.date, _ = parse_date(md.get(key))
                    if info.date:
                        break
            info.device = make_device(md.get("camera_manufacturer", None) if md.has("camera_manufacturer") else None,
                                      md.get("camera_model", None) if md.has("camera_model") else None)
    except Exception:
        pass
    return info


# ----------------------------------------------------------------- exiftool ile okuma
ET_TAGS = ["-DateTimeOriginal", "-CreationDate", "-CreateDate", "-MediaCreateDate",
           "-Make", "-Model",
           "-SerialNumber", "-BodySerialNumber", "-GPSLatitude", "-GPSLongitude", "-UserComment",
           "-ModifyDate"]


class ExifTool:
    """exiftool'u bir kez başlatıp açık tutar (-stay_open). Her dosya için yeniden başlatmaktan çok hızlı."""

    def __init__(self, exe: str):
        flags = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW
        self.p = subprocess.Popen([exe, "-stay_open", "True", "-@", "-"], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=flags)

    def read(self, paths: list) -> dict:
        args = ["-j", "-n", "-fast", "-charset", "filename=utf8", *ET_TAGS, *map(str, paths), "-execute"]
        self.p.stdin.write(("\n".join(args) + "\n").encode("utf-8"))
        self.p.stdin.flush()
        buf = b""
        while not buf.rstrip().endswith(b"{ready}"):
            chunk = self.p.stdout.read1(1 << 16)
            if not chunk:
                raise RuntimeError("exiftool beklenmedik şekilde kapandı")
            buf += chunk
        text = buf.rstrip()[:-len(b"{ready}")].decode("utf-8", "replace").strip()
        out = {}
        for item in (json.loads(text) if text else []):
            out[os.path.normcase(os.path.normpath(item.get("SourceFile", "")))] = item
        return out

    def close(self):
        try:
            self.p.stdin.write(b"-stay_open\nFalse\n")
            self.p.stdin.flush()
            self.p.wait(timeout=5)
        except Exception:
            self.p.kill()


def info_from_exiftool(d: dict, kind: str) -> MediaInfo:
    info = MediaInfo()
    if kind == "photo":
        # ModifyDate son çare: bazı telefonlar paylaşılan fotoğrafta yalnızca bunu bırakır (Python okuyucusuyla aynı kural)
        order = [("DateTimeOriginal", "local"), ("CreateDate", "local"), ("ModifyDate", "local")]
    else:
        # CreationDate (telefonlar) saat dilimi içerir; DateTimeOriginal bazı kameralarda yerel;
        # QuickTime CreateDate/MediaCreateDate standart olarak UTC'dir (ama bazı kameralar yerel yazar).
        order = [("CreationDate", "tz"), ("DateTimeOriginal", "local"),
                 ("CreateDate", "utc"), ("MediaCreateDate", "utc")]
    for key, kind_ in order:
        dt, has_tz = parse_date(d.get(key))
        if dt:
            info.date = dt
            info.date_kind = "local" if (kind_ == "local" or has_tz) else "utc"
            break
    # Not: ICC renk profilindeki DeviceManufacturer ("APPL" gibi) cihaz değildir, kullanılmaz.
    info.device = make_device(d.get("Make"), d.get("Model"))
    serial = d.get("SerialNumber") or d.get("BodySerialNumber")
    info.serial = str(serial).strip() if serial not in (None, "", 0) else None
    try:
        lat, lon = float(d["GPSLatitude"]), float(d["GPSLongitude"])
        if lat or lon:
            info.lat, info.lon = lat, lon
    except (KeyError, TypeError, ValueError):
        pass
    info.comment = str(d.get("UserComment") or "").strip()
    return info


# ----------------------------------------------------------------- ekran görüntüleri
# (desen, cihaz adı tahmini). Desendeki y,mo,d,h,mi,s grupları varsa tarih dosya adından okunur.
_SS_NAME_RULES = [
    # Windows Ekran Alıntısı Aracı / Win+PrtSc: "Ekran görüntüsü 2025-05-25 005223.png", "Screenshot 2025-05-25 005223.png"
    (re.compile(r"^(?:ekran görüntüsü|ekran goruntusu|screenshot)\s+(?P<y>\d{4})-(?P<mo>\d{2})-(?P<d>\d{2})\s+"
                r"(?P<h>\d{2})(?P<mi>\d{2})(?P<s>\d{2})", re.I), "Windows PC"),
    # Windows eski: "Ekran Görüntüsü (12).png" / "Screenshot (12).png"
    (re.compile(r"^(?:ekran görüntüsü|ekran goruntusu|screenshot)\s*\(\d+\)", re.I), "Windows PC"),
    # Roblox (bilgisayar): "RobloxScreenShot20250525_005219337.png"
    (re.compile(r"^RobloxScreenShot(?P<y>\d{4})(?P<mo>\d{2})(?P<d>\d{2})_(?P<h>\d{2})(?P<mi>\d{2})(?P<s>\d{2})", re.I),
     "Windows PC"),
    # Android: "Screenshot_20210102-181538.jpg", "Screenshot_2021-01-02-18-15-38-12_com.app.jpg"
    (re.compile(r"^Screenshot_(?P<y>\d{4})-?(?P<mo>\d{2})-?(?P<d>\d{2})[-_]?(?P<h>\d{2})-?(?P<mi>\d{2})-?(?P<s>\d{2})", re.I),
     "Android"),
    (re.compile(r"^(?:screenshot|ekran)", re.I), None),
]


def detect_screenshot(path: Path, info: MediaInfo) -> None:
    """Ekran görüntüsünü tanır; tarihi/cihazı eksikse dosya adından ve kaynağından tamamlar."""
    if "screenshot" in info.comment.lower():          # iPhone/iPad: EXIF UserComment = "Screenshot"
        info.screenshot = True
        if not info.device:
            info.device = "Apple iPhone"
        return
    for rx, dev in _SS_NAME_RULES:
        m = rx.match(path.stem)
        if not m:
            continue
        info.screenshot = True
        g = m.groupdict()
        if not info.date and g.get("y"):
            try:
                info.date = datetime(int(g["y"]), int(g["mo"]), int(g["d"]), int(g["h"]), int(g["mi"]), int(g["s"]))
                info.date_kind = "local"
            except ValueError:
                pass
        if not info.device and dev:
            info.device = dev
        return


# ----------------------------------------------------------------- cihaz adı eşleştirme
# Aynı cihaz farklı uygulamalarda farklı adla yazılabilir (ör. model kodu). Program bunları "öğrenir":
# kullanıcı birleştirdikçe %APPDATA%\FotoDuzenleyici\cihaz_esleme.json dosyasına kaydedilir.
BUILTIN_ALIASES = {
    "realme RMX2030": "realme 5i",
}


def aliases_file() -> Path:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / "FotoDuzenleyici" / "cihaz_esleme.json"


def load_aliases() -> dict:
    data = dict(BUILTIN_ALIASES)
    try:
        data.update(json.loads(aliases_file().read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return {k: v for k, v in data.items() if isinstance(v, str) and k and v and k != v and not k.startswith("_")}


def _read_file() -> dict:
    try:
        return json.loads(aliases_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load_separate() -> set:
    """Kullanıcının 'aynı cihaz değil' dediği ad grupları (bir daha sorulmaz)."""
    return {tuple(g) for g in _read_file().get("_ayri_cihazlar", [])}


def save_aliases(aliases: dict, separate: Optional[set] = None) -> None:
    f = aliases_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: v for k, v in aliases.items() if k and v and k != v and not k.startswith("_")}
    for k in BUILTIN_ALIASES:          # hazır bir eşleştirme kaldırıldıysa bunu "kendisi" olarak hatırla
        if k not in clean:
            clean[k] = k
    sep = load_separate() if separate is None else separate
    if sep:
        clean["_ayri_cihazlar"] = sorted(list(g) for g in sep)
    f.write_text(json.dumps(clean, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def resolve_alias(name: Optional[str], aliases: dict) -> Optional[str]:
    seen = set()
    while name in aliases and name not in seen:   # zincirleri izle, döngüye girme
        seen.add(name)
        name = aliases[name]
    return name


def apply_aliases(plan: "Plan", aliases: dict) -> None:
    for a in plan.actions:
        if a.info.raw_device is None:
            a.info.raw_device = a.info.device
        a.info.device = resolve_alias(a.info.raw_device, aliases)


def raw_device_counts(plan: "Plan") -> dict:
    c: dict = {}
    for a in plan.actions:
        r = a.info.raw_device if a.info.raw_device is not None else a.info.device
        if r:
            c[r] = c.get(r, 0) + 1
    return c


def similar_device_names(plan: "Plan") -> list:
    """Aynı markadan birden fazla (birleştirilmemiş) ad: aynı cihaz olabilir, kullanıcıya sorulur."""
    by_brand: dict = {}
    for name in {a.info.device for a in plan.actions if a.info.device}:
        by_brand.setdefault(name.split()[0].lower(), set()).add(name)
    sep = load_separate()
    return [sorted(v) for v in by_brand.values() if len(v) > 1 and tuple(sorted(v)) not in sep]


# ----------------------------------------------------------------- 1) tarama
def list_media(source: Path, target: Path):
    target_r = target.resolve()
    for root, dirs, files in os.walk(source):
        rootp = Path(root)
        dirs[:] = sorted((d for d in dirs
                          if (rootp / d).resolve() != target_r and not d.startswith(".")),
                         key=natural_key)
        for name in sorted(files, key=_file_order):
            yield rootp / name


def scan(source, target, use_exiftool: bool = True,
         progress: Optional[Callable[[int, int, str], None]] = None,
         cancel: Optional[Callable[[], bool]] = None, batch: int = 100) -> Plan:
    t0 = time.perf_counter()
    source, target = Path(source), Path(target)
    plan = Plan(source, target)
    media = []
    for p in list_media(source, target):
        ext = p.suffix.lower()
        kind = "photo" if ext in PHOTO_EXT else "video" if ext in VIDEO_EXT else None
        if kind:
            media.append((p, kind))
        else:
            plan.skipped.append(p)

    et = None
    if use_exiftool and EXIFTOOL:
        try:
            et = ExifTool(EXIFTOOL)
            plan.used_exiftool = True
        except Exception:
            et = None
    try:
        for start in range(0, len(media), batch):
            if cancel and cancel():
                break
            chunk = media[start:start + batch]
            et_data = {}
            if et:
                try:
                    et_data = et.read([p for p, _ in chunk])
                except Exception:
                    et.close()
                    et, et_data = None, {}
            for i, (p, kind) in enumerate(chunk, start + 1):
                if progress:
                    progress(i, len(media), p.name)
                d = et_data.get(os.path.normcase(os.path.normpath(str(p))))
                if d is not None:
                    info = info_from_exiftool(d, kind)
                    if kind == "photo" and (not (info.date and info.device)
                                            or (p.suffix.lower() == ".png" and not info.comment)):
                        # exiftool bazı dosyalarda (ör. PNG'de görüntüden sonra gelen EXIF) eksik okuyabilir:
                        # Python okuyucusuyla eksik alanları tamamla.
                        extra = read_photo_python(p)
                        info.date = info.date or extra.date
                        info.device = info.device or extra.device
                        info.comment = info.comment or extra.comment
                        info.serial = info.serial or extra.serial
                        if info.lat is None:
                            info.lat, info.lon = extra.lat, extra.lon
                else:
                    info = read_photo_python(p) if kind == "photo" else read_video_python(p)
                if kind == "photo":
                    detect_screenshot(p, info)
                plan.actions.append(Action(p, kind, info))
    finally:
        if et:
            et.close()
    apply_aliases(plan, load_aliases())
    plan.scan_seconds = time.perf_counter() - t0
    return plan


# ----------------------------------------------------------------- sorular için analiz
def utc_video_groups(plan: Plan) -> dict:
    """Saati UTC olabilecek videoları cihaza göre gruplar: {cihaz: [Action, ...]}."""
    g: dict = {}
    for a in plan.actions:
        if a.kind == "video" and a.info.date and a.info.date_kind == "utc":
            g.setdefault(a.info.device or UNKNOWN_DEVICE, []).append(a)
    return g


def tz_for(a: Action, fallback_tz: str) -> str:
    if _TF and a.info.lat is not None:
        try:
            name = _TF.timezone_at(lat=a.info.lat, lng=a.info.lon)
            if name:
                return name
        except Exception:
            pass
    return fallback_tz


def to_local(dt: datetime, tz_name: str) -> datetime:
    if not HAS_ZONEINFO:
        return dt + timedelta(hours=3) if tz_name == DEFAULT_TZ else dt
    return dt.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tz_name)).replace(tzinfo=None)


def guess_video_utc(plan: Plan, device: str, videos: list, tz_name: str) -> tuple[bool, str]:
    """Videoların UTC mi yerel mi yazıldığını tahmin eder. (tahmin, açıklama) döner.

    Aynı cihazın fotoğrafları varsa: her video için en yakın fotoğrafa uzaklık iki varsayımla
    hesaplanır, hangisinde daha yakınsa o seçilir. Yoksa markaya göre tahmin edilir.
    """
    photos = sorted(a.info.date for a in plan.actions
                    if a.kind == "photo" and a.info.date and (a.info.device or UNKNOWN_DEVICE) == device)
    if photos and device != UNKNOWN_DEVICE:
        import bisect

        def gap(t):
            i = bisect.bisect_left(photos, t)
            return min(abs((photos[j] - t).total_seconds()) for j in (i - 1, i) if 0 <= j < len(photos))
        as_local = median(gap(v.info.date) for v in videos)
        as_utc = median(gap(to_local(v.info.date, tz_for(v, tz_name))) for v in videos)
        if abs(as_local - as_utc) > 1800:
            return as_utc < as_local, "aynı cihazın fotoğraflarıyla karşılaştırıldı"
    is_utc = device.lower().startswith(UTC_BRANDS)
    return is_utc, "markaya göre tahmin"


def multi_body_models(plan: Plan) -> dict:
    """Aynı modelden birden fazla seri numarası görülen cihazlar: {cihaz: {seri: dosya_sayısı}}."""
    seen: dict = {}
    for a in plan.actions:
        if a.info.device and a.info.serial:
            seen.setdefault(a.info.device, {}).setdefault(a.info.serial, 0)
            seen[a.info.device][a.info.serial] += 1
    return {d: s for d, s in seen.items() if len(s) > 1}


# ----------------------------------------------------------------- 2) son adlar
_HASH_CACHE: dict = {}


def _cached_hash(p: Path) -> Optional[bytes]:
    """Dosya özetini (SHA-1) okur; aynı dosya tekrar okunmaz. Okunamazsa None."""
    try:
        st = p.stat()
    except OSError:
        return None
    key = (str(p), st.st_size, st.st_mtime_ns)
    if key not in _HASH_CACHE:
        for i in range(3):
            try:
                _HASH_CACHE[key] = _file_hash(p)
                break
            except OSError:
                if i == 2:
                    return None
                time.sleep(0.5 * (i + 1))
    return _HASH_CACHE[key]


def _target_index(target: Path) -> dict:
    """Hedefte zaten bulunan medya dosyaları: {boyut: [yol, ...]} (rapor ve işlem kaydı hariç)."""
    idx: dict = {}
    if not target.exists():
        return idx
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d != JOURNAL_DIR]
        for n in files:
            if Path(n).suffix.lower() in PHOTO_EXT | VIDEO_EXT:
                fp = Path(root) / n
                try:
                    idx.setdefault(fp.stat().st_size, []).append(fp)
                except OSError:
                    pass
    return idx


def _file_hash(p: Path) -> bytes:
    d = hashlib.sha1()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            d.update(chunk)
    return d.digest()


def _same_file(a: Path, b: Path, tries: int = 3) -> Optional[bool]:
    """True: aynı içerik, False: farklı, None: okunamadı (ör. OneDrive o an dosyayı kilitlemiş).

    Okuma hatası 'farklı' sayılmaz; yoksa aynı dosyanın ikinci kopyası oluşurdu."""
    for i in range(tries):
        try:
            if a.stat().st_size != b.stat().st_size:
                return False
            return _file_hash(a) == _file_hash(b)
        except OSError:
            if i + 1 < tries:
                time.sleep(0.5 * (i + 1))
    return None


def _base_location(target: Path, a: Action, F: dict = FOLDERS["tr"]) -> tuple[Path, str]:
    if a.dup_of is not None:    # kopya: normal yerinin aynısı, ama _Kopyalar altında
        folder, stem = _base_location_normal(target, a, F)
        return target / F["duplicates"] / folder.relative_to(target), stem
    return _base_location_normal(target, a, F)


def _base_location_normal(target: Path, a: Action, F: dict) -> tuple[Path, str]:
    if a.info.screenshot:   # Ekran Görüntüleri/<Cihaz>/..., eksikler Ekran Görüntüleri/_Eksik Bilgi/...
        root = target / F["screenshots"]
        if a.date and a.device:
            return root / a.device, f"{a.date.strftime(DATE_FMT)}_{file_label(a.device)}"
        if a.device:
            return root / F["missing"] / F["no_date"] / a.device, a.src.stem
        if a.date:
            return root / F["missing"] / F["no_device"], a.date.strftime(DATE_FMT)
        return root / F["missing"] / F["no_both"], a.src.stem
    kind_dir = F["photo"] if a.kind == "photo" else F["video"]
    if a.date and a.device:
        return target / a.device / kind_dir, f"{a.date.strftime(DATE_FMT)}_{file_label(a.device)}"
    if a.device:
        return target / F["missing"] / F["no_date"] / a.device / kind_dir, a.src.stem
    if a.date:
        return target / F["missing"] / F["no_device"] / kind_dir, a.date.strftime(DATE_FMT)
    return target / F["missing"] / F["no_both"] / kind_dir, a.src.stem


def file_label(device: str) -> str:
    """Dosya adındaki cihaz kısmı: 'Canon EOS R6 (1234)' -> 'Canon-EOS-R6-1234'."""
    return re.sub(r"[()]", "", device).replace(" ", "-")


def _serial_labels(serials) -> dict:
    """Seri numaralarını kısa etiketlere çevirir (son 4 hane, çakışırsa tamamı)."""
    short = {s: s[-4:] for s in serials}
    if len(set(short.values())) < len(short):
        short = {s: s for s in serials}
    return {s: clean_name(v) for s, v in short.items()}


def finalize(plan: Plan, opts: Options) -> Plan:
    # Hedefte önceki klasörler hangi dildeyse onu kullan; yoksa seçili dil
    plan.folder_lang = detect_folder_lang(plan.target) or (opts.lang if opts.lang in FOLDERS else "tr")
    plan.lang = opts.lang if opts.lang in TEXT else "tr"
    F, T = FOLDERS[plan.folder_lang], TEXT[plan.lang]
    labels = {d: _serial_labels(s) for d, s in multi_body_models(plan).items() if d in opts.split_models}
    for a in plan.actions:
        a.status, a.note, a.dest, a.dup_of = "bekliyor", "", None, None
        a.device = a.info.device
        if a.device in labels and a.info.serial in labels[a.device]:
            a.device = f"{a.device} ({labels[a.device][a.info.serial]})"
        a.date = a.info.date
        if a.date and a.kind == "video" and a.info.date_kind == "utc":
            if opts.video_utc.get(a.info.device or UNKNOWN_DEVICE, False):
                tz = tz_for(a, opts.tz_name)
                a.date = to_local(a.date, tz)
                a.note = T["utc"].format(tz=tz)
        off = opts.clock_offsets.get(a.info.device) if a.info.device else None
        if a.date and off:
            a.date = a.date + timedelta(minutes=off)
            sign = "+" if off > 0 else "-"
            a.note = (a.note + "; " if a.note else "") + T["shift"].format(v=f"{sign}{abs(off) // 60}:{abs(off) % 60:02d}")

    # 1) içeriği hedefte zaten olan dosyalar (önceden düzenlenmiş klasöre sadece yenileri eklemek için)
    idx = _target_index(plan.target)
    for a in plan.actions:
        try:
            size = a.src.stat().st_size
        except OSError:
            continue
        for existing in idx.get(size, []):
            h1, h2 = _cached_hash(a.src), _cached_hash(existing)
            if h1 is not None and h1 == h2:
                a.status, a.dest = "zaten var", existing
                a.note = (a.note + "; " if a.note else "") + T["exists"]
                break

    # 2) kaynakta içeriği aynı olan dosyalar: ilki normal yerine, diğerleri _Kopyalar'a
    by_size: dict = {}
    for a in plan.actions:
        if a.status == "bekliyor":
            try:
                by_size.setdefault(a.src.stat().st_size, []).append(a)
            except OSError:
                pass
    for same_size in by_size.values():
        if len(same_size) < 2:
            continue
        first_by_hash: dict = {}
        for a in same_size:            # kaynak sırasıyla
            h = _cached_hash(a.src)
            if h is None:
                continue
            if h in first_by_hash:
                a.dup_of = first_by_hash[h]
                a.note = (a.note + "; " if a.note else "") + T["dup"].format(name=a.dup_of.src.name)
            else:
                first_by_hash[h] = a

    groups: dict = {}
    for a in plan.actions:
        if a.status != "bekliyor":
            continue
        folder, stem = _base_location(plan.target, a, F)
        key = (str(folder).lower(), stem.lower(), a.src.suffix.lower())
        groups.setdefault(key, []).append((a, folder, stem))

    used: set = set()
    for members in groups.values():
        width = max(2, len(str(len(members))))
        for n, (a, folder, stem) in enumerate(members, 1):
            ext = a.src.suffix.lower()
            seq = n if len(members) > 1 else 0
            while True:
                dest = folder / (f"{stem}_{seq:0{width}d}{ext}" if seq else f"{stem}{ext}")
                if str(dest).lower() in used:
                    seq += 1
                    continue
                if dest.exists():
                    same = _same_file(a.src, dest)
                    if same is None:
                        a.status = "hata: hedefteki aynı adlı dosya okunamadı (başka bir program kullanıyor olabilir)"
                        break
                    if same:
                        a.status = "zaten var"
                        break
                    seq += 1
                    continue
                break
            used.add(str(dest).lower())
            a.dest = dest
    return plan


def build_plan(source, target, opts: Optional[Options] = None, use_exiftool: bool = True, **kw) -> Plan:
    """Tek adımda: tara + varsayılan seçimlerle (tahminlerle) adları belirle."""
    plan = scan(source, target, use_exiftool=use_exiftool, **kw)
    opts = opts or Options()
    for dev, vids in utc_video_groups(plan).items():
        opts.video_utc.setdefault(dev, guess_video_utc(plan, dev, vids, opts.tz_name)[0])
    return finalize(plan, opts)


# ----------------------------------------------------------------- uygula
def execute(plan: Plan, move: bool = False,
            progress: Optional[Callable[[int, int, str], None]] = None,
            cancel: Optional[Callable[[], bool]] = None) -> Path:
    todo = [a for a in plan.actions if a.status == "bekliyor"]
    plan.target.mkdir(parents=True, exist_ok=True)
    journal = Journal(plan.target, "move" if move else "copy")
    try:
        for i, a in enumerate(todo, 1):
            if cancel and cancel():
                break
            if progress:
                progress(i, len(todo), a.src.name)
            try:
                new_dirs = _missing_parents(a.dest.parent, plan.target)
                a.dest.parent.mkdir(parents=True, exist_ok=True)
                if a.dest.exists():
                    raise FileExistsError("hedefte aynı adlı dosya var")
                if move:
                    shutil.move(str(a.src), str(a.dest))
                else:
                    shutil.copy2(a.src, a.dest)
                a.status = "taşındı" if move else "kopyalandı"
                journal.add(a.src, a.dest, new_dirs)
            except Exception as e:
                a.status = f"hata: {e}"
    finally:
        report = write_report(plan)
        journal.report = report
        journal.save()
    return report


# ----------------------------------------------------------------- geri alma
def _missing_parents(folder: Path, stop: Path) -> list:
    """folder'a kadar henüz var olmayan klasörler (geri almada boşsa silinecekler)."""
    out = []
    while folder != stop and not folder.exists() and stop in folder.parents:
        out.append(str(folder))
        folder = folder.parent
    return out


class Journal:
    """Her işlemin kaydı: hedef klasörde _islem_gecmisi/islem_<zaman>.json. Son işlemi geri almak için."""

    def __init__(self, target: Path, mode: str):
        self.target, self.mode = Path(target), mode
        self.items: list = []
        self.dirs: list = []
        self.report: Optional[Path] = None
        self.started = datetime.now()

    def add(self, src: Path, dest: Path, new_dirs: list):
        st = dest.stat()
        self.items.append({"src": str(src), "dest": str(dest), "size": st.st_size, "mtime_ns": st.st_mtime_ns})
        self.dirs.extend(new_dirs)

    def save(self):
        if not self.items:
            return
        d = self.target / JOURNAL_DIR
        d.mkdir(exist_ok=True)
        name = f"islem_{self.started.strftime('%Y-%m-%d_%H-%M-%S_%f')}.json"
        (d / name).write_text(json.dumps({
            "mode": self.mode, "time": self.started.isoformat(timespec="seconds"),
            "report": str(self.report) if self.report else None, "items": self.items, "dirs": self.dirs,
        }, ensure_ascii=False, indent=1), encoding="utf-8")


def last_journal(target) -> Optional[Path]:
    d = Path(target) / JOURNAL_DIR
    files = sorted(d.glob("islem_*.json")) if d.exists() else []
    files = [f for f in files if not f.name.endswith(".geri_alindi.json")]
    return files[-1] if files else None


def describe_last(target) -> Optional[dict]:
    j = last_journal(target)
    if not j:
        return None
    data = json.loads(j.read_text(encoding="utf-8"))
    return {"path": j, "mode": data["mode"], "time": data["time"], "count": len(data["items"])}


def undo_last(target, progress: Optional[Callable[[int, int, str], None]] = None) -> dict:
    """Son işlemi geri alır. Kopyalamada: hedefe kopyalanan dosyalar silinir (sonradan değiştirilmemişse).
    Taşımada: dosyalar eski yerlerine geri taşınır. Sonuç: {"geri_alindi": n, "atlandi": [(dosya, neden)]}."""
    j = last_journal(target)
    if not j:
        return {"geri_alindi": 0, "atlandi": [], "yok": True}
    data = json.loads(j.read_text(encoding="utf-8"))
    done, skipped = 0, []
    items = data["items"]
    for i, it in enumerate(reversed(items), 1):
        src, dest = Path(it["src"]), Path(it["dest"])
        if progress:
            progress(i, len(items), dest.name)
        try:
            if not dest.exists():
                skipped.append((str(dest), "hedefte artık yok"))
                continue
            st = dest.stat()
            if st.st_size != it["size"] or st.st_mtime_ns != it["mtime_ns"]:
                skipped.append((str(dest), "sonradan değiştirilmiş, dokunulmadı"))
                continue
            if data["mode"] == "move":
                if src.exists():
                    skipped.append((str(dest), "eski yerinde aynı adlı dosya var"))
                    continue
                src.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dest), str(src))
            else:
                if not src.exists():   # kopyalamada asıl dosya kaybolduysa tek kopyayı silme
                    skipped.append((str(dest), "asıl dosya bulunamadı, kopya silinmedi"))
                    continue
                dest.unlink()
            done += 1
        except OSError as e:
            skipped.append((str(dest), f"hata: {e}"))
    for d in sorted(set(data.get("dirs", [])), key=len, reverse=True):   # işlemin açtığı boş klasörler
        try:
            Path(d).rmdir()
        except OSError:
            pass
    j.rename(j.with_name(j.stem + ".geri_alindi.json"))
    return {"geri_alindi": done, "atlandi": skipped, "rapor": data.get("report")}


def write_report(plan: Plan) -> Path:
    plan.target.mkdir(parents=True, exist_ok=True)
    T = TEXT.get(plan.lang, TEXT["tr"])
    prefix = "rapor" if plan.lang == "tr" else "report"
    path = plan.target / f"{prefix}_{datetime.now().strftime(DATE_FMT)}.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(T["cols"])
        for a in plan.actions:
            w.writerow([a.src, a.dest or "", T["photo"] if a.kind == "photo" else T["video"],
                        a.date.strftime("%Y-%m-%d %H:%M:%S") if a.date else "",
                        a.device or "", a.info.raw_device or "", a.info.serial or "",
                        a.dup_of.src if a.dup_of else "", a.note, status_text(a.status, plan.lang)])
        for p in plan.skipped:
            w.writerow([p, "", "", "", "", "", "", "", "", T["unsupported"]])
    return path


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Fotoğraf/video düzenleyici")
    ap.add_argument("source")
    ap.add_argument("target")
    ap.add_argument("--move", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--no-exiftool", action="store_true")
    ap.add_argument("--tz", default=DEFAULT_TZ)
    args = ap.parse_args()
    pl = build_plan(args.source, args.target, Options(tz_name=args.tz), use_exiftool=not args.no_exiftool)
    for a in pl.actions:
        print(f"{a.src}  ->  {a.dest}  [{a.status}] {a.note}")
    print(pl.counts(), f"tarama: {pl.scan_seconds:.2f} sn, exiftool: {pl.used_exiftool}")
    if args.run:
        print("Rapor:", execute(pl, move=args.move))
