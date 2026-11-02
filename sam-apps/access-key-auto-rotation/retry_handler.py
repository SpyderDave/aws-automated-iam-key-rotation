# (c) 2021 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
# https://aws.amazon.com/agreement/ or other written agreement between Customer
# and Amazon Web Services, Inc.

"""Retry Handler.

Provides exponential backoff retry logic for AWS API calls.
"""

import time
import functools
from botocore.exceptions import ClientError
from config import log


def retry_with_backoff(max_retries=3, base_delay=1, backoff_factor=2):
    """Decorator for retrying API calls with exponential backoff.

    :param max_retries: Maximum number of retry attempts
    :param base_delay: Initial delay in seconds before first retry
    :param backoff_factor: Multiplier for exponential backoff (delay * 2^attempt)
    :return: Decorated function that retries on throttling/rate limit errors
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except ClientError as e:
                    error_code = e.response['Error']['Code']
                    last_exception = e

                    # Retry on throttling and rate limiting errors
                    if error_code in ['Throttling', 'RequestLimitExceeded', 'TooManyRequestsException']:
                        if attempt < max_retries - 1:
                            delay = base_delay * (backoff_factor ** attempt)
                            log.info(
                                f'{func.__name__} rate limited (attempt {attempt + 1}/{max_retries}). '
                                f'Retrying in {delay}s...'
                            )
                            time.sleep(delay)
                        else:
                            log.error(
                                f'{func.__name__} failed after {max_retries} attempts due to throttling'
                            )
                            raise
                    else:
                        # Don't retry on non-throttling errors
                        raise
                except Exception as e:
                    # Don't retry on non-ClientError exceptions
                    raise

            # This should not be reached, but just in case
            if last_exception:
                raise last_exception

        return wrapper
    return decorator
