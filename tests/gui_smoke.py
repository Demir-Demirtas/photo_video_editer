# -*- coding: utf-8 -*-
"""Arayüz duman testi: pencereyi açar, önizler, saat düzeltir, dili değiştirir, başlatır, geri alır.
Çalıştırma (Linux): xvfb-run python3 tests/gui_smoke.py   Windows'ta: python tests\\gui_smoke.py"""
import os, shutil, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
tmp = Path(tempfile.mkdtemp(prefix="gui_smoke_"))
os.environ["APPDATA"] = str(tmp / "appdata")

import tkinter.messagebox as mb  # noqa: E402
import app, lang, sorter  # noqa: E402

ok = True
def check(cond, label):
    global ok
    print(("GEÇTİ " if cond else "HATA  ") + label)
    ok &= bool(cond)

answers = []
mb.askyesno = lambda *a, **k: (answers.append(a[1]), True)[1]
mb.showinfo = lambda *a, **k: answers.append(a[1])
mb.showwarning = lambda *a, **k: answers.append("UYARI " + a[1])
mb.showerror = lambda *a, **k: answers.append("HATA " + a[1])
app.QuestionsDialog.needed = staticmethod(lambda plan: False)
app.os.startfile = lambda p: None

src = tmp / "kaynak"; dst = tmp / "hedef"
shutil.copytree(HERE / "fixtures" / "temel", src)
N_SRC = sum(1 for p in src.rglob("*") if p.is_file())
lang.set_lang("tr")
w = app.App()

def pump(cond, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        w.update()
        if cond():
            return True
        time.sleep(0.02)
    return False

w.src_var.set(str(src)); w.dst_var.set(str(dst))
w._preview()
check(pump(lambda: w.plan is not None and not w.busy), "önizleme bitti")
check("dosya:" in w.status.cget("text") and "kopya" in w.status.cget("text"), "özet Türkçe: " + w.status.cget("text")[:70])
check(w.prev_btn.cget("text") == "1) Önizle", "düğme Türkçe")
dev = sorted(app.device_counts(w.plan))[0]

# saat düzeltme penceresi: ilk cihaza +2 yaz
def fill_clock():
    d = [c for c in w.winfo_children() if isinstance(c, app.ClockDialog)][0]
    d.vars[dev].set("+2")
    d._ok()
w.after(300, fill_clock)
w._clock()
check(w.opts.clock_offsets == {dev: 120}, f"saat düzeltme kaydedildi ({dev}: +2 -> 120 dk)")
check(pump(lambda: not w.busy), "yeniden hesaplandı")
check(any("+2" in a.note for a in w.plan.actions if a.device == dev), "not 'saat +2' gösteriyor")

# dil değiştir
w.lang_var.set("English"); w._change_lang("en")
check(pump(lambda: not w.busy), "İngilizce yeniden hesaplandı")
check(w.prev_btn.cget("text") == "1) Preview" and w.undo_btn.cget("text") == "Undo last run", "düğmeler İngilizce")
check("files:" in w.status.cget("text"), "özet İngilizce: " + w.status.cget("text")[:70])
check(w.plan.lang == "en" and w.plan.folder_lang == "en", "yeni hedefte klasörler İngilizce")
row = w.tree.item(w.tree.get_children()[0])["values"]
check(row[3] == "pending", f"durum sütunu İngilizce ({row[3]})")

# başlat
w._run()
check(pump(lambda: w.plan is None and not w.busy), "kopyalama bitti")
check((dst / "Photos").is_dir() or any(p.name == "Photos" for p in dst.rglob("*")), "Photos klasörü oluştu")
check(any(p.name.startswith("report_") for p in dst.iterdir()), "report_*.csv yazıldı")
n_files = sum(1 for p in dst.rglob("*") if p.is_file() and sorter.JOURNAL_DIR not in p.parts and not p.suffix == ".csv")
check(n_files > 0, f"{n_files} dosya kopyalandı")

# geri al
w._undo()
check(pump(lambda: not w.busy), "geri alma bitti")
left = sum(1 for p in dst.rglob("*") if p.is_file() and sorter.JOURNAL_DIR not in p.parts and not p.suffix == ".csv")
check(left == 0, f"geri almadan sonra hedefte medya dosyası kalmadı ({left})")
check(any("undone" in str(a) for a in answers), "geri alma mesajı İngilizce")
check(sum(1 for p in src.rglob("*") if p.is_file()) == N_SRC, "kaynak dosyalar yerinde")

# saat ayrıştırma
P = app.parse_offset
check([P("+2"), P("-1:30"), P("+0:45"), P("1,5"), P(""), P("abc"), P("1:75")] == [120, -90, 45, 90, 0, None, None],
      "saat yazımı ayrıştırma")

# soru penceresi ve cihaz adları penceresi iki dilde açılıp kapanabiliyor mu
vplan = sorter.finalize(sorter.scan(HERE / "fixtures" / "video", tmp / "vhedef", use_exiftool=bool(sorter.EXIFTOOL)),
                        sorter.Options())
for code in ("tr", "en"):
    lang.set_lang(code)
    def close_q():
        for c in w.winfo_children():
            if isinstance(c, (app.QuestionsDialog, app.DevicesDialog)):
                (c._ok if isinstance(c, app.QuestionsDialog) else c.destroy)()
    w.after(300, close_q)
    try:
        app.QuestionsDialog(w, vplan, sorter.Options())
        w.after(300, close_q)
        app.DevicesDialog(w, vplan)
        check(True, f"soru ve cihaz pencereleri açıldı ({code})")
    except Exception as e:
        check(False, f"pencere hatası ({code}): {e!r}")
w.destroy()
lang.set_lang("tr")
shutil.rmtree(tmp, ignore_errors=True)
print("SONUÇ:", "hepsi geçti" if ok else "HATA VAR")
sys.exit(0 if ok else 1)
