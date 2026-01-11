# macOS App Icon

To create the `app.icns` file for the macOS application:

## Option 1: Using iconutil (Recommended)

1. Create a folder named `app.iconset` with the following PNG images:
   - icon_16x16.png (16x16)
   - icon_16x16@2x.png (32x32)
   - icon_32x32.png (32x32)
   - icon_32x32@2x.png (64x64)
   - icon_128x128.png (128x128)
   - icon_128x128@2x.png (256x256)
   - icon_256x256.png (256x256)
   - icon_256x256@2x.png (512x512)
   - icon_512x512.png (512x512)
   - icon_512x512@2x.png (1024x1024)

2. Run:
   ```bash
   iconutil -c icns app.iconset -o app.icns
   ```

## Option 2: Using sips (from a single high-res image)

If you have a single 1024x1024 PNG (`icon.png`):

```bash
mkdir app.iconset
sips -z 16 16     icon.png --out app.iconset/icon_16x16.png
sips -z 32 32     icon.png --out app.iconset/icon_16x16@2x.png
sips -z 32 32     icon.png --out app.iconset/icon_32x32.png
sips -z 64 64     icon.png --out app.iconset/icon_32x32@2x.png
sips -z 128 128   icon.png --out app.iconset/icon_128x128.png
sips -z 256 256   icon.png --out app.iconset/icon_128x128@2x.png
sips -z 256 256   icon.png --out app.iconset/icon_256x256.png
sips -z 512 512   icon.png --out app.iconset/icon_256x256@2x.png
sips -z 512 512   icon.png --out app.iconset/icon_512x512.png
sips -z 1024 1024 icon.png --out app.iconset/icon_512x512@2x.png
iconutil -c icns app.iconset -o app.icns
rm -rf app.iconset
```

## Option 3: Using online tools

Upload a 1024x1024 PNG to services like:
- https://cloudconvert.com/png-to-icns
- https://iconverticons.com/online/

Place the resulting `app.icns` file in this directory.
