import os
import sys
import logging

# Setup logging for the hook itself
log_dir = os.path.join(os.path.expanduser('~'), 'Documents', 'WordDocsEMR')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_file = os.path.join(log_dir, 'hook_debug.log')
logging.basicConfig(filename=log_file, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

logging.info("--- Runtime Hook Executing ---")

try:
    if sys.platform == 'darwin':
        logging.info("Platform is macOS.")
        # The path inside the bundle where libraries are stored
        lib_path = os.path.join(sys._MEIPASS)
        logging.info(f"sys._MEIPASS is: {lib_path}")
        
        # Add this path to the library search paths
        if 'DYLD_LIBRARY_PATH' not in os.environ:
            os.environ['DYLD_LIBRARY_PATH'] = ''
        
        if lib_path not in os.environ['DYLD_LIBRARY_PATH']:
            logging.info(f"Adding {lib_path} to DYLD_LIBRARY_PATH.")
            os.environ['DYLD_LIBRARY_PATH'] = lib_path + ':' + os.environ['DYLD_LIBRARY_PATH']
        else:
            logging.info(f"{lib_path} is already in DYLD_LIBRARY_PATH.")
            
        logging.info(f"Final DYLD_LIBRARY_PATH: {os.environ['DYLD_LIBRARY_PATH']}")

except Exception as e:
    logging.critical("Exception in runtime hook!", exc_info=True)

logging.info("--- Runtime Hook Finished ---") 