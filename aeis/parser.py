import glob
import os
import re
import struct
import sys

from pyquery import PyQuery

CAMPUS = 'campus'
DISTRICT = 'district'
REGION = 'region'
STATE = 'state'

GROUP_GRADE_RE = re.compile(r'G\d\d')
TAKS_GRADE_RE = re.compile(r'0\d\d')


class NoData(Exception):
    pass


class BaseRecordParser(object):
    def __init__(self, file):
        self.file = file

    def get_cdc_code(self, record):
        if self.file.level in (STATE, REGION):
            return None

        keys = record.keys()
        for key in keys:
            lower_key = key.lower()
            if 'cdc' in lower_key:
                return record[key]
            elif self.file.level == CAMPUS == lower_key:
                return record[key]
            elif self.file.level == DISTRICT == lower_key:
                return record[key]

        raise ValueError(record)

    def clean_value(self, value, data_type=float):
        """
        Cleans a raw AEIS value.

        Negative values are masked, and the value "." is either masked
        or N/A. Surrounding whitespace is also removed.
        """
        value = value.strip('><%')
        if not value:
            value = None
        elif value == '-3':
            value = 0.1
        elif value == '-4':
            value = 99.9
        elif value.startswith('-') or value == '.':
            value = None
        else:
            value = data_type(value)

        return value

    def get_region_code(self, record):
        return 'R%s' % record['REGION'].strip("\'")

    def parse(self, record):
        data = {'year': self.file.year}

        # Key data by level
        if self.file.level == STATE:
            data['key'] = 'TX'  # Texas FIPS code
        elif self.file.level == REGION:
            data['key'] = self.get_region_code(record)
        else:
            data['key'] = self.get_cdc_code(record)

        yield data


class GroupCodeFacetMixin(object):
    def get_group_code(self, key):
        return key[4:-1]

    def get_facets(self, key):
        facets = {}
        group_code = self.get_group_code(key)

        # Facet by grade
        if group_code == 'GKN':
            facets['grade'] = 'k'
        elif group_code == 'GPK':
            facets['grade'] = 'pk'
        elif group_code == 'GEE':
            facets['grade'] = 'ee'
        elif GROUP_GRADE_RE.match(group_code):
            facets['grade'] = str(int(group_code[1:]))

        # Facet by race
        if group_code == 'ASI':
            facets['race'] = 'asian'
        if group_code == 'BLA':
            facets['race'] = 'african-american'
        elif group_code == 'IND':
            facets['race'] = 'native-american'
        elif group_code == 'HIS':
            facets['race'] = 'hispanic'
        elif group_code == 'OTH':
            facets['race'] = 'other'
        elif group_code == 'PAC':
            facets['race'] = 'asian-pacific-islander'
        elif group_code == 'PCI':
            facets['race'] = 'pacific-islander'
        elif group_code == 'TWO':
            facets['race'] = 'two-or-more-races'
        elif group_code == 'WHI':
            facets['race'] = 'white'

        # Facet by gender
        if group_code == 'NED':
            facets['group'] = 'non-educationally-disadvantaged'
        elif group_code == 'SPE':
            facets['group'] = 'special-education'
        elif group_code == 'VOC':
            facets['group'] = 'career-and-technical-education'
        elif group_code == 'ECO':
            facets['group'] = 'economically-disadvantaged'
        elif group_code == 'RSK':
            facets['group'] = 'at-risk'
        elif group_code == 'BIL':
            facets['group'] = 'bilingual-esl'
        elif group_code == 'GIF':
            facets['group'] = 'gifted-and-talented'
        elif group_code == 'DIS':
            facets['group'] = 'disciplinary-placement'
        elif group_code == 'LEP':
            facets['group'] = 'limited-english-proficient'

        # Facet by generic group
        # Group 'all' also implies gender 'all' and race 'all'
        if group_code == 'ALL':
            facets['group'] = 'all'
            facets['gender'] = 'all'
            facets['race'] = 'all'

        # TODO: Facet by gender
        # M = male, F = female

        if not facets:
            raise ValueError('No known facets for group "%s"' % group_code)

        return facets


