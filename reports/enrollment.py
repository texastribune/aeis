"""
Report on 2013 enrollment by district and campus.

At the campus level, includes enrollment by race and other groups.

Usage:

    python reports/enrollment.py --district > district_enrollment_2013.csv
    python reports/enrollment.py --campus > campus_enrollment_2013.csv

Verify the number of districts (1228) and campuses (8555):

    csvcut --columns=CAMPUS  data/2013/CREF.txt | wc -l
    csvcut --columns=DISTRICT  data/2013/CREF.txt | sort | uniq | wc -l

Example demographic data:

    {u'asian': u'5',
     u'black': u'5',
     u'hispanic': u'55',
     u'native-american': u'2',
     u'pacific-islander': u'0',
     u'two-or-more-races': u'3',
     u'white': u'238',
     u'at-risk': u'89',
     u'economically-disadvantaged': u'129',
     u'gifted-and-talented': u'39',
     u'limited-english-proficient': u'1',
     u'non-educationally-disadvantaged': u'179'}
"""
import collections
import csv
import sys

from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search, Q


RACES = ['asian', 'black', 'hispanic', 'native-american', 'white',
         'two-or-more-races']

GROUPS = ['at-risk', 'economically-disadvantaged', 'gifted-and-talented',
          'limited-english-proficient', 'non-educationally-disadvantaged']


def set_value(mapping, key, value):
    """
    Like `dict.set` but raises an exception if the value is different.

    >>> mapping = {}
    >>> set_value(mapping, 'foo', 'bar')
    >>> set_value(mapping, 'foo', 'baz')
    ValueError
    """
    try:
        if value != mapping[key]:
            message = 'New value %r for key %r != existing value %r'
            message %= (value, key, mapping[key])
            raise ValueError(message)
    except KeyError:
        mapping[key] = value


def get_district_names(client):
    district_names = {}
    search = Search(using=client, index='aeis', doc_type='name')
    search = (search
       .query('match', version='2013')
       .query('match', column='DISTNAME')
    )
    limit = search.count() + 1
    response = search[:limit].execute()
    for hit in response:
        set_value(district_names, hit.key, hit.value)

    return district_names


def get_campus_names(client):
    campus_names = {}
    search = Search(using=client, index='aeis', doc_type='name')
    search = (search
       .query('match', version='2013')
       .query('match', column='CAMPNAME')
    )
    limit = search.count() + 1
    response = search[:limit].execute()
    for hit in response:
        set_value(campus_names, hit.key, hit.value)

    return campus_names


def get_enrollment_by_district(client, version=2013):
    enrollment_by_district = {}
    search = Search(using=client, index='aeis', doc_type='enrollment')
    search = (search
       .query('match', version=str(version))
       .query('match', level='district')
       .query('match', column='DPETALLC')  # XXX
    )
    limit = search.count() + 1
    response = search[:limit].execute()
    for hit in response:
        set_value(enrollment_by_district, hit.key, hit.value)

    return enrollment_by_district


def get_enrollment_by_campus(client, version=2013):
    enrollment_by_campus = {}
    search = Search(using=client, index='aeis', doc_type='enrollment')
    search = (search
       .query('match', version=str(version))
       .query('match', level='campus')
       .query('match', column='CPETALLC')  # XXX
    )
    limit = search.count() + 1
    response = search[:limit].execute()
    for hit in response:
        set_value(enrollment_by_campus, hit.key, hit.value)

    return enrollment_by_campus


def get_group_counts_by_campus(client, version=2013):
    group_counts_by_campus = collections.defaultdict(dict)
    search = Search(using=client, index='aeis', doc_type='enrollment')
    any_group_or_race = Q('match', race='*') | Q('match', group='*')
    exclude_all = ~(Q('match', race='all') | Q('match', group='all'))
    search = (search
       .query('match', version=str(version))
       .query('match', level='campus')
       .query('match', measure='count')
       .query(any_group_or_race)
       .query(exclude_all)
    )
    limit = search.count() + 1
    response = search[:limit].execute()
    for hit in response:
        if 'race' in hit:
            set_value(group_counts_by_campus[hit.key], hit.race, hit.value)
        elif 'group' in hit:
            set_value(group_counts_by_campus[hit.key], hit.group, hit.value)

    return group_counts_by_campus


def write_district_enrollment(client):
    enrollment_by_district = get_enrollment_by_district(client)
    district_names = get_district_names(client)

    writer = csv.writer(sys.stdout)
    header = ['key', 'name', 'enrollment']
    writer.writerow(header)
    items = sorted(enrollment_by_district.items())
    for key, enrollment in items:
        row = [key, district_names[key], enrollment]
        writer.writerow(row)


def write_campus_enrollment(client):
    enrollment_by_campus = get_enrollment_by_campus(client)
    group_counts_by_campus = get_group_counts_by_campus(client)
    campus_names = get_campus_names(client)
    district_names = get_district_names(client)

    writer = csv.writer(sys.stdout)
    header = ['key', 'name', 'district', 'enrollment'] + RACES + GROUPS
    def get_row(key, enrollment):
        name = campus_names[key]
        district_key = key[:6]
        district_name = district_names[district_key]
        group_counts = group_counts_by_campus[key]
        races = map(group_counts.get, RACES)
        groups = map(group_counts.get, GROUPS)
        return [key, name, district_name, enrollment] + races + groups

        # Sanity check fails sometimes
        total = int(enrollment)
        race_total = sum(map(int, races))
        assert total == race_total

    writer.writerow(header)
    items = sorted(enrollment_by_campus.items())
    for key, enrollment in items:
        row = get_row(key, enrollment)
        writer.writerow(row)


def main():
    client = Elasticsearch()
    if '--district' in sys.argv:
        write_district_enrollment(client)
        exit()
    elif '--campus' in sys.argv:
        write_campus_enrollment(client)
        exit()


if __name__ == '__main__':
    main()
