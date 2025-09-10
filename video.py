#!/usr/bin/env python3
"""
20 saniye video çekme scripti
app.py'deki kayıt yöntemini kullanır
"""

import os
import sys
import datetime
import time
import threading
import cv2
import subprocess
import shutil
import sounddevice as sd
import soundfile as sf
import numpy as np
from pathlib import Path

# app.py'den gerekli fonksiyonları import et
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def get_ffmpeg_path():
    """FFmpeg yolunu bul"""
    path = shutil.which('ffmpeg') or shutil.which('ffmpeg.exe')
    if path:
        print(f"FFmpeg bulundu: {path}")
        return path
    try:
        import imageio_ffmpeg
        p = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"FFmpeg (imageio) bulundu: {p}")
        return p
    except Exception:
        print("FFmpeg bulunamadı.")
        return None

def get_available_audio_devices():
    """Mevcut ses cihazlarını tespit et"""
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        return []
    
    try:
        result = subprocess.run([
            ffmpeg, '-f', 'avfoundation', '-list_devices', 'true', '-i', ''
        ], capture_output=True, text=True, timeout=10)
        
        audio_devices = []
        lines = result.stderr.split('\n')
        in_audio_section = False
        
        for line in lines:
            if 'AVFoundation audio devices:' in line:
                in_audio_section = True
                continue
            elif 'AVFoundation video devices:' in line:
                in_audio_section = False
                continue
            elif in_audio_section and '[' in line and ']' in line:
                try:
                    brackets = []
                    for i, char in enumerate(line):
                        if char == '[':
                            brackets.append(i)
                        elif char == ']':
                            brackets.append(i)
                    
                    if len(brackets) >= 4:
                        start_bracket = brackets[2]
                        end_bracket = brackets[3]
                        device_index = int(line[start_bracket+1:end_bracket])
                        audio_devices.append(device_index)
                except (ValueError, IndexError):
                    continue
        
        print(f"Tespit edilen ses cihazları: {audio_devices}")
        return audio_devices
        
    except Exception as e:
        print(f"Ses cihazı tespit hatası: {e}")
        return [0, 1, 2]

def find_rode_device():
    """Rode Wireless GO 2 cihazını tespit et"""
    try:
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            device_name = device['name'].lower()
            
            if any(keyword in device_name for keyword in ['rode', 'wireless', 'go']):
                print(f"🎤 Rode cihazı bulundu: {device['name']} (ID: {i})")
                return i, device['name']
        
        print("❌ Rode cihazı bulunamadı")
        return None
        
    except Exception as e:
        print(f"Rode cihaz tespit hatası: {e}")
        return None

def get_rode_audio_device_index():
    """Rode mikrofon için FFmpeg cihaz indeksini bul"""
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        return None
    
    try:
        result = subprocess.run([
            ffmpeg, '-f', 'avfoundation', '-list_devices', 'true', '-i', ''
        ], capture_output=True, text=True, timeout=10)
        
        lines = result.stderr.split('\n')
        in_audio_section = False
        
        for line in lines:
            if 'AVFoundation audio devices:' in line:
                in_audio_section = True
                continue
            elif 'AVFoundation video devices:' in line:
                in_audio_section = False
                continue
            elif in_audio_section and '[' in line and ']' in line:
                if any(keyword in line.lower() for keyword in ['rode', 'wireless', 'go']):
                    try:
                        brackets = []
                        for i, char in enumerate(line):
                            if char == '[':
                                brackets.append(i)
                            elif char == ']':
                                brackets.append(i)
                        
                        if len(brackets) >= 4:
                            start_bracket = brackets[2]
                            end_bracket = brackets[3]
                            device_index = int(line[start_bracket+1:end_bracket])
                            print(f"🎤 Rode FFmpeg cihaz indeksi: {device_index}")
                            return device_index
                    except (ValueError, IndexError):
                        continue
        
        return None
        
    except Exception as e:
        print(f"Rode FFmpeg cihaz tespit hatası: {e}")
        return None

