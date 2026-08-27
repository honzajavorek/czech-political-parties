BOT_NAME = 'czech_political_parties'

SPIDER_MODULES = ['czech_political_parties.spiders']

USER_AGENT = 'czech-political-parties (+https://github.com/honzajavorek/czech-political-parties)'

# Ask Next.js for the React Flight payload (text/x-component) rather than the
# full HTML page. It's the same request the site makes when navigating on the
# client, and it returns the server-rendered data without the surrounding markup
DEFAULT_REQUEST_HEADERS = {'RSC': '1'}

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
