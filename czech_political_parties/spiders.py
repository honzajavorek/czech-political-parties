import json
import re
from operator import itemgetter
from urllib.parse import parse_qs, urlencode, urlparse

import arrow
import scrapy


# The registry publishes an official open-data dataset with all of the party
# details we need. It doesn't say whether a record is a party or a movement,
# nor whether it's still active, so we enrich it with those two fields from the
# website's own React Server Components (RSC) list endpoint.
OPEN_DATA_URL = 'https://mv.gov.cz/app/opendata/boards/SPS'
LIST_URL = 'https://mv.gov.cz/seznam-politickych-stran'

# Ask Next.js for the React Flight payload (text/x-component) instead of HTML
RSC_HEADERS = {'RSC': '1'}

# `typ`, mirrored from the site's JavaScript bundle:
# 0 = party (politická strana), 1 = movement (politické hnutí)
TYPE_MAPPING = {0: 'party', 1: 'movement'}
# `Stavy` (SpsState) filter values: 1 = active, 2 = cancelled, 3 = paused,
# 4 = deleted. We list every state to include inactive parties and movements.
ALL_STATES = '1,2,3,4'
ACTIVE_STATE = '1'


class CzechPoliticalPartiesSpider(scrapy.Spider):
    name = 'czech-political-parties'
    start_urls = [OPEN_DATA_URL]

    def parse(self, response):
        parties = json.loads(response.text)['strany']
        # The open data omits the party/movement distinction, so fetch the RSC
        # list of all records to learn each one's `typ`.
        yield self._list_request(ALL_STATES, self.parse_types, parties=parties)

    def parse_types(self, response, parties):
        types = {party['id']: party['typ'] for party in self._list(response)}
        # ...and the list filtered to active records tells us which are active.
        yield self._list_request(
            ACTIVE_STATE, self.parse_active, parties=parties, types=types
        )

    def parse_active(self, response, parties, types):
        active_ids = {party['id'] for party in self._list(response)}
        for party in parties:
            yield build_item(party, types, active_ids)

    def _list_request(self, states, callback, **cb_kwargs):
        query = urlencode({'Stavy': states, 'PageSize': 1000, 'PageNo': 1})
        return scrapy.Request(
            f'{LIST_URL}?{query}',
            headers=RSC_HEADERS,
            callback=callback,
            cb_kwargs=cb_kwargs,
        )

    def _list(self, response):
        payload = FlightPayload(response.text)
        parties = payload.find('"politickeStranyList":')
        if parties is None:
            raise ValueError(
                f"Couldn't find the list of parties at {response.url}. "
                "The website's structure has probably changed."
            )
        paging = payload.find('"pagingInfo":')
        if paging and len(parties) < paging['itemCount']:
            raise ValueError(
                f"Got only {len(parties)} of {paging['itemCount']} records at "
                f"{response.url}. The 'PageSize' is no longer large enough."
            )
        return parties


def build_item(party, types, active_ids):
    party_id = int(parse_qs(urlparse(party['url']).query)['id'][0])
    people = [
        {
            'name': person['jméno'].strip(),
            'role': person['funkce'].rstrip(':').strip(),
        }
        for person in (party.get('osoby') or [])
        if person['jméno'].strip()
    ]
    ico = party['identifikační_číslo']
    return {
        'name': party['název'].strip('"„”“'),
        'code': party['zkratka'].strip('"„”“'),
        # Parties without an IČO come with the literal string "None"; the rest
        # come without leading zeros, so pad them back to the canonical 8 digits.
        'id': None if ico == 'None' else ico.zfill(8),
        'reg_number': party['číslo_registrace'],
        'reg_date': arrow.get(party['den_registrace']).date(),
        'address': party['adresa_sídla'],
        'people': sorted(people, key=itemgetter('name')),
        'type': TYPE_MAPPING[types[party_id]],
        'is_active': party_id in active_ids,
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
