# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[
        # Core Rendering & Text
        ('/opt/homebrew/lib/libpango-1.0.0.dylib', '.'),
        ('/opt/homebrew/lib/libcairo.2.dylib', '.'),
        ('/opt/homebrew/lib/libfontconfig.1.dylib', '.'),
        ('/opt/homebrew/lib/libfreetype.6.dylib', '.'),
        ('/opt/homebrew/lib/libfribidi.0.dylib', '.'),
        ('/opt/homebrew/lib/libharfbuzz.0.dylib', '.'),
        ('/opt/homebrew/lib/libgdk_pixbuf-2.0.0.dylib', '.'),
        # Dependencies of the above (common ones)
        ('/opt/homebrew/lib/libglib-2.0.0.dylib', '.'),
        ('/opt/homebrew/lib/libgobject-2.0.0.dylib', '.'),
        ('/opt/homebrew/lib/libgio-2.0.0.dylib', '.'), # For Glib
        ('/opt/homebrew/lib/libintl.8.dylib', '.'), # For gettext/glib
        ('/opt/homebrew/lib/libpixman-1.0.dylib', '.'), # For Cairo
        ('/opt/homebrew/lib/libunistring.5.dylib', '.'), # For Fribidi or Harfbuzz
        ('/opt/homebrew/lib/libgraphite2.3.dylib', '.'), # For Harfbuzz
        # Image libraries (likely used by GDK-Pixbuf or Pillow via WeasyPrint)
        ('/opt/homebrew/lib/libpng16.16.dylib', '.'),
        ('/opt/homebrew/lib/libjpeg.8.dylib', '.'), # From jpeg-turbo
        ('/opt/homebrew/lib/libtiff.6.dylib', '.'),
        ('/opt/homebrew/lib/libgif.7.dylib', '.'),
        ('/opt/homebrew/lib/libwebp.7.dylib', '.'),
        ('/opt/homebrew/lib/libopenjp2.7.dylib', '.'), # openjpeg
        ('/opt/homebrew/lib/liblcms2.2.dylib', '.'), # little-cms2 (color management)
        # Other supporting libs from brew deps list that seem relevant
        ('/opt/homebrew/lib/libpcre2-8.0.dylib', '.'), # PCRE2 for glib
        ('/opt/homebrew/lib/liblzma.5.dylib', '.'), # xz for libtiff or others
        ('/opt/homebrew/lib/libzstd.1.dylib', '.'), # zstd, often used with tiff
        # Potentially needed by Pango/Cairo for X11 interactions, though less likely for pure PDF generation
        # ('/opt/homebrew/lib/libX11.6.dylib', '.'),
        # ('/opt/homebrew/lib/libxcb.1.dylib', '.'),
        # ('/opt/homebrew/lib/libXrender.1.dylib', '.'),
        # ('/opt/homebrew/lib/libXext.6.dylib', '.'),
        # ('/opt/homebrew/lib/libXau.6.dylib', '.'),
        # ('/opt/homebrew/lib/libXdmcp.6.dylib', '.'),
    ],
    datas=[
        ('templates', 'templates'), 
        ('static', 'static'),
        ('pdf_config.json', '.'),
        ('data/who_standards', 'data/who_standards'),
        # GDK-Pixbuf loaders
        ('/opt/homebrew/lib/gdk-pixbuf-2.0/2.10.0/loaders', 'gdk-pixbuf-2.0/2.10.0/loaders'),
        # Fontconfig configuration files
        ('/opt/homebrew/etc/fonts', 'etc/fonts')
    ],
    hiddenimports=['weasyprint', 'jinja2.ext', 'webview', 'objc', 'Cocoa', 'WebKit', 'Quartz', 'weasyprint.fonts'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    codesign_identity=None,
    codesign_entitlements_file=None,
    cipher=None,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PediatricEMR',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    codesign_entitlements_file=None,
    icon=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='app',
)
app = BUNDLE(
    coll,
    name='PediatricEMR.app',
    icon='AppIcon.icns',
    bundle_identifier=None,
)
