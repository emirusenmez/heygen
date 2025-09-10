#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import os

def run_command(command):
    """Terminal komutunu çalıştır ve sonucunu döndür"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def main():
    print("🚀 Otomatik Git Push Scripti")
    print("=" * 40)
    
    # Git durumunu kontrol et
    success, stdout, stderr = run_command("git status --porcelain")
    if not success:
        print("❌ Git repository bulunamadı!")
        return
    
    if not stdout.strip():
        print("✅ Güncellenecek dosya yok!")
        return
    
    # Değişen dosyaları göster
    print("📝 Değişen dosyalar:")
    success, stdout, stderr = run_command("git status --short")
    if success:
        print(stdout)
    
    # Kullanıcıdan commit mesajı al
    commit_message = input("\n💬 Commit mesajınızı girin: ").strip()
    
    if not commit_message:
        print("❌ Commit mesajı boş olamaz!")
        return
    
    print("\n🔄 Git işlemleri başlatılıyor...")
    
    # 1. Tüm değişiklikleri ekle
    print("1️⃣ Dosyalar ekleniyor...")
    success, stdout, stderr = run_command("git add .")
    if not success:
        print(f"❌ Git add hatası: {stderr}")
        return
    
    # 2. Commit yap
    print("2️⃣ Commit yapılıyor...")
    success, stdout, stderr = run_command(f'git commit -m "{commit_message}"')
    if not success:
        print(f"❌ Git commit hatası: {stderr}")
        return
    
    print(f"✅ Commit başarılı: {commit_message}")
    
    # 3. Push yap
    print("3️⃣ GitHub'a gönderiliyor...")
    success, stdout, stderr = run_command("git push origin main")
    if not success:
        print(f"❌ Git push hatası: {stderr}")
        print("💡 SSH sorunu olabilir, HTTPS kullanmayı deneyin:")
        print("   git remote set-url origin https://github.com/emirusenmez/heygen.git")
        return
    
    print("🎉 Başarıyla GitHub'a gönderildi!")
    print("=" * 40)

if __name__ == "__main__":
    main()