def record_with_ffmpeg_improved(output_path: str, device_index: int = 0, duration_sec: int = 20, with_audio: bool = True):
    """FFmpeg ile geliştirilmiş kayıt - Rode mikrofon için optimize edilmiş"""
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("FFmpeg bulunamadı")
    
    # Çıktı klasörünü oluştur
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Geri sayım göster
    print("Kayıt başlamadan önce geri sayım...")
    for i in range(3, 0, -1):
        print(f"{i}...")
        time.sleep(1)
    print("Kayıt başlıyor!")
    
    # macOS için FFmpeg komutu - Rode mikrofon için geliştirilmiş
    import platform
    if platform.system() == "Darwin":
        if with_audio:
            # Önce Rode cihazını ara
            rode_audio_device = get_rode_audio_device_index()
            
            if rode_audio_device is not None:
                print(f"🎤 Rode mikrofon FFmpeg ile kullanılıyor (cihaz: {rode_audio_device})")
                # Rode için optimize edilmiş ayarlar
                cmd = [
                    ffmpeg, '-y', 
                    '-f', 'avfoundation', 
                    '-video_size', '1280x720',
                    '-framerate', '30',
                    '-i', f'{device_index}:{rode_audio_device}',
                    '-t', str(duration_sec),
                    '-c:v', 'libx264',
                    '-preset', 'ultrafast',  # Daha hızlı encoding
                    '-crf', '23',  # Kalite kontrolü
                    '-c:a', 'aac',
                    '-b:a', '320k',  # Daha yüksek bitrate
                    '-ar', '48000',  # 48kHz
                    '-ac', '2',  # Stereo
                    '-af', 'aresample=48000,volume=3.0,highpass=f=100,lowpass=f=12000,compand=.3|.3:1|1:-90/-60|-60/-40|-40/-30|-20/-20:6:0:-90:0.2',  # Geliştirilmiş ses filtreleri
                    '-async', '1',  # Ses senkronizasyonu
                    '-vsync', '1',  # Video senkronizasyonu
                    '-fflags', '+genpts',  # PTS oluştur
                    output_path
                ]
            else:
                # Rode bulunamazsa mevcut ses cihazlarını tespit et
                audio_devices = get_available_audio_devices()
                
                if not audio_devices:
                    print("⚠️ Ses cihazı bulunamadı, sadece video kaydı yapılıyor...")
                    cmd = [
                        ffmpeg, '-y', 
                        '-f', 'avfoundation', 
                        '-video_size', '1280x720',
                        '-framerate', '30',
                        '-i', str(device_index), 
                        '-t', str(duration_sec),
                        '-c:v', 'libx264',
                        '-preset', 'ultrafast',
                        '-crf', '23',
                        output_path
                    ]
                else:
                    # Mevcut ses cihazlarını dene
                    audio_device = None
                    for preferred_device in [2, 1, 0]:
                        if preferred_device in audio_devices:
                            audio_device = preferred_device
                            break
                    
                    if audio_device is None:
                        audio_device = audio_devices[0]
                    
                    print(f"⚠️ Rode bulunamadı, varsayılan ses cihazı {audio_device} kullanılıyor...")
                    cmd = [
                        ffmpeg, '-y', 
                        '-f', 'avfoundation', 
                        '-video_size', '1280x720',
                        '-framerate', '30',
                        '-i', f'{device_index}:{audio_device}',
                        '-t', str(duration_sec),
                        '-c:v', 'libx264',
                        '-preset', 'ultrafast',
                        '-crf', '23',
                        '-c:a', 'aac',
                        '-b:a', '256k',
                        '-ar', '44100',
                        '-ac', '2',
                        '-af', 'volume=3.0,highpass=f=80,lowpass=f=15000',
                        '-async', '1',
                        '-vsync', '1',
                        output_path
                    ]
        else:
            cmd = [
                ffmpeg, '-y', 
                '-f', 'avfoundation', 
                '-video_size', '1280x720',
                '-framerate', '30',
                '-i', str(device_index), 
                '-t', str(duration_sec),
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-crf', '23',
                output_path
            ]
    else:
        # Linux için
        video_device = f"/dev/video{device_index}"
        if with_audio:
            cmd = [ffmpeg, '-y', '-f', 'v4l2', '-i', video_device, '-f', 'alsa', '-i', 'default', '-t', str(duration_sec), output_path]
        else:
            cmd = [ffmpeg, '-y', '-f', 'v4l2', '-i', video_device, '-t', str(duration_sec), output_path]
    
    print(f"FFmpeg kayıt komutu: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration_sec + 30)
        
        if result.returncode == 0:
            print(f"✅ FFmpeg kayıt tamamlandı: {output_path}")
            return True
        else:
            print(f"❌ FFmpeg hatası: {result.stderr}")
            
            # Ses ile kayıt başarısız olduysa, sadece video ile dene
            if with_audio and platform.system() == "Darwin":
                print("Ses ile kayıt başarısız, sadece video ile tekrar deneniyor...")
                video_only_cmd = [
                    ffmpeg, '-y', 
                    '-f', 'avfoundation', 
                    '-video_size', '1280x720',
                    '-framerate', '30',
                    '-i', str(device_index), 
                    '-t', str(duration_sec),
                    '-c:v', 'libx264',
                    '-preset', 'ultrafast',
                    '-crf', '23',
                    output_path
                ]
                
                print(f"Video-only FFmpeg komutu: {' '.join(video_only_cmd)}")
                video_result = subprocess.run(video_only_cmd, capture_output=True, text=True, timeout=duration_sec + 30)
                
                if video_result.returncode == 0:
                    print(f"✅ Video-only kayıt tamamlandı: {output_path}")
                    return True
                else:
                    print(f"❌ Video-only FFmpeg hatası: {video_result.stderr}")
                    return False
            else:
                return False
                
    except subprocess.TimeoutExpired:
        print("❌ FFmpeg zaman aşımı")
        return False
    except Exception as e:
        print(f"❌ FFmpeg kayıt hatası: {e}")
        return False

def record_with_separate_audio_video(output_path: str, device_index: int = 0, duration_sec: int = 20):
    """Video ve sesi ayrı ayrı kaydet, sonra birleştir (daha güvenilir)"""
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("FFmpeg bulunamadı")
    
    # Çıktı klasörünü oluştur
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Geçici dosyalar
    video_temp = output_path.replace('.mp4', '_video_temp.mp4')
    audio_temp = output_path.replace('.mp4', '_audio_temp.wav')
    
    print("🎥 Video ve ses ayrı ayrı kaydediliyor...")
    
    # Geri sayım göster
    print("Kayıt başlamadan önce geri sayım...")
    for i in range(3, 0, -1):
        print(f"{i}...")
        time.sleep(1)
    print("Kayıt başlıyor!")
    
    try:
        # 1. Sadece video kaydet
        print("📹 Video kaydı başlıyor...")
        video_cmd = [
            ffmpeg, '-y',
            '-f', 'avfoundation',
            '-video_size', '1280x720',
            '-framerate', '30',
            '-i', str(device_index),
            '-t', str(duration_sec),
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '23',
            video_temp
        ]
        
        video_result = subprocess.run(video_cmd, capture_output=True, text=True, timeout=duration_sec + 30)
        
        if video_result.returncode != 0:
            print(f"❌ Video kayıt hatası: {video_result.stderr}")
            return False
        
        print("✅ Video kaydı tamamlandı")
        
        # 2. Sadece ses kaydet (Rode mikrofon ile)
        print("🎤 Ses kaydı başlıyor...")
        rode_audio_device = get_rode_audio_device_index()
        
        if rode_audio_device is not None:
            print(f"🎤 Rode mikrofon kullanılıyor (cihaz: {rode_audio_device})")
            audio_cmd = [
                ffmpeg, '-y',
                '-f', 'avfoundation',
                '-i', f':{rode_audio_device}',
                '-t', str(duration_sec),
                '-c:a', 'pcm_s24le',  # 24-bit PCM
                '-ar', '48000',  # 48kHz
                '-ac', '2',  # Stereo
                '-af', 'volume=3.0,highpass=f=100,lowpass=f=12000,compand=.3|.3:1|1:-90/-60|-60/-40|-40/-30|-20/-20:6:0:-90:0.2',
                audio_temp
            ]
        else:
            print("⚠️ Rode bulunamadı, varsayılan ses cihazı kullanılıyor...")
            audio_devices = get_available_audio_devices()
            audio_device = audio_devices[0] if audio_devices else 0
            
            audio_cmd = [
                ffmpeg, '-y',
                '-f', 'avfoundation',
                '-i', f':{audio_device}',
                '-t', str(duration_sec),
                '-c:a', 'pcm_s16le',  # 16-bit PCM
                '-ar', '44100',  # 44.1kHz
                '-ac', '2',  # Stereo
                '-af', 'volume=3.0,highpass=f=80,lowpass=f=15000',
                audio_temp
            ]
        
        audio_result = subprocess.run(audio_cmd, capture_output=True, text=True, timeout=duration_sec + 30)
        
        if audio_result.returncode != 0:
            print(f"❌ Ses kayıt hatası: {audio_result.stderr}")
            # Sadece video ile devam et
            if os.path.exists(video_temp):
                os.rename(video_temp, output_path)
                print("✅ Sadece video kaydedildi")
                return True
            return False
        
        print("✅ Ses kaydı tamamlandı")
        
        # 3. Video ve sesi birleştir
        print("🔗 Video ve ses birleştiriliyor...")
        merge_cmd = [
            ffmpeg, '-y',
            '-i', video_temp,
            '-i', audio_temp,
            '-c:v', 'copy',  # Video'yu yeniden encode etme
            '-c:a', 'aac',
            '-b:a', '320k',
            '-ar', '48000',
            '-ac', '2',
            '-shortest',  # En kısa dosyaya göre kes
            '-map', '0:v:0',  # İlk dosyadan video
            '-map', '1:a:0',  # İkinci dosyadan ses
            output_path
        ]
        
        merge_result = subprocess.run(merge_cmd, capture_output=True, text=True, timeout=60)
        
        if merge_result.returncode != 0:
            print(f"❌ Birleştirme hatası: {merge_result.stderr}")
            return False
        
        print("✅ Video ve ses başarıyla birleştirildi")
        
        # Geçici dosyaları temizle
        try:
            if os.path.exists(video_temp):
                os.remove(video_temp)
            if os.path.exists(audio_temp):
                os.remove(audio_temp)
            print("🧹 Geçici dosyalar temizlendi")
        except Exception as e:
            print(f"⚠️ Geçici dosya temizleme hatası: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Kayıt hatası: {e}")
        return False

def record_with_opencv_and_sounddevice(output_path: str, device_index: int = 0, duration_sec: int = 20):
    """macOS native OpenCV + sounddevice ile kayıt (basit yöntem)"""
    print("🎥 macOS native OpenCV + sounddevice ile kayıt yapılıyor...")
    
    # Çıktı klasörünü oluştur
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # macOS için AVFoundation backend kullan
    cap = cv2.VideoCapture(device_index, cv2.CAP_AVFOUNDATION)
    
    if not cap.isOpened():
        print("❌ Hata: Kamera açılamadı!")
        return False
    
    try:
        # Video ayarları
        width = 1280
        height = 720
        fps = 30
        
        # Kamera ayarları
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)
        
        # Dosya adları
        video_file = output_path.replace('.mp4', '_video.mp4')
        final_file = output_path
        
        # Video yazıcı oluştur
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(video_file, fourcc, fps, (width, height))
        
        if not out.isOpened():
            print("❌ Video yazıcı açılamadı!")
            return False
        
        print(f"Kayıt başlıyor: {final_file}")
        print(f"{duration_sec} saniye boyunca video ve ses kaydı yapılacak...")
        
        # Geri sayım
        print("\nGeri sayım:")
        for i in range(3, 0, -1):
            print(f"  {i}...")
            time.sleep(1)
        print("  🎬 Kayıt başladı!")
        
        # Rode mikrofon ile ses kaydını başlat (ayrı thread'de)
        rode_device = find_rode_device()
        device_index_audio = rode_device[0] if rode_device else None
        
        # Ses kaydı fonksiyonu
        def ses_kaydet():
            try:
                print("🎤 Ses kaydı başlıyor...")
                
                # Rode mikrofon ayarları
                if rode_device:
                    print(f"🎤 Rode mikrofon kullanılıyor: {rode_device[1]}")
                    sample_rate = 48000
                    channels = 2
                else:
                    print("⚠️ Rode bulunamadı, varsayılan ses cihazı kullanılıyor")
                    sample_rate = 44100
                    channels = 1
                
                # Ses kaydı
                audio_data = sd.rec(
                    int(duration_sec * sample_rate), 
                    samplerate=sample_rate, 
                    channels=channels, 
                    dtype='float32',
                    device=device_index_audio
                )
                
                # Kayıt bitene kadar bekle
                sd.wait()
                
                # WAV dosyası olarak kaydet
                wav_dosya = video_file.replace('.mp4', '.wav')
                sf.write(wav_dosya, audio_data, sample_rate)
                
                print(f"✅ Ses kaydı tamamlandı: {wav_dosya}")
                return wav_dosya
                
            except Exception as e:
                print(f"❌ Ses kaydı hatası: {e}")
                return None
        
        # Ses kaydını başlat (ayrı thread'de)
        ses_thread = threading.Thread(target=ses_kaydet)
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
            remaining = duration_sec - elapsed
            
            # İlerleme göster (her saniye)
            if frame_count % 30 == 0:
                print(f"📹 Kayıt: {elapsed:.1f}s / {duration_sec}s (Kalan: {remaining:.1f}s)")
            
            # Süre doldu mu kontrol et
            if elapsed >= duration_sec:
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
            
            # Video ve sesi birleştir
            ffmpeg = get_ffmpeg_path()
            if ffmpeg:
                merge_cmd = [
                    ffmpeg, '-y',
                    '-i', video_file,
                    '-i', ses_dosya,
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-b:a', '320k',
                    '-shortest',
                    final_file
                ]
                
                merge_result = subprocess.run(merge_cmd, capture_output=True, text=True, timeout=60)
                
                if merge_result.returncode == 0:
                    print("✅ Video ve ses başarıyla birleştirildi")
                    
                    # Geçici dosyaları temizle
                    try:
                        os.remove(video_file)
                        os.remove(ses_dosya)
                        print("🧹 Geçici dosyalar temizlendi")
                    except Exception as e:
                        print(f"⚠️ Geçici dosya temizleme hatası: {e}")
                    
                    return True
                else:
                    print(f"❌ Birleştirme hatası: {merge_result.stderr}")
                    return False
            else:
                print("❌ FFmpeg bulunamadı, birleştirme yapılamıyor")
                return False
        else:
            print(f"📹 Video kaydı (ses yok): {video_file}")
            return True
            
    except Exception as e:
        print(f"❌ Kayıt hatası: {e}")
        return False
    
    finally:
        # Kamera kapat
        if cap is not None:
            try:
                cap.release()
            except Exception as e:
                print(f"Kamera kapatma hatası: {e}")
        try:
            cv2.destroyAllWindows()
        except Exception as e:
            print(f"Pencere kapatma hatası: {e}")

