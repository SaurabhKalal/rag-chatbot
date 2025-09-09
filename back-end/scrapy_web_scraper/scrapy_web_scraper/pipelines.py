from scrapy.pipelines.images import ImagesPipeline
from scrapy import Request

class UniversalImagesPipeline(ImagesPipeline):

    def get_media_requests(self, item, info):
        # Ask Scrapy to download each image URL
        for image_url in item.get('images', []):
            yield Request(image_url)

    def item_completed(self, results, item, info):
        # Store file paths of downloaded images
        item['image_files'] = [x['path'] for ok, x in results if ok]
        return item
