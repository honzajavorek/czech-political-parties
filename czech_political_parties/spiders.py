import re

import arrow
import scrapy


TYPE_MAPPING = {
    'Politická strana': 'party',
    'Politické hnutí': 'movement',
}

KEY_MAPPING = {
    'Název hnutí:': 'name',
    'Název strany:': 'name',
    'Zkratka hnutí:': 'code',
    'Zkratka strany:': 'code',
    'Číslo registrace:': 'reg_number',
    'Identifikační číslo:': 'id',
    'Adresa sídla:': 'address',
    'Den registrace:': 'reg_date',
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
        item = dict(type=TYPE_MAPPING[extract_text(type_)])

        data = {}
        for tr in response.css('#vypisRejstrik tr'):
            try:
                key, value = tr.css('td')
            except ValueError:
                pass
            else:
                key, value = extract_text(key), extract_text(value)
                data[key] = value
        data = {new_key: data[key] for key, new_key in KEY_MAPPING.items()
                if key in data}

        item = {**item, **data}
        item['name'] = item['name'].strip('"„”“')
        item['code'] = item['code'].strip('"„”“')
        item['id'] = None if item['id'] == 'None' else item['id']
        item['reg_date'] = arrow.get(item['reg_date'], 'M/D/YYYY').date()
        yield item


def extract_text(td):
    return ' '.join([text.get() for text in td.css('::text, *::text')]).strip()
