# 🇨🇿 czech-political-parties

Tracking changes in Czech political parties:

- [History of changes](https://github.com/honzajavorek/czech-political-parties/commits/main/items.json)
- [Feed of changes](https://github.com/honzajavorek/czech-political-parties/commits/main.atom) (aka RSS)
- [Download JSON](https://raw.githubusercontent.com/honzajavorek/czech-political-parties/main/items.json)

Inspired by [@simonw](https://github.com/simonw)'s [git scraping article](https://simonwillison.net/2020/Oct/9/git-scraping/) and [this tweet](https://twitter.com/simonw/status/1324479089760104448). I noticed there is a [registry of all political parties and movements in the Czech Republic](https://mv.gov.cz/seznam-politickych-stran), and that for journalists [it's sometimes useful to monitor it for changes](https://www.seznamzpravy.cz/clanek/minar-si-zalozil-novy-spolek-pro-cr-ma-zmenit-cesko-k-lepsimu-126163#utm_content=ribbonnavignews&utm_term=milion%20chvilek&utm_medium=hint&utm_source=search.seznam.cz). Hence I decided to scrape the registry and have it as a git scraping pet project.

The scraper uses my favorite [Scrapy](https://docs.scrapy.org/) framework. So far I scrape only a few fields. If you want to build on top of the data and you're missing something, let me know in [issues](https://github.com/honzajavorek/czech-political-parties/issues). The data is sorted by registration date, so that the newest parties and movements are at the top of the file.

If you just need the raw registry data, you may not need this project at all: the Ministry publishes it as official open data — a machine-readable dataset at [`/app/opendata/boards/SPS`](https://mv.gov.cz/app/opendata/boards/SPS) (described by its [metadata](https://mv.gov.cz/app/opendata/boards/SPS/meta), updated hourly). What this project adds on top are two fields the open data doesn't expose: whether each record is a party or a movement (`type`), and whether it's still active (`is_active`).

That's also how the scraper works. It takes the bulk of the data from that open-data dataset — a single, official request — and enriches it with `type` and `is_active` from the registry's RSC (React Server Components) list endpoint, requested via the `RSC` header and read out of the React Flight payload it returns. Leaning on the open data keeps things resilient: the RSC endpoint is an internal implementation detail of the website that can change without notice, while the open data is a documented, stable interface.

I'm curious what changes I'm about to see!
