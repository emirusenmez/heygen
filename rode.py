#!/usr/bin/env python3
"""
Rode Wireless GO 2 Mikrofon Test Kodu
Bu kod Rode Wireless GO 2 mikrofonunuzla ses kaydı yapmanızı sağlar.
"""

import sounddevice as sd
import soundfile as sf
import numpy as np
import time
import os
from datetime import datetime
import threading
import queue

class RodeMicrophoneTest:
    def __init__(self):
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.sample_rate = 44100
        self.channels = 1  # Mono kayıt
        self.chunk_size = 1024
        
    def list_audio_devices(self):
        """Sistemdeki tüm ses cihazlarını listeler"""
        print("🔍 Mevcut ses cihazları:")
        print("-" * 50)
        
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:  # Sadece giriş cihazları
                print(f"ID: {i} | {device['name']}")
                print(f"    Giriş kanalları: {device['max_input_channels']}")
                print(f"    Örnekleme hızı: {device['default_samplerate']}")
                print()
    
    def find_rode_device(self):
        """Rode cihazını otomatik olarak bulur"""
        devices = sd.query_devices()
        rode_devices = []
        
        for i, device in enumerate(devices):
            device_name = device['name'].lower()
            
            # Rode cihazlarını tespit et
            if any(keyword in device_name for keyword in ['rode', 'wireless', 'go']):
                rode_devices.append((i, device))
        
        return rode_devices
    
    def test_microphone_levels(self, device_index=None, duration=5):
        """Mikrofon seviyelerini test eder"""
        print(f"🎤 Mikrofon seviye testi başlıyor... ({duration} saniye)")
        print("Konuşun ve seviyeleri izleyin...")
        print("-" * 50)
        
        try:
            def audio_callback(indata, frames, time, status):
                if status:
                    print(f"Status: {status}")
                
                # RMS (Root Mean Square) hesapla
                rms = np.sqrt(np.mean(indata**2))
                
                # Seviye çubuğu oluştur
                level = min(int(rms * 1000), 50)  # 0-50 arası normalize et
                bar = "█" * level + "░" * (50 - level)
                
                # Gerçek zamanlı seviye göster
                print(f"\rSeviye: {bar} {rms:.4f}", end="", flush=True)
            
            with sd.InputStream(device=device_index, 
                              channels=self.channels, 
                              samplerate=self.sample_rate,
                              callback=audio_callback):
                time.sleep(duration)
            
            print("\n✅ Seviye testi tamamlandı!")
            
        except Exception as e:
            print(f"❌ Hata: {e}")
    
    def record_audio(self, filename=None, duration=10, device_index=None):
        """Ses kaydı yapar"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rode_test_{timestamp}.wav"
        
        print(f"🎙️  Kayıt başlıyor: {filename}")
        print(f"⏱️  Süre: {duration} saniye")
        print("Kaydı durdurmak için Ctrl+C basın...")
        print("-" * 50)
        
        try:
            # Ses kaydı yap
            recording = sd.rec(int(duration * self.sample_rate), 
                             samplerate=self.sample_rate, 
                             channels=self.channels,
                             device=device_index)
            
            # İlerleme göster
            start_time = time.time()
            while sd.get_stream().active:
                elapsed = time.time() - start_time
                progress = int((elapsed / duration) * 50)
                bar = "█" * progress + "░" * (50 - progress)
                print(f"\rİlerleme: {bar} {elapsed:.1f}/{duration}s", end="", flush=True)
                time.sleep(0.1)
            
            # Kaydı bekle
            sd.wait()
            
            # WAV dosyasına kaydet
            sf.write(filename, recording, self.sample_rate)
            
            print(f"\n✅ Kayıt tamamlandı: {filename}")
            print(f"📁 Dosya boyutu: {os.path.getsize(filename)} bytes")
            
        except KeyboardInterrupt:
            print("\n⏹️  Kayıt kullanıcı tarafından durduruldu")
        except Exception as e:
            print(f"\n❌ Kayıt hatası: {e}")
    
    def continuous_monitoring(self, device_index=None):
        """Sürekli ses seviyesi izleme"""
        print("🔊 Sürekli ses izleme başlıyor...")
        print("Çıkmak için Ctrl+C basın")
        print("-" * 50)
        
        try:
            def audio_callback(indata, frames, time, status):
                if status:
                    print(f"Status: {status}")
                
                rms = np.sqrt(np.mean(indata**2))
                peak = np.max(np.abs(indata))
                
                # Seviye çubuğu
                level = min(int(rms * 1000), 50)
                bar = "█" * level + "░" * (50 - level)
                
                # Peak göstergesi
                peak_level = min(int(peak * 1000), 50)
                peak_bar = "█" * peak_level + "░" * (50 - peak_level)
                
                print(f"\rRMS: {bar} {rms:.4f} | Peak: {peak_bar} {peak:.4f}", end="", flush=True)
            
            with sd.InputStream(device=device_index, 
                              channels=self.channels, 
                              samplerate=self.sample_rate,
                              callback=audio_callback):
                while True:
                    time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n⏹️  İzleme durduruldu")
        except Exception as e:
            print(f"\n❌ İzleme hatası: {e}")
    
    def cleanup(self):
        """Kaynakları temizler"""
        # sounddevice otomatik olarak kaynakları temizler
        pass

def main():
    print("🎤 Rode Wireless GO 2 Mikrofon Test Aracı")
    print("=" * 50)
    
    rode_test = RodeMicrophoneTest()
    
    try:
        while True:
            print("\n📋 Menü:")
            print("1. Ses cihazlarını listele")
            print("2. Rode cihazını bul")
            print("3. Mikrofon seviye testi")
            print("4. Ses kaydı yap")
            print("5. Sürekli ses izleme")
            print("6. Çıkış")
            
            choice = input("\nSeçiminizi yapın (1-6): ").strip()
            
            if choice == "1":
                rode_test.list_audio_devices()
                
            elif choice == "2":
                rode_devices = rode_test.find_rode_device()
                if rode_devices:
                    print("🎯 Bulunan Rode cihazları:")
                    for device_id, device_info in rode_devices:
                        print(f"ID: {device_id} | {device_info['name']}")
                else:
                    print("❌ Rode cihazı bulunamadı")
                    
            elif choice == "3":
                device_id = input("Cihaz ID'si (boş bırakırsanız varsayılan): ").strip()
                device_index = int(device_id) if device_id else None
                duration = int(input("Test süresi (saniye, varsayılan 5): ") or "5")
                rode_test.test_microphone_levels(device_index, duration)
                
            elif choice == "4":
                device_id = input("Cihaz ID'si (boş bırakırsanız varsayılan): ").strip()
                device_index = int(device_id) if device_id else None
                duration = int(input("Kayıt süresi (saniye, varsayılan 10): ") or "10")
                filename = input("Dosya adı (boş bırakırsanız otomatik): ").strip() or None
                rode_test.record_audio(filename, duration, device_index)
                
            elif choice == "5":
                device_id = input("Cihaz ID'si (boş bırakırsanız varsayılan): ").strip()
                device_index = int(device_id) if device_id else None
                rode_test.continuous_monitoring(device_index)
                
            elif choice == "6":
                print("👋 Çıkılıyor...")
                break
                
            else:
                print("❌ Geçersiz seçim!")
                
    except KeyboardInterrupt:
        print("\n👋 Program sonlandırılıyor...")
    finally:
        rode_test.cleanup()

if __name__ == "__main__":
    main()
