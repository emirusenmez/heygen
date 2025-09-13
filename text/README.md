# MacOS Otomatik Ses Kayıt ve Metin Dönüştürme Aracı

Bu Python scripti 10 saniye boyunca otomatik olarak mikrofonu dinler, sesi gerçek zamanlı olarak metne çevirir ve tarih-saat bilgisiyle birlikte txt dosyasına kaydeder.

## 🚀 Hızlı Başlangıç

### Otomatik Çalıştırma (Önerilen)
```bash
./run_ses_kayit.sh
```

### Manuel Çalıştırma
```bash
# Virtual environment ile
source .venv/bin/activate
python ses_kayit_metin.py

# Sistem Python ile
python3 ses_kayit_metin.py
```

## 📦 Kurulum

### 1. Gerekli Kütüphaneler
```bash
# Virtual environment oluştur (opsiyonel)
python3 -m venv .venv
source .venv/bin/activate

# Kütüphaneleri yükle
pip install SpeechRecognition
```

### 2. Ses Kayıt Araçları
Script otomatik olarak SoX araçlarını indirir ve kullanır. Manuel kurulum gerekmez.

## ✨ Özellikler

- 🎤 **10 saniye otomatik ses kaydı** - SoX ile gerçek mikrofon kaydı
- 🔄 **Gerçek zamanlı metin dönüştürme** - Google Speech Recognition ile
- 🇹🇷 **Türkçe dil desteği** - Konuşmanızı Türkçe olarak anlar
- 📅 **Tarih-saat bilgisi** - Her kayıt için otomatik zaman damgası
- 💾 **Otomatik dosya kaydetme** - `ses_kayit_YYYYMMDD_HHMMSS.txt` formatında
- ⏱️ **İlerleme göstergesi** - Geri sayım ve durum mesajları
- 🔧 **Çoklu ortam desteği** - Virtual environment ve sistem Python
- 🛡️ **Hata yönetimi** - Ses kaydı başarısız olursa simülasyon moduna geçer

## 📁 Dosya Yapısı

```
text/
├── ses_kayit_metin.py      # Ana Python scripti
├── run_ses_kayit.sh        # Otomatik çalıştırıcı script
├── requirements.txt        # Gerekli kütüphaneler
├── README.md              # Bu dosya
├── sox-14.4.2/            # Ses kayıt araçları (otomatik indirilir)
└── ses_kayit_*.txt        # Oluşturulan metin dosyaları
```

## 🎯 Kullanım Örnekleri

### Temel Kullanım
```bash
./run_ses_kayit.sh
```

### Çıktı Örneği
```
🎯 MacOS Otomatik Ses Kayıt Aracı
==================================================
🎤 10 saniye boyunca otomatik ses kaydı başlıyor...
Konuşmaya başlayabilirsiniz!
🎯 Gerçek ses kaydı başlatılıyor...
✅ 10 saniye gerçek ses kaydı tamamlandı!
🔄 Ses dosyası metne çevriliyor...
✅ Gerçek metin dönüştürme başarılı!
💾 Metin dosyaya kaydedildi: ses_kayit_20250913_110800.txt

🎉 İşlem tamamlandı!
📄 Kaydedilen dosya: /Users/emirefeusenmez/code/text/ses_kayit_20250913_110800.txt
📝 Metin içeriği:
Merhaba sesimi duyabiliyor musun teknofest Türkiye'nin en iyi teknoloji firmaları
```

## 🔧 Sorun Giderme

### Virtual Environment Sorunu
```bash
# Virtual environment'ı yeniden oluştur
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install SpeechRecognition
```

### Ses Kaydı Sorunu
Script otomatik olarak SoX bulamazsa simülasyon moduna geçer. Gerçek ses kaydı için SoX araçları gerekir.

### İzin Sorunu
```bash
chmod +x run_ses_kayit.sh
```

## 📋 Gereksinimler

- macOS (test edildi: macOS 14.6.0)
- Python 3.7+
- İnternet bağlantısı (Google Speech Recognition için)
- Mikrofon erişimi

## 🆘 Destek

Sorun yaşarsanız:
1. İnternet bağlantınızı kontrol edin
2. Mikrofon izinlerini kontrol edin
3. Python ve kütüphane versiyonlarını kontrol edin
4. Script'i yeniden çalıştırın
