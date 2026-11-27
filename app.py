# -*- coding: utf-8 -*-
"""Foto Düzenleyici: basit Windows arayüzü (tkinter). Metinler lang.py'den gelir (Türkçe / İngilizce)."""
from __future__ import annotations

import os
import queue
import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import lang
import sorter
from lang import t


def APP() -> str:
    return t("app_title")


WHY_KEYS = {"aynı cihazın fotoğraflarıyla karşılaştırıldı": "why_photos", "markaya göre tahmin": "why_brand"}
SKIP_EN = {"hedefte artık yok": "no longer in target",
           "sonradan değiştirilmiş, dokunulmadı": "changed afterwards, left alone",
           "eski yerinde aynı adlı dosya var": "a file with the same name is already at the old place",
           "asıl dosya bulunamadı, kopya silinmedi": "original not found, copy kept"}


def parse_offset(text: str):
    """'+2' -> 120, '-1:30' -> -90, '+0:45' -> 45, '1,5' -> 90, '' -> 0. Anlaşılmazsa None."""
    v = text.strip().replace(" ", "").replace(",", ".")
    if not v:
        return 0
    m = re.fullmatch(r"([+-]?)(\d{1,3})(?::(\d{2}))?", v)
    if m:
        if m.group(3) and int(m.group(3)) >= 60:
            return None
        mins = int(m.group(2)) * 60 + int(m.group(3) or 0)
    else:
        m = re.fullmatch(r"([+-]?)(\d{1,3}\.\d+)", v)
        if not m:
            return None
        mins = round(float(m.group(2)) * 60)
    return -mins if m.group(1) == "-" else mins


def format_offset(mins: int) -> str:
    if not mins:
        return ""
    h, m = divmod(abs(mins), 60)
    return ("-" if mins < 0 else "+") + str(h) + (f":{m:02d}" if m else "")


def timezone_list():
    common = ["Europe/Istanbul", "Europe/London", "Europe/Berlin", "Europe/Paris", "Europe/Moscow",
              "Asia/Dubai", "Asia/Tokyo", "America/New_York", "America/Los_Angeles", "UTC"]
    if sorter.HAS_ZONEINFO:
        rest = sorted(z for z in sorter.available_timezones() if "/" in z and z not in common)
        return common + rest
    return common


def device_counts(plan) -> dict:
    counts: dict = {}
    for a in plan.actions:
        if a.info.device:
            counts[a.info.device] = counts.get(a.info.device, 0) + 1
    return counts


