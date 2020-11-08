from operator import itemgetter

from scrapy.utils.python import to_bytes
from scrapy.exporters import BaseItemExporter
from scrapy.utils.serialize import ScrapyJSONEncoder


class SortedJsonItemExporter(BaseItemExporter):
    def __init__(self, file, **kwargs):
        super().__init__(dont_fail=True, **kwargs)
        self.file = file
        self._kwargs.setdefault('indent', 4)
        self._kwargs.setdefault('ensure_ascii', not self.encoding)
        self.encoder = ScrapyJSONEncoder(**self._kwargs)
        self.items = []

    def export_item(self, item):
        self.items.append(dict(self._get_serialized_fields(item)))

    def finish_exporting(self):
        data = self.encoder.encode(sorted(self.items, key=sort_key))
        self.file.write(to_bytes(data, self.encoding))


def sort_key(item):
    return (-1 * item['reg_date'].toordinal(), item['name'])
