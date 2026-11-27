# Foto Düzenleyici (sürüm 3)

Birden fazla makineden gelen fotoğraf ve videoları cihaza, türe ve çekim zamanına göre düzenler.

## Sonuç klasör yapısı

```
Hedef/
  Canon EOS R6/
    Fotoğraflar/2026-11-20_10-00-00_Canon-EOS-R6.jpg
    Videolar/...
  Sony ILCE-7M3/...
  _Eksik Bilgi/
    Tarih Yok/<Cihaz>/Fotoğraflar|Videolar/   (orijinal adıyla)
    Cihaz Yok/Fotoğraflar|Videolar/           (2026-11-21_08-00-00.jpg)
    Tarih ve Cihaz Yok/Fotoğraflar|Videolar/  (orijinal adıyla)
  Ekran Görüntüleri/
    Apple iPhone/2024-06-18_15-18-58_Apple-iPhone.png
    Windows PC/2025-05-25_00-52-23_Windows-PC.png
    _Eksik Bilgi/...                          (aynı kurallar)
  _Kopyalar/                                  (içeriği birebir aynı olan dosyalar, aynı düzende)
    Canon EOS R6/Fotoğraflar/2026-11-20_10-00-00_Canon-EOS-R6.jpg
  _islem_gecmisi/                             (geri alma kaydı; silmeyin)
  rapor_<tarih>.csv                           (hangi dosya nereye gitti; Excel'de açılır)
```

Program İngilizce kullanılırsa klasörler `Photos`, `Videos`, `_Missing Info`, `Screenshots`, `_Duplicates`
adıyla açılır. Hedefte daha önce açılmış klasörler varsa onların dili korunur, iki dil karışmaz.

* Ad tarihle başladığı için Gezgin'de "Ad"a göre sıralayınca her şey kronolojik dizilir.
* Aynı saniyede çekilen dosyalar kaynak klasördeki sıralarına göre `_01`, `_02`, ... alır.
* Aynı anda çekilen JPG + RAW çifti aynı adı (farklı uzantıyla) alır ve yan yana durur.
* **Sadece yeniler:** Aynı hedefe tekrar çalıştırılırsa hedefte aynı içerikle zaten bulunan dosyalar atlanır
  ("zaten var"), yalnızca yeni dosyalar eklenir. Yeni dosyanın numarası, hedefteki dosyalarla çakışmayacak şekilde verilir.
* **Kopyalar:** Kaynakta içeriği birebir aynı olan dosyalar (ör. aynı fotoğraf iki klasörde) silinmez;
  ilki normal yerine, diğerleri `_Kopyalar` altına aynı düzende konur. Raporda "Kopyası olduğu dosya" sütunu
  hangi dosyanın kopyası olduğunu yazar. Böylece bir yanlışlık olursa hiçbir şey kaybolmaz; kontrol edip
  `_Kopyalar` klasörünü elle silebilirsiniz.
* Fotoğraf/video olmayan dosyalara dokunulmaz, raporda listelenir.

### Ekran görüntüleri nasıl tanınır

* iPhone/iPad: EXIF'te `UserComment = Screenshot` yazar; tarih EXIF'ten okunur, cihaz "Apple iPhone" olur
  (model yazmaz; program "Apple iPhone 14 ile aynı mı?" diye sorabilir).
* Windows (`Ekran görüntüsü 2025-05-25 005223.png`, `Screenshot ...`), Roblox (`RobloxScreenShot2025...`):
  EXIF yoktur; tarih dosya adından okunur, cihaz "Windows PC" olur.
* Android (`Screenshot_20210102-181538.jpg`): tarih dosya adından, cihaz EXIF'te varsa ondan, yoksa "Android".

## Kullanım

1. **Önizle**: Dosyaları okur. Gerekirse birkaç soru sorar (aşağıda), sonra her dosyanın nereye gideceğini
   gösterir. Hiçbir şey değişmez. Sarı satırlar bilgisi eksik olanlardır. Alt satırda okuma süresi yazar.
2. **Seçimler...**: Soruları yeniden açar (dosyaları tekrar okumadan).
3. **Saat düzeltme...**: Bir makinenin saati yanlışsa (ör. yurt dışında güncellenmemiş) o cihazın bütün
   dosyalarına süre eklenir: `+2`, `-1:30`, `+0:45`. Sadece o çalıştırma için geçerlidir; raporda not olarak yazar.
4. **Başlat**: Onay sorar, sonra kopyalar (ya da "Taşı" seçiliyse taşır).
5. **Son işlemi geri al**: Hedef klasördeki en son işlemi geri alır. Kopyalamada hedefe kopyalanan dosyalar
   silinir (asılları yerinde durduğu için), taşımada dosyalar eski yerlerine döner. Sonradan değiştirilmiş
   ya da asıl dosyası bulunamayan dosyalara dokunulmaz ve bunlar listelenir. Art arda basılırsa bir önceki işlemi geri alır.
6. **Dil**: Sağ üstten Türkçe / English seçilir. İlk açılışta Windows'un diline göre gelir, seçim hatırlanır.

### Önizlemeden sonra sorulabilecek sorular

