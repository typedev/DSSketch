# DSSketch Data Customization

## 📍 Data Files Location

DSSketch uses a two-level system for data files:

1. **Built-in data** (in package) - default files shipped with the package
2. **User data** - modified versions, take priority

### Where user data is stored:

- **macOS**: `~/Library/Application Support/dssketch/`
- **Linux**: `~/.config/dssketch/` (or `$XDG_CONFIG_HOME/dssketch/`)
- **Windows**: `%APPDATA%\dssketch\`
- **Custom path**: set the `DSSKETCH_DATA_DIR` environment variable

## 🎯 Loading Priority

When loading data, DSSketch checks in the following order:

1. User file (if exists)
2. Built-in file from package
3. Empty dictionary (if nothing found)

## 📝 Data Files

### unified-mappings.yaml
Axis value mappings (weight, width, etc.):
```yaml
weight:
  Thin:
    os2: 100
    user_space: 100
  Regular:
    os2: 400
    user_space: 400
  Bold:
    os2: 700
    user_space: 700
```

### discrete-axis-labels.yaml
Labels for discrete axes (italic, slant):
```yaml
ital:
  0: [Upright, Roman, Normal]
  1: [Italic]
slnt:
  0: [Upright, Normal]
  1: [Slanted, Oblique]
```

### stylenames.json
Old mapping format (for backward compatibility):
```json
{
  "weight": {
    "100": "Thin",
    "400": "Regular",
    "700": "Bold"
  }
}
```

## 🛠️ CLI Data Management

After installing the package (`pip install -e .`), the `dssketch-data` utility will be available:

```bash
# Show file location information
dssketch-data info

# Show path to user data
dssketch-data path

# Open data folder in file manager
dssketch-data edit

# Reset all files to defaults
dssketch-data reset --all

# Reset specific file
dssketch-data reset --file unified-mappings.yaml
```

## ✏️ How to Customize Data

### Method 1: Direct Editing

1. Find the data folder:
   ```bash
   dssketch-data path
   ```

2. Open the folder:
   ```bash
   dssketch-data edit
   ```

3. Edit the desired file in a text editor

4. Changes will apply automatically on next run

### Method 2: Via Environment Variable

Set a custom data path:

```bash
# Linux/macOS
export DSSKETCH_DATA_DIR=/my/custom/path

# Windows
set DSSKETCH_DATA_DIR=C:\my\custom\path
```

### Method 3: Copy for Editing

```bash
# Copy file from package to user directory
dssketch-data copy unified-mappings.yaml

# Then edit the copied file
dssketch-data edit
```

### Method 4: Programmatically (Python API)

```python
from dssketch.config import get_data_manager

dm = get_data_manager()

# Load and modify data
mappings = dm.load_data_file("unified-mappings.yaml")
mappings['weight']['SuperLight'] = {
    'os2': 50,
    'user_space': 50
}

# Save to user directory
dm.save_user_data("unified-mappings.yaml", mappings)
```

## 🔄 Package Updates

When updating DSSketch via pip:
- **Built-in data** updates automatically
- **User data** remains unchanged
- New fields from built-in data will be used as fallback

## 💡 Customization Examples

### Add New Weight

In file `~/Library/Application Support/dssketch/unified-mappings.yaml`:

```yaml
weight:
  # Existing weights...
  ExtraBlack:
    os2: 950
    user_space: 950
  Hairline:
    os2: 50
    user_space: 50
```

### Add Custom Axis

```yaml
custom_axes:
  GRADE:
    Thin:
      user_space: -200
    Normal:
      user_space: 0
    Heavy:
      user_space: 200
```

### Change Labels for Italic

In file `discrete-axis-labels.yaml`:

```yaml
ital:
  0: [Roman, Upright, Regular]  # Changed order
  1: [Italic, Cursive]  # Added alias
```

## ⚠️ Important Notes

1. **Validation**: DSSketch does not validate user data. Incorrect data may lead to errors.

2. **Backups**: Before making changes, it's recommended to create a backup:
   ```bash
   cp ~/Library/Application\ Support/dssketch/unified-mappings.yaml{,.backup}
   ```

3. **File Format**: Maintain correct YAML/JSON syntax

4. **Encoding**: Use UTF-8 for all files

## 🔍 Debugging

If something doesn't work:

1. Check which files are being loaded:
   ```bash
   dssketch-data info
   ```

2. Reset to default settings:
   ```bash
   dssketch-data reset --all
   ```

3. Check YAML syntax:
   ```bash
   python -c "import yaml; yaml.safe_load(open('unified-mappings.yaml'))"
   ```

## 📚 Additional Resources

- [YAML syntax](https://yaml.org/spec/1.2/spec.html)
- [JSON syntax](https://www.json.org/)
- [DesignSpace specification](https://github.com/fonttools/fonttools/tree/master/Doc/source/designspaceLib)