class StudentRecordParser(GroupCodeFacetMixin, BaseRecordParser):
    def get_enrollment_keys(self, record, suffix):
        """
        Yields a key and group code for each field matched by the given
        start_pattern and suffix.
        """
        start_key = '%sPET' % self.file.level[0].upper()
        for key in record.keys():
            if key.startswith(start_key) and key.endswith(suffix):
                yield key

    def get_enrollment_count(self, record, base_data):
        for key in self.get_enrollment_keys(record, suffix='C'):
            facets = self.get_facets(key)
            value = self.clean_value(record[key], data_type=int)
            yield dict(base_data, field='enrollment_count',
                       facets=facets, value=value)

    def get_enrollment_percent(self, record, base_data):
        for key in self.get_enrollment_keys(record, suffix='P'):
            facets = self.get_facets(key)
            value = self.clean_value(record[key])
            yield dict(base_data, field='enrollment_percent',
                       facets=facets, value=value)

    def parse(self, record):
        base_data = next(super(StudentRecordParser, self).parse(record))
        for data in self.get_enrollment_count(record, base_data):
            yield data
        for data in self.get_enrollment_percent(record, base_data):
            yield data


class CollegeReadinessRecordParser(GroupCodeFacetMixin, BaseRecordParser):
    def parse(self, record):
        iter_data = super(CollegeReadinessRecordParser, self).parse(record)
        base_data = next(iter_data)
        print base_data
        yield base_data


class TAKSFacetMixin(object):
    key_struct = struct.Struct('<cc3scc2sc')

    def parse_key(self, raw_key):
        return self.key_struct.unpack(raw_key)

    def get_facets(self, level_code, group_code, grade_code, measure_code,
                   subject_code, year, unit_code):
        facets = {}

        # Facet by grade
        if grade_code == '311':
            facets['grade'] = 'all'
        elif TAKS_GRADE_RE.match(grade_code):
            facets['grade'] = int(grade_code)
        else:
            raise ValueError('unknown grade code "%s"' % grade_code)

        # Facet by race
        if group_code == '2':
            facets['race'] = 'two-or-more-races'
        elif group_code == '3':
            facets['race'] = 'asian'
        elif group_code == '4':
            facets['race'] = 'pacific-islander'
        elif group_code == 'B':
            facets['race'] = 'african-american'
        elif group_code == 'I':
            facets['race'] = 'native-american'
        elif group_code == 'H':
            facets['race'] = 'hispanic'
        elif group_code == 'P':
            facets['race'] = 'asian-pacific-islander'
        elif group_code == 'W':
            facets['race'] = 'white'

        # Facet by group
        elif group_code == 'S':
            facets['group'] = 'special-education'
        elif group_code == 'E':
            facets['group'] = 'economically-disadvantaged'
        elif group_code == 'C':
            facets['group'] = 'esl-program'
        elif group_code == 'X':
            facets['group'] = 'esl-content-based'
        elif group_code == 'Y':
            facets['group'] = 'esl-pull-out'
        elif group_code == 'R':
            facets['group'] = 'at-risk'
        elif group_code == 'U':
            facets['group'] = 'bilingual'
        elif group_code == 'J':
            facets['group'] = 'transitional-bilingual-early-exit'
        elif group_code == 'K':
            facets['group'] = 'transitional-bilingual-late-exit'
        elif group_code == 'L':
            facets['group'] = 'limited-english-proficient'
        elif group_code == '5':
            facets['group'] = 'lep-with-services'
        elif group_code == 'Z':
            facets['group'] = 'lep-no-services'
        elif group_code == 'T':
            facets['group'] = 'dual-language-immersion-one-way'
        elif group_code == 'Q':
            facets['group'] = 'dual-language-immersion-two-way'

        # Facet by gender
        if group_code == 'F':
            facets['gender'] = 'female'
        elif group_code == 'M':
            facets['gender'] = 'male'

        # Facet by subject
        if subject_code == 'A':
            facets['subject'] = 'all'
        elif subject_code == 'C':
            facets['subject'] = 'science'
        elif subject_code == 'E':
            facets['subject'] = 'english-language-arts'
        elif subject_code == 'M':
            facets['subject'] = 'mathematics'
        elif subject_code == 'R':
            facets['subject'] = 'reading-language-arts'
        elif subject_code == 'S':
            facets['subject'] = 'social-studies'
        elif subject_code == 'W':
            facets['subject'] = 'writing'
        else:
            raise ValueError('unknown subject code "%s"' % subject_code)

        # Facet by generic group
        # Group 'all' also implies gender 'all' and race 'all'
        if group_code == 'A':
            facets['group'] = 'all'
            facets['gender'] = 'all'
            facets['race'] = 'all'

        if not facets:
            raise ValueError('No known facets for group "%s"' % group_code)

        return facets


