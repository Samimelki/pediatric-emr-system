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
    ],
    datas=[
        ('templates', 'templates'), 
        ('static', 'static'), 
        ('data/who_standards', 'data/who_standards'), 
        ('EMRAppIcon.icns', '.'),
        # GDK-Pixbuf loaders
        ('/opt/homebrew/lib/gdk-pixbuf-2.0/2.10.0/loaders', 'gdk-pixbuf-2.0/2.10.0/loaders'),
        # Fontconfig configuration files
        ('/opt/homebrew/etc/fonts', 'etc/fonts'),
    ],
    hiddenimports=[
        # Core webview and macOS frameworks
        'webview', 'objc', 'Cocoa', 'WebKit', 'Quartz',
        
        # PDF generation and styling
        'weasyprint', 'weasyprint.fonts', 'jinja2.ext',
        
        # Core application modules
        'database', 'database_operations', 'unified_database',
        'emr_config', 'config_manager',
        'word_document_manager', 'word_importer', 
        'csv_exporter', 'csv_importer', 'xml_exporter', 'xml_parser',
        'migration_utility', 'who_data_loader', 'who_data_utils',
        'populate_db', 'init_schema',
        
        # Route modules
        'routes', 'routes.patient_routes', 'routes.pdf_export_routes', 
        'routes.admin_routes', 'routes.settings_routes', 'routes.emr_settings_routes',
        'routes.demographics_routes', 'routes.statistics_routes', 'routes.import_routes',
        'routes.vaccine_routes', 'routes.visit_routes',
        
        # Utils modules
        'utils', 'utils.vaccine_schedule_engine', 'utils.vaccine_name_utils',
        'utils.vaccine_mapping', 'utils.form_validators', 'utils.patient_utils',
        
        # Statistics engine
        'statistics_engine', 'statistics_engine.statistics_calculator',
        'statistics_engine.pdf_to_csv_who_hfa',
        
        # Immunization logic
        'immunization_logic',
        
        # Data processing libraries
        'pandas', 'numpy', 'openpyxl', 'python-docx',
        
        # Web server
        'waitress',
        
        # Flask extensions and utilities
        'flask', 'flask.ext', 'werkzeug', 'werkzeug.serving', 'werkzeug.utils',
        'itsdangerous', 'markupsafe', 'click', 'blinker',
        
        # Date and time utilities
        'dateutil', 'dateutil.parser', 'dateutil.tz', 'pytz',
        
        # Image processing
        'PIL', 'PIL.Image', 'PIL.ImageTk', 'pillow',
        
        # WeasyPrint dependencies
        'cssselect2', 'tinycss2', 'pyphen', 'pydyf', 'tinyhtml5',
        'fonttools', 'fonttools.ttLib', 'fonttools.subset',
        
        # Compression
        'zopfli', 'brotli',
        
        # XML processing
        'et_xmlfile',
        
        # PyObjC frameworks (for macOS integration)
        'Foundation', 'AppKit', 'CoreFoundation', 'CoreServices',
        'SecurityFoundation', 'SystemConfiguration',
    ],
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'],
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
    name='EMR',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='EMR_app_contents',
)

# Ensure BUNDLE section for .app creation
app = BUNDLE(
    coll,
    name='EMR.app',
    icon='EMRAppIcon.icns',
    bundle_identifier='com.emr.wordocs', # Updated with a proper bundle ID
    info_plist={
        'CFBundleName': 'Word Docs EMR',
        'CFBundleDisplayName': 'Word Docs EMR',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleExecutable': 'EMR',
        'CFBundleIconFile': 'EMRAppIcon.icns',
        'NSHighResolutionCapable': True,
        'NSSupportsAutomaticGraphicsSwitching': True,
        'LSMinimumSystemVersion': '10.15.0',
        'NSRequiresAquaSystemAppearance': False,
    }
)