class QuestionsDialog(tk.Toplevel):
    """Taramadan sonra gerekirse sorulan sorular: video saatleri, konum, aynı model ayırma, benzer adlar."""

    def __init__(self, master, plan: sorter.Plan, opts: sorter.Options):
        super().__init__(master)
        self.title(t("q_title"))
        self.transient(master)
        self.resizable(True, False)
        self.result = None
        self.plan, self.opts = plan, opts
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        row = 0
        bold = ("Segoe UI", 11, "bold")

        groups = sorter.utc_video_groups(plan)
        self.utc_vars = {}
        self.tz_var = tk.StringVar(value=opts.tz_name)
        if groups:
            ttk.Label(body, text=t("q_video"), font=bold).grid(row=row, column=0, sticky="w", columnspan=3)
            row += 1
            ttk.Label(body, wraplength=640, justify="left", text=t("q_video_help")
                      ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 6))
            row += 1
            choices = [t("q_utc"), t("q_local")]
            for dev, vids in groups.items():
                guess, why = sorter.guess_video_utc(plan, dev, vids, opts.tz_name)
                current = opts.video_utc.get(dev, guess)
                var = tk.StringVar(value=choices[0] if current else choices[1])
                self.utc_vars[dev] = (var, choices[0])
                ex = vids[0]
                conv = sorter.to_local(ex.info.date, sorter.tz_for(ex, opts.tz_name))
                ttk.Label(body, text=t("q_n_videos", dev=dev, n=len(vids))).grid(row=row, column=0, sticky="w")
                ttk.Combobox(body, textvariable=var, values=choices, state="readonly", width=34
                             ).grid(row=row, column=1, sticky="w", padx=6)
                row += 1
                ttk.Label(body, foreground="#666666", text=t(
                    "q_example", name=ex.src.name, conv=f"{conv:%d.%m %H:%M}", raw=f"{ex.info.date:%d.%m %H:%M}",
                    why=t(WHY_KEYS[why]) if why in WHY_KEYS else why)
                ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 4))
                row += 1

            no_gps = sum(1 for v in groups.values() for a in v if a.info.lat is None)
            if no_gps:
                ttk.Label(body, text=t("q_where", n=no_gps)).grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 0))
                row += 1
                ttk.Combobox(body, textvariable=self.tz_var, values=timezone_list(), width=34
                             ).grid(row=row, column=0, sticky="w")
                ttk.Label(body, foreground="#666666", text=t("q_where_help")).grid(row=row, column=1, sticky="w", padx=6)
                row += 1

        multi = sorter.multi_body_models(plan)
        self.split_vars = {}
        if multi:
            ttk.Separator(body).grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)
            row += 1
            ttk.Label(body, text=t("q_bodies"), font=bold).grid(row=row, column=0, sticky="w", columnspan=3)
            row += 1
            for dev, serials in multi.items():
                desc = ", ".join(t("q_body_desc", s=s[-4:], n=n) for s, n in serials.items())
                var = tk.BooleanVar(value=dev in opts.split_models)
                self.split_vars[dev] = var
                ttk.Checkbutton(body, variable=var, text=t("q_body_line", dev=dev, n=len(serials), desc=desc)
                                ).grid(row=row, column=0, columnspan=3, sticky="w")
                row += 1
            ttk.Label(body, foreground="#666666", wraplength=640, justify="left", text=t("q_bodies_help")
                      ).grid(row=row, column=0, columnspan=3, sticky="w")
            row += 1

        similar = sorter.similar_device_names(plan)
        self.merge_vars = []
        if similar:
            ttk.Separator(body).grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)
            row += 1
            ttk.Label(body, text=t("q_similar"), font=bold).grid(row=row, column=0, sticky="w", columnspan=3)
            row += 1
            ttk.Label(body, foreground="#666666", wraplength=640, justify="left", text=t("q_similar_help")
                      ).grid(row=row, column=0, columnspan=3, sticky="w")
            row += 1
            counts = device_counts(plan)
            for names in similar:
                # "Apple iPhone" (modelsiz, ör. ekran görüntüsü) + tek bir "Apple iPhone 14" -> büyük ihtimalle aynı
                generic = [n for n in names if any(o != n and o.startswith(n + " ") for o in names)]
                chk = tk.BooleanVar(value=len(names) == 2 and len(generic) == 1)
                main = max(names, key=lambda n: (n not in generic, counts.get(n, 0)))
                target = tk.StringVar(value=main)
                desc = ", ".join(f"{n} ({counts.get(n, 0)})" for n in names)
                ttk.Checkbutton(body, variable=chk, text=t("q_same", desc=desc)
                                ).grid(row=row, column=0, columnspan=2, sticky="w")
                ttk.Combobox(body, textvariable=target, values=names, width=24).grid(row=row, column=2, sticky="w")
                self.merge_vars.append((names, chk, target))
                row += 1

        btns = ttk.Frame(body)
        btns.grid(row=row, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(btns, text=t("ok"), command=self._ok).pack(side="right")
        self.bind("<Return>", lambda e: self._ok())
        self.protocol("WM_DELETE_WINDOW", self._ok)
        self.grab_set()
        self.wait_window(self)

    def _ok(self):
        tz = self.tz_var.get().strip() or sorter.DEFAULT_TZ
        if sorter.HAS_ZONEINFO and tz not in sorter.available_timezones():
            messagebox.showwarning(APP(), t("bad_tz", tz=tz), parent=self)
            return
        self.opts.tz_name = tz
        for dev, (var, utc_label) in self.utc_vars.items():
            self.opts.video_utc[dev] = var.get() == utc_label
        self.opts.split_models = {d for d, v in self.split_vars.items() if v.get()}
        merges = [(names, tv.get().strip()) for names, c, tv in self.merge_vars if c.get() and tv.get().strip()]
        separate = {tuple(names) for names, c, tv in self.merge_vars if not c.get()}
        if merges or separate:
            aliases = sorter.load_aliases()
            for names, target in merges:
                for n in names:
                    if n != target:
                        aliases[n] = target
                aliases.pop(target, None)
            try:
                sorter.save_aliases(aliases, sorter.load_separate() | separate)
            except OSError as e:
                messagebox.showwarning(APP(), t("save_fail", e=e), parent=self)
            sorter.apply_aliases(self.plan, aliases)
        self.result = self.opts
        self.destroy()

    @staticmethod
    def needed(plan) -> bool:
        return bool(sorter.utc_video_groups(plan) or sorter.multi_body_models(plan)
                    or sorter.similar_device_names(plan))


class DevicesDialog(tk.Toplevel):
    """Öğrenilmiş cihaz adı eşleştirmelerini görme ve düzeltme."""

    def __init__(self, master, plan):
        super().__init__(master)
        self.title(t("d_title"))
        self.transient(master)
        self.changed = False
        self.aliases = sorter.load_aliases()
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(body, wraplength=560, justify="left", text=t("d_help")
                  ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        raw = sorter.raw_device_counts(plan) if plan else {}
        names = sorted(set(raw) | set(self.aliases), key=str.lower)
        choices = sorted({sorter.resolve_alias(n, self.aliases) for n in names} | set(names), key=str.lower)
        self.vars = {}
        for i, n in enumerate(names, 1):
            ttk.Label(body, text=t("d_count", name=n, n=raw.get(n, 0))).grid(row=i, column=0, sticky="w")
            ttk.Label(body, text="→").grid(row=i, column=1, padx=6)
            v = tk.StringVar(value=sorter.resolve_alias(n, self.aliases))
            ttk.Combobox(body, textvariable=v, values=choices, width=28).grid(row=i, column=2, sticky="w", pady=1)
            self.vars[n] = v
        if not names:
            ttk.Label(body, text=t("d_empty")).grid(row=1, column=0, sticky="w")
        btns = ttk.Frame(body)
        btns.grid(row=len(names) + 2, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(btns, text=t("cancel"), command=self.destroy).pack(side="right")
        ttk.Button(btns, text=t("save"), command=self._save).pack(side="right", padx=6)
        self.grab_set()
        self.wait_window(self)

    def _save(self):
        new = {}
        for n, v in self.vars.items():
            target = sorter.clean_name(v.get())
            if target and target != n:
                new[n] = target
        for target in list(new.values()):      # hedef adın kendisi başka bir ada gitmesin
            new.pop(target, None)
        try:
            sorter.save_aliases(new)
        except OSError as e:
            messagebox.showwarning(APP(), t("save_fail", e=e), parent=self)
            return
        self.aliases = new
        self.changed = True
        self.destroy()


class ClockDialog(tk.Toplevel):
    """Cihaz başına saat düzeltme (makinenin saati yanlış ayarlıysa). Sadece bu çalıştırma için."""

    def __init__(self, master, plan, opts: sorter.Options):
        super().__init__(master)
        self.title(t("c_title"))
        self.transient(master)
        self.changed = False
        self.opts = opts
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(body, wraplength=520, justify="left", text=t("c_help")
                  ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        counts = device_counts(plan)
        self.vars = {}
        for i, dev in enumerate(sorted(counts, key=str.lower), 1):
            ttk.Label(body, text=t("d_count", name=dev, n=counts[dev])).grid(row=i, column=0, sticky="w")
            v = tk.StringVar(value=format_offset(opts.clock_offsets.get(dev, 0)))
            ttk.Entry(body, textvariable=v, width=10).grid(row=i, column=1, sticky="w", padx=6, pady=1)
            self.vars[dev] = v
        if not counts:
            ttk.Label(body, text=t("d_empty")).grid(row=1, column=0, sticky="w")
        btns = ttk.Frame(body)
        btns.grid(row=len(counts) + 2, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text=t("cancel"), command=self.destroy).pack(side="right")
        ttk.Button(btns, text=t("ok"), command=self._ok).pack(side="right", padx=6)
        self.grab_set()
        self.wait_window(self)

    def _ok(self):
        new = {}
        for dev, v in self.vars.items():
            mins = parse_offset(v.get())
            if mins is None:
                messagebox.showwarning(APP(), t("c_bad", v=v.get()), parent=self)
                return
            if mins:
                new[dev] = mins
        self.changed = new != self.opts.clock_offsets
        self.opts.clock_offsets = new
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.geometry("1100x640")
        self.minsize(820, 480)
        self.q: queue.Queue = queue.Queue()
        self.plan: sorter.Plan | None = None
        self.plan_key = None
        self.opts = sorter.Options(lang=lang.current())
        self.cancel_flag = False
        self.busy = False
        self.src_var, self.dst_var = tk.StringVar(), tk.StringVar()
        self.move_var = tk.BooleanVar(value=False)
        self.et_var = tk.BooleanVar(value=bool(sorter.EXIFTOOL))
        self.status_text = None          # (anahtar, parametreler): dil değişince yeniden yazmak için
        self._build()
        self.after(100, self._poll)

    # ------------------------------------------------------------ arayüz
    def _build(self):
        for w in self.winfo_children():
            if not isinstance(w, tk.Toplevel):
                w.destroy()
        self.title(APP())
        pad = {"padx": 8, "pady": 4}
        top = ttk.Frame(self)
        top.pack(fill="x", **pad)
        for row, (label, var) in enumerate(((t("src_label"), self.src_var), (t("dst_label"), self.dst_var))):
            ttk.Label(top, text=label).grid(row=row, column=0, sticky="w")
            ttk.Entry(top, textvariable=var).grid(row=row, column=1, sticky="ew", padx=6)
            ttk.Button(top, text=t("pick"), command=lambda v=var: self._pick(v)).grid(row=row, column=2)
        names = {lang.STRINGS[c]["lang_name"]: c for c in lang.STRINGS}
        self.lang_var = tk.StringVar(value=lang.STRINGS[lang.current()]["lang_name"])
        ttk.Label(top, text=t("language") + ":").grid(row=0, column=3, sticky="e", padx=(16, 4))
        cb = ttk.Combobox(top, textvariable=self.lang_var, values=list(names), state="readonly", width=10)
        cb.grid(row=0, column=4, sticky="w")
        cb.bind("<<ComboboxSelected>>", lambda e: self._change_lang(names[self.lang_var.get()]))
        self.lang_cb = cb
        top.columnconfigure(1, weight=1)

        opts = ttk.Frame(self)
        opts.pack(fill="x", **pad)
        ttk.Radiobutton(opts, text=t("copy"), variable=self.move_var, value=False).pack(side="left")
        ttk.Radiobutton(opts, text=t("move"), variable=self.move_var, value=True).pack(side="left", padx=12)
        ttk.Checkbutton(opts, text=t("use_exiftool"), variable=self.et_var,
                        state="normal" if sorter.EXIFTOOL else "disabled").pack(side="left", padx=12)

        bar = ttk.Frame(self)
        bar.pack(fill="x", **pad)
        self.prev_btn = ttk.Button(bar, text=t("preview"), command=self._preview)
        self.dev_btn = ttk.Button(bar, text=t("devices"), command=self._devices)
        self.ask_btn = ttk.Button(bar, text=t("choices"), command=self._reask)
        self.clock_btn = ttk.Button(bar, text=t("clock"), command=self._clock)
        self.run_btn = ttk.Button(bar, text=t("run"), command=self._run)
        self.stop_btn = ttk.Button(bar, text=t("stop"), command=self._cancel)
        for b in (self.prev_btn, self.dev_btn, self.ask_btn, self.clock_btn, self.run_btn, self.stop_btn):
            b.pack(side="left", padx=(0, 6))

        mid = ttk.Frame(self)
        mid.pack(fill="both", expand=True, **pad)
        cols = ("src", "dest", "info", "status")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings")
        for c, w in (("src", 240), ("dest", 430), ("info", 260), ("status", 100)):
            self.tree.heading(c, text=t("col_" + c))
            self.tree.column(c, width=w, anchor="w")
        ys = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ys.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")
        self.tree.tag_configure("missing", background="#fff4d6")
        self.tree.tag_configure("dup", background="#e8eefc")
        self.tree.tag_configure("done", foreground="#777777")

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", **pad)
        self.pb = ttk.Progressbar(bottom, mode="determinate")
        self.pb.pack(fill="x")
        row2 = ttk.Frame(bottom)
        row2.pack(fill="x", pady=(4, 0))
        self.undo_btn = ttk.Button(row2, text=t("undo"), command=self._undo)
        self.undo_btn.pack(side="right")
        self.status = ttk.Label(row2, text="", wraplength=900, justify="left")
        self.status.pack(side="left", fill="x", expand=True)
        if sorter._TF is None:
            ttk.Label(bottom, foreground="#b45309", text=t("tf_missing")).pack(fill="x")
        if not sorter.EXIFTOOL:
            ttk.Label(bottom, foreground="#666666", text=t("et_missing")).pack(fill="x")
        self._show_status()
        self._set_busy(self.busy)
        if self.plan:
            self._fill(self.plan)

    def _change_lang(self, code):
        if code == lang.current():
            return
        lang.set_lang(code)
        self.opts.lang = code
        self._build()
        if self.plan and not self.busy:
            # notlar ve rapor dili değişsin diye planı yeni dille yeniden hesapla
            self._finalize(self.plan, then_run=False)

    def _say(self, key=None, **kw):
        self.status_text = (key, kw) if key else None
        self._show_status()

    def _show_status(self):
        if self.status_text is None:
            self.status.config(text=t("start_hint"))
            return
        key, kw = self.status_text
        if key == "_raw":
            self.status.config(text=kw["text"])
        elif key == "_summary":
            self.status.config(text=self._summary_text(kw["plan"]))
        else:
            self.status.config(text=t(key, **kw).replace("\n", "  "))

    def _pick(self, var):
        d = filedialog.askdirectory(initialdir=var.get() or os.path.expanduser("~"))
        if d:
            var.set(os.path.normpath(d))

    def _set_busy(self, busy: bool):
        self.busy = busy
        st = "disabled" if busy else "normal"
        for b in (self.prev_btn, self.run_btn, self.dev_btn, self.undo_btn):
            b.config(state=st)
        self.lang_cb.config(state="disabled" if busy else "readonly")
        for b in (self.ask_btn, self.clock_btn):
            b.config(state="disabled" if busy or not self.plan else "normal")
        self.stop_btn.config(state="normal" if busy else "disabled")

    def _cancel(self):
        self.cancel_flag = True

    def _bg(self, fn, *args):
        def work():
            try:
                self.q.put(fn(*args))
            except Exception as e:
                self.q.put(("error", str(e)))
        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------ akış
    def _paths(self, need_src=True):
        src, dst = self.src_var.get().strip(), self.dst_var.get().strip()
        if need_src and (not src or not Path(src).is_dir()):
            messagebox.showwarning(APP(), t("need_src"))
            return None
        if not dst:
            messagebox.showwarning(APP(), t("need_dst"))
            return None
        d = Path(dst).resolve()
        if not need_src:
            return None, d
        s = Path(src).resolve()
        if s == d:
            messagebox.showwarning(APP(), t("same_dirs"))
            return None
        return s, d

    def _preview(self, then_run=False):
        p = self._paths()
        if not p:
            return
        self.cancel_flag = False
        self.plan = None
        self._set_busy(True)
        self.tree.delete(*self.tree.get_children())
        self._say("reading")
        use_et = self.et_var.get()

        def scan():
            plan = sorter.scan(*p, use_exiftool=use_et, progress=self._progress,
                               cancel=lambda: self.cancel_flag)
            return ("scanned", plan, p, then_run)
        self._bg(scan)

    def _reask(self):
        if self.plan:
            self._ask_and_finalize(self.plan, then_run=False, force=True)

    def _devices(self):
        d = DevicesDialog(self, self.plan)
        if d.changed and self.plan:
            sorter.apply_aliases(self.plan, d.aliases)
            self._ask_and_finalize(self.plan, then_run=False, force=False)

    def _clock(self):
        if not self.plan:
            messagebox.showinfo(APP(), t("c_first"))
            return
        d = ClockDialog(self, self.plan, self.opts)
        if d.changed:
            self._finalize(self.plan, then_run=False)

    def _ask_and_finalize(self, plan, then_run, force=False):
        if force or QuestionsDialog.needed(plan):
            # varsayılanları önce tahminle doldur, sonra kullanıcıya göster
            for dev, vids in sorter.utc_video_groups(plan).items():
                self.opts.video_utc.setdefault(dev, sorter.guess_video_utc(plan, dev, vids, self.opts.tz_name)[0])
            QuestionsDialog(self, plan, self.opts)
        self._finalize(plan, then_run)

    def _finalize(self, plan, then_run):
        for dev, vids in sorter.utc_video_groups(plan).items():   # birleştirmeden sonra yeni adlar için
            self.opts.video_utc.setdefault(dev, sorter.guess_video_utc(plan, dev, vids, self.opts.tz_name)[0])
        self.opts.lang = lang.current()
        self._set_busy(True)
        self._say("naming")
        self._bg(lambda: ("plan", sorter.finalize(plan, self.opts), then_run))

    def _run(self):
        p = self._paths()
        if not p:
            return
        if self.plan is None or self.plan_key != p:
            self._preview(then_run=True)
            return
        self._confirm_and_execute()

    def _confirm_and_execute(self):
        todo = sum(1 for a in self.plan.actions if a.status == "bekliyor")
        if todo == 0:
            messagebox.showinfo(APP(), t("nothing_new"))
            return
        move = self.move_var.get()
        if not messagebox.askyesno(APP(), t("confirm_move" if move else "confirm_copy", n=todo),
                                   icon="warning" if move else "question"):
            return
        self.cancel_flag = False
        self._set_busy(True)
        plan = self.plan
        self._bg(lambda: ("done", plan, sorter.execute(plan, move=move, progress=self._progress,
                                                       cancel=lambda: self.cancel_flag)))

    def _undo(self):
        p = self._paths(need_src=False)
        if not p:
            return
        target = p[1]
        try:
            last = sorter.describe_last(target)
        except (OSError, ValueError, KeyError) as e:
            messagebox.showerror(APP(), t("error", e=e))
            return
        if not last:
            messagebox.showinfo(APP(), t("u_none"))
            return
        key = "u_confirm_move" if last["mode"] == "move" else "u_confirm_copy"
        if not messagebox.askyesno(APP(), t(key, time=last["time"], n=last["count"]), icon="warning"):
            return
        self.plan = None
        self.tree.delete(*self.tree.get_children())
        self._set_busy(True)
        self._say("u_running")
        self._bg(lambda: ("undone", sorter.undo_last(target, progress=self._progress)))

    def _progress(self, i, n, name):
        self.q.put(("progress", i, n, name))

    # ------------------------------------------------------------ olaylar
    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                getattr(self, "_on_" + msg[0])(*msg[1:])
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _on_progress(self, i, n, name):
        self.pb.config(maximum=max(n, 1), value=i)
        self._say("_raw", text=f"{i} / {n}  {name}")

    def _on_error(self, text):
        self._set_busy(False)
        self._say("error", e=text)
        messagebox.showerror(APP(), t("error", e=text))

    def _on_scanned(self, plan, key, then_run):
        self._set_busy(False)
        if self.cancel_flag:
            self._say("stopped")
            return
        self.plan_key = key
        self._ask_and_finalize(plan, then_run)

    def _summary_text(self, plan) -> str:
        c = plan.counts()
        n = max(c["toplam"], 1)
        text = t("summary", **c) + " " + t("speed", s=plan.scan_seconds, ms=plan.scan_seconds / n * 1000,
                                           et=t("on") if plan.used_exiftool else t("off"))
        if plan.folder_lang != lang.current():
            text += " " + t("folder_lang_kept", lang=lang.STRINGS[plan.folder_lang]["lang_name"])
        return text

    def _on_plan(self, plan, then_run):
        self.plan = plan
        self._set_busy(False)
        self._fill(plan)
        self._say("_summary", plan=plan)
        if then_run:
            self._confirm_and_execute()

    def _on_done(self, plan, report):
        self._fill(plan)
        ok = sum(1 for a in plan.actions if a.status in ("kopyalandı", "taşındı"))
        err = sum(1 for a in plan.actions if a.status.startswith("hata"))
        self.plan = None
        self._set_busy(False)
        self._say("done", ok=ok, err=err, report=report)
        if messagebox.askyesno(APP(), t("done", ok=ok, err=err, report=report) + "\n\n" + t("open_target")):
            try:
                os.startfile(plan.target)  # type: ignore[attr-defined]
            except Exception:
                pass

    def _on_undone(self, res):
        self._set_busy(False)
        if res.get("yok"):
            self._say("u_none")
            messagebox.showinfo(APP(), t("u_none"))
            return
        self._say("u_done", n=res["geri_alindi"])
        msg = t("u_done", n=res["geri_alindi"])
        skipped = res["atlandi"]
        if skipped:
            en = lang.current() == "en"
            lines = [f"{Path(f).name}: {SKIP_EN.get(r, r) if en else r}" for f, r in skipped[:15]]
            if len(skipped) > 15:
                lines.append("...")
            msg += "\n\n" + t("u_skipped", n=len(skipped)) + "\n" + "\n".join(lines)
        messagebox.showinfo(APP(), msg)

    def _fill(self, plan):
        self.tree.delete(*self.tree.get_children())
        for a in plan.actions:
            try:
                src = str(a.src.relative_to(plan.source))
            except ValueError:
                src = str(a.src)
            try:
                dest = str(a.dest.relative_to(plan.target)) if a.dest else ""
            except ValueError:
                dest = str(a.dest)
            info = (a.date.strftime("%Y-%m-%d %H:%M:%S") if a.date else t("no_date")) + " / " + \
                   (a.device or t("no_device"))
            if a.note:
                info += f"  ({a.note})"
            tags = ("done",) if a.status != "bekliyor" else ("dup",) if a.dup_of is not None \
                else ("missing",) if not (a.date and a.device) else ()
            self.tree.insert("", "end", values=(src, dest, info, sorter.status_text(a.status, lang.current())),
                             tags=tags)


if __name__ == "__main__":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App().mainloop()
