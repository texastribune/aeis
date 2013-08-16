import os
import pprint
import re
import shelve
import sys

from .files import get_files
from .fields import get_columns


TWO_DIGIT_YEAR = re.compile('\d\d')


def parse_two_digit_year(partial):
    years = int(partial)
    if years > 90:
        return 1900 + years
    else:
        return 2000 + years


def analyzer(analyze_function):
    def analyze(aeis_file, column):
        yield '', {'version': aeis_file.year}

        # Some columns are words that signify a special field
        if column.lower() in ('campus', 'district', 'region'):
            yield column, {'field': 'key'}
        elif column.lower() in ('campname', 'distname'):
            yield column, {'field': 'name'}
        elif column.lower() == 'class':
            yield column, {'field': 'school-type'}
        else:
            # Parse the first character to determine the level and
            # possibly the group-mean measure (for campus data).
            if column.startswith('B'):
                yield 'B', {'level': 'campus', 'group': 'tea-peers'}
            elif column.startswith('G'):
                yield 'G', {'level': 'campus', 'group': 'tea-peers'}
            elif column.startswith('C'):
                yield 'C', {'level': 'campus'}
            elif column.startswith('D'):
                yield 'D', {'level': 'district'}
            elif column.startswith('R'):
                yield 'R', {'level': 'region'}
            elif column.startswith('S'):
                yield 'S', {'level': 'state'}

            # Assume we parse the first character at this point.
            # If we haven't, the caller should detect that we skipped some
            # characters and raise an exception.
            remainder = column[1:]

            # Now there are some possible level-specific special fields,
            # like supplemental accountability rating acknowledgments
            # at the campus and district levels.
            if remainder.lower() == 'suprate':
                yield remainder, {
                    'field': ('accountability-rating/'
                              'supplemental-acknowledgment')
                }
            elif remainder.lower() == '_rating':
                yield remainder, {'field': 'accountability-rating'}

            # Finally we get to the file-specific analyzer
            for partial, data in analyze_function(aeis_file, remainder):
                yield partial, data
                remainder = remainder.replace(partial, '', 1)

            # Expect a final possible 1-digit measure code
            if remainder == 'T':
                yield 'T', {'measure': 'total'}
            elif remainder == 'P':
                yield 'P', {'measure': 'percent'}
            elif remainder == 'K':
                yield 'K', {'measure': 'per-pupil'}

    return analyze


@analyzer
def analyze_fin(aeis_file, remainder):
    # Analyze expenditure by function
    if remainder.startswith('PFE'):
        yield 'PFE', {'field': 'expenditure'}
        remainder = remainder[3:]

        # Now expect a 3-digit code
        if remainder.startswith('ADI'):
            yield 'ADI', {'function': 'administration/instructional'}
        elif remainder.startswith('ADS'):
            yield 'ADS', {'function': 'administration/campus'}
        elif remainder.startswith('INR'):
            yield 'INR', {'function': 'administration/instruction-related'}
        elif remainder.startswith('INS'):
            yield 'INS', {'function': 'instruction'}
        elif remainder.startswith('OPR'):
            yield 'OPR', {'function': 'operating'}
        elif remainder.startswith('OTH'):
            yield 'OTH', {'function': 'other'}

    # Analyze expenditure by program
    elif remainder.startswith('PFP'):
        yield 'PFP', {'field': 'expenditure'}
        remainder = remainder[3:]

        # Expect a different 3-digit code
        if remainder.startswith('BIL'):
            yield 'BIL', {'program': 'bilingual'}
        elif remainder.startswith('COM'):
            yield 'COM', {'program': 'compensatory-expenditure'}
        elif remainder.startswith('GIF'):
            yield 'GIF', {'program': 'gifted-and-talented'}
        elif remainder.startswith('REG'):
            yield 'REG', {'program': 'regular'}
        elif remainder.startswith('SPE'):
            yield 'SPE', {'program': 'special'}
        elif remainder.startswith('VOC'):
            yield 'VOC', {'program': 'vocational'}


