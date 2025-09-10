#!/usr/bin/env python3
"""
GIF overlay ekleme fonksiyonları
"""

import cv2
import numpy as np
from PIL import Image, ImageSequence
import os

def load_gif_frames(gif_path: str, target_size: tuple = (40, 40)) -> list:
    """
    GIF dosyasını frame'lere ayırır ve hedef boyuta resize eder
    
    Args:
        gif_path: GIF dosyasının yolu
        target_size: Hedef boyut (width, height)
    
    Returns:
        Frame listesi (BGR formatında)
    """
    try:
        # GIF'i PIL ile aç
        gif = Image.open(gif_path)
        
        frames = []
        for frame in ImageSequence.Iterator(gif):
            # Alpha channel'ı koru (RGBA formatında tut)
            if frame.mode == 'RGBA':
                # RGBA formatında tut, alpha channel'ı koru
                frame = frame.convert('RGBA')
            elif frame.mode == 'P' and 'transparency' in frame.info:
                # Palette mode'da transparency varsa RGBA'ya çevir
                frame = frame.convert('RGBA')
            elif frame.mode != 'RGBA':
                # Diğer formatları RGBA'ya çevir (alpha = 255, tam opak)
                frame = frame.convert('RGBA')
            
            # Hedef boyuta resize et
            frame = frame.resize(target_size, Image.Resampling.LANCZOS)
            
            # PIL'den OpenCV formatına çevir (RGBA -> BGRA)
            frame_cv = cv2.cvtColor(np.array(frame), cv2.COLOR_RGBA2BGRA)
            frames.append(frame_cv)
        
        print(f"✅ GIF yüklendi: {len(frames)} frame, boyut: {target_size}")
        return frames
        
    except Exception as e:
        print(f"❌ GIF yükleme hatası: {e}")
        return []

def overlay_gif_on_frame(frame: np.ndarray, gif_frames: list, gif_frame_index: int, 
                        position: tuple = (0, 0), alpha: float = 1.0) -> np.ndarray:
    """
    Frame'e GIF overlay ekler
    
    Args:
        frame: Ana video frame'i
        gif_frames: GIF frame'leri listesi
        gif_frame_index: GIF frame indeksi (hız kontrolü yapılmış)
        position: Overlay pozisyonu (x, y)
        alpha: Şeffaflık (0.0-1.0)
    
    Returns:
        Overlay eklenmiş frame
    """
    if not gif_frames:
        return frame
    
    # GIF frame indeksini sınırla
    gif_frame_index = gif_frame_index % len(gif_frames)
    gif_frame = gif_frames[gif_frame_index]
    
    # Frame boyutlarını al
    frame_h, frame_w = frame.shape[:2]
    gif_h, gif_w = gif_frame.shape[:2]
    
    # Pozisyonu hesapla
    if position == (0, 0):  # Sağ üst köşe
        x = frame_w - gif_w - 10  # 10px margin
        y = 10  # 10px margin
    elif position == (1, 1):  # Sol üst köşe
        x = 10  # 10px margin
        y = 10  # 10px margin
    elif position == (2, 2):  # Merkez
        x = (frame_w - gif_w) // 2  # Merkez
        y = (frame_h - gif_h) // 2  # Merkez
    else:
        x, y = position
    
    # Sınırları kontrol et
    if x < 0 or y < 0 or x + gif_w > frame_w or y + gif_h > frame_h:
        print(f"⚠️ GIF overlay sınırlar dışında: ({x}, {y})")
        return frame
    
    # Overlay ekle (alpha channel ile)
    try:
        # GIF frame'in alpha channel'ını kontrol et
        if gif_frame.shape[2] == 4:  # BGRA formatında
            # Alpha channel'ı ayır
            gif_bgr = gif_frame[:, :, :3]  # BGR kanalları
            gif_alpha = gif_frame[:, :, 3] / 255.0  # Alpha channel (0-1)
            
            # Alpha blending ile overlay ekle
            for c in range(3):  # BGR kanalları için
                frame[y:y+gif_h, x:x+gif_w, c] = (
                    frame[y:y+gif_h, x:x+gif_w, c] * (1 - gif_alpha) + 
                    gif_bgr[:, :, c] * gif_alpha
                )
        else:
            # Alpha channel yoksa normal overlay
            if alpha < 1.0:
                # Şeffaflık ile overlay
                overlay = frame[y:y+gif_h, x:x+gif_w].copy()
                blended = cv2.addWeighted(overlay, 1-alpha, gif_frame, alpha, 0)
                frame[y:y+gif_h, x:x+gif_w] = blended
            else:
                # Tam opak overlay
                frame[y:y+gif_h, x:x+gif_w] = gif_frame
        
        return frame
        
    except Exception as e:
        print(f"❌ Overlay ekleme hatası: {e}")
        return frame

