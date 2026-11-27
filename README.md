# Foto Düzenleyici / Photo Organizer

Birden fazla fotoğraf makinesinden ve telefondan gelen fotoğraf ve videoları **cihaza**, **türe** ve
**çekim zamanına** göre düzenleyen basit bir Windows programı.

```
Hedef/
  Canon EOS R6/Fotoğraflar/2026-11-20_10-00-00_Canon-EOS-R6.jpg
  Canon EOS R6/Videolar/...
  Apple iPhone 14/Fotoğraflar/...
  Ekran Görüntüleri/<Cihaz>/...
  _Eksik Bilgi/...        (tarihi veya cihazı okunamayanlar)
  _Kopyalar/...           (içeriği birebir aynı olanlar; hiçbir şey silinmez)
```

## İndir ve kur

1. Sağdaki **Releases** bölümünden en son sürümün `FotoDuzenleyici_Kurulum.exe` dosyasını indir.
2. Çift tıkla. Python gerekmez, yönetici izni istemez.
   Windows "Bilgisayarınız korundu" uyarısı gösterirse **Ek bilgi → Yine de çalıştır**'a bas
   (program dijital olarak imzalı olmadığı için bu uyarı çıkar).
3. Başlat menüsünden **Foto Düzenleyici**'yi aç.

## Kısaca kullanım

1. Kaynak klasörü (fotoğrafların olduğu yer) ve hedef klasörü seç.
2. **1) Önizle**: hiçbir şeyi değiştirmeden her dosyanın nereye gideceğini gösterir. Gerekirse birkaç soru sorar.
3. **2) Başlat**: varsayılan olarak *kopyalar*, asıllar yerinde kalır.
4. Bir yanlışlık olursa **Son işlemi geri al**.

Aynı hedef klasöre sonradan tekrar çalıştırırsan sadece yeni dosyalar eklenir. Ayrıntılar, sorulan sorular,
saat düzeltme ve bilinen sınırlar için: **[BENIOKU.md](BENIOKU.md)**.

---

## English

A small Windows app that sorts photos and videos from several cameras and phones into
`Device/Photos` and `Device/Videos` folders. Files are renamed `YYYY-MM-DD_HH-MM-SS_Device.ext`, so sorting
by name is chronological.

* Files with missing date or device info go to `_Missing Info`. Screenshots go to `Screenshots/<Device>`.
* Exact duplicates are moved aside to `_Duplicates` and never deleted.
* It converts video times stored in UTC to local time, using GPS or a location you pick.
* Per-device clock fix. The app remembers device names you merged (e.g. `realme RMX2030` = `realme 5i`).
* Running it again on the same target adds only new files. **Undo last run** reverts the last copy or move.
* The interface is in Turkish and English, picked from the Windows language at first start. You can change it at the top right.

**Install:** download `FotoDuzenleyici_Kurulum.exe` from **Releases** and run it. Python and admin rights
are not needed. If SmartScreen warns you, choose *More info → Run anyway*.

## Geliştirici / Developer

```
pip install -r requirements.txt
python app.py                 # programı kaynak koddan çalıştır / run from source
python tests/run_tests.py     # 146 kural testi / rule tests
python tests/gui_smoke.py     # arayüz testi / GUI smoke test
build.bat                     # dist\FotoDuzenleyici_Kurulum.exe üretir / builds the installer
```

`build.bat` exiftool'u ve Inno Setup'ı kendisi indirir (`get_exiftool.ps1`, `get_innosetup.ps1`).
Yeni sürüm yayınlamak için:
1. `installer.iss` içindeki `AppVersion` değerini artır.
2. `build.bat` çalıştır.
3. GitHub'da **Releases → Draft a new release** sayfasında `dist\FotoDuzenleyici_Kurulum.exe` dosyasını ekle.

## Lisanslar / Licenses

Bu programın kodu [MIT lisansı](LICENSE) ile yayınlanır. / The code of this program is MIT licensed.

Kurulum dosyası şu açık kaynak bileşenleri içerir:

| Bileşen | Lisans |
|---|---|
| [ExifTool](https://exiftool.org) (Phil Harvey) | Perl lisansı (GPL veya Artistic) |
| [ExifRead](https://github.com/ianare/exif-py) | BSD |
| [hachoir](https://github.com/vstinner/hachoir) | GPL v2 |
| [timezonefinder](https://github.com/jannikmi/timezonefinder) | MIT |
| [tzdata](https://github.com/python/tzdata) | Apache 2.0 |
| Python ve tkinter | PSF |

Kurulum dosyası [Inno Setup](https://jrsoftware.org/isinfo.php) ile, paketleme
[PyInstaller](https://pyinstaller.org) ile yapılır. Bu iki araç programın içine gömülmez.
