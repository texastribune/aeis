from __future__ import absolute_import

import glob
import os
import sys

from pyquery import PyQuery

from .files import AEISFile, get_files


class DummyAEISFile(object):
    def __init__(self, root_name, level, root, year):
        self.year = year
        self.file_name = 'foo'
        self.root_name = root_name
        self.root_name_with_level = '{}{}'.format(level, root_name)
        self.directory = os.path.join(root, str(year))

    @classmethod
    def generate(cls, root_name, root, year):
        for level in ('c', 'd', 'r', 's'):
            yield cls(root_name, level, root, year)


def get_columns(aeis_file, metadata=None):
    metadata = metadata if metadata is not None else {}
    try:
        record = next(iter(aeis_file))
    except StopIteration:
        return

    # Load column descriptions from this file's layout file
    layout = aeis_file._get_dat_parser().layout

    # Get or set column metdata if the layout exists
    if layout is not None:
        for l in layout:
            column, description = str(l['name']), l['description']
            metadata.setdefault(column, {})
            meta = metadata.get(column)
            meta.setdefault('descriptions', set())
            meta['descriptions'].add(description)
    else:
        get_metadata_for_file(aeis_file, metadata=metadata)

    for column in record:
        yield str(column)


def get_extra_metadata(root, metadata):
    """
    Get metadata for unmatched 2013 files.
    """
    for aeis_file in DummyAEISFile.generate('comp', root, 2013):
        get_metadata_for_file(aeis_file, metadata=metadata)

    for aeis_file in DummyAEISFile.generate('othr', root, 2013):
        get_metadata_for_file(aeis_file, metadata=metadata)


def get_metadata_for_file(aeis_file, metadata):
    """
    Update metadata from 2013 reference files matching the current file.
    """
    if aeis_file.year < 2013:
        return

    patterns = [
        aeis_file.file_name + '*.html',
        aeis_file.root_name_with_level + '*.html'
    ]
    found_paths = set()
    for pattern in patterns:
        pattern = os.path.join(aeis_file.directory, pattern)
        for path in glob.iglob(pattern):
            if path in found_paths:
                continue

            found_paths.add(path)
            if aeis_file.root_name == 'ref':
                data = parse_ref_metadata(path)
            else:
                data = parse_html_metadata(path)

            for column, description in data:
                metadata.setdefault(column, {})
                meta = metadata.get(column)
                meta.setdefault('descriptions', set())
                meta.setdefault('files', set())
                meta['descriptions'].add(description)
                meta['layouts'].add(path)
                metadata[column] = meta


def parse_html_metadata(path):
    """
    Parse column names and descriptions from a 2013 HTML reference file.
    """
    html = open(path).read()
    pq = PyQuery(html)

    # The reference table should be the only one with a THEAD element
    thead = pq('thead')[0]
    table = thead.getparent()

    # Parse column NAME/LABEL from each row
    tq = PyQuery(table)
    for row in tq('tr'):
        columns = row.getchildren()
        name = columns[0].text
        description = columns[3].text
        if name and description:
            yield name.strip(), description.strip()


def parse_ref_metadata(path):
    """
    Parse non-tabular HTML reference data for "REF" datasets.
    """
    html = open(path).read()
    pq = PyQuery(html)
    for p in pq('p'):
        if p.text and '--' in p.text:
            name, label = p.text.split('--')
            yield name.strip(), label.strip()


if __name__ == '__main__':
    from csvkit import CSVKitWriter

    root = sys.argv[1]
    columns = set()
    metadata = dict()
    for aeis_file in get_files(root):
        for column in get_columns(aeis_file, metadata=metadata):
            columns.add(column)

    # XXX, some 2013 metadata is totally disjoint from any file name
    get_extra_metadata(root, metadata)

    writer = CSVKitWriter(sys.stdout)
    writer.writerow(('column', 'first', 'middle', 'last', 'descriptions'))
    for column in columns:
        meta = metadata.get(column, {})
        descriptions = map(str, meta.get('descriptions', []))
        writer.writerow((column, column[0], column[1:-1], column[-1],
                         descriptions))
