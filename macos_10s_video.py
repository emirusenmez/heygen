#!/usr/bin/env python3
"""
Mac OS için 10 saniye video kayıt scripti
Kamerayı açar, 10 saniye kayıt yapar ve kapatır
"""

import cv2
import time
import os
import datetime
import threading
import sounddevice as sd
import soundfile as sf
import numpy as np

def kamera_ac():
    """Kamerayı açar ve ayarlar"""
    print("📹 Kamera açılıyor...")
    
    # macOS için AVFoundation backend kullan
    cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
    
    if not cap.isOpened():
        print("❌ Hata: Kamera açılamadı!")
        return None
    
    # Kamera ayarları
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    print("✅ Kamera başarıyla açıldı")
    print(f"   • Çözünürlük: 1280x720")
    print(f"   • FPS: 30")
    
    return cap

def kamera_kapat(cap):
    """Kamerayı kapatır"""
    if cap is not None:
        cap.release()
        cv2.destroyAllWindows()
        print("📹 Kamera kapatıldı")

def ses_kaydet(sure, dosya_adi):
    """Ses kaydı yapar"""
    try:
        print("🎤 Ses kaydı başlıyor...")
        
        # macOS için ses ayarları
        sample_rate = 44100
        channels = 1  # Mono daha güvenli
        
        # Ses cihazlarını listele
        print("Mevcut ses cihazları:")
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            print(f"  {i}: {device['name']}")
        
        # Ses kaydı
        audio_data = sd.rec(
            int(sure * sample_rate), 
            samplerate=sample_rate, 
            channels=channels, 
            dtype='float32',
            device=None  # Varsayılan cihaz
        )
        
        # Kayıt bitene kadar bekle
        sd.wait()
        
        # WAV dosyası olarak kaydet
        wav_dosya = dosya_adi.replace('.mp4', '.wav')
        sf.write(wav_dosya, audio_data, sample_rate)
        
        print(f"✅ Ses kaydı tamamlandı: {wav_dosya}")
        return wav_dosya
        
    except Exception as e:
        print(f"❌ Ses kaydı hatası: {e}")
        return None

