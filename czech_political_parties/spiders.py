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


class CzechPoliticalPartiesSpider(scrapy.Spider):
    # The `RSC` request header (see settings.py) makes every request return the
    # React Flight payload instead of the full HTML page.
    name = 'czech-political-parties'
    start_urls = [f'{BASE_URL}?{urlencode({"Stavy": ALL_STATES, "PageSize": 1000, "PageNo": 1})}']

    def parse(self, response):
        payload = FlightPayload(response.text)

        data = payload.find('"politickeStranyList":')
        if data is None:
            raise ValueError(
                f"Couldn't find the list of parties at {response.url}. "
                "The website's structure has probably changed."
            )

        # A single large page returns every record. If that ever stops being
        # true, fail loudly instead of silently scraping only the first page
        paging = payload.find('"pagingInfo":')
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
        party = FlightPayload(response.text).find('"data":{"id":')
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

        # Parties without an IČO come with the literal string "None".
        ico = party.get('ico')

        yield {
            'name': party['nazev'].strip('"„”“'),
            'code': party['zkratka'].strip('"„”“'),
            'id': None if ico in (None, '', 'None') else ico,
            'reg_number': party['cisloRegistrace'],
            'reg_date': arrow.get(party['datumRegistrace']).date(),
            'address': party['sidlo'],
            'people': sorted(people, key=itemgetter('name')),
            'type': TYPE_MAPPING[party['typ']],
            'is_active': party['stav'] == STATE_ACTIVE,
        }


class FlightPayload:
    """A parsed React Flight (RSC) payload.

    The payload is a sequence of newline-separated rows, each one ``<id>:<value>``.
    Most values are a single line of JSON; long or repeated strings are stored
    as a length-prefixed ``T<hexadecimal byte length>,<text>`` blob and referenced
    from elsewhere as ``"$<id>"`` (a literal leading ``$`` is escaped as ``$$``).
    """

    _REFERENCE_RE = re.compile(r'^\$[0-9a-f]+$')

    def __init__(self, text):
        self.text = text
        self.rows = self._parse_rows(text)

    def find(self, needle):
        """Decode the JSON value following ``needle`` and resolve its references.

        Returns ``None`` when ``needle`` isn't present.
        """
        index = self.text.find(needle)
        if index == -1:
            return None
        # When the needle already contains the value's opening brace (e.g.
        # ``"data":{"id":``) decode from that brace, otherwise from right after it
        brace = needle.find('{')
        start = index + (brace if brace != -1 else len(needle))
        value, _ = json.JSONDecoder().raw_decode(self.text[start:])
        return self._resolve(value)

    @staticmethod
    def _parse_rows(text):
        rows = {}
        index, length = 0, len(text)
        while index < length:
            colon = text.find(':', index)
            if colon == -1:
                break
            row_id = text[index:colon]
            start = colon + 1
            if start < length and text[start] == 'T':
                # A length-prefixed text blob: ``T<hexadecimal byte length>,<text>``
                comma = text.find(',', start)
                size = int(text[start + 1:comma], 16)
                body = text[comma + 1:].encode('utf-8')[:size].decode('utf-8')
                rows[row_id] = body
                index = comma + 1 + len(body)
                if index < length and text[index] == '\n':
                    index += 1
            else:
                end = text.find('\n', start)
                if end == -1:
                    end = length
                try:
                    rows[row_id] = json.loads(text[start:end])
                except json.JSONDecodeError:
                    rows[row_id] = text[start:end]  # non-JSON rows, e.g. `I[...]`
                index = end + 1
        return rows

    def _resolve(self, value):
        if isinstance(value, dict):
            return {key: self._resolve(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._resolve(item) for item in value]
        if isinstance(value, str):
            if self._REFERENCE_RE.match(value):
                target = self.rows.get(value[1:])
                return value if target is None else self._resolve(target)
            if value.startswith('$$'):
                return value[1:]
        return value
