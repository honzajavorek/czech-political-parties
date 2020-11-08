BOT_NAME = 'czech_political_parties'

SPIDER_MODULES = ['czech_political_parties.spiders']

USER_AGENT = 'czech-political-parties (+https://github.com/honzajavorek/czech-political-parties)'

FEED_EXPORTERS = {
    'sorted_json': 'czech_political_parties.exporters.SortedJsonItemExporter',
}

FEEDS = {
    'items.json': {
        'format': 'sorted_json',
        'encoding': 'utf-8',
        'indent': 4,
        'overwrite': True,
    },
}