class TAKSRecordParser(TAKSFacetMixin, BaseRecordParser):
    def parse_keys(self, record):
        for key in record:
            try:
                key_tuple = self.parse_key(key)
                (level_code, group_code, grade_code, measure_code,
                 subject_code, year, unit_code) = key_tuple
                year = 2000 + int(year)
            except struct.error:
                continue
            except ValueError:
                print key
                raise

            # Skip Group Median measures
            if level_code == 'G':
                continue

            # Skip Grades 3-10 measures
            if grade_code == '310':
                # Skip data for grades 3-10
                continue

            # Skip measures with units that are not rates
            if unit_code != 'R':
                continue

            # Ignore old taks_met_panel_recommmendation_rate for now
            # yield 'taks_met_panel_recommmendation_rate', key_tuple
            if measure_code == 'R' and self.file.year <= 2006:
                continue

            # T stands for the passing rate for the accountability
            # subset and is used in most reports.
            elif measure_code == 'T':
                # Only use revised data for 2004, since passing rates
                # weren't reported accurately for 2003.
                if year != self.file.year and year != 2004:
                    continue
                yield key, year, 'taks_passing_rate', key_tuple

            # S and C stand for the commended rate.
            # S requires caution because it changed to represent
            # the code for Spanish-language tests in later reports.
            elif (self.file.year <= 2005 and measure_code == 'S' or
                  self.file.year >= 2006 and measure_code == 'C'):
                yield key, year, 'taks_commended_rate', key_tuple

    def parse(self, record):
        has_data = False
        base_data = next(super(TAKSRecordParser, self).parse(record))
        for key, year, field, key_tuple in self.parse_keys(record):
            has_data = True
            facets = self.get_facets(*key_tuple)
            value = self.clean_value(record[key])
            record_data = {
                'field': field,
                'year': year,
                'facets': facets,
                'value': value,
            }
            yield dict(base_data, **record_data)

        # If a single record does not contain data, short-circuit the
        # entire file instead of parsing each record.
        if not has_data:
            raise NoData


def html_to_records(html):
    pq = PyQuery(html)
    rows = pq.find('table tr')
    get_row = lambda r: map(lambda th: th.text, r)
    headers = get_row(rows[0])
    for row in rows[1:]:
        yield dict(zip(headers, get_row(row)))


def get_files(root):
    files = []
    pattern = os.path.join(root, '*', 'raw', '*', '*')
    print pattern
    for path in glob.iglob(pattern):
        base_name = os.path.basename(path)
        name, extension = os.path.splitext(base_name)
        if not extension in ('.dat', '.xls'):
            continue

        year_dir = os.path.dirname(path)
        year = int(os.path.basename(year_dir))
        dataset_dir = os.path.dirname(os.path.dirname(os.path.dirname(path)))
        level, dataset = os.path.basename(dataset_dir).split('_', 1)
        format = extension.strip('.').lower()
        aeis_file = AEISFile(path=path, level=level, dataset=dataset,
                             year=year, format=format)
        files.append(aeis_file)

    files.sort(key=lambda f: (f.year, f.dataset, f.base_name))
    return files


def main(script, root, level=None, year=None, dataset='students'):
    from pprint import pprint

    from tx_schools.models import AEISField, AEISFacets, AEISData
    from tx_schools.utils import BatchImporter

    files = get_files(root)
    data_count = 0
    columns = ['key', 'year', 'field_id', 'value', 'facets_id']
    importer = BatchImporter(AEISData, columns=columns)
    for aeis_file in files:
        if level and aeis_file.level != level:
            continue
        if year and aeis_file.year != int(year):
            continue
        if dataset and aeis_file.dataset != dataset:
            continue
        else:
            print dataset, aeis_file

        file_data_count = 0
        for data in aeis_file.parse():
            file_data_count += 1
            pprint(data)
            continue

            # Get or create field
            field_slug = data.pop('field')
            field = AEISField.objects.get_or_create_cached(slug=field_slug)
            data['field_id'] = field.id

            # Get or create facets
            facets_kwargs = data.pop('facets')
            facets = AEISFacets.objects.get_or_create_cached(**facets_kwargs)
            data['facets_id'] = facets.id

            # Insert None values as null
            if data['value'] is None:
                data['value'] = r'\N'

            # Save data
            importer.feed([data[c] for c in columns])

        data_count += file_data_count
        if file_data_count:
            print aeis_file
            print 'file:', file_data_count
            print 'total:', data_count
            print 'batch:', importer.batch_count, '/', importer.batch_size
            print '=' * 80

    importer.flush()
    importer.commit_unless_managed()


if __name__ == '__main__':
    main(*sys.argv)
