#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import os
import datetime
import json

def run_command(command):
    """Terminal komutunu çalıştır ve sonucunu döndür"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def get_version_info():
    """Versiyon bilgilerini al"""
    version_info = {}
    
    # Git versiyonu
    success, stdout, stderr = run_command("git --version")
    if success:
        version_info['git'] = stdout.strip()
    
    # Python versiyonu
    version_info['python'] = f"Python {sys.version.split()[0]}"
    
    # Son commit bilgisi
    success, stdout, stderr = run_command("git log -1 --pretty=format:'%h - %an, %ar : %s'")
    if success:
        version_info['last_commit'] = stdout.strip()
    
    # Son commit tarihi
    success, stdout, stderr = run_command("git log -1 --pretty=format:'%ci'")
    if success:
        version_info['last_commit_date'] = stdout.strip()
    
    return version_info

def get_commit_history(limit=5):
    """Son commit'leri al"""
    success, stdout, stderr = run_command(f"git log -{limit} --pretty=format:'%h|%ci|%an|%s'")
    if not success:
        return []
    
    commits = []
    for line in stdout.strip().split('\n'):
        if line:
            parts = line.split('|', 3)
            if len(parts) >= 4:
                commits.append({
                    'hash': parts[0],
                    'date': parts[1],
                    'author': parts[2],
                    'message': parts[3]
                })
    return commits

def main():
    print("📥 Otomatik Git Pull Scripti")
    print("=" * 50)
    
    # Zaman bilgisi
    now = datetime.datetime.now()
    print(f"🕐 Çalışma zamanı: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Versiyon bilgilerini göster
    print("🔧 Versiyon Bilgileri:")
    version_info = get_version_info()
    for key, value in version_info.items():
        if key == 'git':
            print(f"   {key.upper()}: {value}")
        elif key == 'python':
            print(f"   {key.upper()}: {value}")
        elif key == 'last_commit':
            print(f"   SON COMMIT: {value}")
        elif key == 'last_commit_date':
            print(f"   SON COMMIT TARİHİ: {value}")
    print()
    
    # Git repository kontrolü
    success, stdout, stderr = run_command("git status")
    if not success:
        print("❌ Git repository bulunamadı!")
        return
    
    # Mevcut branch'i göster
    success, stdout, stderr = run_command("git branch --show-current")
    if success:
        current_branch = stdout.strip()
        print(f"📍 Mevcut branch: {current_branch}")
    
    # Remote repository kontrolü
    success, stdout, stderr = run_command("git remote -v")
    if not success:
        print("❌ Remote repository bulunamadı!")
        return
    
    print("🌐 Remote repository:")
    print(stdout)
    
    # Git pull yap
    print("\n🔄 GitHub'dan son değişiklikleri çekiliyor...")
    success, stdout, stderr = run_command("git pull origin main")
    
    if not success:
        print(f"❌ Git pull hatası: {stderr}")
        print("💡 SSH sorunu olabilir, HTTPS kullanmayı deneyin:")
        print("   git remote set-url origin https://github.com/emirusenmez/heygen.git")
        return
    
    # Sonuçları göster
    if stdout.strip():
        print("✅ Başarıyla güncellendi!")
        print("\n📋 Güncelleme detayları:")
        print(stdout)
        
        # Güncelleme sonrası yeni commit'leri göster
        print("\n📝 Son 5 Commit:")
        commits = get_commit_history(5)
        for i, commit in enumerate(commits, 1):
            date_obj = datetime.datetime.strptime(commit['date'][:19], '%Y-%m-%d %H:%M:%S')
            formatted_date = date_obj.strftime('%d.%m.%Y %H:%M')
            print(f"   {i}. {commit['hash']} - {formatted_date}")
            print(f"      👤 {commit['author']}")
            print(f"      💬 {commit['message']}")
            print()
    else:
        print("✅ Zaten güncel! Yeni değişiklik yok.")
    
    # Son durumu göster
    print("📊 Güncel durum:")
    success, stdout, stderr = run_command("git status --short")
    if success and stdout.strip():
        print(stdout)
    else:
        print("✅ Working directory temiz")
    
    # Güncelleme sonrası versiyon bilgilerini tekrar göster
    print("\n🔧 Güncel Versiyon Bilgileri:")
    updated_version_info = get_version_info()
    for key, value in updated_version_info.items():
        if key == 'last_commit':
            print(f"   SON COMMIT: {value}")
        elif key == 'last_commit_date':
            print(f"   SON COMMIT TARİHİ: {value}")
    
    print("=" * 50)

if __name__ == "__main__":
    main()
