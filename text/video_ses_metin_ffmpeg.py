#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Dosyasından Ses Çıkarıp Metne Çevirme Aracı (FFmpeg ile)
Video dosyasından ses çıkarır ve txt dosyasına kaydeder
"""

import os
import sys
import subprocess
from datetime import datetime
import tempfile
import speech_recognition as sr

def video_dosyasindan_ses_cikar(video_yolu, cikti_yolu=None):
    """
    FFmpeg kullanarak video dosyasından ses çıkarır
    """
    print(f"🎬 Video dosyası işleniyor: {os.path.basename(video_yolu)}")
    
    try:
        # Çıktı dosyası yolu belirle
        if cikti_yolu is None:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            cikti_yolu = temp_file.name
            temp_file.close()
        
        # FFmpeg komutu ile ses çıkar
        cmd = [
            'ffmpeg',
            '-i', video_yolu,
            '-vn',  # Video olmadan
            '-acodec', 'pcm_s16le',  # 16-bit PCM
            '-ar', '44100',  # 44.1kHz sample rate
            '-ac', '1',  # Mono
            '-y',  # Overwrite output file
            cikti_yolu
        ]
        
        print("🔄 FFmpeg ile ses dosyası çıkarılıyor...")
        print(f"Komut: {' '.join(cmd)}")
        
        # FFmpeg komutunu çalıştır
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Ses dosyası başarıyla çıkarıldı: {os.path.basename(cikti_yolu)}")
            return cikti_yolu
        else:
            print(f"❌ FFmpeg hatası: {result.stderr}")
            return None
            
    except FileNotFoundError:
        print("❌ FFmpeg bulunamadı! Lütfen FFmpeg'i yükleyin:")
        print("   brew install ffmpeg")
        return None
    except Exception as e:
        print(f"❌ Video işleme hatası: {e}")
        return None

def sesi_metne_cevir(ses_dosyasi, dil='tr-TR'):
    """
    Ses dosyasını metne çevirir
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
        
        # Google Speech Recognition ile metne çevir
        metin = r.recognize_google(audio, language=dil)
        print("✅ Metin dönüştürme başarılı!")
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

def txt_dosyasina_kaydet(metin, video_adi):
    """
    Metni tarih-saat bilgisiyle birlikte txt dosyasına kaydeder
    """
    # Mevcut tarih ve saat
    simdi = datetime.now()
    tarih_saat = simdi.strftime("%d.%m.%Y %H:%M:%S")
    
    # Dosya adı oluştur
    video_basename = os.path.splitext(os.path.basename(video_adi))[0]
    dosya_adi = f"video_ses_{video_basename}_{simdi.strftime('%Y%m%d_%H%M%S')}.txt"
    
    # Script'in bulunduğu klasöre kaydet (text klasörü)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dosya_yolu = os.path.join(script_dir, dosya_adi)
    
    # Dosyaya yaz
    with open(dosya_yolu, 'w', encoding='utf-8') as f:
        f.write(f"Video Ses Kaydı - {tarih_saat}\n")
        f.write(f"Video Dosyası: {os.path.basename(video_adi)}\n")
        f.write("=" * 50 + "\n\n")
        f.write(metin)
        f.write("\n\n" + "=" * 50)
    
    print(f"💾 Metin dosyaya kaydedildi: {dosya_adi}")
    return dosya_yolu

def main():
    """
    Ana fonksiyon
    """
    print("🎬 Video Ses Çıkarıp Metne Çevirme Aracı (FFmpeg)")
    print("=" * 50)
    
    # Video dosyası yolunu al
    if len(sys.argv) > 1:
        video_yolu = sys.argv[1]
    else:
        video_yolu = input("📁 Video dosyasının yolunu girin: ").strip()
    
    # Dosya var mı kontrol et
    if not os.path.exists(video_yolu):
        print(f"❌ Dosya bulunamadı: {video_yolu}")
        return
    
    # Mutlak yol yap
    video_yolu = os.path.abspath(video_yolu)
    
    try:
        # 1. Video dosyasından ses çıkar
        ses_dosyasi = video_dosyasindan_ses_cikar(video_yolu)
        
        if ses_dosyasi is None:
            print("❌ Ses çıkarma başarısız oldu!")
            return
        
        # 2. Ses dosyasını metne çevir
        metin = sesi_metne_cevir(ses_dosyasi)
        
        # 3. Metni txt dosyasına kaydet
        dosya_yolu = txt_dosyasina_kaydet(metin, video_yolu)
        
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
