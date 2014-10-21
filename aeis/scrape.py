"""
Downloads all data from the TEA report site.

Usage: python -m aeis.scrape <path_to_output_dir>
"""

import itertools
import os
import re
import sys
from StringIO import StringIO
from zipfile import ZipFile, BadZipfile

from pyquery import PyQuery
import requests


BASE_URL = 'http://ritter.tea.state.tx.us'
DOWNLOAD_PATTERN = 'http://ritter.tea.state.tx.us/perfreport/aeis/%d/%s'
PRE_97_DOWNLOAD_PAGE = 'download.html'
POST_97_DOWNLOAD_PAGE = 'DownloadData.html'
FILENAME_RE = re.compile(r'filename="?(.*)"?')

TAPR_BASE_URL = 'http://ritter.tea.state.tx.us'
TAPR_DOWNLOAD_PATH = '/cgi/sas/broker'
TAPR_FORM_PATH = '/perfreport/tapr/2013/download/DownloadData.html'


def url_for_year(year):
    url_year = year - 1900 if year < 2000 else year
    page = PRE_97_DOWNLOAD_PAGE if year < 1997 else POST_97_DOWNLOAD_PAGE
    return DOWNLOAD_PATTERN % (url_year, page)


def save_file(root, year, response):
    # Get filename from response headers
    disposition = response.headers['content-disposition']
    filename = FILENAME_RE.search(disposition).group(1).strip('"')

    # Handle zip files
    file_mode = 'w'
    if filename.endswith('.zip'):
        dat_filename = filename.replace('.zip', '.dat')
        try:
            zip_file = ZipFile(StringIO(response.content))
            content = zip_file.open(dat_filename).read()
            filename = dat_filename
        except BadZipfile:
            print 'bad zip file: "%s"' % filename
            file_mode = 'wb'
            content = response.content
    else:
        content = response.content

    # Write file to subdirectory by year
    year_dir = os.path.join(root, str(year))
    if not os.path.exists(year_dir):
        os.makedirs(year_dir)
    file_path = os.path.join(year_dir, filename)
    print file_path
    with open(file_path, file_mode) as f:
        f.write(content)

    return file_path


def classify_level(level):
    return {
        'c': 'campus',
        'd': 'district',
        's': 'state',
        'r': 'region',
    }[level[:1].lower()]


def scrape_pre_2012(data_dir):
    for year in range(1994, 2012):
        # Request download page
        url = url_for_year(year)
        response = requests.get(url)
        page = response.content

        # Scrape all form data
        pq = PyQuery(page)
        level_options = pq('select[name=level] option')
        levels = [o.attrib['value'] for o in level_options]
        campus_level = [o.attrib['value'] for o in level_options
                        if o.text.strip().lower() == 'campus'][0]
        files = [o.attrib['value'] for o in pq('select[name=file] option')]
        sets = [o.attrib['value'] for o in pq('input[name=set]')]
        suffixes = [o.attrib['value'] for o in pq('input[name=suf]')]
        cgi_url = BASE_URL + pq('form').attr.action

        # Save each file from all form data
        for level in levels:
            for filename in files:
                for suf in suffixes:
                    form_data = {'level': level, 'file': filename, 'suf': suf}
                    if level == campus_level and sets:
                        for set in sets:
                            form_data['set'] = set
                            response = requests.post(cgi_url, form_data)
                            save_file(data_dir, year, response)
                    else:
                        response = requests.post(cgi_url, form_data)
                        save_file(data_dir, year, response)


