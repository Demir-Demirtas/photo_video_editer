# -*- coding: utf-8 -*-
"""Arayüz metinleri (Türkçe / İngilizce). Yeni bir dil eklemek için STRINGS'e bir sözlük eklemek yeterli."""
from __future__ import annotations

import json
import locale
import os
from pathlib import Path

STRINGS = {
    "tr": {
        "app_title": "Foto Düzenleyici",
        "lang_name": "Türkçe",
        "src_label": "Kaynak klasör (fotoğrafların olduğu yer):",
        "dst_label": "Hedef klasör (düzenlenmiş hali buraya):",
        "pick": "Seç...",
        "copy": "Kopyala (asıllar yerinde kalır, önerilen)",
        "move": "Taşı",
        "use_exiftool": "exiftool kullan (videolar için daha iyi)",
        "stop": "Durdur", "run": "2) Başlat", "choices": "Seçimler...", "devices": "Cihaz adları...",
        "clock": "Saat düzeltme...", "undo": "Son işlemi geri al", "preview": "1) Önizle", "language": "Dil",
        "col_src": "Şu anki dosya", "col_dest": "Yeni konum (hedef klasöre göre)",
        "col_info": "Çekim zamanı / cihaz", "col_status": "Durum",
        "start_hint": "Kaynak ve hedef klasörü seçip Önizle'ye basın.",
        "tf_missing": "Uyarı: konumdan saat dilimi bulma modülü (timezonefinder) yüklenemedi; GPS'li videolarda da sorulan konum kullanılacak.",
        "et_missing": "exiftool bulunamadı: videoların cihaz bilgisi çoğu zaman okunamaz. Kurulum için BENIOKU'ya bakın.",
        "need_src": "Lütfen geçerli bir kaynak klasör seçin.", "need_dst": "Lütfen bir hedef klasör seçin.",
        "same_dirs": "Hedef klasör, kaynak klasörle aynı olamaz.",
        "reading": "Dosyalar okunuyor...", "naming": "Yeni adlar belirleniyor...", "stopped": "Durduruldu.",
        "nothing_new": "Yapılacak yeni bir dosya yok.",
        "confirm_move": "{n} dosya TAŞINACAK (kaynak klasörden silinecek). Devam edilsin mi?",
        "confirm_copy": "{n} dosya kopyalanacak. Devam edilsin mi?",
        "error": "Bir hata oluştu:\n{e}",
        "summary": ("{toplam} dosya: {tam} tam bilgili, {tarih_yok} tarihsiz, {cihaz_yok} cihazsız, {ikisi_yok} ikisi de yok; "
                    "{ekran_goruntusu} ekran görüntüsü, {kopya} kopya. {zaten_var} zaten hedefte, {yeni} yeni işlenecek. "
                    "{desteklenmeyen} desteklenmeyen dosyaya dokunulmayacak."),
        "speed": "Okuma süresi {s:.1f} sn ({ms:.0f} ms/dosya, exiftool {et}).", "on": "açık", "off": "kapalı",
        "folder_lang_kept": "Hedefte önceki klasörler {lang} olduğu için klasör adları {lang} kalacak.",
        "done": "Bitti. {ok} dosya işlendi, {err} hata.\nRapor: {report}", "open_target": "Hedef klasör açılsın mı?",
        "no_date": "tarih yok", "no_device": "cihaz yok",
        # sorular
        "q_title": "Birkaç sorum var", "q_video": "Video saatleri",
        "q_video_help": "Bazı cihazlar videonun saatini dünya saatiyle (UTC) kaydeder, bazıları yerel saatle. Programın tahmini seçili geldi. Örnek saate bakıp emin değilsen olduğu gibi bırakabilirsin.",
        "q_utc": "UTC kaydediyor, yerel saate çevir", "q_local": "Zaten yerel saat, dokunma",
        "q_n_videos": "{dev}  ({n} video)",
        "q_example": "   Örnek {name}: çevrilirse {conv}, çevrilmezse {raw}   (tahmin: {why})",
        "why_photos": "aynı cihazın fotoğraflarıyla karşılaştırıldı", "why_brand": "markaya göre tahmin",
        "q_where": "Konum bilgisi (GPS) olmayan {n} video hangi ülkede/şehirde çekildi?",
        "q_where_help": "GPS'i olan videolarda konum otomatik bulunur.",
        "q_bodies": "Aynı modelden birden fazla makine",
        "q_body_line": "{dev}: {n} farklı makine bulundu ({desc}). Ayrı klasörlere ayır",
        "q_body_desc": "seri sonu {s}: {n} dosya",
        "q_bodies_help": "Ayrılırsa klasör adı 'Canon EOS R6 (1234)' gibi olur. Seri numarası yazmayan dosyalar (genelde videolar) ortak klasörde kalır.",
        "q_similar": "Benzer cihaz adları",
        "q_similar_help": "Aynı telefon bazen farklı adla yazılır (ör. 'realme RMX2030' ile 'realme 5i'). Aynı cihazsa işaretle ve hangi adın kullanılacağını seç. Program cevabını hatırlar ve aynı şeyi bir daha sormaz. Sonradan değiştirmek için 'Cihaz adları...' düğmesini kullan.",
        "q_same": "Aynı cihaz: {desc}", "ok": "Tamam", "cancel": "Vazgeç", "save": "Kaydet",
        "bad_tz": "'{tz}' tanınmadı. Listeden seçin (ör. Europe/Istanbul).", "save_fail": "Kaydedilemedi: {e}",
        # cihaz adları
        "d_title": "Cihaz adları",
        "d_help": "Soldaki ad dosyada yazan addır. Sağdaki ad, klasör ve dosya adında kullanılacak addır. İki adı birleştirmek için sağ tarafa diğer cihazın adını yaz ya da listeden seç. Ayrı kalması için sağ tarafı soldakiyle aynı bırak.",
        "d_count": "{name}  ({n} dosya)", "d_empty": "Henüz cihaz yok. Önce Önizle'ye basın.",
        # saat düzeltme
        "c_title": "Saat düzeltme",
        "c_help": "Bir makinenin saati yanlış ayarlıysa (ör. yurt dışında güncellenmemiş) o cihazın bütün fotoğraf ve videolarına eklenecek süreyi yaz. Örnek: +2, -1:30, +0:45. Boş bırakılırsa değişmez. Bu ayar sadece bu çalıştırma için geçerlidir.",
        "c_bad": "'{v}' anlaşılamadı. Örnek: +2, -1:30", "c_first": "Önce Önizle'ye basın.",
        # geri alma
        "u_none": "Bu hedef klasörde geri alınacak bir işlem yok.",
        "u_confirm_copy": "{time} tarihindeki kopyalama geri alınacak: hedefe kopyalanan {n} dosya silinecek (asılları yerinde duruyor). Devam edilsin mi?",
        "u_confirm_move": "{time} tarihindeki taşıma geri alınacak: {n} dosya eski yerlerine taşınacak. Devam edilsin mi?",
        "u_done": "{n} dosya geri alındı.", "u_skipped": "{n} dosyaya dokunulmadı:",
        "u_running": "Geri alınıyor...",
    },
    "en": {
        "app_title": "Photo Organizer",
        "lang_name": "English",
        "src_label": "Source folder (where the photos are):",
        "dst_label": "Target folder (organized copy goes here):",
        "pick": "Browse...",
        "copy": "Copy (originals stay in place, recommended)",
        "move": "Move",
        "use_exiftool": "Use exiftool (better for videos)",
        "stop": "Stop", "run": "2) Start", "choices": "Choices...", "devices": "Device names...",
        "clock": "Clock fix...", "undo": "Undo last run", "preview": "1) Preview", "language": "Language",
        "col_src": "Current file", "col_dest": "New location (inside target)",
        "col_info": "Taken at / device", "col_status": "Status",
        "start_hint": "Choose the source and target folders, then press Preview.",
        "tf_missing": "Warning: the time-zone-from-location module (timezonefinder) could not be loaded; the chosen location will be used for GPS videos too.",
        "et_missing": "exiftool not found: device info of videos usually can't be read. See the README to install it.",
        "need_src": "Please choose a valid source folder.", "need_dst": "Please choose a target folder.",
        "same_dirs": "The target folder can't be the same as the source folder.",
        "reading": "Reading files...", "naming": "Working out new names...", "stopped": "Stopped.",
        "nothing_new": "There are no new files to process.",
        "confirm_move": "{n} files will be MOVED (removed from the source folder). Continue?",
        "confirm_copy": "{n} files will be copied. Continue?",
        "error": "An error occurred:\n{e}",
        "summary": ("{toplam} files: {tam} complete, {tarih_yok} without date, {cihaz_yok} without device, {ikisi_yok} without both; "
                    "{ekran_goruntusu} screenshots, {kopya} duplicates. {zaten_var} already in target, {yeni} new to process. "
                    "{desteklenmeyen} unsupported files will be left alone."),
        "speed": "Reading took {s:.1f} s ({ms:.0f} ms/file, exiftool {et}).", "on": "on", "off": "off",
        "folder_lang_kept": "The target already has {lang} folders, so folder names stay {lang}.",
        "done": "Done. {ok} files processed, {err} errors.\nReport: {report}", "open_target": "Open the target folder?",
        "no_date": "no date", "no_device": "no device",
        "q_title": "A few questions", "q_video": "Video times",
        "q_video_help": "Some devices record video time in world time (UTC), others in local time. The program's guess is preselected. Check the example time; if unsure, leave it as it is.",
        "q_utc": "Records UTC, convert to local time", "q_local": "Already local time, leave it",
        "q_n_videos": "{dev}  ({n} videos)",
        "q_example": "   Example {name}: converted {conv}, not converted {raw}   (guess: {why})",
        "why_photos": "compared with photos from the same device", "why_brand": "guessed from the brand",
        "q_where": "Where were the {n} videos without location (GPS) taken?",
        "q_where_help": "Videos with GPS get their location automatically.",
        "q_bodies": "More than one camera of the same model",
        "q_body_line": "{dev}: {n} different cameras found ({desc}). Split into separate folders",
        "q_body_desc": "serial ending {s}: {n} files",
        "q_bodies_help": "If split, folders are named like 'Canon EOS R6 (1234)'. Files without a serial number (usually videos) stay in the shared folder.",
        "q_similar": "Similar device names",
        "q_similar_help": "The same phone is sometimes written under different names (e.g. 'realme RMX2030' and 'realme 5i'). If they are the same device, tick it and choose the name to use. The program remembers the answer and won't ask again. Use 'Device names...' to change it later.",
        "q_same": "Same device: {desc}", "ok": "OK", "cancel": "Cancel", "save": "Save",
        "bad_tz": "'{tz}' was not recognized. Pick one from the list (e.g. Europe/London).", "save_fail": "Could not save: {e}",
        "d_title": "Device names",
        "d_help": "The left name is what the file says. The right name is used for folders and file names. To merge two names, type or pick the other device's name on the right. Leave it equal to the left to keep it separate.",
        "d_count": "{name}  ({n} files)", "d_empty": "No devices yet. Press Preview first.",
        "c_title": "Clock fix",
        "c_help": "If a camera's clock was set wrong (e.g. not changed abroad), enter the time to add to all photos and videos of that device. Examples: +2, -1:30, +0:45. Leave empty for no change. This setting applies to this run only.",
        "c_bad": "Could not understand '{v}'. Examples: +2, -1:30", "c_first": "Press Preview first.",
        "u_none": "There is nothing to undo in this target folder.",
        "u_confirm_copy": "The copy from {time} will be undone: the {n} files copied to the target will be deleted (the originals stay where they are). Continue?",
        "u_confirm_move": "The move from {time} will be undone: {n} files will be moved back to where they were. Continue?",
        "u_done": "{n} files undone.", "u_skipped": "{n} files were left alone:",
        "u_running": "Undoing...",
    },
}


def settings_file() -> Path:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / "FotoDuzenleyici" / "ayarlar.json"


def load_settings() -> dict:
    try:
        return json.loads(settings_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(data: dict) -> None:
    f = settings_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def system_lang() -> str:
    """Windows arayüz dili Türkçe ise 'tr', değilse 'en'."""
    try:
        import ctypes
        lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()   # type: ignore[attr-defined]
        return "tr" if (lid & 0x3FF) == 0x1F else "en"
    except Exception:
        pass
    try:
        loc = (locale.getlocale()[0] or os.environ.get("LANG", "")).lower()
    except Exception:
        loc = os.environ.get("LANG", "").lower()
    return "tr" if loc.startswith("tr") or "turkish" in loc else "en"


_current = None


def current() -> str:
    global _current
    if _current is None:
        saved = load_settings().get("lang")
        _current = saved if saved in STRINGS else system_lang()
    return _current


def set_lang(code: str) -> None:
    global _current
    _current = code if code in STRINGS else "tr"
    data = load_settings()
    data["lang"] = _current
    try:
        save_settings(data)
    except OSError:
        pass


def t(key: str, **kw) -> str:
    s = STRINGS[current()].get(key) or STRINGS["tr"].get(key, key)
    return s.format(**kw) if kw else s
