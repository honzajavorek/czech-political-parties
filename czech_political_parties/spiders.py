import re

import arrow
import scrapy


TYPE_MAPPING = {
    'Politická strana': 'party',
    'Politické hnutí': 'movement',
}


class CzechPoliticalPartiesSpider(scrapy.Spider):
    name = 'czech-political-parties'
    start_urls = ['https://aplikace.mvcr.cz/seznam-politickych-stran/']

    def parse(self, response):
        yield scrapy.FormRequest.from_response(
            response,
            formid='aspnetForm',
            clickdata={'id': 'ctl00_Application_btnVyhledejVse'},
            callback=self.parse_search_results,
        )

    def parse_search_results(self, response):
        for link in response.css('#searchResults a'):
            yield response.follow(link, callback=self.parse_item)
        for link in response.css('#PagingRepeater1BottomPager a'):
            yield response.follow(link, callback=self.parse_search_results)

    def parse_item(self, response):
        type_ = response.css('#vypisRejstrik h3')[0]
        rows = response.css('#vypisRejstrik tr')

        data = {}
        for tr in rows:
            try:
                key, value = tr.css('td')
            except ValueError:
                pass
            else:
                key, value = extract_text(key), extract_text(value)
                data[key] = value

        heading = None
        people = []
        is_active = True
        for tr in rows:
            try:
                heading = tr.css('h3::text').get().strip()
            except AttributeError:
                if heading == 'Osoby':
                    role, person = tr.css('td')
                    role, person = extract_text(role), extract_text(person)
                    people.append({
                        'name': person.splitlines()[0].strip(),
                        'role': role.lower().rstrip(':'),
                    })
                if heading == 'Aktuální stav':
                    is_active = False

        yield {
            'name': (data.get('Název strany:') or data['Název hnutí:']).strip('"„”“'),
            'code': (data.get('Zkratka strany:') or data['Zkratka hnutí:']).strip('"„”“'),
            'id': None if data['Identifikační číslo:'] == 'None' else data['Identifikační číslo:'],
            'reg_number': data['Číslo registrace:'],
            'reg_date': arrow.get(data['Den registrace:'], 'M/D/YYYY').date(),
            'address': data['Adresa sídla:'],
            'people': people,
            'type': TYPE_MAPPING[extract_text(type_)],
            'is_active': is_active,
        }


def extract_text(td):
    return ' '.join([text.get() for text in td.css('::text, *::text')]).strip()
