download:
	python -m aeis.scrape data

analyze:
	rm *.shelf
	python analyze.py data --json > data/analysis.json

parse:
	rm -rf data/target
	mkdir -p data/target
	python parse.py data
