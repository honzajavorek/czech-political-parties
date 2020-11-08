# 🇨🇿 czech-political-parties

Tracking changes in Czech political parties

- [History of changes](https://github.com/honzajavorek/czech-political-parties/commits/main/items.json)
- [Feed of changes](https://github.com/honzajavorek/czech-political-parties/commits/main.atom) (aka RSS)
- [Download JSON](https://raw.githubusercontent.com/honzajavorek/czech-political-parties/main/items.json)

Inspired by [@simonw](https://github.com/simonw)'s [git scraping article](https://simonwillison.net/2020/Oct/9/git-scraping/) and [this tweet](https://twitter.com/simonw/status/1324479089760104448). I noticed there is a [registry of all political parties and movements in the Czech Republic](https://aplikace.mvcr.cz/seznam-politickych-stran/), and that for journalists [it's sometimes useful to monitor it for changes](https://www.seznamzpravy.cz/clanek/minar-si-zalozil-novy-spolek-pro-cr-ma-zmenit-cesko-k-lepsimu-126163#utm_content=ribbonnavignews&utm_term=milion%20chvilek&utm_medium=hint&utm_source=search.seznam.cz). Hence I decided to scrape the registry and have it as a git scraping pet project.

The scraper uses my favorite [Scrapy](https://docs.scrapy.org/) framework. So far I scrape only a few fields. If you want to build on top of the data and you're missing something, let me know in [issues](https://github.com/honzajavorek/czech-political-parties/issues). The data is sorted by registration date, so that the newest parties and movements are at the top of the file.

I'm curious what changes I'm about to see!
