import itertools
import os
import pprint
import re
import shelve
import sre_constants
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


def parse_one_digit_grade(grade):
    if grade == '0':
        return '3-8-and-10'
    if grade == 'Z':
        return '4-8-and-10'
    elif grade == 'X':
        return '10'
    else:
        return str(int(grade))


def parse_two_digit_grade(grade):
    if grade == 'KG':
        return 'kindergarten'
    elif grade == 'ME':
        return 'mixed-elementary'
    else:
        return str(int(grade))


def analyzer(analyze_function):
    """
    Decorates a core analyzer function that consumes the column name and
    yields analysis of an AEIS column.

    Returns an `analyze` function that analyzes a column in three steps:

    1. Pre-process the column to analyze common column names
    2. Yield analysis from applying `analyze_function` to the remainder
    3. Post-process the column to analyze common suffixes

    Yields analysis tuples of the form `(evidence, metadata)`,
    where `evidence` is the substring of the column that determined the
    analysis in the `metadata` dict.
    """
    def analyze(aeis_file, column):
        yield '', {'version': aeis_file.year}

        # Some columns are words that signify a special field
        if column.lower() in ('campus', 'district', 'region'):
            yield column, {'field': 'key'}
        elif column.lower() in ('campname', 'distname'):
            yield column, {'field': 'name'}
        elif column.lower() == 'class':
            yield column, {'field': 'school-type'}
        elif column.lower() == 'paircamp':
            yield column, {'field': 'paired-campus/code'}
        elif column.lower() == 'pairname':
            yield column, {'field': 'paired-campus/name'}
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
            elif remainder == 'C':
                yield 'C', {'measure': 'count'}
            elif remainder == 'P':
                yield 'P', {'measure': 'percent'}
            elif remainder == 'K':
                yield 'K', {'measure': 'per-pupil'}
            elif remainder == 'A':
                yield 'A', {'measure': 'average'}
            elif remainder == 'R':
                yield 'R', {'measure': 'rate'}

    return analyze


def analyzer_dsl(get_dsl):
    """
    Decorates a function that takes an AEIS file and a partial column
    and consumes yields (partial, data) tuples...

    The result of `get_dsl` is a dictionary where each key traverses a
    path to more specific metadata.

    Example:

        Full column: campothr.dat:CH0EQ94R
        Partial column: H0EQ94R
        DSL dictionary:
            {'H0': (
                {'race': 'hispanic'},
                {'EQ': (
                    {'field': 'taas-tasp-equivalence'},
                    # ...
                )}
            )}
        Analysis: {'field': 'taas-tasp-equivalence', 'race': 'hispanic'}

    DSL follows the format `{rule: (metadata, *rules)}`, where:

    1. `rule` is a literal string or a regex beginning the remainder
    2. `metadata` is a dict that is yielded as a result of matching the rule
    3. `rules` are additional rules that may be applied after stripping the
       remainder of the parent rule.
    """
    def analyze(aeis_file, remainder):
        tree = get_dsl(aeis_file)
        items = tree.iteritems()

        # We will continue to walk our DSL tree until we've parsed the
        # full remainder or we run out of transitions.
        while remainder:
            try:
                transition, subtree = next(items)
            except StopIteration:
                break

            # Get a match object for a possible regex transition
            try:
                match = re.match(r'^' + transition, remainder, re.X)
            except sre_constants.error:
                raise ValueError(
                    'r"{}" is not a valid regex'.format(transition)
                )

            # First try to transition via literal prefix
            if remainder.startswith(transition):
                # In the case of literal transitions, the metadata will
                # always be the only subtree, or it will be the first
                # subtree, because there is only a single value covered
                # by the transition.
                partial = transition
                if isinstance(subtree, dict):
                    metadata, subtrees = subtree, []
                else:
                    metadata, subtrees = subtree[0], subtree[1:]
                yield partial, metadata
            # Then fall back to a regex transition
            elif match:
                # We can pass a dict as the terminal subtree
                if isinstance(subtree, dict):
                    metadata, subtrees = subtree, []
                else:
                    metadata, subtrees = subtree[0], subtree[1:]

                # Yield metadata from first item of subtree
                sorted_groups = sorted(
                    match.re.groupindex.items(),
                    key=lambda ko: ko[1]
                )
                for key, _ in sorted_groups:
                    # Extract the partial from the match in the order
                    # it was parsed. Depending on the expression, the
                    # group may not have matched, in which case we can
                    # ignore it and continue on.
                    partial = match.group(key)
                    if partial is None:
                        continue

                    # Extract metadata using the partial match, either
                    # by getting it from a dictionary of metadata or
                    # by transforming it with a callable.
                    dict_or_callable = metadata[key]
                    if callable(dict_or_callable):
                        yield partial, {key: dict_or_callable(partial)}
                    else:
                        try:
                            # If the metadata element is a string, just
                            # assume the key we used to extract it.
                            element = dict_or_callable[partial]
                            if isinstance(element, basestring):
                                yield partial, {key: element}
                            else:
                                # Otherwise assume we have a dict
                                yield partial, element
                        except KeyError:
                            # Stop parsing here so that the partial
                            # error will bubble up.
                            break

                # Finally set partial to the full match text
                partial = match.group(0)
            else:
                # We cannot transition to the current subtree, so
                # continue to the next one.
                continue

            # Then traverse the remaining subtrees
            subitems = itertools.imap(lambda d: d.items(), subtrees)
            items = itertools.chain(*subitems)

            # Trim the partial string that we analyzed
            remainder = remainder.replace(partial, '', 1)

    return analyze


