import pprint
import sys
import time
import traceback

from aeis.analyzers import get_or_create_metadata
from aeis.fields import get_columns
from aeis.files import get_files
from aeis import analyzers


def get_analyzer(aeis_file):
    """
    Get an appropriate analyzer for the file.
    """
    analyzer_name = 'analyze_%s' % aeis_file.root_name
    analyzer_name_by_year = '%s_%s' % (analyzer_name, aeis_file.year)
    analyzer = getattr(analyzers, analyzer_name, None)
    analyzer = getattr(analyzers, analyzer_name_by_year, analyzer)
    if not analyzer:
        raise RuntimeError(
            'You must implement an analyzer named "%s" to parse "%s"' % (
                analyzer_name, aeis_file
            ))

    return analyzer


def get_analyzer_in_loop(aeis_file):
    while True:
        try:
            return get_analyzer(aeis_file)
        except RuntimeError as e:
            traceback.print_exc()
            time.sleep(3)

            print 'reloading...'
            try:
                globals()['analyzers'] = reload(analyzers)
            except SyntaxError as e:
                traceback.print_exc()
                continue


def analyze_column(column, analyzer, metadata):
    analysis = {}
    pretty_metadata = pprint.pformat(metadata.get(column))

    position = 0
    remainder = column
    for partial, data in analyzer(aeis_file, remainder):
        print repr(partial), repr(data)
        try:
            analysis.update(data)
        except ValueError:
            message = 'Analyzer %r yielded invalid data:\n%s' % (
                analyzer.func_name,
                pprint.pformat(data)
            )
            raise ValueError(message)

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

    return analysis


def analyze_column_in_loop(column, analyzer, metadata):
    while True:
        try:
            return analyze_column(column, analyzer, metadata=metadata)
        except Exception as e:
            traceback.print_exc()
            time.sleep(3)

            print 'reloading...'
            try:
                globals()['analyzers'] = reload(analyzers)
                analyzer = get_analyzer(aeis_file)
            except SyntaxError as e:
                traceback.print_exc()
                continue


def analyze_columns(aeis_file, metadata=None):
    metadata = metadata if metadata is not None else {}
    columns = list(get_columns(aeis_file, metadata=metadata))
    analyzer = get_analyzer_in_loop(aeis_file)

    analyzed_columns = set()
    for column in sorted(columns):
        # Print the current column
        print '{}/{}:{}'.format(aeis_file.year, aeis_file.base_name, column)

        analysis = analyze_column_in_loop(column, analyzer, metadata)

        # Print analysis
        pprint.pprint(analysis)

        # Report progress
        analyzed_columns.add(column)
        print '{}/{}...'.format(len(analyzed_columns), len(columns))


if __name__ == '__main__':
    root = sys.argv[1]
    metadata = get_or_create_metadata(root)
    files = sorted(get_files(root), key=lambda f: f.year, reverse=True)

    # Make another pass for analysis
    for aeis_file in files:
        analyze_columns(aeis_file, metadata=metadata)
