import re


GROUP_GRADE_RE = re.compile(r'G\d\d')
TAKS_GRADE_RE = re.compile(r'0\d\d')


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
