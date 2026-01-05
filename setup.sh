#!/bin/bash
# 快速部署脚本 - Quick Deployment Script

echo "=================================================="
echo "  OCR数据处理管道 - 快速部署"
echo "  OCR Data Processing Pipeline - Quick Setup"
echo "=================================================="

# 1. 检查Python环境
echo ""
echo "📝 Step 1: Checking Python environment..."
if command -v python3 &> /dev/null; then
    echo "✅ Python3 found: $(python3 --version)"
else
    echo "❌ Python3 not found! Please install Python 3.8+"
    exit 1
fi

# 2. 创建/激活虚拟环境
echo ""
echo "📝 Step 2: Setting up virtual environment..."
if [ -d "py313_env" ]; then
    echo "✅ Virtual environment found"
    source py313_env/bin/activate
else
    echo "Creating new virtual environment..."
    python3 -m venv py313_env
    source py313_env/bin/activate
fi

# 3. 安装依赖
echo ""
echo "📝 Step 3: Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Dependencies installed"

# 4. 检查Ollama
echo ""
echo "📝 Step 4: Checking Ollama..."
if command -v ollama &> /dev/null; then
    echo "✅ Ollama found"
    echo ""
    echo "Available models:"
    ollama list
    echo ""
    
    # 检查必需模型
    if ollama list | grep -q "qwen2.5vl:3b"; then
        echo "✅ qwen2.5vl:3b found"
    else
        echo "⚠️  qwen2.5vl:3b not found"
        read -p "Download now? (y/n): " download
        if [ "$download" = "y" ]; then
            ollama pull qwen2.5vl:3b
        fi
    fi
    
    if ollama list | grep -q "qwen2.5vl:7b"; then
        echo "✅ qwen2.5vl:7b found"
    else
        echo "⚠️  qwen2.5vl:7b not found"
        read -p "Download now? (y/n): " download
        if [ "$download" = "y" ]; then
            ollama pull qwen2.5vl:7b
        fi
    fi
else
    echo "❌ Ollama not found!"
    echo "Please install Ollama: curl https://ollama.ai/install.sh | sh"
    exit 1
fi

# 5. 检查配置文件
echo ""
echo "📝 Step 5: Checking configuration files..."
if [ -f "roi.json" ]; then
    echo "✅ roi.json found"
else
    echo "⚠️  roi.json not found"
    echo "Please create roi.json with your ROI configuration"
fi

if [ -f "config_pipeline.py" ]; then
    echo "✅ config_pipeline.py found"
else
    echo "❌ config_pipeline.py not found!"
    exit 1
fi

# 6. 创建必要目录
echo ""
echo "📝 Step 6: Creating directories..."
python3 -c "from config_pipeline import create_directories; create_directories()"
echo "✅ Directories created"

# 7. 完成
echo ""
echo "=================================================="
echo "✅ Setup complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Edit config_pipeline.py to set your SERVER_ROOT"
echo "2. Ensure roi.json contains your ROI configuration"
echo "3. Run the pipeline:"
echo "   python run_pipeline.py --full"
echo ""
echo "For help:"
echo "   python run_pipeline.py --help-usage"
echo ""
echo "Happy processing! 🚀"
echo ""

