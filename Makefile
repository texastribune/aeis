download:
	python -m aeis.scrape data

analyze:
	python analyze.py data --json > data/analysis.json