@analyzer
@analyzer_dsl
def analyze_fin(aeis_file):
    # Primer on public schools finance and tax rates:
    # http://www.lbb.state.tx.us/Other_Pubs/Financing%20Public%20Education%20in%20Texas%20Kindergarten%20through%20Grade%20Twelve%20Legislative%20Primer-Second%20Edition.pdf
    return {
        'PFFENDT': {'field': 'fund-balance/ending'},
        'PFFENDP': {'field': 'fund-balance/percent-of-expenditure'},
        'PFE': (  # Expenditure by function
            {'field': 'expenditure'},
            {'OPR': {'field': 'expenditure/total', 'function': 'operating'}},
            {'OPO': {'field': 'expenditure/total', 'object': 'operating'}},
            {
                'ADI': {'function': 'administration/instructional'},
                'ADC': {'function': 'administration/central'},
                'ADS': {'function': 'administration/campus'},
                'ALL': {'function': 'all'},
                'CAP': {'function': 'capital-outlay'},
                'COM': {'function': 'community-services'},
                'DEB': {'function': 'debt-service'},
                'INR': {'function': 'administration/instruction-related'},
                'INS': {'function': 'instruction'},
                'NOF': {'function': 'non-operating'},
                'OPF': {'function': 'operating'},
                'OTH': {'function': 'other'},
                'OTR': {'function': 'other'},
                'SUP': {'function': 'support-services/student'},
            },
            {
                'NOO': {'object-type': 'non-operating'},
                'OOP': {'object-type': 'other-operating'},
            },
            {
                'PAY': {'object': 'payroll'},
                'PLA': {'object': 'plant-services'},
            }
        ),
        'PFP': (  # Expenditure by program
            {'field': 'expenditure'},
            {
                'BIL': {'program': 'bilingual'},
                'COM': {'program': 'compensatory-expenditure'},
                'GIF': {'program': 'gifted-and-talented'},
                'REG': {'program': 'regular'},
                'SPE': {'program': 'special'},
                'VOC': {'program': 'vocational'}
            }
        ),
        'PFR': (
            {'field': 'revenue'},
            {
                'ALL': {'source': 'all'},
                'FED': {'source': 'federal'},
                'LOC': {'source': 'local'},
                'OTH': {'source': 'other-local-and-intermediate'},
                'STA': {'source': 'state'},
            }
        ),
        'PFCR': (
            {'field': 'revenue/cooperative'},
            {
                'LO': {'source': 'local'},
                'ST': {'source': 'state'},
                'FE': {'source': 'federal'},
                'TO': {'source': 'all'},
            }
        ),
        'PFCE': (
            {'field': 'expenditure/cooperative'},
            {
                'TO': {'function': 'all'},
                'IN': {'function': 'instructional'},
                'OP': {'function': 'operating-total'},
                'NO': {'function': 'non-operating-objects'},
            }
        ),
        'PFT': (
            {'field': 'tax'},
            {
                # Nominal and adopted tax rates are the same. These are
                # the rates that appear on tax forms.
                'ADP': {'rate': 'nominal'},
                # Interest/sinking is also called the debt service tax
                'INS': {'rate': 'interest-and-sinking'},
                'MNO': {'rate': 'maintenance-and-operations'},
                'TOT': {'rate': 'total'},
            }
        ),
        'PFVTOT': {'field': 'tax/property-value/total'},
        'PFV': (
            {'field': 'tax/property-value'},
            {
                'BUS': {'category': 'business'},
                'LAN': {'category': 'land'},
                'OIL': {'category': 'oil-and-gas'},
                'OTH': {'category': 'other'},
                'RES': {'category': 'residential'},
            }
        ),
        'PFX': (
            {'field': 'expenditure/exclusion'},  # ???
            {
                'SSA': {'exclusion': 'ssa-and-payments-to-fiscal-agents'},
                'EAD': {'exclusion': 'fund-31'},  # ???
                'ECA': {'exclusion': 'fund-60'},  # ???
                'RCA': {'exclusion': 'fund-60'},  # ???
                'EAE': {'exclusion': 'adult-education-programs'},
                'RAD': {'exclusion': 'adult-education-programs'},
                'ECP': {'exclusion': 'capital-projects'},  # ???
                'WLH': {'exclusion': 'wealth-equalization-transfers'},  # ???
            }
        )
    }

    # Exclusion fields from prior analysis
    # "exclusion_fields = [\n",
    # "      (u'ALL', 'expenditure/total/excluded'),\n",
    # "      (u'AWLH', 'expenditure/by-exclusion/wealth-equalization-transfers'),\n",
    # "      (u'EAE', 'expenditure/by-exclusion/adult-education-programs'),\n",
    # "      (u'ECP', 'expenditure/by-exclusion/capital-projects-funds'),\n",
    # "      (u'EIF', 'expenditure/by-exclusion/tax-increment-fund'),\n",
    # "      (u'ESS', 'expenditure/by-exclusion/shared-services-arrangements-funds'),\n",
    # "      (u'GWLH', 'expenditure/by-exclusion/wealth-equalization-transfers'),\n",
    # "      (u'RCA', 'revenue/by-exclusion/fund-60'),\n",
    # "      (u'RCP', 'revenue/by-exclusion/capital-projects-funds'),\n",
    # "      (u'RIF', 'revenue/by-exclusion/tax-increment-fund'),\n",
    # "      (u'RSS', 'revenue/by-exclusion/shared-services-arrangements-funds'),\n",
    # "      (u'SSA', 'expenditure/by-exclusion/ssa-payments-to-fiscal-agents'),\n",
    # "      (u'TUI', 'expenditure/by-exclusion/tuition-transfers-for-grades-not-offered'),\n",
    # "]"


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


