from collections import namedtuple
import json
import logging
import os
import pprint
import shutil
import sys

from aeis.analyzers import get_or_create_analysis
from aeis.files import get_files
from aeis.keys import get_cdc_code
from aeis.logging import logger


Data = namedtuple('Data', ['key', 'value', 'column', 'file', 'version'])


def parse_file(aeis_file):
    try:
        file_ = aeis_file.file_name
        version = aeis_file.year
        for record in aeis_file:
            key = get_cdc_code(record, level=aeis_file.level)
            for column, value in record.items():
                data = Data(key, value, column, file_, version)
                yield key, data
    except KeyboardInterrupt:
        sys.exit()


def flush_from_queue(root, queue, analysis=None):
    stream = None
    last_key = None
    for key, data in queue:
        # Override default analysis data with more specific data
        data = dict(analysis[data.column], **data._asdict())
        data.pop('metadata', None)
        if key != last_key:
            if stream:
                stream.close()
            filename = '{}.json.txt'.format(key)
            path = os.path.join(root, 'target', filename)
            stream = open(path, 'a')
            last_key = key

        content = json.dumps(data)
        stream.write(content + '\n')


def main(script, root):
    files = sorted(get_files(root), key=lambda f: f.year, reverse=True)
    files = (f for f in files if f.year in (1994, 2012, 2013))
    analysis = get_or_create_analysis(root)

    # TESTING
    files = (f for f in files if f.year in (2013,))
    files = (f for f in files if f.root_name.startswith('prof'))

    # Parse all files
    for aeis_file in files:
        logger.info('parsing {}...'.format(aeis_file))
        queue = parse_file(aeis_file)
        flush_from_queue(root, queue, analysis=analysis)


if __name__ == '__main__':
    main(*sys.argv)
