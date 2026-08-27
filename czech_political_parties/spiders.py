import json
import re
from operator import itemgetter
from urllib.parse import urlencode

import arrow
import scrapy


BASE_URL = 'https://mv.gov.cz/seznam-politickych-stran'

# Numeric enums mirrored from the site's JavaScript bundle
# `typ`: 0 = party (politická strana), 1 = movement (politické hnutí)
TYPE_MAPPING = {0: 'party', 1: 'movement'}
# `stav` (SpsState): 1 = active, 2 = cancelled, 3 = paused, 4 = deleted
STATE_ACTIVE = 1
# All of the states, so that we scrape inactive parties and movements too
ALL_STATES = '1,2,3,4'

_NEXT_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[\d+,"((?:[^"\\]|\\.)*)"\]\)', re.DOTALL)
_REFERENCE_RE = re.compile(r'^\$[0-9a-f]+$')


class CzechPoliticalPartiesSpider(scrapy.Spider):
    name = 'czech-political-parties'
    start_urls = [f'{BASE_URL}?{urlencode({"Stavy": ALL_STATES, "PageSize": 1000, "PageNo": 1})}']

    def parse(self, response):
        data = extract_next_data(response, '"politickeStranyList":')
        if data is None:
            raise ValueError(
                f"Couldn't find the list of parties at {response.url}. "
                "The website's structure has probably changed."
            )

        # A single large page returns every record. If that ever stops being
        # true, fail loudly instead of silently scraping only the first page.
        paging = extract_next_data(response, '"pagingInfo":')
        if paging and len(data) < paging['itemCount']:
            raise ValueError(
                f"Got only {len(data)} of {paging['itemCount']} records at "
                f"{response.url}. The 'PageSize' is no longer large enough."
            )

        for party in data:
            yield response.follow(
                f'{BASE_URL}?{urlencode({"id": party["id"]})}',
                callback=self.parse_item,
            )

    def parse_item(self, response):
        party = extract_next_data(response, '"data":{"id":')
        if party is None:
            raise ValueError(
                f"Couldn't find party details at {response.url}. "
                "The website's structure has probably changed."
            )

        people = [
            {
                'name': person['cele_jmeno'].strip(),
                'role': person['typ_osoby'].rstrip(':').strip(),
            }
            for person in (party.get('osoby') or [])
            if not person.get('datum_do') and person['cele_jmeno'].strip()
        ]

        yield {
            'name': party['nazev'].strip('"„”“'),
            'code': party['zkratka'].strip('"„”“'),
            'id': party.get('ico') or None,
            'reg_number': party['cisloRegistrace'],
            'reg_date': arrow.get(party['datumRegistrace']).date(),
            'address': party['sidlo'],
            'people': sorted(people, key=itemgetter('name')),
            'type': TYPE_MAPPING[party['typ']],
            'is_active': party['stav'] == STATE_ACTIVE,
        }


def extract_next_data(response, needle):
    """Read a JSON value that follows ``needle`` in the page's RSC payload.

    The frontend streams its server-rendered data as a series of
    ``self.__next_f.push([n, "..."])`` calls whose string chunks concatenate
    into one big RSC payload. We rebuild that payload, locate ``needle``,
    decode the JSON value right after it and resolve any RSC references it
    contains. Returns ``None`` when ``needle`` isn't present.
    """
    payload = ''.join(
        json.loads(f'"{chunk}"') for chunk in _NEXT_PUSH_RE.findall(response.text)
    )
    index = payload.find(needle)
    if index == -1:
        return None
    # When the needle already contains the value's opening brace (e.g.
    # ``"data":{"id":``) decode from that brace, otherwise from right after it.
    brace = needle.find('{')
    start = index + (brace if brace != -1 else len(needle))
    value, _ = json.JSONDecoder().raw_decode(payload[start:])
    return resolve_references(value, payload)


def resolve_references(value, payload):
    """Replace RSC references with the values they point to.

    Long or repeated strings (e.g. some party names) aren't inlined; the RSC
    payload stores them as a numbered row and references them from elsewhere
    as ``"$1f"``. A literal leading ``$`` is escaped as ``$$``.
    """
    if isinstance(value, dict):
        return {key: resolve_references(item, payload) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_references(item, payload) for item in value]
    if isinstance(value, str):
        if _REFERENCE_RE.match(value):
            resolved = read_row(value[1:], payload)
            if resolved == value:  # row not found; leave the reference as-is
                return value
            return resolve_references(resolved, payload)
        if value.startswith('$$'):
            return value[1:]
    return value


def read_row(row_id, payload):
    """Return the value of the RSC payload row labelled ``row_id``."""
    match = re.search(rf'(?:^|\n){re.escape(row_id)}:', payload)
    if match is None:
        return f'${row_id}'
    start = match.end()
    if payload[start] == 'T':
        # A length-prefixed text blob: ``T<hexadecimal byte length>,<text>``.
        comma = payload.index(',', start)
        length = int(payload[start + 1:comma], 16)
        return payload[comma + 1:].encode('utf-8')[:length].decode('utf-8', 'ignore')
    value, _ = json.JSONDecoder().raw_decode(payload[start:])
    return value