* **Video saatleri:** Bazı cihazlar videonun saatini UTC (dünya saati) yazar, bazıları yerel saat.
  Program her cihaz için bir tahmin seçer: aynı cihazın fotoğrafları varsa videoları onlara göre karşılaştırır,
  yoksa markaya bakar (telefonlar ve GoPro/DJI UTC, fotoğraf makineleri yerel). Kullanıcı değiştirebilir.
  UTC olanlar videonun GPS konumuna göre o yerin saatine çevrilir. GPS yoksa sorulan konum kullanılır.
  Saat dilimi bilgisi yazan videolar (ör. iPhone) ve fotoğraflar zaten yerel saattir, dokunulmaz.
* **Aynı modelden birden fazla makine:** Aynı modelde farklı seri numaraları görülürse sorulur. İşaretlenirse
  `Canon EOS R6 (1234)` gibi ayrı klasörlere gider. Seri numarası olmayan dosyalar (genelde videolar) ortak klasörde kalır.

* **Benzer cihaz adları:** Aynı telefon bazen farklı adla yazılır (ör. `realme RMX2030` = `realme 5i`).
  Aynı markadan birden fazla ad bulunursa program sorar; "aynı cihaz" denirse seçilen adla tek klasöre toplar,
  "değil" denirse ayrı bırakır. Cevaplar `%APPDATA%\FotoDuzenleyici\cihaz_esleme.json` dosyasına kaydedilir
  ve bir daha sorulmaz. **Cihaz adları...** düğmesiyle tüm eşleştirmeler görülüp değiştirilebilir.
  Raporda dosyada yazan orijinal ad da ayrı bir sütunda durur.

## Testler

`python tests/run_tests.py` örnek dosyalarla (tests/fixtures) bütün kuralları dener, beklenen ve gerçek sonucu
karşılaştırır ve `tests/test_raporu.md` dosyasına yazar. Asıl fotoğraflara dokunmaz.
`python tests/gui_smoke.py` pencereyi açıp önizleme, saat düzeltme, dil değiştirme, başlatma ve geri almayı dener.

## Kurulum dosyası yapmak (bir kere, kendi bilgisayarında)

1. Python 3.10+ kurulu olsun (python.org, kurarken "Add python.exe to PATH" işaretli).
2. Bu klasördeki `build.bat` dosyasına çift tıkla. Sırayla:
   exiftool'u indirir (`get_exiftool.ps1`), programı paketler, Inno Setup yoksa sadece bu kullanıcı için
   kurar (`get_innosetup.ps1`) ve `installer.iss` ile kurulum dosyasını üretir.
3. `dist\FotoDuzenleyici_Kurulum.exe` oluşur. Arkadaşına sadece bu dosyayı gönder. Çift tıklayınca Türkçe
   kurulum açılır, yönetici izni istemez, Başlat menüsüne (istenirse masaüstüne) kısayol koyar ve
   "Uygulamalar"dan kaldırılabilir. Python kurmasına gerek yoktur.

Kurulum dosyası olmadan denemek için `dist\FotoDuzenleyici\FotoDuzenleyici.exe` doğrudan çalıştırılabilir.
Python ile direkt denemek için: `pip install -r requirements.txt` sonra `python app.py`.

## exiftool ve hız

exiftool videoların cihaz bilgisini, telefon videolarının saat dilimini, Canon CR3 gibi yeni RAW türlerini ve
makine seri numaralarını okur. Program onu bir kez açıp açık tutar, dosyaları 100'erli gruplar halinde okutur.
Ekranda "exiftool kullan" kutusuyla açılıp kapatılabilir; her önizlemede okuma süresi alt satırda yazar.

Ölçüm (Linux test makinesi, 1000 fotoğraf + 100 video, dosyalar önbellekte):

| Yöntem | Süre | Dosya başına | Cihazı bulunan |
|---|---|---|---|
| exiftool kapalı | 0,25 sn | 0,2 ms | 1000 / 1100 (videolar bulunamadı) |
| exiftool açık (açık tutulan tek süreç) | 2,9 sn | 2,7 ms | 1100 / 1100 |
| exiftool'u her dosya için ayrı çalıştırmak (kullanılmıyor) | ~2 dk | 108 ms | |

Yani 10.000 dosyada fark yaklaşık yarım dakika. Windows'ta sayılar biraz daha yüksek olabilir; gerçek
sayıyı program kendi ekranında gösterir. SD kart veya harici diskten okurken diskin hızı daha belirleyici olur.

## Bilinen sınırlar / tahminler

* Fotoğrafların saati makinenin kendi saatidir; makine yanlış ayarlıysa "Saat düzeltme..." ile elle düzeltilir, program kendisi anlamaz.
* Video için UTC/yerel tahmini yanlış olabilir; bu yüzden soruda örnek saatlerle gösterilir.
* Dosya tarihine (değiştirilme tarihi) bakılmaz; EXIF yoksa dosya "Eksik Bilgi"ye gider.
* Kopyalar içerik olarak birebir aynı olanlardır. Yeniden kaydedilmiş, küçültülmüş ya da WhatsApp'tan gelmiş
  bir fotoğraf aynı kare olsa bile kopya sayılmaz.
