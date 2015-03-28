import json
import logging
import os
import pprint
import sys

from elasticsearch import Elasticsearch
from elasticsearch.client import IndicesClient
from elasticsearch.helpers import streaming_bulk

from aeis.analyzers import get_or_create_analysis
from aeis.files import get_files
from aeis.keys import get_cdc_code
from aeis.logging import logger

ES_HOST = os.environ.get('ES_HOST', 'localhost:9200')

def get_documents(root, files):
    # Get all analyzed columns
    analysis = get_or_create_analysis(root)
    for aeis_file in files:
        logger.info(aeis_file)
        for i, record in enumerate(aeis_file):
            key = get_cdc_code(record, level=aeis_file.level)
            for column, value in record.items():
                # Build the document source
                data = analysis[column]
                data.pop('metadata', None)
                column = data['key']
                data = dict(
                    data,
                    key=key,
                    value=value,
                    column=column,
                    file=aeis_file.file_name,
                    version=aeis_file.year
                )
                logger.debug(pprint.pformat(data))

                # Build a globally unique ID
                _id = '%s:%s:%d' % (key, column, aeis_file.year)

                # Yield the document as a bulk action
                yield {
                    '_index': 'aeis',
                    '_type': data['field'],
                    '_id': _id,
                    '_source': data
                }


if __name__ == '__main__':
    root = sys.argv[1]

    # Configure Elasticsearch index
    es = Elasticsearch(ES_HOST)
    indices = IndicesClient(es)

    # Recreate index if necessary
    if '--recreate' in sys.argv:
        indices.delete('aeis')
        indices.create(index='aeis', body={
            'index': {
                'mapping': {
                    'ignore_malformed': True,
                    'coerce': False
                }
            }
        })

    # Get documents to index
    files = sorted(get_files(root), key=lambda f: f.year, reverse=False)
    files = (f for f in files if f.year in (1994, 2012, 2013))
    files = (f for f in files if 'staar' not in f.root_name)

    # TESTING
    # files = (f for f in files if f.year in (2013,))
    # files = (f for f in files if 'taks' not in f.root_name)
    # files = (f for f in files if 'prof' in f.root_name)

    # Index to Elasticsearch
    documents = get_documents(root, files)
    for result in streaming_bulk(
        es,
        documents,
        chunk_size=300,
        raise_on_error=True
    ):
        pass
