from __future__ import absolute_import

import logging

from rest_framework.exceptions import Throttled
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def extended_exception_handler(exc, context):
    """
    Custom exception handler for Django Rest Framework that adds
    the `status_code` to the response and renames the `detail` key to `error`.
    """
    logger.exception(exc)
    response = exception_handler(exc, context)

    if response is not None:
        try:
            response.data["status_code"] = response.status_code
            if "detail" in response.data:
                response.data["error"] = response.data["detail"]
                del response.data["detail"]

            if "non_field_errors" in response.data:
                response.data["error"] = response.data["non_field_errors"]
                del response.data["non_field_errors"]

            if "default_code" in response.data:
                response.data["code"] = response.data["default_code"]
                del response.data["default_code"]

            if isinstance(exc, Throttled):
                response.data["availableIn"] = exc.wait

            # if exception has errors attribute, set errors field in response
            if hasattr(exc, "errors") and exc.errors:
                response.data["errors"] = exc.errors
        except KeyError:
            logger.exception("KeyError in extended_exception_handler")
        except TypeError:
            # because sometimes request.data is a list...
            logger.exception("TypeError in extended_exception_handler")

    return response
