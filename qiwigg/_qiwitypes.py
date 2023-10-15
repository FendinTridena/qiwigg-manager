from inspect import getmembers
from json import JSONEncoder

from . import _qiwi


__all__ = [
    "QiwiCommon",
    "QiwiFolder",
    "QiwiFile",
    "QiwiIDJSONEncoder",
    "QiwiJSONEncoder",
]


class QiwiCommon:
    def __str__(self):
        return f"{self.name} (ID:{self.id})"

    def __repr__(self):
        return (
            f"<{self.__class__.__name__} "
            f"id={self.id} "
            f'name="{self.name}" '
            f"parent_id={self.parent_id}>"
        )


class QiwiFolder(QiwiCommon):
    def __init__(self, id, name, parent_id, root=False):
        self.id = id
        self.name = name
        self.parent_id = parent_id
        self.root = root

    @property
    def url(self):
        return f"{_qiwi.QIWI_URL}/folder/{self.id}"

    @classmethod
    def from_object(cls, object):
        return cls(
            object["_id"],
            object["folderName"],
            object.get("parentFolder"),
            "parentFolder" not in object,
        )


class QiwiFile(QiwiCommon):
    def __init__(self, object):
        self.id = object["_id"]
        self.name = object["fileName"]
        self.uploaded = object["createdAt"]
        self.size = int(object["fileSize"])
        self.slug = object["slug"]
        self.parent_id = object["folder"]
        self.downloads = object["downloadCount"]

        if self.parent_id is None:
            self.parent_id = "nullFolder"

    @property
    def url(self):
        return f"{_qiwi.QIWI_URL}/file/{self.slug}"


class QiwiIDJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, QiwiCommon):
            return obj.id
        return JSONEncoder.default(self, obj)


class QiwiJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, QiwiCommon):
            return dict(
                (k, v)
                for k, v in getmembers(obj)
                if not k.startswith("_") and not callable(v)
            )
        return JSONEncoder.default(self, obj)
