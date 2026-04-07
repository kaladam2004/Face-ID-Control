#!/bin/bash
# Quick Start Guide for Automatic Face Recognition

echo "=========================================="
echo "ATTENDANCE SYSTEM - AUTO MODE SETUP"
echo "=========================================="
echo ""

# Check Python
echo "1️⃣  Checking Python..."
if command -v python3 &> /dev/null; then
    python_version=$(python3 --version 2>&1)
    echo "   ✅ $python_version found"
else
    echo "   ❌ Python 3 not found. Install Python 3.9+"
    exit 1
fi

echo ""
echo "2️⃣  Installing dependencies..."
echo "   Run: pip install -r requirements.txt"
echo ""

echo "3️⃣  Starting the application..."
echo "   Run: python app.py"
echo ""

echo "4️⃣  Using AUTO MODE:"
echo "   • Click 'REGISTER EMPLOYEE' and register at least 1 person"
echo "   • Click '🤖 AUTO MODE OFF' button to enable automatic scanning"
echo "   • Position face in front of camera"
echo "   • System automatically logs attendance"
echo "   • Click '🤖 AUTO MODE ON' to disable"
echo ""

echo "=========================================="
echo "✅ AUTOMATIC FACE RECOGNITION IS READY!"
echo "=========================================="
