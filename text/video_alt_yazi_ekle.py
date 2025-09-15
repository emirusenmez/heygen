#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Dosyasına Kayan Band Alt Yazı Ekleme Aracı
Video dosyasına metin dosyasından gelen yazıyı kayan band olarak ekler
"""

import os
import sys
import subprocess
from datetime import datetime
import tempfile

def video_alt_yazi_ekle(video_yolu, metin, cikti_yolu=None):
    """
    Video dosyasına kayan band alt yazı ekler
    """
    print(f"🎬 Video dosyasına alt yazı ekleniyor: {os.path.basename(video_yolu)}")
    print(f"📝 Alt yazı metni: {metin[:50]}...")
    
    try:
        # Çıktı dosyası yolu belirle
        if cikti_yolu is None:
            video_basename = os.path.splitext(os.path.basename(video_yolu))[0]
            cikti_yolu = f"{video_basename}_alt_yazili.mp4"
        
        # FFmpeg komutu ile kayan band alt yazı ekle
        cmd = [
            'ffmpeg',
            '-i', video_yolu,
            '-vf', f"drawtext=text='{metin}':fontfile=/System/Library/Fonts/Arial.ttf:fontsize=24:fontcolor=white:x=(w-text_w)/2:y=h-th-20:box=1:boxcolor=black@0.5:boxborderw=5",
            '-c:a', 'copy',  # Ses codec'ini değiştirme
            '-y',  # Overwrite output file
            cikti_yolu
        ]
        
        print("🔄 FFmpeg ile alt yazı ekleniyor...")
        print(f"Komut: {' '.join(cmd)}")
        
        # FFmpeg komutunu çalıştır
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Alt yazı başarıyla eklendi: {os.path.basename(cikti_yolu)}")
            return cikti_yolu
        else:
            print(f"❌ FFmpeg hatası: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"❌ Alt yazı ekleme hatası: {e}")
        return None

def video_kayan_band_alt_yazi_ekle(video_yolu, metin, cikti_yolu=None):
    """
    Video dosyasına kayan band (scrolling) alt yazı ekler
    """
    print(f"🎬 Video dosyasına kayan band alt yazı ekleniyor: {os.path.basename(video_yolu)}")
    print(f"📝 Alt yazı metni: {metin[:50]}...")
    
    try:
        # Çıktı dosyası yolu belirle
        if cikti_yolu is None:
            video_basename = os.path.splitext(os.path.basename(video_yolu))[0]
            cikti_yolu = f"{video_basename}_kayan_band.mp4"
        
        # Metni temizle (FFmpeg için özel karakterleri escape et)
        metin_temiz = metin.replace("'", "\\'").replace(":", "\\:").replace("\\", "\\\\").replace(")", "\\)").replace("(", "\\(")
        
        # FFmpeg komutu ile kayan band alt yazı ekle
        cmd = [
            'ffmpeg',
            '-i', video_yolu,
            '-vf', f"drawtext=text='{metin_temiz}':fontfile=/System/Library/Fonts/Arial.ttf:fontsize=28:fontcolor=white:x='if(gte(t,2),-w+(t-2)*50,0)':y=h-th-30:box=1:boxcolor=black@0.7:boxborderw=8",
            '-c:a', 'copy',  # Ses codec'ini değiştirme
            '-y',  # Overwrite output file
            cikti_yolu
        ]
        
        print("🔄 FFmpeg ile kayan band alt yazı ekleniyor...")
        print(f"Komut: {' '.join(cmd)}")
        
        # FFmpeg komutunu çalıştır
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Kayan band alt yazı başarıyla eklendi: {os.path.basename(cikti_yolu)}")
            return cikti_yolu
        else:
            print(f"❌ FFmpeg hatası: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"❌ Kayan band alt yazı ekleme hatası: {e}")
        return None

def video_alt_yazi_ekle_gelismis(video_yolu, metin, cikti_yolu=None):
    """
    Video dosyasına gelişmiş kayan band alt yazı ekler (daha güzel görünüm)
    """
    print(f"🎬 Video dosyasına gelişmiş kayan band alt yazı ekleniyor: {os.path.basename(video_yolu)}")
    print(f"📝 Alt yazı metni: {metin[:50]}...")
    
    try:
        # Çıktı dosyası yolu belirle
        if cikti_yolu is None:
            video_basename = os.path.splitext(os.path.basename(video_yolu))[0]
            cikti_yolu = f"{video_basename}_gelismis_alt_yazi.mp4"
        
        # Metni geçici dosyaya yaz
        temp_text_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8')
        temp_text_file.write(metin)
        temp_text_file.close()
        
        # Basit kayan band alt yazı (daha güvenli)
        cmd = [
            'ffmpeg',
            '-i', video_yolu,
            '-vf', f"drawtext=textfile={temp_text_file.name}:fontfile=/System/Library/Fonts/Arial.ttf:fontsize=28:fontcolor=white:x='if(gte(t,1),-w+(t-1)*30,0)':y=h-th-30:box=1:boxcolor=black@0.7:boxborderw=8",
            '-c:a', 'copy',  # Ses codec'ini değiştirme
            '-y',  # Overwrite output file
            cikti_yolu
        ]
        
        print("🔄 FFmpeg ile gelişmiş kayan band alt yazı ekleniyor...")
        print(f"Komut: {' '.join(cmd)}")
        
        # FFmpeg komutunu çalıştır
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Geçici dosyayı sil
        os.unlink(temp_text_file.name)
        
        if result.returncode == 0:
            print(f"✅ Gelişmiş kayan band alt yazı başarıyla eklendi: {os.path.basename(cikti_yolu)}")
            return cikti_yolu
        else:
            print(f"❌ FFmpeg hatası: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"❌ Gelişmiş kayan band alt yazı ekleme hatası: {e}")
        return None

def txt_dosyasindan_metin_oku(txt_dosyasi):
    """
    TXT dosyasından metin okur
    """
    try:
        with open(txt_dosyasi, 'r', encoding='utf-8') as f:
            icerik = f.read()
        
        # Başlık ve ayırıcıları temizle
        satirlar = icerik.split('\n')
        metin_satirlari = []
        
        for satir in satirlar:
            if not satir.startswith('=') and not satir.startswith('Kamera Video Kaydı') and not satir.startswith('Video Dosyası') and satir.strip():
                metin_satirlari.append(satir.strip())
        
        metin = ' '.join(metin_satirlari)
        return metin
        
    except Exception as e:
        print(f"❌ TXT dosyası okuma hatası: {e}")
        return None

def main():
    """
    Ana fonksiyon
    """
    print("🎬 Video Alt Yazı Ekleme Aracı")
    print("=" * 50)
    
    # Video dosyası yolunu al
    if len(sys.argv) > 1:
        video_yolu = sys.argv[1]
    else:
        video_yolu = input("📁 Video dosyasının yolunu girin: ").strip()
    
    # TXT dosyası yolunu al
    if len(sys.argv) > 2:
        txt_yolu = sys.argv[2]
    else:
        txt_yolu = input("📄 TXT dosyasının yolunu girin: ").strip()
    
    # Dosyalar var mı kontrol et
    if not os.path.exists(video_yolu):
        print(f"❌ Video dosyası bulunamadı: {video_yolu}")
        return
    
    if not os.path.exists(txt_yolu):
        print(f"❌ TXT dosyası bulunamadı: {txt_yolu}")
        return
    
    # Mutlak yol yap
    video_yolu = os.path.abspath(video_yolu)
    txt_yolu = os.path.abspath(txt_yolu)
    
    try:
        # 1. TXT dosyasından metin oku
        metin = txt_dosyasindan_metin_oku(txt_yolu)
        
        if not metin:
            print("❌ TXT dosyasından metin okunamadı!")
            return
        
        print(f"📝 Okunan metin: {metin[:100]}...")
        
        # 2. Alt yazı türünü seç
        print("\n🎨 Alt yazı türünü seçin:")
        print("1. Sabit alt yazı")
        print("2. Kayan band alt yazı")
        print("3. Gelişmiş kayan band alt yazı")
        
        secim = input("Seçiminiz (1-3): ").strip()
        
        # 3. Alt yazıyı ekle
        if secim == "1":
            cikti_dosyasi = video_alt_yazi_ekle(video_yolu, metin)
        elif secim == "2":
            cikti_dosyasi = video_kayan_band_alt_yazi_ekle(video_yolu, metin)
        elif secim == "3":
            cikti_dosyasi = video_alt_yazi_ekle_gelismis(video_yolu, metin)
        else:
            print("❌ Geçersiz seçim! Varsayılan olarak kayan band kullanılıyor.")
            cikti_dosyasi = video_kayan_band_alt_yazi_ekle(video_yolu, metin)
        
        if cikti_dosyasi:
            print("\n🎉 İşlem tamamlandı!")
            print(f"📹 Orijinal video: {video_yolu}")
            print(f"📹 Alt yazılı video: {cikti_dosyasi}")
        else:
            print("\n❌ Alt yazı ekleme başarısız oldu!")
        
    except KeyboardInterrupt:
        print("\n❌ İşlem kullanıcı tarafından iptal edildi")
    except Exception as e:
        print(f"\n❌ Hata oluştu: {e}")

if __name__ == "__main__":
    main()