@analyzer
@analyzer_dsl
def analyze_staf(aeis_file):
    """
    Info on permits: http://info.sos.state.tx.us/pls/pub/readtac$ext.TacPage?sl=R&app=9&p_dir=&p_rloc=&p_tloc=&p_ploc=&pg=1&p_tac=&ti=19&pt=7&ch=230&rl=77
    Example permit form: file://localhost/Users/noah/Downloads/TCAPreaderadded.pdf
    """
    field_transitions = {
        'F': {'status': 'full-time'},
        'P': {'status': 'permit'},
        'S': {'field': 'salary'},
    }

    return {
        '(?P<field>PCT|PET)': (
            {'field': lambda field: 'class-size'},
            {
                'ENG': {'subject': 'english'},
                'FLA': {'subject': 'foreign-language'},
                'MAT': {'subject': 'math'},
                'SCI': {'subject': 'science'},
                'SST': {'subject': 'social-studies'},
                'ELE': {'grade': 'elementary'},
                'G(?P<grade>\w\w)': ({'grade': parse_two_digit_grade}),
            }
        ),
        'PS': (
            {'field': 'staff'},
            {
                'T': (
                    {'role': 'teachers'},
                    {'EXP': {'field': 'experience'}},
                    {'KID': {'field': 'student-teacher-ratio'}},
                    {'TEN': {'field': 'tenure'}},
                    {'URN': {'field': 'turnover'}},
                    {
                        '(?P<code>\w\w)': (
                            {
                                'code': {
                                    # Total
                                    'TO': {},
                                    # Experience
                                    '00': 'zero-years',
                                    '01': 'one-to-five-years',
                                    '06': 'six-to-ten-years',
                                    '11': 'eleven-to-twenty-years',
                                    '20': 'twenty-or-more-years',
                                    # Program
                                    'BI': {'program': 'bilingual'},
                                    'CO': {'program': 'compensatory'},
                                    'GI': {'program': 'gifted-and-talented'},
                                    'OP': {'program': 'other'},
                                    'RE': {'program': 'regular'},
                                    'SP': {'program': 'special-education'},
                                    # Vocational AKA Career & Tech
                                    'VO': {'program': 'vocational'},
                                    # Race
                                    'BL': {'race': 'black'},
                                    'WH': {'race': 'white'},
                                    'HI': {'race': 'hispanic'},
                                    'NA': {'race': 'native-american'},
                                    'PA': {'race': 'asian-pacific-islander'},
                                    'OE': {'race': 'other'},
                                    # Gender
                                    'FE': {'gender': 'female'},
                                    'MA': {'gender': 'male'},
                                    # Degree
                                    'NO': {'degree': 'none'},
                                    'BA': {'degree': 'bachelors'},
                                    'MS': {'degree': 'masters'},
                                    'PH': {'degree': 'phd'},
                                    # Permit
                                    'CA': {'permit': 'temporary-assignment'},
                                    'ET': {'permit': 'emergency-teaching'},
                                    'NR': {'permit': 'non-renewable'},
                                    'SA': {'permit': 'special-assignment'},
                                },
                            },
                            field_transitions,
                        )
                    }
                ),
                '(?P<role>[A-Z])': (
                    {
                        'role': {
                            'A': 'all',
                            'C': 'central-administrators',
                            'E': 'educational-aides',
                            'P': 'professionals',
                            'S': 'school-administrators',
                            'U': 'support',
                            'X': 'auxiliary',
                        }
                    },
                    {
                        '(?P<code>\w{2})': (
                            {
                                'code': {
                                    'MI': {'group': 'minority'},
                                    'TO': {'field': 'staff/total'},
                                    'CO': {'program': 'compensatory'},
                                }
                            },
                            field_transitions,
                        )
                    }
                )
            }
        )
    }


