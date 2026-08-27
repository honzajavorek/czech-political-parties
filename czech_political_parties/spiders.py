import json
import re
from operator import itemgetter
from urllib.parse import urlencode

import arrow
import scrapy


# The registry moved from the old ASP.NET application at
# aplikace.mvcr.cz/seznam-politickych-stran to a new React (Next.js) frontend
# at mv.gov.cz/seznam-politickych-stran. The new site renders everything on the
# client from an internal API which is not reachable from the outside. However,
# the same data is server-side rendered into every page as a dehydrated
# @tanstack/react-query cache embedded in the streamed RSC payload (the
# `self.__next_f.push(...)` scripts). We reconstruct that payload and read the
# data straight out of it.
BASE_URL = 'https://mv.gov.cz/seznam-politickych-stran'

# The frontend numeric enums, mirrored from its JavaScript bundle.
# `typ`: 0 = party (politická strana), 1 = movement (politické hnutí).
TYPE_MAPPING = {0: 'party', 1: 'movement'}
# `stav` (SpsState): 1 = active, 2 = cancelled, 3 = paused, 4 = deleted.
STATE_ACTIVE = 1
# All of the states, so that we scrape inactive parties and movements too.
ALL_STATES = '1,2,3,4'

_NEXT_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[\d+,"((?:[^"\\]|\\.)*)"\]\)', re.S)


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

        for party in data:
            party_id = party['id']
            yield response.follow(
                f'{BASE_URL}?{urlencode({"id": party_id})}',
                callback=self.parse_item,
            )

        # Follow the remaining pages, should the page size ever stop being
        # enough to fit all the records into a single response.
        paging = extract_next_data(response, '"pagingInfo":')
        if paging and response.url == self.start_urls[0]:
            for page_no in range(2, (paging.get('pageCount') or 1) + 1):
                yield response.follow(
                    f'{BASE_URL}?{urlencode({"Stavy": ALL_STATES, "PageSize": 1000, "PageNo": page_no})}',
                    callback=self.parse,
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

    The Next.js frontend streams its server-rendered data as a series of
    ``self.__next_f.push([n, "..."])`` calls whose string chunks concatenate
    into one big RSC payload. We rebuild that payload, locate ``needle`` and
    decode the JSON value right after it. Returns ``None`` when ``needle``
    isn't present.
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
    return value
