import scrapy
from ..items import UniversalItem
from urllib.parse import urljoin

class UniversalSpider(scrapy.Spider):
    name = "universal_spider"

    custom_settings = {
        'CONCURRENT_REQUESTS': 32,
        'DOWNLOAD_DELAY': 0,
        'ROBOTSTXT_OBEY': False,
        'COOKIES_ENABLED': False,
        'LOG_LEVEL': 'WARNING',
        'RETRY_ENABLED': False,
        'DOWNLOAD_TIMEOUT': 60
    }

    def __init__(self, start_url=None, *args, **kwargs):
        super(UniversalSpider, self).__init__(*args, **kwargs)
        self.start_urls = [start_url]

    def parse(self, response):
        item = UniversalItem()

        # Extract visible content
        text_parts = response.xpath(
            '''
            //h1//text() | //h2//text() | //h3//text() | //h4//text() | //h5//text() | //h6//text() |
            //p//text() | //span//text() | //li//text() |
            //strong//text() | //b//text() | //em//text() | //i//text() |
            //a//text() | //button//text()
            '''
        ).getall()
        clean_text = " ".join(t.strip() for t in text_parts if t.strip())

        title = response.xpath('//title/text()').get(default='')
        meta_desc = response.xpath('//meta[@name="description"]/@content').get(default='')

        item['url'] = response.url
        item['title'] = title
        item['meta_description'] = meta_desc
        item['text'] = clean_text

        if clean_text:
            yield item
        else:
            self.logger.warning(f"No clean text found on: {response.url}")





# import scrapy
# from ..items import UniversalItem
# from urllib.parse import urljoin

# class UniversalSpider(scrapy.Spider):
#     name = "universal_spider"

#     custom_settings = {
#         'CONCURRENT_REQUESTS': 32,
#         'DOWNLOAD_DELAY': 0,
#         'ROBOTSTXT_OBEY': False,
#         'COOKIES_ENABLED': False,
#         'LOG_LEVEL': 'WARNING',
#         'RETRY_ENABLED': False,
#         'DOWNLOAD_TIMEOUT': 60
#     }

#     def __init__(self, start_url=None, *args, **kwargs):
#         super(UniversalSpider, self).__init__(*args, **kwargs)
#         self.start_urls = [start_url]

#     def parse(self, response):
#         item = UniversalItem()

#         text_parts = response.xpath(
#             "//h1//text() | //h2//text() | //h3//text() | //h4//text() | //h5//text() | //h6//text() | "
#             "//p//text() | //span//text() | //li//text() | "
#             "//strong//text() | //b//text() | //em//text() | //i//text() | "
#             "//a//text() | //button//text()"
#         ).getall()
#         clean_text = " ".join(t.strip() for t in text_parts if t.strip())

#         title = response.xpath('//title/text()').get(default='')
#         meta_desc = response.xpath('//meta[@name="description"]/@content').get(default='')

#         links = [urljoin(response.url, href) for href in response.xpath('//a/@href').getall()]

#         item['url'] = response.url
#         item['title'] = title
#         item['meta_description'] = meta_desc
#         item['text'] = clean_text
#         item['links'] = links

#         yield item

#         for link in links:
#             if link.startswith("http"):
#                 yield response.follow(link, callback=self.parse)
