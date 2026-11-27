# -*- coding: utf-8 -*-
"""Test case'leri: her senaryoda beklenen sonuç ile programın gerçek sonucunu karşılaştırır.

Çalıştırma:  python tests/run_tests.py
Sonuç ekrana ve tests/test_raporu.md dosyasına yazılır. Asıl dosyalara dokunmaz: fixtures/ geçici bir
klasöre kopyalanır, program orada çalıştırılır. exiftool yoksa onu gerektiren testler "atlandı" olur."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import sorter  # noqa: E402

FIX = HERE / "fixtures"
results = []          # (grup, case, beklenen, gerçek, durum)


class Env:
    """Geçici çalışma alanı: kaynak kopyası, hedef ve ayrı bir eşleştirme dosyası (APPDATA)."""

    def __init__(self, fixture: str):
        self.tmp = Path(tempfile.mkdtemp(prefix="fototest_"))
        self.src = self.tmp / "kaynak"
        shutil.copytree(FIX / fixture, self.src)
        self.dst = self.tmp / "hedef"
        os.environ["APPDATA"] = str(self.tmp / "appdata")

    def plan(self, use_exiftool, opts=None, guess=True):
        p = sorter.scan(self.src, self.dst, use_exiftool=use_exiftool)
        opts = opts or sorter.Options()
        if guess:
            for d, v in sorter.utc_video_groups(p).items():
                opts.video_utc.setdefault(d, sorter.guess_video_utc(p, d, v, opts.tz_name)[0])
        return sorter.finalize(p, opts)

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def mapping(plan):
    return {a.src.relative_to(plan.source).as_posix(): (a.dest.relative_to(plan.target).as_posix() if a.dest else None)
            for a in plan.actions}


def check(group, case, expected, actual):
    ok = expected == actual
    results.append((group, case, expected, actual, "GEÇTİ" if ok else "KALDI"))
    return ok


def check_map(group, plan, expected: dict):
    m = mapping(plan)
    for src, dest in expected.items():
        check(group, src, dest, m.get(src, "(dosya listede yok)"))


def skip(group, case, why):
    results.append((group, case, "-", "-", f"ATLANDI ({why})"))


# --------------------------------------------------------------------------- senaryolar
def t_temel(mode):
    g = f"Temel adlandırma [{mode}]"
    e = Env("temel")
    try:
        p = e.plan(mode == "exiftool")
        C = "Canon EOS R6/Fotoğraflar/"
        check_map(g, p, {
            "kart/IMG_2.jpg": C + "2026-11-20_10-00-00_Canon-EOS-R6_01.jpg",   # aynı saniye: kaynak sırası
            "kart/IMG_3.jpg": C + "2026-11-20_10-00-00_Canon-EOS-R6_02.jpg",
            "kart/IMG_10.jpg": C + "2026-11-20_10-00-00_Canon-EOS-R6_03.jpg",  # 10, 3'ten sonra (doğal sıra)
            "kart/IMG_11.jpg": C + "2026-11-20_10-05-00_Canon-EOS-R6.jpg",     # çift: aynı ad, farklı uzantı
            "kart/IMG_11.tif": C + "2026-11-20_10-05-00_Canon-EOS-R6.tif",
            "nikon/DSC_1.jpg": "NIKON Z 6/Fotoğraflar/2026-11-20_09-59-00_NIKON-Z-6.jpg",
            "eksik/tarihsiz.jpg": "_Eksik Bilgi/Tarih Yok/Sony ILCE-7M3/Fotoğraflar/tarihsiz.jpg",
            "eksik/cihazsiz.jpg": "_Eksik Bilgi/Cihaz Yok/Fotoğraflar/2026-11-21_08-00-00.jpg",
            "eksik/WhatsApp.jpg": "_Eksik Bilgi/Tarih ve Cihaz Yok/Fotoğraflar/WhatsApp.jpg",
        })
        check(g, "notlar.txt dokunulmadan atlanır", ["notlar.txt"], [x.name for x in p.skipped])
    finally:
        e.close()


def t_kopyala_tekrar(mode):
    g = f"Kopyalama, tekrar çalıştırma, taşıma [{mode}]"
    e = Env("temel")
    try:
        ex = mode == "exiftool"
        p = e.plan(ex)
        sorter.execute(p, move=False)
        n_src = sum(1 for _ in e.src.rglob("*") if _.is_file())
        check(g, "kopyalandıktan sonra kaynakta 10 dosya kalır", 10, n_src)
        check(g, "hedefte 9 medya + 1 rapor (+ işlem kaydı)", 10,
              sum(1 for _ in e.dst.rglob("*") if _.is_file() and sorter.JOURNAL_DIR not in _.parts))
        p2 = e.plan(ex)
        check(g, "ikinci çalıştırmada hepsi 'zaten var'", ["zaten var"] * 9, [a.status for a in p2.actions])
        # hedefte aynı adda ama farklı içerikte dosya varsa üzerine yazılmaz, sıra no alır
        e.close(); e = Env("temel")
        hedef = e.dst / "_Eksik Bilgi/Tarih ve Cihaz Yok/Fotoğraflar/WhatsApp.jpg"
        hedef.parent.mkdir(parents=True)
        hedef.write_bytes(b"baska icerik")
        p3 = e.plan(ex)
        check(g, "farklı içerikli aynı ad: yeni sıra no", "_Eksik Bilgi/Tarih ve Cihaz Yok/Fotoğraflar/WhatsApp_01.jpg",
              mapping(p3)["eksik/WhatsApp.jpg"])
        sorter.execute(p3, move=True)
        check(g, "taşı: kaynakta medya kalmaz (txt kalır)", ["notlar.txt"],
              sorted(x.name for x in e.src.rglob("*") if x.is_file()))
        check(g, "taşı: eski dosya bozulmadı", b"baska icerik", hedef.read_bytes())
        # hedef dosya o an okunamıyorsa (OneDrive kilidi gibi) ikinci kopya oluşturulmaz, hata yazılır
        e.close(); e = Env("temel")
        orig = sorter._file_hash
        hedef2 = e.dst / "NIKON Z 6/Fotoğraflar/2026-11-20_09-59-00_NIKON-Z-6.jpg"
        hedef2.parent.mkdir(parents=True)
        shutil.copyfile(e.src / "nikon/DSC_1.jpg", hedef2)
        sorter._file_hash = lambda p: (_ for _ in ()).throw(OSError("kilitli"))
        try:
            p4 = e.plan(ex)
        finally:
            sorter._file_hash = orig
        a4 = next(a for a in p4.actions if a.src.name == "DSC_1.jpg")
        check(g, "okunamayan hedef: kopya yapılmaz, hata yazılır",
              ("NIKON Z 6/Fotoğraflar/2026-11-20_09-59-00_NIKON-Z-6.jpg", True),
              (a4.dest.relative_to(p4.target).as_posix(), a4.status.startswith("hata")))
    finally:
        e.close()


def t_govde(mode):
    g = f"Aynı model iki gövde [{mode}]"
    e = Env("govde")
    try:
        p = e.plan(mode == "exiftool")
        check(g, "iki seri no bulunur", {"Canon EOS R6": {"11111234": 1, "22225678": 1}}, sorter.multi_body_models(p))
        check_map(g, p, {"a.jpg": "Canon EOS R6/Fotoğraflar/2026-11-22_10-00-00_Canon-EOS-R6.jpg"})
        p = e.plan(mode == "exiftool", sorter.Options(split_models={"Canon EOS R6"}))
        check_map(g + " (ayır seçildi)", p, {
            "a.jpg": "Canon EOS R6 (1234)/Fotoğraflar/2026-11-22_10-00-00_Canon-EOS-R6-1234.jpg",
            "b.jpg": "Canon EOS R6 (5678)/Fotoğraflar/2026-11-22_10-01-00_Canon-EOS-R6-5678.jpg"})
    finally:
        e.close()


def t_esleme(mode):
    g = f"Cihaz adı öğrenme [{mode}]"
    e = Env("esleme")
    try:
        ex = mode == "exiftool"
        p = e.plan(ex)
        check_map(g, p, {"a.jpg": "realme 5i/Fotoğraflar/2021-01-01_10-00-00_realme-5i.jpg",
                         "b.jpg": "realme 5i/Fotoğraflar/2021-01-01_10-00-05_realme-5i.jpg"})   # hazır eşleştirme
        check(g, "benzer adlar sorulur", [["Samsung Galaxy A51", "Samsung SM-A515F"]], sorter.similar_device_names(p))
        sorter.save_aliases({**sorter.load_aliases(), "Samsung SM-A515F": "Samsung Galaxy A51"})   # kullanıcı: aynı
        p = e.plan(ex)
        check_map(g + " (birleştirildi)", p, {"c.jpg": "Samsung Galaxy A51/Fotoğraflar/2022-01-01_10-00-00_Samsung-Galaxy-A51.jpg"})
        check(g, "birleştirilince bir daha sorulmaz", [], sorter.similar_device_names(p))
        check(g, "raporda orijinal ad korunur", "Samsung SM-A515F",
              next(a.info.raw_device for a in p.actions if a.src.name == "c.jpg"))
        # 'aynı değil' cevabı da hatırlanır
        sorter.save_aliases({k: v for k, v in sorter.load_aliases().items() if k != "Samsung SM-A515F"},
                            {("Samsung Galaxy A51", "Samsung SM-A515F")})
        p = e.plan(ex)
        check(g, "'aynı değil' denince bir daha sorulmaz", [], sorter.similar_device_names(p))
        check_map(g + " (ayrı bırakıldı)", p, {"c.jpg": "Samsung SM-A515F/Fotoğraflar/2022-01-01_10-00-00_Samsung-SM-A515F.jpg"})
    finally:
        e.close()


def t_ekran(mode):
    g = f"Ekran görüntüleri [{mode}]"
    e = Env("ekran")
    try:
        ex = mode == "exiftool"
        p = e.plan(ex)
        E = "Ekran Görüntüleri/"
        check_map(g, p, {
            "IMG_1142.PNG": E + "Apple iPhone/2024-06-18_15-18-58_Apple-iPhone.png",          # EXIF: Screenshot
            "Ekran görüntüsü 2025-05-25 005223.png": E + "Windows PC/2025-05-25_00-52-23_Windows-PC.png",  # ad
            "RobloxScreenShot20250525_005219337.png": E + "Windows PC/2025-05-25_00-52-19_Windows-PC.png",
            "Screenshot_20210102-181538.jpg": E + "Android/2021-01-02_18-15-38_Android.jpg",
            "cv.png": "_Eksik Bilgi/Tarih ve Cihaz Yok/Fotoğraflar/cv.png",                     # ekran görüntüsü değil
            "iphone_foto.jpg": "Apple iPhone 14/Fotoğraflar/2024-06-18_15-00-00_Apple-iPhone-14.jpg",
        })
        check(g, "Apple iPhone ile Apple iPhone 14 için sorulur", [["Apple iPhone", "Apple iPhone 14"]],
              sorter.similar_device_names(p))
        sorter.save_aliases({**sorter.load_aliases(), "Apple iPhone": "Apple iPhone 14"})
        p = e.plan(ex)
        check_map(g + " (iPhone 14 ile birleştirildi)", p,
                  {"IMG_1142.PNG": E + "Apple iPhone 14/2024-06-18_15-18-58_Apple-iPhone-14.png"})
        check(g, "ekran görüntüsü sayısı", 4, p.counts()["ekran_goruntusu"])
    finally:
        e.close()


def t_modify(mode):
    g = f"Sadece ModifyDate olan fotoğraf [{mode}]"
    e = Env("modify")
    try:
        p = e.plan(mode == "exiftool")
        check_map(g, p, {"FNWY1029.JPG": "_Eksik Bilgi/Cihaz Yok/Fotoğraflar/2020-11-03_12-13-56.jpg"})
    finally:
        e.close()


def media_files(root: Path):
    return sorted(x.relative_to(root).as_posix() for x in root.rglob("*")
                  if x.is_file() and x.suffix.lower() in sorter.PHOTO_EXT | sorter.VIDEO_EXT)


def t_kopyalar(mode):
    g = f"Tekrar eden dosyalar [{mode}]"
    e = Env("temel")
    try:
        ex = mode == "exiftool"
        # aynı içerik: farklı adla aynı klasörde ve başka bir klasörde
        shutil.copyfile(e.src / "nikon/DSC_1.jpg", e.src / "nikon/DSC_1 (1).jpg")
        (e.src / "yedek").mkdir()
        shutil.copyfile(e.src / "nikon/DSC_1.jpg", e.src / "yedek/DSC_1.jpg")
        shutil.copyfile(e.src / "eksik/WhatsApp.jpg", e.src / "yedek/WhatsApp.jpg")
        p = e.plan(ex)
        N = "NIKON Z 6/Fotoğraflar/2026-11-20_09-59-00_NIKON-Z-6"
        check_map(g, p, {
            "nikon/DSC_1.jpg": N + ".jpg",                                   # ilki normal yerinde
            "nikon/DSC_1 (1).jpg": "_Kopyalar/" + N + "_01.jpg",            # kopyalar ayrı klasörde
            "yedek/DSC_1.jpg": "_Kopyalar/" + N + "_02.jpg",
            "yedek/WhatsApp.jpg": "_Kopyalar/_Eksik Bilgi/Tarih ve Cihaz Yok/Fotoğraflar/WhatsApp.jpg",
            "kart/IMG_2.jpg": "Canon EOS R6/Fotoğraflar/2026-11-20_10-00-00_Canon-EOS-R6_01.jpg",  # içerik farklı: kopya değil
        })
        check(g, "kopya sayısı", 3, p.counts()["kopya"])
        check(g, "raporda kopyası olduğu dosya", "DSC_1.jpg",
              next(a.dup_of.src.name for a in p.actions if a.src.name == "DSC_1 (1).jpg"))
        sorter.execute(p)
        check(g, "kopyalar silinmez, hepsi hedefte", 12, len(media_files(e.dst)))
        p2 = e.plan(ex)
        check(g, "tekrar çalıştırınca hepsi 'zaten var'", 12, sum(a.status == "zaten var" for a in p2.actions))
    finally:
        e.close()


def t_sadece_yeniler(mode):
    g = f"Düzenlenmiş klasöre sadece yenileri ekleme [{mode}]"
    e = Env("temel")
    try:
        ex = mode == "exiftool"
        sorter.execute(e.plan(ex))
        # kullanıcı hedefte bir dosyanın adını değiştirmiş olsun; yine de tanınmalı
        eski = e.dst / "NIKON Z 6/Fotoğraflar/2026-11-20_09-59-00_NIKON-Z-6.jpg"
        eski.rename(eski.with_name("en sevdiğim.jpg"))
        # kaynağa yeni bir fotoğraf (farklı içerik) eklenir
        shutil.copytree(FIX / "govde", e.src / "yeni")
        p = e.plan(ex)
        yeni = sorted(a.src.relative_to(p.source).as_posix() for a in p.actions if a.status == "bekliyor")
        check(g, "sadece yeni dosyalar işlenecek", ["yeni/a.jpg", "yeni/b.jpg"], yeni)
        check(g, "adı değiştirilmiş dosya içerikten tanınır", "zaten var",
              next(a.status for a in p.actions if a.src.name == "DSC_1.jpg"))
        check_map(g, p, {"yeni/a.jpg": "Canon EOS R6/Fotoğraflar/2026-11-22_10-00-00_Canon-EOS-R6.jpg"})
    finally:
        e.close()


def t_saat_kaydirma(mode):
    g = f"Cihaz başına saat kaydırma [{mode}]"
    e = Env("temel")
    try:
        p = e.plan(mode == "exiftool", sorter.Options(clock_offsets={"Canon EOS R6": 120, "NIKON Z 6": -30}))
        check_map(g, p, {
            "kart/IMG_11.jpg": "Canon EOS R6/Fotoğraflar/2026-11-20_12-05-00_Canon-EOS-R6.jpg",   # +2 saat
            "nikon/DSC_1.jpg": "NIKON Z 6/Fotoğraflar/2026-11-20_09-29-00_NIKON-Z-6.jpg",        # -30 dk
            "eksik/cihazsiz.jpg": "_Eksik Bilgi/Cihaz Yok/Fotoğraflar/2026-11-21_08-00-00.jpg",   # diğerleri aynı
        })
        check(g, "raporda not", "saat +2:00", next(a.note for a in p.actions if a.src.name == "IMG_11.jpg"))
    finally:
        e.close()


def t_geri_al(mode):
    g = f"Son işlemi geri alma [{mode}]"
    e = Env("temel")
    try:
        ex = mode == "exiftool"
        once = media_files(e.src)
        sorter.execute(e.plan(ex))
        check(g, "geri alınacak işlem görünür", ("copy", 9), (sorter.describe_last(e.dst)["mode"],
                                                              sorter.describe_last(e.dst)["count"]))
        r = sorter.undo_last(e.dst)
        check(g, "kopyalama geri alındı: 9 dosya silindi", 9, r["geri_alindi"])
        check(g, "hedefte medya kalmadı, kaynak aynı", ([], once), (media_files(e.dst), media_files(e.src)))
        check(g, "işlemin açtığı boş klasörler silindi", [], sorted(x.name for x in e.dst.iterdir()
                                                                   if x.is_dir() and x.name != sorter.JOURNAL_DIR))
        check(g, "ikinci kez geri alınacak işlem yok", None, sorter.describe_last(e.dst))
        # taşıma geri alma + sonradan değiştirilmiş dosyaya dokunmama
        p = e.plan(ex)
        sorter.execute(p, move=True)
        degisen = next(a.dest for a in p.actions if a.src.name == "WhatsApp.jpg")
        degisen.write_bytes(b"kullanici duzenledi")
        r = sorter.undo_last(e.dst)
        check(g, "taşıma geri alındı (değişen 1 dosya hariç)", (8, 1), (r["geri_alindi"], len(r["atlandi"])))
        check(g, "taşınan dosyalar eski yerinde", [x for x in once if x != "eksik/WhatsApp.jpg"], media_files(e.src))
        check(g, "değiştirilen dosya hedefte bırakıldı", b"kullanici duzenledi", degisen.read_bytes())
    finally:
        e.close()


def t_dil(mode):
    g = f"Dil ve klasör adları [{mode}]"
    e = Env("temel")
    try:
        ex = mode == "exiftool"
        p = e.plan(ex, sorter.Options(lang="en"))
        check_map(g + " (İngilizce, boş hedef)", p, {
            "nikon/DSC_1.jpg": "NIKON Z 6/Photos/2026-11-20_09-59-00_NIKON-Z-6.jpg",
            "eksik/WhatsApp.jpg": "_Missing Info/No Date or Device/Photos/WhatsApp.jpg"})
        rapor = sorter.execute(p)
        check(g, "İngilizce rapor başlığı", "Source;New location", rapor.read_text(encoding="utf-8-sig")[:19])
        # hedefte artık İngilizce klasörler var: Türkçe seçilse bile aynı klasörler kullanılmalı
        shutil.copytree(FIX / "govde", e.src / "yeni")
        p = e.plan(ex, sorter.Options(lang="tr"))
        check_map(g + " (hedefteki dil korunur)", p, {"yeni/a.jpg": "Canon EOS R6/Photos/2026-11-22_10-00-00_Canon-EOS-R6.jpg"})
        check(g, "öncekiler yine tanınır", 9, sum(a.status == "zaten var" for a in p.actions))
        check(g, "Türkçe not", "UTC → X", sorter.TEXT["tr"]["utc"].format(tz="X"))
    finally:
        e.close()


def t_video(mode):
    g = f"Videolar ve saat dilimi [{mode}]"
    if mode != "exiftool":
        skip(g, "videolar", "videolarda cihaz/saat dilimi için exiftool gerekir")
        return
    e = Env("video")
    try:
        p = e.plan(True)
        V = "Apple iPhone 14/Videolar/"
        if sorter._TF is None:
            skip(g, "tokyo.mov (GPS'ten saat dilimi)", "timezonefinder kurulu değil")
            gps = {"utc_gpssiz.mov": V + "2026-11-20_10-00-00_Apple-iPhone-14.mov"}
        else:
            gps = {"tokyo.mov": V + "2026-11-20_10-00-00_Apple-iPhone-14_01.mov",      # UTC 01:00 + GPS Tokyo (+9)
                   "utc_gpssiz.mov": V + "2026-11-20_10-00-00_Apple-iPhone-14_02.mov"}  # UTC 07:00 + İstanbul (+3)
        check_map(g, p, {
            "iphone.mov": V + "2026-11-20_18-30-00_Apple-iPhone-14.mov",       # saat dilimi yazılı: dokunulmaz
            **gps,
            "sony/C0001.mp4": "Sony ILCE-7M3/Videolar/2026-11-20_13-01-00_Sony-ILCE-7M3.mp4",  # fotoğraflara göre UTC
            "bilgisiz.mp4": "_Eksik Bilgi/Tarih ve Cihaz Yok/Videolar/bilgisiz.mp4",
        })
        check(g, "Sony için tahmin: UTC (fotoğraflarla karşılaştırıldı)",
              (True, "aynı cihazın fotoğraflarıyla karşılaştırıldı"),
              sorter.guess_video_utc(p, "Sony ILCE-7M3", sorter.utc_video_groups(p)["Sony ILCE-7M3"], "Europe/Istanbul"))
        p = e.plan(True, sorter.Options(video_utc={"Sony ILCE-7M3": False, "Apple iPhone 14": True}))
        check_map(g + " (kullanıcı 'yerel' dedi)", p,
                  {"sony/C0001.mp4": "Sony ILCE-7M3/Videolar/2026-11-20_10-01-00_Sony-ILCE-7M3.mp4"})
        p = e.plan(True, sorter.Options(tz_name="Europe/London"))
        check_map(g + " (konum Londra seçildi)", p,
                  {"utc_gpssiz.mov": V + "2026-11-20_07-00-00_Apple-iPhone-14.mov"})
    finally:
        e.close()


def main():
    t0 = time.time()
    modes = ["python"] + (["exiftool"] if sorter.EXIFTOOL else [])
    for mode in modes:
        for t in (t_temel, t_kopyala_tekrar, t_kopyalar, t_sadece_yeniler, t_saat_kaydirma, t_geri_al,
                  t_govde, t_esleme, t_ekran, t_modify, t_dil, t_video):
            try:
                t(mode)
            except Exception as ex:  # beklenmeyen hata da bir test sonucu
                results.append((t.__name__ + f" [{mode}]", "çalışırken hata", "-", repr(ex), "KALDI"))
    if not sorter.EXIFTOOL:
        skip("exiftool modu", "tüm senaryolar", "exiftool bulunamadı")
    passed = sum(r[4] == "GEÇTİ" for r in results)
    failed = sum(r[4] == "KALDI" for r in results)
    lines = [f"# Test raporu", "", f"{passed} geçti, {failed} kaldı, "
             f"{sum(r[4].startswith('ATLANDI') for r in results)} atlandı. Süre {time.time() - t0:.1f} sn. "
             f"exiftool: {sorter.EXIFTOOL or 'yok'}", "",
             "| Durum | Grup | Durum / dosya | Beklenen | Gerçek |", "|---|---|---|---|---|"]
    for g, c, exp, act, st in results:
        mark = "✅" if st == "GEÇTİ" else "❌" if st == "KALDI" else "⏭"
        lines.append(f"| {mark} {st} | {g} | {c} | `{exp}` | `{act}` |")
    (HERE / "test_raporu.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for g, c, exp, act, st in results:
        if st != "GEÇTİ":
            print(f"{st}: {g} / {c}\n   beklenen: {exp}\n   gerçek  : {act}")
    print(lines[2])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
