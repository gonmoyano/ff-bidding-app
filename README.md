# AYON Fireframe Prodigy

Standalone application for fetching Shotgrid data and creating data packages for AYON.

## Installation

1. Build the package:
   ```bash
   python create_package.py
   ```

2. Upload to AYON server through web interface

3. Configure settings in AYON Settings -> Addons -> Fireframe Prodigy

## Usage

### From AYON Tray

1. Click AYON Tray icon
2. Navigate to: **Fireframe Prodigy** -> **Open Fireframe Prodigy**
3. Select projects and create packages

### From CLI

```bash
ayon addon ff_bidding_app open-manager
```

## Features

- Fetch Shotgrid projects, assets, shots, tasks
- Create JSON data packages
- Import packages into AYON
- Web actions support
- CLI interface

## Requirements

- AYON Server >= 1.0.0
- AYON Launcher >= 1.0.0
- Python 3.9+

## License

[Add your license]