def record_with_ffmpeg(output_path: str, device_index: int = 0, duration_sec: int = 20, with_audio: bool = True):
    """Ana kayıt fonksiyonu - farklı yöntemleri dener"""
    print("🎥 Video kayıt yöntemleri deneniyor...")
    
    # Önce OpenCV + sounddevice yöntemini dene (macOS native)
    print("\n1️⃣ OpenCV + sounddevice yöntemi deneniyor (macOS native)...")
    if record_with_opencv_and_sounddevice(output_path, device_index, duration_sec):
        return True
    
    # Başarısız olursa geliştirilmiş FFmpeg yöntemini dene
    print("\n2️⃣ Geliştirilmiş FFmpeg yöntemi deneniyor...")
    if record_with_ffmpeg_improved(output_path, device_index, duration_sec, with_audio):
        return True
    
    # Son olarak ayrı kayıt yöntemini dene
    if with_audio:
        print("\n3️⃣ Ayrı video/ses kayıt yöntemi deneniyor...")
        if record_with_separate_audio_video(output_path, device_index, duration_sec):
            return True
    
    print("\n❌ Tüm yöntemler başarısız oldu")
    return False

def main():
    """Ana fonksiyon - 20 saniye video çek"""
    print("🎥 20 Saniye Video Çekme Aracı (macOS Native + Rode)")
    print("=" * 55)
    
    # Çıktı dosyası adını oluştur
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"video_native_{timestamp}.mp4")
    
    print(f"📁 Çıktı dosyası: {output_path}")
    print(f"⏱️  Süre: 10 saniye")
    print(f"🎤 Ses: macOS Native + Rode Wireless GO 2")
    print(f"📹 Video: OpenCV + AVFoundation")
    print(f"🔧 Yöntem: OpenCV + sounddevice (FFmpeg yerine)")
    print()
    
    # Rode cihazını kontrol et
    rode_device = find_rode_device()
    if rode_device:
        print(f"✅ Rode cihazı tespit edildi: {rode_device[1]}")
        print(f"   • Ses cihazı ID: {rode_device[0]}")
        print(f"   • Örnekleme hızı: 48kHz")
        print(f"   • Kanal: Stereo (2)")
    else:
        print("⚠️ Rode cihazı bulunamadı, varsayılan ses cihazı kullanılacak")
        print("   • Örnekleme hızı: 44.1kHz")
        print("   • Kanal: Mono (1)")
    
    print()
    
    try:
        # Video çek
        success = record_with_ffmpeg(output_path, device_index=0, duration_sec=10, with_audio=True)
        
        if success:
            print(f"\n🎉 Video başarıyla çekildi!")
            print(f"📁 Dosya konumu: {os.path.abspath(output_path)}")
            
            # Dosya boyutunu göster
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                file_size_mb = file_size / (1024 * 1024)
                print(f"📊 Dosya boyutu: {file_size_mb:.2f} MB")
                
                # Ses ve video bilgilerini göster
                print(f"\n📋 Video Bilgileri:")
                print(f"   • Çözünürlük: 1280x720")
                print(f"   • FPS: 30")
                print(f"   • Video Codec: H.264 (libx264)")
                print(f"   • Ses Codec: AAC 320kbps @ 48kHz")
                print(f"   • Mikrofon: {'Rode Wireless GO 2' if rode_device else 'Varsayılan'}")
                print(f"   • Kayıt Yöntemi: macOS Native (OpenCV + sounddevice)")
        else:
            print(f"\n❌ Video çekme başarısız!")
            return 1
            
    except KeyboardInterrupt:
        print(f"\n⏹️  Kayıt kullanıcı tarafından durduruldu.")
        return 1
    except Exception as e:
        print(f"\n❌ Hata: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
