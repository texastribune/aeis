import json
import logging
import pprint
import sys
import time
import traceback

from aeis.analyzers import get_or_create_metadata
from aeis.analyzers import get_or_create_analysis
from aeis.fields import get_columns
from aeis.files import get_files
from aeis import analyzers


logging.basicConfig()
logger = logging.getLogger('aeis')

if '--debug' in sys.argv:  # XXX
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)


def sleep_or_raise():
    if '--reload' not in sys.argv:  # XXX
        raise
    else:
        time.sleep(3)


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
            sleep_or_raise()

            try:
                logger.info('reloading analyzers...')
                globals()['analyzers'] = reload(analyzers)
                continue
            except SyntaxError as e:
                traceback.print_exc()
                continue


def analyze_column(column, analyzer, metadata):
    analysis = {}
    pretty_metadata = pprint.pformat(metadata.get(column))

    position = 0
    remainder = column
    for partial, data in analyzer(aeis_file, remainder):
        logger.debug('partial: %r', repr(partial))
        logger.debug('data: %r', repr(data))
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
    """
    Reload the current analyzer until it produces a usable analysis.
    """
    while True:
        try:
            # Print the current column
            logger.info('{}/{}:{}'.format(
                aeis_file.year,
                aeis_file.base_name,
                column
            ))
            analysis = analyze_column(column, analyzer, metadata=metadata)
            return analysis, analyzer
        except Exception as e:
            traceback.print_exc()
            sleep_or_raise()

            try:
                logger.info('reloading analyzers...')
                globals()['analyzers'] = reload(analyzers)
                analyzer = get_analyzer(aeis_file)
                continue
            except SyntaxError as e:
                traceback.print_exc()
                continue


def analyze_columns(aeis_file, metadata=None):
    metadata = metadata if metadata is not None else {}
    columns = list(get_columns(aeis_file, metadata=metadata))
    analyzer = get_analyzer_in_loop(aeis_file)

    n_analyzed = 0
    for column in sorted(columns):
        # Keep analyzing until we get it right...
        analysis, analyzer = analyze_column_in_loop(column, analyzer, metadata)

        # Report analysis
        logger.debug(pprint.pformat(analysis))

        if '--json' in sys.argv:  # XXX
            print json.dumps(analysis)

        # Report progress
        n_analyzed += 1
        logger.debug('%d/%d...', n_analyzed, len(columns))

        # Yield the analysis
        yield analysis


if __name__ == '__main__':
    root = sys.argv[1]

    # Get files to process
    files = sorted(get_files(root), key=lambda f: f.year, reverse=True)
    files = (f for f in files if f.year in (1994, 2012, 2013))

    # Get all analyzed columns
    metadata = get_or_create_metadata(root)
    analysis = get_or_create_analysis(root)
    for aeis_file in files:
        for column in analyze_columns(aeis_file, metadata=metadata):
            key = column['key']
            analysis[key] = column