def add_gif_to_video(input_video: str, output_video: str, gif_path: str, 
                    gif_size: tuple = (40, 40), position: tuple = (0, 0), 
                    alpha: float = 1.0) -> bool:
    """
    Mevcut videoya GIF overlay ekler
    
    Args:
        input_video: Giriş video dosyası
        output_video: Çıkış video dosyası
        gif_path: GIF dosyasının yolu
        gif_size: GIF boyutu (width, height)
        position: Overlay pozisyonu (0,0 = sağ üst köşe)
        alpha: Şeffaflık (0.0-1.0)
    
    Returns:
        Başarı durumu
    """
    try:
        print(f"🎬 Video'ya GIF ekleniyor: {gif_path}")
        
        # GIF frame'lerini yükle
        gif_frames = load_gif_frames(gif_path, gif_size)
        if not gif_frames:
            print("❌ GIF frame'leri yüklenemedi")
            return False
        
        # Video'yu aç
        cap = cv2.VideoCapture(input_video)
        if not cap.isOpened():
            print(f"❌ Video açılamadı: {input_video}")
            return False
        
        # Video özelliklerini al
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"📹 Video özellikleri: {width}x{height}, {fps} FPS, {total_frames} frame")
        
        # Çıkış video yazıcısı
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_video, fourcc, fps, (width, height))
        
        if not out.isOpened():
            print("❌ Çıkış video yazıcısı açılamadı")
            cap.release()
            return False
        
        # Frame'leri işle
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # GIF overlay ekle
            frame_with_gif = overlay_gif_on_frame(frame, gif_frames, frame_count, position, alpha)
            
            # Frame'i yaz
            out.write(frame_with_gif)
            
            frame_count += 1
            
            # İlerleme göster
            if frame_count % 30 == 0:
                progress = (frame_count / total_frames) * 100
                print(f"📊 İlerleme: {frame_count}/{total_frames} ({progress:.1f}%)")
        
        # Temizlik
        cap.release()
        out.release()
        
        print(f"✅ GIF overlay tamamlandı: {output_video}")
        return True
        
    except Exception as e:
        print(f"❌ GIF overlay hatası: {e}")
        return False

def test_gif_overlay():
    """GIF overlay'i test et"""
    gif_path = "/Users/emirefeusenmez/code/heygen/gif.gif"
    
    if not os.path.exists(gif_path):
        print(f"❌ GIF dosyası bulunamadı: {gif_path}")
        return False
    
    # Test için basit bir video oluştur
    test_video = "/Users/emirefeusenmez/code/heygen/test_video.mp4"
    output_video = "/Users/emirefeusenmez/code/heygen/test_video_with_gif.mp4"
    
    # Basit test video oluştur
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(test_video, fourcc, 30, (1280, 720))
    
    for i in range(300):  # 10 saniye
        # Basit renkli frame
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        frame[:, :] = (i % 255, (i * 2) % 255, (i * 3) % 255)
        
        # Frame numarası yaz
        cv2.putText(frame, f"Frame {i}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
        
        out.write(frame)
    
    out.release()
    print(f"✅ Test video oluşturuldu: {test_video}")
    
    # GIF overlay ekle
    success = add_gif_to_video(test_video, output_video, gif_path, (200, 200), (0, 0), 1.0)
    
    if success:
        print(f"✅ Test başarılı: {output_video}")
        # Test dosyalarını temizle
        try:
            os.remove(test_video)
        except:
            pass
        return True
    else:
        print("❌ Test başarısız")
        return False

if __name__ == "__main__":
    test_gif_overlay()
