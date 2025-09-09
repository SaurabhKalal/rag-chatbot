import scrapy

class UniversalItem(scrapy.Item):
    url = scrapy.Field()
    title = scrapy.Field()
    meta_description = scrapy.Field()
    text = scrapy.Field()
    images = scrapy.Field()
    image_files = scrapy.Field()
    videos = scrapy.Field()   
    iframes = scrapy.Field()  
    tables = scrapy.Field()
    links = scrapy.Field()
