import os
import sys

def _setup_weasyprint():
    if getattr(sys, 'frozen', False):
        # Running in a bundle
        bundle_dir = os.path.dirname(sys.executable)
        os.environ['DYLD_LIBRARY_PATH'] = os.path.join(bundle_dir, 'lib')
        os.environ['FONTCONFIG_PATH'] = os.path.join(bundle_dir, 'etc/fonts')
        os.environ['GDK_PIXBUF_MODULE_FILE'] = os.path.join(bundle_dir, 'gdk-pixbuf-2.0/2.10.0/loaders.cache')

_setup_weasyprint() 