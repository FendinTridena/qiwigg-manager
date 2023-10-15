import os


class Chunk():
    def __init__(self, f, offset, max_size):
        f.seek(0, os.SEEK_END)

        self.final_offset = min(f.tell(), offset + max_size)
        self.size = self.final_offset - offset
        self.f = f

        f.seek(offset, os.SEEK_SET)

    def read(self, limit=-1):
        left = self.final_offset - self.f.tell()

        if limit == -1 or limit > left:
            limit = left

        return self.f.read(limit)
