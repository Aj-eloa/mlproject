import sys
import logger
import logging

log = logger.setup_logger(log_level=logging.ERROR)

def error_message_detail(error, error_detail: sys):
    """
    Returns a detailed error message including the file name, line number, and error message.
    """
    _, _, exc_tb = error_detail.exc_info()
    file_name = exc_tb.tb_frame.f_code.co_filename
    line_number = exc_tb.tb_lineno
    error_message = f"Error occurred in python script: {file_name} at line number: {line_number}. Error message: {error}"
    return error_message

class CustomException(Exception):
    def __init__(self, error, error_detail: sys):
        """
        Initializes CustomException with detailed error information.
        """
        self.error_message = error_message_detail(error, error_detail)
        super().__init__(self.error_message)

    def __str__(self):
        return self.error_message


if __name__ == "__main__":
    try:
        5/0
    except Exception as e:
        log.error("An error occurred: %s", CustomException(e, sys))