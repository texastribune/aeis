from collections import Counter, defaultdict
import sys

from .files import get_files
from .fields import get_columns


KNOWN_COLUMNS = set([
    'campus',
    'district',
    'region',
])


def iter_ngrams(column):
    assert '/' not in column

    length = len(column)
    column = column.lower()
    if column in KNOWN_COLUMNS:
        yield '{}/0/{}'.format(column, length - 1)
        return

    for n in range(1, 4):
        for i in range(length):
            for j in range(i + 1, i + n + 1):
                if j > length:
                    break
                yield '{}/{}/{}'.format(column[i:j], i, length - 1)


def ngramize(column):
    return list(iter_ngrams(column))


def tokenize(description):
    return description.lower().split()


def alphabetize(metadata):
    descriptions = set()
    alphabet = set()
    for m in metadata:
        for d in metadata.get(m, {}).get('descriptions', []):
            descriptions.add(d)
            for c in d.lower():
                alphabet.add(c)

    for d in sorted(descriptions):
        print repr(d)

    print sorted(alphabet)


def correlate_ngrams(columns, metadata, threshold=0.5):
    column_count_by_ngram = defaultdict(int)
    token_counts_by_ngram = {}
    for column in columns:
        meta = metadata.get(column, {})
        for ngram in iter_ngrams(column):
            column_count_by_ngram[ngram] += 1
            token_counts_by_ngram.setdefault(ngram, Counter())
            for description in meta.get('descriptions', []):
                tokens = tokenize(description)
                token_counts_by_ngram[ngram].update(tokens)

    correlations = {}
    for ngram, counter in token_counts_by_ngram.iteritems():
        for token, count in counter.most_common(3):
            total = column_count_by_ngram[ngram]
            correlations[(ngram, token)] = 1.0 * count / total

    sorted_correlations = sorted(
        correlations.items(),
        key=lambda kv: (kv[0], -kv[1])
    )
    for (ngram, token), correlation in sorted_correlations:
        if correlation < threshold:
            continue
        print ngram, token, correlation


def correlate_tokens(columns, metadata, threshold=0.5):
    token_count = defaultdict(int)
    ngram_counts_by_token = {}
    for column in columns:
        meta = metadata.get(column, {})
        ngrams = ngramize(column)
        for description in meta.get('descriptions', []):
            for token in tokenize(description):
                token_count[token] += 1
                ngram_counts_by_token.setdefault(token, Counter())
                ngram_counts_by_token[token].update(ngrams)

    correlations = {}
    for token, counter in ngram_counts_by_token.iteritems():
        for ngram, count in counter.most_common(3):
            total = token_count[token]
            correlations[(token, ngram)] = 1.0 * count / total

    sorted_correlations = sorted(
        correlations.items(),
        key=lambda kv: (kv[0], -kv[1])
    )
    for (token, ngram), correlation in sorted_correlations:
        if correlation < threshold:
            break
        print token, ngram, correlation


if __name__ == '__main__':
    aeis_files = get_files(sys.argv[1])

    metadata = dict()
    columns_by_root_name = dict()
    for aeis_file in aeis_files:
        columns_by_root_name.setdefault(aeis_file.root_name, set())
        for column in get_columns(aeis_file, metadata=metadata):
            columns_by_root_name[aeis_file.root_name].add(column)

    # alphabetize(metadata)
    # exit()

    all_columns = set()
    for root_name in sorted(columns_by_root_name.keys()):
        columns = sorted(columns_by_root_name[root_name])
        all_columns = all_columns.union(columns)
        # for column in columns:
        #     descriptions = metadata.get(column, {}).get('descriptions', [])
        #     print column
        #     print ngramize(column)
        #     print descriptions
        #     print '=' * 80
        #     import ipdb; ipdb.set_trace()

    correlate_ngrams(all_columns, metadata)
