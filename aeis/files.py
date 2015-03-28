from __future__ import absolute_import

import glob
import os
import sys

from pyquery import PyQuery

from .dat import DatParser


def html_to_records(html):
    pq = PyQuery(html)
    rows = pq.find('table tr')
    get_row = lambda r: map(lambda th: th.text, r)
    headers = get_row(rows[0])
    for row in rows[1:]:
        yield dict(zip(headers, get_row(row)))


class AEISFile(object):
    def __init__(self, path, format='dat'):
        self.path = path
        self.directory = os.path.dirname(path)
        self.base_name = os.path.basename(self.path).lower()
        self.file_name, _ = os.path.splitext(self.base_name)
        self.format = format if format != 'txt' else 'dat'

        # Parse year from path
        year_dir = os.path.dirname(path)
        year = int(os.path.basename(year_dir))
        self.year = year

        # Derive `root_name` from the common portion of the base name
        root_name = self.file_name.lower()
        for old_prefix, new_prefix in (
            ('state', 's'),
            ('stat', 's'),
            ('dist', 'd'),
            ('regn', 'r'),
            ('camp', 'c'),
            ('cad', 'ccad'),
            ('rad', 'rcad'),
            ('dad', 'dcad'),
            ('sad', 'scad'),
        ):
            if root_name.startswith(old_prefix):
                root_name = root_name.replace(old_prefix, new_prefix, 1)
                break

        # Set normalized root names
        self.root_name = root_name[1:]
        self.root_name_with_level = root_name

        # Parse layout
        self.layout_path = None
        if self.format == 'dat':
            file_name = os.path.splitext(self.base_name)[0]
            layout_path = os.path.join(self.directory, file_name + '.lyt')
            if os.path.exists(layout_path):
                self.layout_path = layout_path

        # Set file level
        if self.base_name.startswith('s'):
            self.level = 'state'
        elif self.base_name.startswith('r'):
            self.level = 'region'
        elif self.base_name.startswith('d'):
            self.level = 'district'
        elif self.base_name.startswith('c'):
            self.level = 'campus'
        else:
            raise ValueError(self.base_name)

    def __repr__(self):
        return '<%d %s>' % (self.year, self.file_name)

    def __iter__(self):
        return getattr(self, '_get_%s_records' % self.format)()

    def _get_dat_parser(self):
        return DatParser(self.layout_path)

    def _get_dat_records(self):
        return self._get_dat_parser().parse(self.path)

    def _get_xls_records(self):
        # The XLS files provided by the TEA are actually HTML files
        # with the data in a TABLE element.
        content = open(self.path).read()
        return html_to_records(content)


def get_files(root):
    pattern = os.path.join(root, '[0-9]*', '*')
    for path in glob.iglob(pattern):
        base_name = os.path.basename(path)
        name, extension = os.path.splitext(base_name)
        if not extension in ('.dat', '.txt', '.xls'):
            continue

        format = extension.strip('.').lower()
        yield AEISFile(path=path, format=format)


if __name__ == '__main__':
    for f in get_files(sys.argv[1]):
        print f
