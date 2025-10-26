# 🔄 Lordnine Build Automation

This system automatically rebuilds the Lordnine executables whenever you make changes to the source code.

## 🚀 Quick Start

### Option 1: Auto-Builder (Recommended)
```bash
# Start the auto-builder (watches for changes)
start_auto_build.bat
```

### Option 2: Manual Commands
```bash
# Quick development build
python scripts/quick_build.py

# Full clean build
python scripts/quick_build.py --clean

# Check build status
python scripts/build_automation.py --status
```

## 📁 Files Created

### Auto-Build Scripts
- **`scripts/auto_build.py`** - Main auto-builder that watches for file changes
- **`scripts/build_automation.py`** - Comprehensive build automation with multiple modes
- **`scripts/quick_build.py`** - Fast development builds
- **`start_auto_build.bat`** - Easy launcher for auto-builder
- **`setup_dev.bat`** - Development environment setup

### Build Output
- **`dist/LordnineGUI/LordnineGUI.exe`** - Main GUI application
- **`dist/LordnineRunner/LordnineRunner.exe`** - Console runner

## 🎯 How It Works

### Auto-Builder Features
- **File Monitoring**: Watches for changes in `.py` and `.yaml` files
- **Smart Filtering**: Ignores build artifacts, temporary files, and cache directories
- **Cooldown Period**: Prevents excessive builds (5-second minimum between builds)
- **Background Building**: Builds run in separate threads to avoid blocking
- **Status Updates**: Shows build progress and results

### Monitored File Types
- ✅ Python files (`.py`)
- ✅ Configuration files (`.yaml`, `.yml`)
- ❌ Build artifacts (`build/`, `dist/`, `__pycache__/`)
- ❌ Git files (`.git/`)
- ❌ Temporary files

## 🛠️ Development Workflow

### 1. Setup (One-time)
```bash
# Install development dependencies
setup_dev.bat
```

### 2. Development
```bash
# Start auto-builder
start_auto_build.bat

# Make your changes to Python files
# The system will automatically rebuild when you save files
```

### 3. Manual Builds
```bash
# Quick build (faster, no clean)
python scripts/quick_build.py

# Full clean build
python scripts/quick_build.py --clean

# Check what's built
python scripts/build_automation.py --status
```

## 📊 Build Status

The system tracks:
- ✅ Build completion status
- 📁 File sizes of executables
- 🕒 Last modification times
- 🔍 Dependency availability

## ⚙️ Configuration

### Build Modes
- **Quick Build**: Fast incremental build (default)
- **Clean Build**: Full rebuild with artifact cleanup
- **Admin Build**: Build with UAC elevation for GUI

### Auto-Builder Settings
- **Cooldown**: 5 seconds between builds
- **File Types**: `.py`, `.yaml`, `.yml`
- **Ignore Patterns**: `build/`, `dist/`, `__pycache__/`, `.git/`

## 🐛 Troubleshooting

### Common Issues

**"watchdog not installed"**
```bash
pip install watchdog
```

**"Python not found"**
- Install Python 3.8+ and add to PATH
- Restart command prompt

**"Build failed"**
```bash
# Try full clean build
python scripts/quick_build.py --clean

# Check dependencies
python scripts/build_automation.py --check
```

**"PowerShell execution policy"**
```bash
# Run as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Build Artifacts
- **Build logs**: Check console output for detailed error messages
- **PyInstaller warnings**: Usually safe to ignore unless build fails
- **File permissions**: Ensure write access to `dist/` directory

## 🎯 Benefits

### For Development
- ✅ **Instant feedback**: See changes immediately
- ✅ **No manual builds**: Focus on coding, not building
- ✅ **Fast iteration**: Quick builds for development
- ✅ **Error detection**: Immediate build failure notification

### For Production
- ✅ **Consistent builds**: Same process every time
- ✅ **Dependency tracking**: Ensures all requirements are met
- ✅ **Status monitoring**: Know what's built and when
- ✅ **Clean builds**: Option for fresh builds when needed

## 📝 Usage Examples

### Start Development Session
```bash
# 1. Setup (first time only)
setup_dev.bat

# 2. Start auto-builder
start_auto_build.bat

# 3. Make changes to your code
# 4. Watch automatic rebuilds happen!
```

### Manual Build Commands
```bash
# Check current status
python scripts/build_automation.py --status

# Quick build
python scripts/quick_build.py

# Full clean build
python scripts/quick_build.py --clean

# Build with admin privileges
python scripts/build_automation.py --admin
```

### Advanced Usage
```bash
# Watch mode with custom settings
python scripts/build_automation.py --watch

# Check dependencies
python scripts/build_automation.py --check

# Full automation with all options
python scripts/build_automation.py --clean --admin --watch
```

---

**🎉 Happy coding! The auto-builder will handle the rest!**