@analyzer
@analyzer_dsl
def analyze_stud(aeis_file):
    graduate_distinctions = {
        'ADV': {'graduate-distinction': 'advanced-seals-on-diploma'},
    }

    groups = {
        'ALL': {'group': 'all'},
        'ECO': {'group': 'economically-disadvantaged'},
        'GIF': {'group': 'gifted-and-talented'},
        'LEP': {'group': 'limited-english-proficient'},
    }

    programs = {
        'SPE': {'program': 'special'},
        'BIL': {'program': 'bilingual'},
        'VOC': {'program': 'vocational'},
    }

    races = {
        'BLA': {'race': 'black'},
        'HIS': {'race': 'hispanic'},
        'OTH': {'race': 'other'},
        'WHI': {'race': 'white'},
    }

    grades_by_program = {
        r'(?P<group>G|R|S)((?P<grade>\d\d)|(?P<code>EE|PK|KI|KN))': (
             {
                'group': {
                    'G': {},  # Stand-in for "Grade"
                    'R': {'program': 'regular'},
                    'S': {'program': 'special'},
                },
                'grade': int,
                'code': {
                    'EE': {'grade': 'early-education'},
                    'PK': {'grade': 'pre-kindergarten'},
                    'KI': {'grade': 'kindergarten'},
                    'KN': {'grade': 'kindergarten'},
                }
            },
            # For some reason, the last "R" means average here
            {'R': {'measure': 'average'}}
        )
    }

    return {
        # Transition
        r'(?P<field>PEG|PEM|PER|PET)': (
            # Metadata
            {
                'field': {
                    'PEG': {'field': 'graduates', 'program': 'regular'},
                    'PEM': {'field': 'enrollment', 'group': 'mobile'},
                    'PER': {'field': 'retention'},
                    'PET': {'field': 'enrollment'},
                },
            },
            # Remainders
            graduate_distinctions,
            groups,
            programs,
            races,
            grades_by_program,
            # TODO: What if "94" came after any of these?
        )
    }


