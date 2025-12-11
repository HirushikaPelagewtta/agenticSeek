import os
import sys
import logging

# Ensure base logs directory exists
if not os.path.exists("logs"):
    os.makedirs("logs")

class Logger:
    def __init__(self, log_filename):
        self.folder = 'logs' 
        self.create_folder(self.folder)
        self.log_path = os.path.join(self.folder, log_filename)
        self.enabled = True
        self.logger = None
        self.last_log_msg = ""
        
        if self.enabled:
            self.create_logging(log_filename)

    def create_logging(self, log_filename):
        self.logger = logging.getLogger(log_filename)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
        self.logger.propagate = False
        
        # FIX 1: Set encoding='utf-8' here. 
        # This ensures emojis don't crash the program when writing to the file.
        file_handler = logging.FileHandler(self.log_path, encoding='utf-8')
        
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Note: Depending on your server setup, a StreamHandler (Console) 
        # might be attached automatically by the root logger or uvicorn.

    def create_folder(self, path):
        """Create log dir"""
        try:
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            return True
        except Exception as e:
            self.enabled = False
            return False

    def log(self, message, level=logging.INFO):
        if self.last_log_msg == message:
            return
        
        # FIX 2: Bulletproof Sanitization
        # Before sending the message to the logger (which might print to the console),
        # we force-replace any characters that the console cannot handle.
        try:
            # Get the console's encoding (usually cp1252 on Windows) or default to utf-8
            encoding = sys.stdout.encoding or 'utf-8'
            
            # Encode string to bytes using the target encoding, replacing errors with '?'
            # Then decode back to a string that is safe to print.
            safe_message = message.encode(encoding, errors='replace').decode(encoding)
        except Exception:
            # Ultimate fallback if system encoding detection fails
            safe_message = str(message).encode('ascii', errors='replace').decode('ascii')

        if self.enabled:
            self.last_log_msg = safe_message
            self.logger.log(level, safe_message)

    def info(self, message):
        self.log(message, level=logging.INFO)

    def error(self, message):
        self.log(message, level=logging.ERROR)

    def warning(self, message):
        self.log(message, level=logging.WARNING)

if __name__ == "__main__":
    # Test to ensure it doesn't crash
    lg = Logger("test.log")
    lg.log("Hello Rocket 🚀") 
    print("If you see this, the rocket didn't crash the app.")