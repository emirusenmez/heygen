#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MacOS için Ses Kaydı ve Metin Dönüştürme Aracı
10 saniye boyunca otomatik olarak ses kaydı yapar ve txt dosyasına kaydeder
"""

import os
from datetime import datetime
import subprocess
import tempfile
import time
import speech_recognition as sr

def ses_kaydet(sure=10):
    """
    10 saniye boyunca otomatik olarak gerçek ses kaydı yapar
    MacOS'ta 'rec' komutunu kullanır
    """
    print(f"🎤 {sure} saniye boyunca otomatik ses kaydı başlıyor...")
    print("Konuşmaya başlayabilirsiniz!")
    
    # Geçici dosya oluştur
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
    temp_filename = temp_file.name
    temp_file.close()
    
    try:
        # MacOS'ta 'rec' komutu ile ses kaydet
        # Önce mevcut dizindeki rec'ı dene, sonra sistem rec'ını
        script_dir = os.path.dirname(os.path.abspath(__file__))
        rec_paths = [os.path.join(script_dir, 'sox-14.4.2', 'rec'), 'rec']
        
        for rec_path in rec_paths:
            if os.path.exists(rec_path) or rec_path == 'rec':
                cmd = [rec_path, '-r', '44100', '-c', '1', temp_filename, 'trim', '0', str(sure)]
                print(f"🎯 Gerçek ses kaydı başlatılıyor...")
                print(f"Komut: {' '.join(cmd)}")
                
                # Komutu çalıştır
                process = subprocess.run(cmd, capture_output=True, text=True, timeout=sure+5)
                break
        else:
            raise FileNotFoundError("rec komutu bulunamadı")
        
        if process.returncode == 0:
            print(f"✅ {sure} saniye gerçek ses kaydı tamamlandı!")
            return temp_filename
        else:
            print(f"❌ Ses kaydı hatası: {process.stderr}")
            # SoX yüklü değilse, simülasyon yap
            print("🔄 SoX bulunamadı, simülasyon moduna geçiliyor...")
            return ses_kaydet_simulasyon(sure)
            
    except FileNotFoundError:
        print("❌ 'rec' komutu bulunamadı. SoX yüklenmeli.")
        print("🔄 Simülasyon moduna geçiliyor...")
        return ses_kaydet_simulasyon(sure)
    except subprocess.TimeoutExpired:
        print("⏰ Zaman aşımı - ses kaydı tamamlandı")
        return temp_filename if os.path.exists(temp_filename) else ses_kaydet_simulasyon(sure)
    except Exception as e:
        print(f"❌ Ses kaydı hatası: {e}")
        print("🔄 Simülasyon moduna geçiliyor...")
        return ses_kaydet_simulasyon(sure)

def ses_kaydet_simulasyon(sure=10):
    """
    Simülasyon modunda ses kaydı yapar
    """
    print("🎯 Simülasyon modunda ses kaydı başlatılıyor...")
    
    # Geçici dosya oluştur
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
    temp_filename = temp_file.name
    temp_file.close()
    
    # Geri sayım ve ilerleme göstergesi
    for i in range(sure, 0, -1):
        print(f"⏱️  Kalan süre: {i} saniyee", end='\r')
        time.sleep(1)
    
    print(f"\n✅ {sure} saniye simülasyon ses kaydı tamamlandı!")
    
    # Gerçek WAV dosyası oluştur (sessizlik)
    import wave
    import struct
    
    # WAV dosyası parametreleri
    sample_rate = 44100
    duration = sure
    num_samples = sample_rate * duration
    
    # WAV dosyası oluştur
    with wave.open(temp_filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        
        # Sessizlik verisi oluştur (sıfır değerler)
        for _ in range(num_samples):
            wav_file.writeframes(struct.pack('<h', 0))  # 16-bit little-endian sıfır
    
    return temp_filename

def sesi_metne_cevir(ses_dosyasi):
    """
    Ses dosyasını metne çevirir (gerçek speech recognition)
    """
    print("🔄 Ses dosyası metne çevriliyor...")
    
    # Speech Recognition nesnesi oluştur
    r = sr.Recognizer()
    
    try:
        # Ses dosyasını aç
        with sr.AudioFile(ses_dosyasi) as source:
            # Gürültü azaltma
            r.adjust_for_ambient_noise(source)
            # Ses verisini oku
            audio = r.record(source)
        
        # Google Speech Recognition ile metne çevir (Türkçe)
        metin = r.recognize_google(audio, language='tr-TR')
        print("✅ Gerçek metin dönüştürme başarılı!")
        return metin
        
    except sr.UnknownValueError:
        print("❌ Ses anlaşılamadı")
        return "Ses anlaşılamadı - lütfen daha net konuşun"
    except sr.RequestError as e:
        print(f"❌ Google Speech Recognition servisi hatası: {e}")
        return f"Servis hatası: {e}"
    except Exception as e:
        print(f"❌ Beklenmeyen hata: {e}")
        return f"Hata: {e}"

def txt_dosyasina_kaydet(metin):
    """
    Metni tarih-saat bilgisiyle birlikte txt dosyasına kaydeder
    """
    # Mevcut tarih ve saat
    simdi = datetime.now()
    tarih_saat = simdi.strftime("%d.%m.%Y %H:%M:%S")
    
    # Dosya adı oluştur
    dosya_adi = f"ses_kayit_{simdi.strftime('%Y%m%d_%H%M%S')}.txt"
    # Script'in bulunduğu klasöre kaydet (text klasörü)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dosya_yolu = os.path.join(script_dir, dosya_adi)
    
    # Dosyaya yaz
    with open(dosya_yolu, 'w', encoding='utf-8') as f:
        f.write(f"Ses Kaydı - {tarih_saat}\n")
        f.write("=" * 50 + "\n\n")
        f.write(metin)
        f.write("\n\n" + "=" * 50)
    
    print(f"💾 Metin dosyaya kaydedildi: {dosya_adi}")
    return dosya_yolu

def main():
    """
    Ana fonksiyon
    """
    print("🎯 MacOS Otomatik Ses Kayıt Aracı")
    print("=" * 50)
    
    try:
        # 1. 10 saniye ses kaydet
        ses_dosyasi = ses_kaydet(10)
        
        if ses_dosyasi is None:
            print("❌ Ses kaydı başarısız oldu!")
            return
        
        # 2. Ses dosyasını işle
        metin = sesi_metne_cevir(ses_dosyasi)
        
        # 3. Metni txt dosyasına kaydet
        dosya_yolu = txt_dosyasina_kaydet(metin)
        
        # 4. Geçici ses dosyasını sil
        if os.path.exists(ses_dosyasi):
            os.unlink(ses_dosyasi)
        
        print("\n🎉 İşlem tamamlandı!")
        print(f"📄 Kaydedilen dosya: {dosya_yolu}")
        print(f"📝 Metin içeriği:\n{metin}")
        
    except KeyboardInterrupt:
        print("\n❌ İşlem kullanıcı tarafından iptal edildi")
    except Exception as e:
        print(f"\n❌ Hata oluştu: {e}")

if __name__ == "__main__":
    main()