def video_ses_birlestir(video_dosya, ses_dosya, cikti_dosya):
    """Video ve ses dosyalarını birleştirir"""
    try:
        # FFmpeg yolunu bul
        import shutil
        ffmpeg_path = shutil.which('ffmpeg')
        
        if not ffmpeg_path:
            try:
                import imageio_ffmpeg
                ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            except ImportError:
                print("❌ FFmpeg bulunamadı. Video ve ses ayrı dosyalar olarak kaydedildi.")
                return False
        
        # FFmpeg ile birleştirme
        import subprocess
        cmd = [
            ffmpeg_path, '-y',
            '-i', video_dosya,
            '-i', ses_dosya,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-shortest',
            cikti_dosya
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Video ve ses birleştirildi: {cikti_dosya}")
            return True
        else:
            print(f"❌ Birleştirme hatası: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Birleştirme hatası: {e}")
        return False

def kayit_yap():
    """Ana kayıt fonksiyonu - 10 saniye video çeker"""
    print("🎥 Mac OS 10 Saniye Video Kayıt Aracı")
    print("=" * 40)
    
    # Çıktı klasörünü oluştur
    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)
    
    # Dosya adı (tarih-saat ile)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    video_file = os.path.join(output_dir, f"video_{timestamp}.mp4")
    final_file = os.path.join(output_dir, f"video_sesli_{timestamp}.mp4")
    
    print(f"📁 Çıktı dosyası: {final_file}")
    print(f"⏱️  Süre: 10 saniye")
    print()
    
    # Kamera aç
    cap = kamera_ac()
    if cap is None:
        return False
    
    try:
        # Video ayarları
        width = 1280
        height = 720
        fps = 30
        duration = 10  # 10 saniye
        
        # Video yazıcı oluştur
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(video_file, fourcc, fps, (width, height))
        
        if not out.isOpened():
            print("❌ Video yazıcı açılamadı!")
            return False
        
        print("🎬 Kayıt başlıyor...")
        print("10 saniye boyunca video ve ses kaydı yapılacak...")
        
        # Geri sayım
        print("\nGeri sayım:")
        for i in range(3, 0, -1):
            print(f"  {i}...")
            time.sleep(1)
        print("  🎬 Kayıt başladı!")
        
        # Ses kaydını başlat (ayrı thread'de)
        ses_thread = threading.Thread(target=ses_kaydet, args=(duration, video_file))
        ses_thread.start()
        
        # Video kayıt döngüsü
        start_time = time.time()
        frame_count = 0
        
        while True:
            # Frame oku
            ret, frame = cap.read()
            
            if not ret:
                print("❌ Hata: Frame okunamadı!")
                break
            
            # Frame'i yeniden boyutlandır
            frame = cv2.resize(frame, (width, height))
            
            # Frame'i videoya yaz
            out.write(frame)
            
            frame_count += 1
            elapsed = time.time() - start_time
            remaining = duration - elapsed
            
            # İlerleme göster (her saniye)
            if frame_count % 30 == 0:
                print(f"📹 Kayıt: {elapsed:.1f}s / {duration}s (Kalan: {remaining:.1f}s)")
            
            # 10 saniye doldu mu kontrol et
            if elapsed >= duration:
                break
            
            # 'q' tuşu ile erken çıkış
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("⏹️  Kayıt kullanıcı tarafından durduruldu")
                break
        
        # Video kaydını bitir
        out.release()
        print("✅ Video kaydı tamamlandı")
        
        # Ses kaydının bitmesini bekle
        print("🎤 Ses kaydı bekleniyor...")
        ses_thread.join()
        
        # Ses dosyasını kontrol et ve birleştir
        ses_dosya = video_file.replace('.mp4', '.wav')
        
        if os.path.exists(ses_dosya):
            print("🔗 Video ve ses birleştiriliyor...")
            
            if video_ses_birlestir(video_file, ses_dosya, final_file):
                # Geçici dosyaları sil
                try:
                    os.remove(video_file)
                    os.remove(ses_dosya)
                    print("🧹 Geçici dosyalar temizlendi")
                except Exception as e:
                    print(f"⚠️ Geçici dosya temizleme hatası: {e}")
                
                # Dosya bilgilerini göster
                if os.path.exists(final_file):
                    file_size = os.path.getsize(final_file) / (1024 * 1024)
                    print(f"🎉 Kayıt tamamlandı: {final_file}")
                    print(f"📊 Dosya boyutu: {file_size:.2f} MB")
                    return True
            else:
                print(f"📹 Video kaydı (ses yok): {video_file}")
                if os.path.exists(video_file):
                    file_size = os.path.getsize(video_file) / (1024 * 1024)
                    print(f"📊 Dosya boyutu: {file_size:.2f} MB")
                return True
        else:
            print(f"📹 Video kaydı (ses yok): {video_file}")
            if os.path.exists(video_file):
                file_size = os.path.getsize(video_file) / (1024 * 1024)
                print(f"📊 Dosya boyutu: {file_size:.2f} MB")
            return True
            
    except Exception as e:
        print(f"❌ Kayıt hatası: {e}")
        return False
    
    finally:
        # Kamera kapat
        kamera_kapat(cap)

def main():
    """Ana fonksiyon"""
    try:
        success = kayit_yap()
        if success:
            print("\n🎉 İşlem başarıyla tamamlandı!")
        else:
            print("\n❌ İşlem başarısız!")
            return 1
    except KeyboardInterrupt:
        print("\n⏹️  İşlem kullanıcı tarafından iptal edildi")
        return 1
    except Exception as e:
        print(f"\n❌ Beklenmeyen hata: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
