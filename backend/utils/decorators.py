from collections import ChainMap
from functools import wraps
from django.core.exceptions import ValidationError
from django.utils.decorators import method_decorator
from utils.exceptions import ConfigurationError, CustomAPIException


def class_view_decorator(func_decorator):
    """
    Converts a function based decorator into a class based decorator
    which should be used with class-based views

    Pulled from here: http://stackoverflow.com/questions/6069070/
    """

    def simple_decorator(View):
        View.dispatch = method_decorator(func_decorator)(View.dispatch)
        return View

    return simple_decorator


def required_fields(params):
    """
    DRF function view decorator for checking that all required request
    params/fields are not None.
    """

    def validator(f):
        @wraps(f)
        def func_wrap(view, request, *args, **kwargs):
            if request:
                data = ChainMap(request.GET, request.data, kwargs)
                for param in params:
                    value = data.get(param)
                    if not value and value is not False:
                        message = param + " is required"
                        raise CustomAPIException(message=message)
            return f(view, request, *args, **kwargs)

        return func_wrap

    return validator


def email_verification_exempt(view_func):
    """
    View decorator to exempt a view from EmailVerification Middleware
    @email_verification_exempt
    Usage: @class_view_decorator(email_verification_exempt)
    """

    def wrapped_view(*args, **kwargs):
        return view_func(*args, **kwargs)

    wrapped_view.email_verification_exempt = True
    return wraps(view_func)(wrapped_view)


def phone_verification_exempt(view_func):
    """
    View decorator to exempt a view from PhoneVerification Middleware
    @email_verification_exempt
    Usage: @class_view_decorator(email_verification_exempt)
    """

    def wrapped_view(*args, **kwargs):
        return view_func(*args, **kwargs)

    wrapped_view.phone_verification_exempt = True
    return wraps(view_func)(wrapped_view)


def exception_handler(func):
    """
    Decorator to catch exceptions that can occur in a viewset request.
    """

    @wraps(func)
    def func_wrapper(self, *args, **kwargs):
        """
        If a viewset raises an exception, catch it, skip remaining viewset
        execution, and send a response with the appropriate error code
        """
        try:
            # execute endpoint
            return func(self, *args, **kwargs)
            # catch errors raised by any wrapped endpoint, a return error
        except (
            ValueError,
            ConfigurationError,
        ) as exc:
            raise CustomAPIException(message=str(exc))
        except ValidationError as exc:
            raise CustomAPIException(message=exc)
        except Exception as exc:
            raise CustomAPIException(message=str(exc))

    return func_wrapper
