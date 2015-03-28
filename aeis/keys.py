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
