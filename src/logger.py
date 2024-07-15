import logging
import os
from datetime import datetime

def setup_logger(log_dir="logs", log_level=logging.INFO):
    """
    Set up a logger that writes to a timestamped log file in the specified directory
    and also logs to the console.

    Parameters:
        log_dir (str): The directory where log files will be stored.
        log_level (int): The logging level (e.g., logging.INFO, logging.DEBUG).

    Returns:
        logging.Logger: Configured logger.
    """
    try:
        # Create log directory if it doesn't exist
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Define the log file name with timestamp
        log_file = os.path.join(log_dir, f"{datetime.now().strftime('%m_%d_%Y_%H_%M_%S')}.log")

        # Create a custom logger
        logger = logging.getLogger('my_logger')
        logger.setLevel(logging.DEBUG)  # Set the overall log level to the lowest to capture all messages

        # Create handlers
        file_handler = logging.FileHandler(log_file)
        console_handler = logging.StreamHandler()

        # Set level for handlers
        file_handler.setLevel(log_level)
        console_handler.setLevel(log_level)

        # Create formatters and add them to the handlers
        formatter = logging.Formatter("[ %(asctime)s ] %(lineno)d %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers to the logger
        if not logger.handlers:  # To avoid adding handlers multiple times in some environments
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)

        return logger

    except Exception as e:
        print(f"Failed to set up logger: {e}")
        raise

if __name__ == "__main__":
    # Correctly call the setup_logger function and assign its return value to logger
    logger = setup_logger()
    logger.info("Logger has been set up successfully")
    logger.error("This is an error message")

# Example usage:
# logger = setup_logger(log_level=logging.DEBUG)
# logger.info("Logger has been set up successfully.")