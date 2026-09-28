from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class TempFileStorage(FileSystemStorage):
    def __init__(self, bucket=None, querystring_auth=False, **kwargs):
        kwargs["location"] = "/tmp/%s" % bucket
        super(TempFileStorage, self).__init__(**kwargs)
