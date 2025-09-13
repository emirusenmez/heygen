#!/bin/bash
# MacOS Ses Kayıt Aracı Çalıştırıcı

echo "🎯 MacOS Ses Kayıt Aracı Başlatılıyor..."
echo "================================================"

# Virtual environment kontrolü
if [ -d ".venv" ]; then
    echo "📦 Virtual environment bulundu, aktifleştiriliyor..."
    source .venv/bin/activate
    python ses_kayit_metin.py
else
    echo "🐍 Sistem Python'u kullanılıyor..."
    python3 ses_kayit_metin.py
fi
