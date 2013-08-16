import codecs
import re

from csvkit import CSVKitReader, CSVKitDictReader


class DatParser(object):
    def __init__(self, lyt_path=None, encoding='utf-8'):
        self.lyt_path = lyt_path
        self.encoding = encoding
        self.layout = self._parse_layout()

    def _parse_layout(self):
        if not self.lyt_path:
            return None

        layout = []
        with codecs.open(self.lyt_path, encoding=self.encoding) as f:
            line_iter = iter(f)

            # Read up to header separator row
            for line in line_iter:
                if line.startswith('-'):
                    break

            # Parse rows from breakpoints
            for line in line_iter:
                if not line.strip().strip('\x1a'):
                    continue

                fields = re.split('\s+', line, 4)
                pos = int(fields[0])
                name = fields[1]
                type = fields[2]
                max_len = int(fields[3])
                description = fields[4].strip()
                layout.append({
                    'pos': pos,
                    'name': name,
                    'type': type,
                    'max_len': max_len,
                    'description': description,
                })

        return layout

    def parse(self, dat_path, header_field='name'):
        if self.layout:
            return self._parse_with_layout(dat_path, header_field)
        else:
            return self._parse_raw(dat_path)

    def _parse_with_layout(self, dat_path, header_field):
        header_name = self.layout[0]['name']
        with open(dat_path) as f:
            reader = CSVKitReader(f)
            for row in reader:
                # Use a heuristic to determine if this file has a header
                # row, and skip it if it does.
                if reader.line_num == 1 and row[0] == header_name:
                    continue
                elif len(row) <= 1:
                    continue

                # Build record with names from layout
                record = {}
                for field in self.layout:
                    header = field[header_field]
                    index = field['pos'] - 1
                    try:
                        record[header] = row[index]
                    except IndexError:
                        record[header] = None

                yield record

    def _parse_raw(self, dat_path):
        with open(dat_path) as f:
            reader = CSVKitDictReader(f)
            for row in reader:
                yield row