@analyzer
@analyzer_dsl
def analyze_taas(aeis_file):
    return {r'(?P<group>[A-Z])': (
        {'group': {
            # Groups
            'A': {'group': 'all'},
            'E': {'group': 'economically-disadvantaged'},
            'S': {'group': 'special-education'},
            # Genders
            'F': {'gender': 'female'},
            'M': {'gender': 'male'},
            # Races
            'B': {'race': 'black'},
            'H': {'race': 'hispanic'},
            'O': {'race': 'other'},
            'W': {'race': 'white'}}},
        {r'(?P<grade>[0-8]|X|Z)': (
            {'grade': parse_one_digit_grade},
            {r'(?P<field>T)': (
                {'field': {'T': 'taas/passing'}},
                {r'(?P<test>A|M|R|W)': (
                    {'test': {
                        'A': {'test': 'all'},
                        'M': {'test': 'math'},
                        'R': {'test': 'reading'},
                        'W': {'test': 'writing'}}},
                    {r'(?P<year>\d\d)': {'year': parse_two_digit_year}}
                )}
            )}
        )}
    )}

@analyzer
@analyzer_dsl
def analyze_cad(aeis_file):
    """
    College Admissions, College-Ready Graduates
    """
    return {r'(?P<group>\w)': (
        {'group': {
            # Groups
            'A': {'group': 'all'},
            'E': {'group': 'economically-disadvantaged'},
            'L': {'group': 'limited-english-proficient'},
            'R': {'group': 'at-risk'},
            'S': {'group': 'special-education'},
            # Genders
            'F': {'gender': 'female'},
            'M': {'gender': 'male'},
            # Races
            '2': {'race': 'two-or-more-races'},
            '3': {'race': 'asian'},
            '4': {'race': 'pacific-islander'},
            'B': {'race': 'black'},
            'H': {'race': 'hispanic'},
            'I': {'race': 'native-american'},
            'O': {'race': 'other'},
            'W': {'race': 'white'}}},
        {'(?P<metric>\w\w\w)': (
            {'metric': {
                'CRR': {'field': 'college-admissions/college-ready',
                        'subject': 'reading'},
                'CRM': {'field': 'college-admissions/college-ready',
                        'subject': 'math'},
                'CRB': {'field': 'college-admissions/college-ready',
                        'subject': 'both'},
                '0CA': {'field': 'act', 'measure': 'average'},
                '0CS': {'field': 'sat', 'measure': 'average'},
                '0CT': {'field': 'college-admissions/taking-act-or-sat'},
                '0CC': {'field': 'college-admissions/above-criteria'}}},
                # ??? Is "above-criteria" equivalent to "at-or-above-criteria"
            {r'(?P<year>\d\d)': {'year': parse_two_digit_year}}
        )}
    )}


analyze_tasa = analyze_taas
analyze_tasb = analyze_taas
analyze_tasc = analyze_taas


def analyze_columns(aeis_file, metadata=None):
    metadata = metadata if metadata is not None else {}
    columns = list(get_columns(aeis_file, metadata=metadata))

    # Get an appropriate analyzer for this file
    analyzer_name = 'analyze_%s' % aeis_file.root_name
    try:
        analyzer = globals()[analyzer_name]
    except KeyError:
        raise RuntimeError(
            'You must implement an analyzer named "%s" to parse "%s"' % (
                analyzer_name, aeis_file))

    analyzed_columns = set()
    for column in sorted(columns):
        position = 0
        remainder = column
        generator = analyzer(aeis_file, remainder)
        pretty_metadata = pprint.pformat(metadata.get(column))

        # Print the current column
        print '{}/{}:{}'.format(aeis_file.year, aeis_file.base_name, column)

        analysis = {}
        for partial, data in generator:
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

        # Print analysis
        pprint.pprint(analysis)

        # Report progress
        analyzed_columns.add(column)
        print '{}/{}...'.format(len(analyzed_columns), len(columns))


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
    files = sorted(get_files(root), key=lambda f: f.year, reverse=True)

    # Make another pass for analysis
    for aeis_file in files:
        analyze_columns(aeis_file, metadata=metadata)
