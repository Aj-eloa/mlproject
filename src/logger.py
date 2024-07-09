import logging
import os
from datetime import datetime

def setup_logger(log_dir="logs", log_level=logging.INFO):
    """
    Set up a logger that writes to a timestamped log file in the specified directory.

    Parameters:
        log_dir (str): The directory where log files will be stored.
        log_level (int): The logging level (e.g., logging.INFO, logging.DEBUG).

    Returns:
        logging.Logger: Configured logger.
    """
    try:
        # Define the log file name with timestamp
        log_file = f"{datetime.now().strftime('%m_%d_%Y_%H_%M_%S')}.log"

        # Define the logs path and create the directory if it doesn't exist
        logs_path = os.path.join(os.getcwd(), log_dir)
        os.makedirs(logs_path, exist_ok=True)

        # Define the full path for the log file
        log_file_path = os.path.join(logs_path, log_file)

        # Configure the logging settings
        logging.basicConfig(
            filename=log_file_path,
            format="[ %(asctime)s ] %(lineno)d %(name)s - %(levelname)s - %(message)s",
            level=log_level,
        )

        logger = logging.getLogger()
        return logger

    except Exception as e:
        print(f"Failed to set up logger: {e}")
        raise

if __name__ == "__main__":
    # Correctly call the setup_logger function and assign its return value to logger
    logger = setup_logger()
    logger.info("Logger has been set up successfully")

# Example usage:
#logger = setup_logger(log_level=logging.DEBUG)
#logger.info("Logger has been set up successfully.")