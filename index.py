import json
import logging
import pprint
import sys

from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk

from aeis.analyzers import get_or_create_analysis
from aeis.files import get_files


logging.basicConfig()
logger = logging.getLogger('aeis')
logger.setLevel(logging.INFO)


# Keys
CAMPUS = 'campus'
DISTRICT = 'district'
REGION = 'region'
STATE = 'state'


def get_cdc_code(record, level):
    if level == STATE:
        return 'state'

    for key, value in record.items():
        lower_key = key.lower()
        if 'cdc' in lower_key:
            return record[key]
        elif level == CAMPUS == lower_key:
            return record[key]
        elif level == DISTRICT == lower_key:
            return record[key]
        elif level == REGION == lower_key:
            return record[key]
        elif level == REGION and lower_key == 'region_n':
            return record[key]

    raise ValueError(record)


def get_documents(root):
    # Get all analyzed columns
    analysis = get_or_create_analysis(root)
    for aeis_file in files:
        logger.info(aeis_file)
        for i, record in enumerate(aeis_file):
            key = get_cdc_code(record, level=aeis_file.level)
            for column, value in record.items():
                # Build the document source
                data = analysis[column]
                column = data['key']
                data = dict(
                    data,
                    key=key,
                    value=value,
                    column=column,
                    file=aeis_file.file_name,
                )
                # logger.info(pprint.pformat(data))

                # Build a globally unique ID
                _id = '%s:%s:%d' % (key, column, aeis_file.year)
                # logger.debug(id_)

                # Yield the document as a bulk action
                yield {
                    '_index': 'aeis',
                    '_type': data['field'],
                    '_id': _id,
                    '_source': data
                }



if __name__ == '__main__':
    root = sys.argv[1]

    # Get documents to index
    files = sorted(get_files(root), key=lambda f: f.year, reverse=False)
    files = (f for f in files if f.year in (1994, 2012))
    documents = get_documents(root)

    # Index to Elasticsearch
    es = Elasticsearch('http://54.200.56.1:9200')
    for result in streaming_bulk(es, documents, raise_on_error=True):
        pass
