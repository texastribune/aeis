from __future__ import absolute_import

import sys

from .files import get_files


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

    for column in record:
        yield str(column)


if __name__ == '__main__':
    from csvkit import CSVKitWriter

    columns = set()
    metadata = dict()
    for aeis_file in get_files(sys.argv[1]):
        for column in get_columns(aeis_file, metadata=metadata):
            columns.add(column)

    writer = CSVKitWriter(sys.stdout)
    writer.writerow(('column', 'first', 'middle', 'last', 'descriptions'))
    for column in columns:
        descriptions = map(str, metadata[column].get('descriptions', []))
        writer.writerow((column, column[0], column[1:-1], column[-1],
                         descriptions))