@analyzer
def analyze_othr(aeis_file, remainder):
    rate_means_percent = False
    rate_is_fake = False

    # Start with a 2-digit demographic code...
    if remainder.startswith('A0'):
        yield 'A0', {'group': 'all'}
    elif remainder.startswith('E0'):
        yield 'E0', {'group': 'economically-disadvantaged'}
    elif remainder.startswith('O0'):
        yield 'O0', {'group': 'other'}
    elif remainder.startswith('S0'):
        yield 'S0', {'group': 'special-education'}

    # Or a gender code...
    elif remainder.startswith('F0'):
        yield 'F0', {'gender': 'female'}
    elif remainder.startswith('M0'):
        yield 'M0', {'gender': 'male'}

    # Or a race code...
    elif remainder.startswith('B0'):
        yield 'B0', {'race': 'black'}
    elif remainder.startswith('H0'):
        yield 'H0', {'race': 'hispanic'}
    elif remainder.startswith('W0'):
        yield 'W0', {'race': 'white'}

    # Assume we parsed something
    remainder = remainder[2:]

    # Next is a 2-digit code siginifying the actualy field
    if remainder.startswith('AD'):
        yield 'AD', {'field': 'advanced-course-enrollment'}
    elif remainder.startswith('AT'):
        yield 'AT', {'field': 'attendance'}
    elif remainder.startswith('CA'):
        rate_is_fake = True
        yield 'CA', {'field': 'act', 'measure': 'average'}
    elif remainder.startswith('CS'):
        rate_is_fake = True
        yield 'CS', {'field': 'sat', 'measure': 'average'}
    elif remainder.startswith('CC'):
        rate_means_percent = True
        yield 'CC', {'field': 'college-admissions/at-or-above-criteria'}
    elif remainder.startswith('CT'):
        rate_means_percent = True
        yield 'CT', {'field': 'college-admissions/taking-act-or-sat'}
    elif remainder.startswith('MM'):
        yield 'MM', {'field': 'dropouts/method-i'}
    elif remainder.startswith('DR'):
        yield 'DR', {'field': 'dropouts/method-ii'}
    elif remainder.startswith('EQ'):
        yield 'EQ', {'field': 'taas-tasp-equivalence'}

    # Assume we parsed something
    remainder = remainder[2:]

    # A 2-digit year appears before the last letter
    if TWO_DIGIT_YEAR.match(remainder[:2]):
        yield remainder[:2], {'year': parse_two_digit_year(remainder[:2])}
        remainder = remainder[2:]

    # The final "R" means percent in this case, except sometimes like in
    # the case of ACT/SAT averages when the "R" is just tagged on for no
    # good reason.
    if remainder == 'R' and rate_is_fake:
        yield 'R', {}
    elif remainder == 'R' and rate_means_percent:
        yield 'R', {'measure': 'percent'}
    elif remainder == 'R':
        yield 'R', {'measure': 'rate'}


@analyzer
def analyze_ref(aeis_file, remainder):
    # Nothing here... it's all parsed by the base analyzer.
    yield '', {}


def analyze_columns(aeis_file, metadata=None):
    metadata = metadata if metadata is not None else {}
    columns = get_columns(aeis_file, metadata=metadata)

    analyzer = globals()['analyze_%s' % aeis_file.root_name]
    for column in sorted(columns):
        position = 0
        remainder = column
        generator = analyzer(aeis_file, remainder)
        pretty_metadata = pprint.pformat(metadata.get(column))

        analysis = {}
        for partial, data in generator:
            # print repr(partial), data
            analysis.update(data)

            # Determine continuation from the partial value
            if partial == remainder:
                remainder = None
                break
            elif not remainder.startswith(partial):
                message = (
                    'Invalid partial %r for remainder %r of %r' +
                    ' in position %d'
                )
                message %= (partial, remainder, column, position)
                message += '\nMetadata: %r' % pretty_metadata
                raise ValueError(message)

            # Remove partial data from remainder
            remainder = remainder.replace(partial, '', 1)
            position += len(partial)

        # If there is a remainder after the generator stops, raise an
        # exception because we didn't parse all metadata from the field.
        if remainder:
            message = 'Could not parse remainder %r of %r in position %d'
            message %= (remainder, column, position)
            message += '\nMetadata: %r' % pretty_metadata
            raise ValueError(message)

        print '{}.{}.{}'.format(aeis_file.base_name, aeis_file.year, column)
        pprint.pprint(analysis)


def get_or_create_metadata(root):
    if os.path.exists('metadata.shelf'):
        return dict(shelve.open('metadata.shelf'))

    metadata = shelve.open('metadata.shelf')
    aeis_files = list(get_files(root))
    for aeis_file in aeis_files:
        for column in get_columns(aeis_file, metadata=metadata):
            pass

    return metadata


if __name__ == '__main__':
    root = sys.argv[1]
    metadata = get_or_create_metadata(root)

    # Make another pass for analysis
    for aeis_file in get_files(root):
        analyze_columns(aeis_file, metadata=metadata)
