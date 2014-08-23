import json
import logging
import pprint
import sys

from aeis.analyzers import get_or_create_analysis
from aeis.files import get_files


logging.basicConfig()
logger = logging.getLogger('aeis')
logger.setLevel(logging.ERROR)


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


if __name__ == '__main__':
    root = sys.argv[1]

    # Get files to process
    files = sorted(get_files(root), key=lambda f: f.year, reverse=False)
    files = (f for f in files if f.year in (1994, 2012))

    # Get all analyzed columns
    analysis = get_or_create_analysis(root)
    for aeis_file in files:
        logger.info(aeis_file)
        for record in aeis_file:
            key = get_cdc_code(record, level=aeis_file.level)
            for column, value in record.items():
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
                print json.dumps(data)
