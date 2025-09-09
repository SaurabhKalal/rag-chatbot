import os

BOT_NAME = "scrapy_web_scraper"

SPIDER_MODULES = ["scrapy_web_scraper.spiders"]
NEWSPIDER_MODULE = "scrapy_web_scraper.spiders"

# Respect robots.txt
ROBOTSTXT_OBEY = True

# Limit crawl depth (prevent endless loops)
DEPTH_LIMIT = 1

# Enable image downloading pipeline
ITEM_PIPELINES = {
    "scrapy_web_scraper.pipelines.UniversalImagesPipeline": 1,
}

# Where to store downloaded images
IMAGES_STORE = "downloaded_images"

# UTF-8 encoding for export
FEED_EXPORT_ENCODING = "utf-8"


OUTPUT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output.json"))

FEEDS = {
    '../output.json': {  # use .. to write to root folder
        'format': 'json',
        'overwrite': True,
        'encoding': 'utf8',
        'indent': 2,
    },
}