def scrape_2012(data_dir):
    year = 2012
    url = 'http://ritter.tea.state.tx.us/cgi/sas/broker'
    base_data = {
        '_service': 'marykay',
        'year4': '2012',
        'year2': '&YEAR2',
        'prgopt': '2012/xplore/pickset.sas',
        '_program': 'perfrept.perfmast.sas',
        'sumlev': 'C',
        # 'camp0': '999999',
        '_debug': '0',
        'step': '0',
        'steps': '2',
    }

    def get_datasets(form_data, level, entity, option=None):
        """Get a list of available datasets for the current level"""
        form_data = dict(base_data, **{'sumlev': level, entity: '999999'})
        if option is not None:
            form_data['prgopt'] = option

        response = requests.post(url, form_data)
        pq = PyQuery(response.content)
        selection = pq.find('select[name=dsname] option')

        return form_data, [o.attrib['value'] for o in selection]

    def get_fields(form_data, dataset):
        """Get a list of available fields for the current dataset"""
        form_data = dict(form_data, prgopt='2012/xplore/pickcol.sas', step='1',
                         dsname=dataset)

        response = requests.post(url, form_data)
        pq = PyQuery(response.content)
        selection = pq.find('input[name=key]')

        return form_data, [i.attrib['value'] for i in selection]

    def get_report(form_data, dataset, fields=None, option=None):
        """Download the current report with the provided fields"""
        form_data = dict(form_data, prgopt='2012/xplore/getdata.sas', step='2',
                         dsname=dataset, _saveas=dataset, datafmt='C')
        if fields is not None:
            form_data['key'] = fields
        if option is not None:
            form_data['prgopt'] = option

        response = requests.post(url, form_data)
        return save_file(data_dir, year, response)

    # The Campus and District reports require you to provide a list of
    # fields to include in each download.
    detailed_report_levels = [('C', 'camp0'), ('D', 'dist0')]
    for level, entity in detailed_report_levels:
        # Step 1: Find all datasets available at this level
        form_data, datasets = get_datasets(base_data, level, entity)
        for dataset in datasets:
            # Step 2: Find all fields available for this dataset
            form_data, fields = get_fields(form_data, dataset)

            # Step 3: Request report with all available fields
            get_report(form_data, dataset, fields=fields)

    # The Region and State levels are a tangle of LIES. First, they
    # don't give you field options or references like the other
    # reports. Also, they download as XLS files that are actually HTML
    # documents containing the reports in a TABLE element. Then, they
    # reuse the campus entity codes. WHYYY?
    broad_report_levels = [('R', 'camp0'), ('S', 'camp0')]
    for level, entity in broad_report_levels:
        form_data, datasets = get_datasets(
            base_data, level, entity, option='2012/xplore/pickset2.sas')
        for dataset in datasets:
            get_report(form_data, dataset, option='2012/xplore/getdata2.sas')


def scrape_2012_reference(data_dir):
    """
    Scrape all the reference files for the different datasets because
    the 2012 downloads don't include LYT files.
    """
    year = 2012
    base_url = 'http://ritter.tea.state.tx.us/perfreport/aeis/2012/xplore/'
    reference_url = base_url + 'aeisref.html'
    response = requests.get(reference_url)
    pq = PyQuery(response.content)
    for link in pq.find('.mainBody a'):
        document = link.attrib['href']
        path = os.path.join(data_dir, str(year), document)
        print path
        response = requests.get(base_url + document)
        with open(path, 'w') as fp:
            fp.write(response.content)


def scrape_2013(data_dir):
    """
    Scrape the raw data from the 2012-2013 TAPR.
    """
    year = 2013
    download_url = '{}{}'.format(TAPR_BASE_URL, TAPR_DOWNLOAD_PATH)
    form_url = '{}{}'.format(TAPR_BASE_URL, TAPR_FORM_PATH)
    levels = ['S']  # ['C', 'D', 'R', 'S']
    form_data = {
        # Service
        '_service': 'marykay',
        '_program': 'perfrept.perfmast.sas',
        '_debug': '0',
        'prgopt': '2013/tapr/tapr_download.sas',
        # Version
        'year4': '2013',
        'year2': '13',
        # Dataset
        'sumlev': 'C',
        'setpick': 'STAAR1'
    }

    # Get a list of available datasets
    response = requests.get(form_url)
    pq = PyQuery(response.content)
    selection = pq.find('input[name=setpick]')
    datasets = [o.attrib['value'] for o in selection]

    # Download all available datasets
    for level, dataset in itertools.product(levels, datasets):
        print (level, dataset)
        if level == 'S' and dataset == 'REF':
            # "Reference data are not available for state."
            continue

        form_data.update(sumlev=level, setpick=dataset)
        response = requests.post(download_url, form_data)
        save_file(data_dir, year, response)


def scrape_2013_reference(data_dir):
    """
    Scrape all 2013 HTML reference pages.

    The raw downloads don't include layout files.

    """
    # http://ritter.tea.state.tx.us/perfreport/tapr/2013/download/taprref.html
    base_url = 'http://ritter.tea.state.tx.us/perfreport/tapr/2013/download/'
    reference_url = base_url + 'taprref.html'
    response = requests.get(reference_url)
    pq = PyQuery(response.content)
    for link in pq.find('.mainBody a'):
        # This is just a link to another dataset, so skip it.
        if link.text == 'Summarized PEIMS Actual Financial Data':
            continue

        document = link.attrib['href']
        path = os.path.join(data_dir, '2013', document)
        print path
        response = requests.get(base_url + document)
        with open(path, 'w') as fp:
            fp.write(response.content)


if __name__ == '__main__':
    data_dir = sys.argv[1]
    scrape_pre_2012(data_dir)
    scrape_2012(data_dir)
    scrape_2012_reference(data_dir)
    scrape_2013(data_dir)
    scrape_2013_reference(data_dir)
