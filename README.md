AEIS
---

Tools for analyzing data from the **Academic Excellence Indicator System** and the **Texas Academic Performance Report**.


For the 2012-2013 school year and later, see the Texas Academic Performance Reports.

> The TAPRs were previously known as the Academic Excellence Indicator System (AEIS) Reports. Those reports were published from 1990-91 to 2011-12. They may be found at the AEIS Archive.


### How to Use

To scrape and download all data from AEIS:

    $ python -m aeis.scrape data

To analyze the columns of the downloaded data:

    $ python analyze.py data --reload
    $ ls analysis.shelf
    $ ls metadata.shelf

To index all data in ElasticSearch:

    $ export ES_HOST=localhost:9200
    $ python index.py data --recreate


### Next Steps

We still need to scrape and analyze the 2013 academic indicators,
but those have moved to a new system: the Texas Academic Performance Report.

The 2012-2013 data can be downloaded from this page:

http://ritter.tea.state.tx.us/perfreport/tapr/2013/download/DownloadData.html
