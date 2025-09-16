#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
App.py Stilinde Kamera Video Kaydı ve Alt Yazı Ekleme Aracı
App.py'deki kayıt yöntemini kullanarak video kaydı yapar, sesi metne çevirir ve videoya kayan band ekler
"""

import os
import sys
import cv2
import numpy as np
from datetime import datetime
import tempfile
import speech_recognition as sr
import subprocess
import time
import shutil
import threading
import sounddevice as sd
import soundfile as sf
import uuid

def get_ffmpeg_path() -> str | None:
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

def find_rode_device() -> tuple[int, str] | None:
    """Rode Wireless GO 2 cihazını tespit et, yoksa en iyi mikrofonu bul"""
    try:
        # sounddevice ile cihazları listele
        devices = sd.query_devices()
        
        # Önce Rode cihazlarını ara
        for i, device in enumerate(devices):
            device_name = device['name'].lower()
            if any(keyword in device_name for keyword in ['rode', 'wireless', 'go']):
                print(f"🎤 Rode cihazı bulundu: {device['name']} (ID: {i})")
                return i, device['name']
        
        # Rode bulunamazsa en iyi mikrofonu bul
        print("❌ Rode cihazı bulunamadı, en iyi mikrofon aranıyor...")
        
        # Mikrofonları öncelik sırasına göre ara
        preferred_names = ['efemiir', 'macbook', 'teams', 'mikrofon', 'microphone']
        
        for preferred in preferred_names:
            for i, device in enumerate(devices):
                device_name = device['name'].lower()
                if preferred in device_name and device['max_input_channels'] > 0:
                    print(f"🎤 En iyi mikrofon bulundu: {device['name']} (ID: {i})")
                    return i, device['name']
        
        # Son çare: ilk mikrofonu kullan
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                print(f"🎤 Varsayılan mikrofon: {device['name']} (ID: {i})")
                return i, device['name']
        
        print("❌ Hiçbir mikrofon bulunamadı")
        return None
        
    except Exception as e:
        print(f"Mikrofon tespit hatası: {e}")
        return None

def ses_kaydet(sure, dosya_adi, device_index=None):
    """Rode mikrofon ile kaliteli ses kaydı yapar - cızırtı önleyici ayarlar"""
    try:
        # SoundDevice ayarlarını optimize et (cızırtı önleyici)
        sd.default.latency = ('low', 'low')  # Düşük gecikme
        sd.default.blocksize = 1024  # Sabit blok boyutu
        
        # Rode mikrofon için optimize edilmiş ayarlar
        sample_rate = 48000  # Rode için 48kHz (doğal)
        channels = 1  # Mono kayıt (Rode tek kapsül için daha temiz)
        
        print(f"🎤 Rode mikrofon ile ses kaydı başlıyor... ({channels} kanal, {sample_rate}Hz)")
        
        # Rode cihazını kullan, yoksa varsayılan cihazı kullan
        if device_index is None:
            rode_device = find_rode_device()
            if rode_device:
                device_index = rode_device[0]
                print(f"🎤 Rode cihazı kullanılıyor: {rode_device[1]}")
            else:
                print("⚠️ Rode cihazı bulunamadı, varsayılan cihaz kullanılıyor")
        
        # Kaliteli ses kaydı (clipping önleyici)
        try:
            audio_data = sd.rec(int(sure * sample_rate), 
                               samplerate=sample_rate, 
                               channels=channels, 
                               dtype='float32',  # Yüksek kalite
                               device=device_index)
            
            # Kayıt bitene kadar bekle
            sd.wait()
        except Exception as e:
            print(f"❌ Rode ses kaydı hatası: {e}")
            print("🔄 Varsayılan ayarlarla tekrar deneniyor...")
            try:
                # Varsayılan cihaz ile tekrar dene
                audio_data = sd.rec(int(sure * sample_rate), 
                                   samplerate=sample_rate, 
                                   channels=channels, 
                                   dtype='float32')
                sd.wait()
            except Exception as e2:
                print(f"❌ Varsayılan ses kaydı da başarısız: {e2}")
                return None
        
        # Ses seviyesini kontrol et ve artır
        max_amplitude = np.max(np.abs(audio_data))
        print(f"🎤 Maksimum ses genliği: {max_amplitude:.6f}")
        
        if max_amplitude < 0.1:  # Düşük seviye
            gain = 0.1 / max_amplitude if max_amplitude > 0 else 1000
            gain = min(gain, 1000)  # Maksimum 1000x yükselt
            print(f"🔊 Ses seviyesi düşük, {gain:.1f}x yükseltiliyor...")
            audio_data = audio_data * gain
            # Clipping kontrolü
            audio_data = np.clip(audio_data, -1.0, 1.0)
        
        # WAV dosyası olarak kaydet (24-bit kalite)
        wav_dosya = dosya_adi.replace('.mp4', '.wav')
        sf.write(wav_dosya, audio_data, sample_rate, subtype='PCM_24')
        
        print(f"✅ Rode ses kaydı tamamlandı: {wav_dosya}")
        return wav_dosya
        
    except Exception as e:
        print(f"❌ Rode ses kaydı hatası: {e}")
        # Hata durumunda varsayılan ayarlarla dene
        try:
            print("🔄 Varsayılan ayarlarla tekrar deneniyor...")
            sample_rate = 44100
            channels = 1
            
            audio_data = sd.rec(int(sure * sample_rate), 
                               samplerate=sample_rate, 
                               channels=channels, 
                               dtype='float32',
                               device=None)
            
            sd.wait()
            
            # Ses seviyesini kontrol et ve artır
            max_amplitude = np.max(np.abs(audio_data))
            print(f"🎤 Maksimum ses genliği: {max_amplitude:.6f}")
            
            if max_amplitude < 0.1:  # Düşük seviye
                gain = 0.1 / max_amplitude if max_amplitude > 0 else 1000
                gain = min(gain, 1000)  # Maksimum 1000x yükselt
                print(f"🔊 Ses seviyesi düşük, {gain:.1f}x yükseltiliyor...")
                audio_data = audio_data * gain
                # Clipping kontrolü
                audio_data = np.clip(audio_data, -1.0, 1.0)
            
            wav_dosya = dosya_adi.replace('.mp4', '.wav')
            sf.write(wav_dosya, audio_data, sample_rate)
            
            print(f"✅ Varsayılan ses kaydı tamamlandı: {wav_dosya}")
            return wav_dosya
            
        except Exception as e2:
            print(f"❌ Varsayılan ses kaydı da başarısız: {e2}")
            return None

def mux_with_ffmpeg(video_path: str, audio_path: str, output_path: str, audio_tempo: float | None = None) -> bool:
    """Video ve sesi FFmpeg ile birleştirir"""
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        return False
    
    # Cızırtı önleyici ayarlar: büyük thread queue, pan + yumuşak resample
    # Dinamik ses zamanlama düzeltmesi (atempo) için filtre zinciri oluştur
    afilters = [
        'highpass=80',
        'lowpass=15000',
        'aresample=async=1000:min_hard_comp=0.100:first_pts=0'
    ]
    if audio_tempo and 0.5 <= audio_tempo <= 2.0 and abs(audio_tempo - 1.0) > 0.01:
        afilters.append(f'atempo={audio_tempo:.4f}')

    cmd = [
        ffmpeg, '-y',
        '-thread_queue_size', '4096', '-i', video_path,
        '-thread_queue_size', '4096', '-i', audio_path,
        '-map', '0:v:0', '-map', '1:a:0',
        # Videoyu CFR 30fps yeniden kodla ve süreyi sabitle
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p',
        '-fps_mode', 'cfr', '-r', '30',
        # Sesi kodla ve filtreleri uygula
        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '1',
        '-af', ','.join(afilters),
        # Çıkış süresini sabitle
        '-t', '10',
        '-movflags', '+faststart',
        output_path
    ]
    
    print("FFmpeg komutu:", ' '.join(cmd))
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        print("FFmpeg hata kodu:", proc.returncode)
        try:
            print("FFmpeg stderr:\n", proc.stderr.decode('utf-8', errors='ignore'))
        except Exception:
            pass
        return False
    return True

def transcribe_audio_to_text(wav_path: str, language: str = 'tr-TR') -> str:
    """WAV dosyasını metne çevirir"""
    if not os.path.exists(wav_path):
        return ""
    if sr is None:
        print("speech_recognition modülü yok, altyazı metni oluşturulamadı")
        return ""
    try:
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.2)
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio, language=language)
        print(f"📝 STT metni: {text[:120]}{'...' if len(text) > 120 else ''}")
        return text
    except Exception as e:
        print(f"STT hata: {e}")
        return ""

def burn_scrolling_text_band(input_mp4: str, output_mp4: str, text: str,
                             band_height: int = 80, opacity: float = 0.6,
                             font_size: int = 36, scroll_speed_px_s: int = 180,
                             font_path: str | None = None, duration_s: int = 10) -> bool:
    """Altta yarı saydam bant üzerinde sağdan sola kayan metni videoya basar."""
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        return False
    if not text:
        # Metin yoksa sadece kopyala
        cmd = [ffmpeg, '-y', '-i', input_mp4, '-c', 'copy', output_mp4]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.returncode == 0

    # Geçici metin dosyası (ASCII yol kullan; /tmp)
    try:
        tmp_txt = os.path.join('/tmp', f"scroll_text_{uuid.uuid4().hex}.txt")
        with open(tmp_txt, 'w', encoding='utf-8') as f:
            f.write(text.replace('\n', ' '))
    except Exception as e:
        print(f"Metin dosyası yazılamadı: {e}")
        return False

    # Opaklık: drawbox alpha 0..1; bant konumu: alt kısım
    # Scroll ifadesi: x = w - mod(t*speed\, text_w + w)
    # text_w için tahmini genişlik yerine drawtext'in internal ölçümü kullanmak için uzun döngü gerektirir; pratikte büyük bir döngü ile mod yapılır.
    # Font: macOS yaygın yolları sırayla dene; path'i drawtext için kaçır
    def _escape_for_drawtext_path(p: str) -> str:
        # ffmpeg drawtext için basit kaçışlar
        return p.replace('\\', r'\\').replace(':', r'\:').replace("'", r"\'").replace(',', r'\,').replace('=', r'\=').replace(' ', r'\ ')

    fontopt = []
    candidate_paths = []
    if font_path:
        candidate_paths.append(font_path)
    # macOS common
    candidate_paths += [
        '/System/Library/Fonts/Supplemental/Arial.ttf',
        '/Library/Fonts/Arial.ttf',
        '/System/Library/Fonts/Supplemental/Helvetica.ttf',
        '/Library/Fonts/Helvetica.ttf',
        '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
    ]
    chosen_font = None
    for p in candidate_paths:
        if p and os.path.exists(p):
            chosen_font = p
            break
    if chosen_font:
        fontopt = [':fontfile=' + _escape_for_drawtext_path(chosen_font)]
        print(f"drawtext fontfile kullanılıyor: {chosen_font}")
    else:
        print("drawtext için özel font bulunamadı; sistem varsayılanını deneyecek (fontconfig gerekebilir)")

    # Alttan kayan metin (siyah band ile) - yazılar bandın içinden kayıyor
    vf = (
        f"drawbox=x=0:y=640:w=1280:h={band_height}:color=black@{opacity}:t=fill,"
        f"drawtext=textfile='{tmp_txt}':fontcolor=white:fontsize={font_size}"
        + (''.join(fontopt)) +
        f":x=1280-t*{scroll_speed_px_s}:y=670"
    )

    cmd = [
        ffmpeg, '-y',
        '-i', input_mp4,
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p',
        '-fps_mode', 'cfr', '-r', '30',
        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '1',
        '-movflags', '+faststart',
        output_mp4
    ]
    print('FFmpeg (scroll band) komutu:', ' '.join(cmd))
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        print("FFmpeg hata kodu:", proc.returncode)
        try:
            print("FFmpeg stderr:\n", proc.stderr.decode('utf-8', errors='ignore'))
        except Exception:
            pass
        try:
            if os.path.exists(tmp_txt):
                os.remove(tmp_txt)
        except Exception:
            pass
        return False
    else:
        print("✅ Kayan bant başarıyla eklendi!")
    try:
        if os.path.exists(tmp_txt):
            os.remove(tmp_txt)
    except Exception:
        pass
    return True

def record_with_opencv_sounddevice_new(output_path: str, device_index: int = 0, duration_sec: int = 10, with_audio: bool = True):
    """OpenCV + SoundDevice ile kayıt (app.py yaklaşımı)"""
    import threading
    import time
    
    print(f"🎥 OpenCV + SoundDevice ile kayıt başlıyor...")
    print(f"📁 Çıktı: {output_path}")
    print(f"⏱️  Süre: {duration_sec} saniye")
    print(f"🎤 Ses: {'Evet' if with_audio else 'Hayır'}")
    
    # Çıktı klasörünü oluştur
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Geçici dosya adları
    video_file = output_path.replace('.mp4', '_temp_video.mp4')
    audio_file = output_path.replace('.mp4', '_temp_audio.wav')
    
    try:
        # 1. Kamera aç
        print("📹 Kamera açılıyor...")
        cap = cv2.VideoCapture(device_index, cv2.CAP_AVFOUNDATION)
        
        if not cap.isOpened():
            print("❌ Hata: Kamera açılamadı!")
            return False
        
        # Kamera ayarları
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        print("✅ Kamera başarıyla açıldı")
        
        # 2. Video yazıcı oluştur
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(video_file, fourcc, 30, (1280, 720))
        
        if not out.isOpened():
            print("❌ Video yazıcı açılamadı!")
            cap.release()
            return False
        
        # 3. Geri sayım (kayıt süresine dahil değil)
        print("Geri sayım başlıyor...")
        for i in range(3, 0, -1):
            print(f"{i}...")
            time.sleep(1)
        print("🎬 Kayıt başladı!")
        
        # 4. Ses ve videoyu AYNI ANDA başlat
        audio_thread = None
        if with_audio:
            print("🎤 Ses kaydı başlatılıyor...")
            rode_device = find_rode_device()
            device_index = rode_device[0] if rode_device else None
            audio_thread = threading.Thread(target=ses_kaydet, args=(duration_sec, audio_file, device_index), daemon=True)
            audio_thread.start()
        
        # 6. Video kayıt döngüsü (geri sayım + 2 saniye sonrası başlar)
        print("🎬 Video kaydı başlıyor...")
        start_time = time.time()
        frame_count = 0
        target_frames = duration_sec * 30  # 10 saniye = 300 frame (30 FPS)
        
        while frame_count < target_frames:
            # Frame sayısına göre kontrol (tam 10 saniye için)
            if frame_count >= target_frames:
                print(f"✅ Hedef frame sayısına ulaşıldı: {frame_count}/{target_frames}")
                break
                
            # Frame oku
            ret, frame = cap.read()
            
            if not ret:
                print("❌ Hata: Frame okunamadı!")
                break
            
            # Frame'i yeniden boyutlandır
            frame = cv2.resize(frame, (1280, 720))
            
            # Frame'i videoya yaz
            out.write(frame)
            
            frame_count += 1
            elapsed = time.time() - start_time
            remaining = duration_sec - elapsed
            
            # İlerleme göster (her saniye)
            if frame_count % 30 == 0:
                print(f"📹 Kayıt: {elapsed:.1f}s / {duration_sec}s (Kalan: {remaining:.1f}s)")
        
        # 5. Video kaydını bitir
        try:
            out.release()
            cap.release()
            cv2.destroyAllWindows()
            print("✅ Video kaydı tamamlandı")
        except Exception as e:
            print(f"Kaynak temizleme hatası: {e}")
        
        # 6. Ses kaydının bitmesini bekle
        if with_audio and audio_thread:
            print("🎤 Ses kaydı bekleniyor...")
            audio_thread.join(timeout=10)
        
        # 7. Video ve sesi birleştir
        if with_audio and os.path.exists(audio_file):
            print("🔗 Video ve ses birleştiriliyor...")
            # Gerçek kayıt süresini ölç ve ses temposunu videoya uydur
            actual_duration = max(0.1, time.time() - start_time)
            tempo_factor = actual_duration / float(duration_sec)
            if 0.5 <= tempo_factor <= 2.0 and abs(tempo_factor - 1.0) > 0.01:
                print(f"⏱️  Gerçek süre: {actual_duration:.2f}s, Hedef: {duration_sec}s, atempo={tempo_factor:.4f}")
            else:
                print(f"⏱️  Gerçek süre: {actual_duration:.2f}s, Hedef: {duration_sec}s, atempo uygulanmayacak")
            
            # 7a. Önce mux -> muxed_path
            muxed_path = output_path
            if mux_with_ffmpeg(video_file, audio_file, muxed_path, tempo_factor):
                # 7b. STT: WAV silmeden önce metni çıkar
                try:
                    stt_text = ""
                    if os.path.exists(audio_file):
                        stt_text = transcribe_audio_to_text(audio_file)
                    elif os.path.exists(muxed_path.replace('.mp4', '.wav')):
                        stt_text = transcribe_audio_to_text(muxed_path.replace('.mp4', '.wav'))
                except Exception:
                    stt_text = ""

                # Geçici dosyaları sil (video_file her durumda silinir, audio_file STT sonrası silinir)
                try:
                    if os.path.exists(video_file):
                        os.remove(video_file)
                    if os.path.exists(audio_file):
                        os.remove(audio_file)
                    print("🧹 Geçici dosyalar temizlendi")
                except Exception as e:
                    print(f"⚠️ Geçici dosya temizleme hatası: {e}")

                # Kayan bant sadece metin varsa basılır
                if stt_text:
                    banded_path = os.path.splitext(muxed_path)[0] + '.band.mp4'
                    font_candidate = '/Library/Fonts/Arial.ttf'
                    ok_band = burn_scrolling_text_band(
                        muxed_path, banded_path, stt_text,
                        band_height=80, opacity=0.6, font_size=36,
                        scroll_speed_px_s=250, font_path=font_candidate if os.path.exists(font_candidate) else None,
                        duration_s=duration_sec
                    )
                    if ok_band:
                        try:
                            os.replace(banded_path, muxed_path)
                        except Exception as rep_err:
                            print(f"Bantlı videoyu yerine koyma hatası: {rep_err}")
                    else:
                        print("Kayan bant eklenemedi, orijinal mux dosyası kullanılacak.")

                print(f"✅ Kayıt tamamlandı: {muxed_path}")
                return True
            else:
                print("❌ Video-ses birleştirme başarısız")
                # Video dosyasını final konuma taşı
                try:
                    os.rename(video_file, output_path)
                    print(f"📹 Video kaydı (ses yok): {output_path}")
                    return True
                except Exception as e:
                    print(f"❌ Video dosyası taşıma hatası: {e}")
                    return False
        else:
            # Sadece video
            try:
                os.rename(video_file, output_path)
                print(f"📹 Video kaydı (ses yok): {output_path}")
                return True
            except Exception as e:
                print(f"❌ Video dosyası taşıma hatası: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Kayıt hatası: {e}")
        return False
    finally:
        # Kaynakları temizle
        try:
            if 'cap' in locals() and cap is not None:
                cap.release()
            if 'out' in locals() and out is not None:
                out.release()
            cv2.destroyAllWindows()
        except Exception as cleanup_error:
            print(f"Cleanup error: {cleanup_error}")

def main():
    """
    Ana fonksiyon - App.py stilinde otomatik işlem
    """
    print("🤖 App.py Stilinde Kamera Video Kaydı ve Alt Yazı Ekleme Aracı")
    print("=" * 70)
    print("📹 10 saniye kamera kaydı yapılacak")
    print("🎵 Ses metne çevrilecek")
    print("🎬 Video'ya kayan band alt yazı eklenecek")
    print("💾 Sonuçlar /Users/emirefeusenmez/code/heygen/text klasörüne kaydedilecek")
    print("=" * 70)
    
    # Hedef klasör
    hedef_klasor = "/Users/emirefeusenmez/code/heygen/text"
    
    try:
        # 1. Kamera ile video kaydet (app.py yöntemi)
        print("\n🎬 ADIM 1: App.py yöntemi ile kamera kaydı")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(hedef_klasor, f"app_style_kamera_{timestamp}.mp4")
        
        success = record_with_opencv_sounddevice_new(output_path, device_index=0, duration_sec=10, with_audio=True)
        
        if success:
            print("\n🎉 TÜM İŞLEMLER TAMAMLANDI!")
            print("=" * 70)
            print(f"📹 Video dosyası: {output_path}")
            print("=" * 70)
        else:
            print("\n❌ Kayıt başarısız oldu!")
        
    except KeyboardInterrupt:
        print("\n❌ İşlem kullanıcı tarafından iptal edildi")
    except Exception as e:
        print(f"\n❌ Hata oluştu: {e}")

if __name__ == "__main__":
    main()
