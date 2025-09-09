# Enhanced scraper.py with Depth Crawling
import requests
from bs4 import BeautifulSoup
import trafilatura
from newspaper import Article
import re
import json
import time
from urllib.parse import urljoin, urlparse, urlunparse
import os
from datetime import datetime
import hashlib
from langdetect import detect
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from collections import Counter, deque
import logging


# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

class DepthRAGScraper:
    def __init__(self, output_dir="premium_rag_data", max_depth=2, max_pages=50):
        self.output_dir = output_dir
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.scraped_urls = set()
        self.discovered_urls = set()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(output_dir, 'scraping.log')),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        print(f"🚀 Depth RAG Scraper initialized")
        print(f"📁 Output directory: {output_dir}")
        print(f"🔄 Max depth: {max_depth}")
        print(f"📄 Max pages: {max_pages}")
    
    def normalize_url(self, url):
        """Normalize URL by removing fragments and unnecessary parameters"""
        try:
            parsed = urlparse(url)
            # Remove fragment and common tracking parameters
            query_parts = []
            if parsed.query:
                for param in parsed.query.split('&'):
                    if not any(track in param.lower() for track in ['utm_', 'fb_', 'gclid', 'ref=']):
                        query_parts.append(param)
            
            normalized = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path.rstrip('/'),
                parsed.params,
                '&'.join(query_parts),
                ''  # Remove fragment
            ))
            return normalized
        except:
            return url
    
    def is_same_domain(self, url, base_url):
        """Check if URL belongs to the same domain as base URL"""
        try:
            base_domain = urlparse(base_url).netloc.lower()
            url_domain = urlparse(url).netloc.lower()
            
            # Handle subdomains
            if base_domain.startswith('www.'):
                base_domain = base_domain[4:]
            if url_domain.startswith('www.'):
                url_domain = url_domain[4:]
                
            return url_domain == base_domain or url_domain.endswith('.' + base_domain)
        except:
            return False
    
    def should_skip_url(self, url):
        """Check if URL should be skipped based on common patterns"""
        skip_patterns = [
            # File types
            r'\.(pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar|tar|gz)$',
            r'\.(jpg|jpeg|png|gif|bmp|svg|ico|webp)$',
            r'\.(mp3|mp4|avi|mov|wmv|flv|wav)$',
            r'\.(css|js|xml|json)$',
            
            # Common pages to skip
            r'/(login|register|signup|signin|logout)',
            r'/(cart|checkout|payment|billing)',
            r'/(admin|dashboard|profile|account)',
            r'/(search|filter|sort)',
            r'/wp-admin',
            r'/wp-content',
            r'/(privacy|terms|cookie|legal)',
            
            # Parameters to skip
            r'[?&](page|p)=\d+',  # Pagination
            r'[?&](sort|order)=',
            r'[?&](filter|category)=',
            r'mailto:',
            r'tel:',
            r'javascript:',
        ]
        
        url_lower = url.lower()
        return any(re.search(pattern, url_lower) for pattern in skip_patterns)
    
    def extract_links(self, soup, base_url):
        """Extract all internal links from the page"""
        links = set()
        
        # Find all anchor tags with href
        for link in soup.find_all('a', href=True):
            href = link['href'].strip()
            if not href or href.startswith('#'):
                continue
            
            try:
                # Convert relative URLs to absolute
                full_url = urljoin(base_url, href)
                normalized_url = self.normalize_url(full_url)
                
                # Check if it's a valid internal link
                if (self.is_same_domain(normalized_url, base_url) and 
                    not self.should_skip_url(normalized_url) and
                    normalized_url not in self.scraped_urls):
                    links.add(normalized_url)
            except Exception as e:
                self.logger.error(f"Error processing link {href}: {e}")
                continue
        
        return links
    
    def crawl_website(self, start_urls, delay=2):
        """Crawl website with depth-first approach"""
        all_scraped_data = []
        
        # Initialize queue with start URLs at depth 0
        url_queue = deque([(url, 0) for url in start_urls])
        
        print(f"\n🕷️  Starting depth crawl...")
        print(f"🎯 Starting URLs: {len(start_urls)}")
        print(f"🔄 Maximum depth: {self.max_depth}")
        print(f"📄 Maximum pages: {self.max_pages}")
        
        pages_scraped = 0
        
        while url_queue and pages_scraped < self.max_pages:
            current_url, depth = url_queue.popleft()
            
            if current_url in self.scraped_urls:
                continue
            
            pages_scraped += 1
            print(f"\n📄 [{pages_scraped}/{self.max_pages}] Depth {depth}: {current_url}")
            
            # Extract content from current page
            result = self.extract_with_multiple_methods(current_url)
            
            if result and result['score'] >= 30:
                result['crawl_depth'] = depth
                all_scraped_data.append(result)
                print(f"✅ Content extracted! Quality score: {result['score']}")
                
                # If we haven't reached max depth, extract links for further crawling
                if depth < self.max_depth:
                    try:
                        response = self.session.get(current_url, timeout=15)
                        soup = BeautifulSoup(response.content, 'html.parser')
                        new_links = self.extract_links(soup, current_url)
                        
                        # Add new links to queue with increased depth
                        for link in new_links:
                            if link not in self.scraped_urls and len(url_queue) < 100:  # Limit queue size
                                url_queue.append((link, depth + 1))
                                self.discovered_urls.add(link)
                        
                        print(f"🔗 Found {len(new_links)} new links at depth {depth}")
                        
                    except Exception as e:
                        self.logger.error(f"Error extracting links from {current_url}: {e}")
            else:
                score = result['score'] if result else 0
                print(f"❌ Content rejected. Quality score: {score}")
            
            self.scraped_urls.add(current_url)
            
            if pages_scraped < self.max_pages:
                print(f"⏱️  Waiting {delay} seconds...")
                time.sleep(delay)
        
        print(f"\n🎉 Crawling completed!")
        print(f"📄 Pages scraped: {pages_scraped}")
        print(f"🔗 Total URLs discovered: {len(self.discovered_urls)}")
        print(f"✅ High-quality documents: {len(all_scraped_data)}")
        
        return all_scraped_data
    
    def extract_with_multiple_methods(self, url):
        """Use multiple extraction methods and pick the best result"""
        results = {}
        
        # Method 1: Trafilatura (Best for content extraction)
        try:
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                content = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
                metadata = trafilatura.extract_metadata(downloaded)
                
                if content and len(content) > 200:
                    results['trafilatura'] = {
                        'content': content,
                        'title': metadata.title if metadata else '',
                        'author': metadata.author if metadata else '',
                        'date': metadata.date if metadata else '',
                        'score': self.quality_score(content),
                        'method': 'trafilatura'
                    }
        except Exception as e:
            self.logger.error(f"❌ Trafilatura failed for {url}: {e}")
        
        # Method 2: Newspaper3k (Best for articles)
        try:
            if self.is_article_url(url):
                article = Article(url)
                article.download()
                article.parse()
                
                if article.text and len(article.text) > 200:
                    results['newspaper'] = {
                        'content': article.text,
                        'title': article.title,
                        'author': ', '.join(article.authors) if article.authors else '',
                        'date': article.publish_date.isoformat() if article.publish_date else '',
                        'score': self.quality_score(article.text),
                        'method': 'newspaper3k'
                    }
        except Exception as e:
            self.logger.error(f"❌ Newspaper3k failed for {url}: {e}")
        
        # Method 3: BeautifulSoup (Fallback)
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            content = self.extract_with_beautifulsoup(soup)
            if content and len(content['content']) > 200:
                results['beautifulsoup'] = {
                    **content,
                    'score': self.quality_score(content['content']),
                    'method': 'beautifulsoup'
                }
        except Exception as e:
            self.logger.error(f"❌ BeautifulSoup failed for {url}: {e}")
        
        # Return the best result based on quality score
        if results:
            best_method = max(results.keys(), key=lambda k: results[k]['score'])
            best_result = results[best_method]
            best_result['url'] = url
            best_result['scraped_at'] = datetime.now().isoformat()
            best_result['extraction_methods_tried'] = list(results.keys())
            
            return best_result
        
        return None
    
    def is_article_url(self, url):
        """Determine if URL likely contains an article"""
        article_indicators = [
            'article', 'post', 'blog', 'news', 'story', 'tutorial',
            '/20', '/21', '/22', '/23', '/24', '/25'  # Years in URL
        ]
        return any(indicator in url.lower() for indicator in article_indicators)
    
    def extract_with_beautifulsoup(self, soup):
        """Enhanced BeautifulSoup extraction"""
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 
                           'aside', 'advertisement', 'ads', 'sidebar', 'menu']):
            element.decompose()
        
        # Try multiple content selectors
        content_selectors = [
            'article', 'main', '.content', '.main-content', 
            '.article-content', '.post-content', '.entry-content',
            '[role="main"]', '.article-body', '.story-body',
            '.post-body', '.content-body'
        ]
        
        main_content = None
        for selector in content_selectors:
            main_content = soup.select_one(selector)
            if main_content and len(main_content.get_text().strip()) > 200:
                break
        
        if not main_content:
            main_content = soup.find('body')
        
        # Extract title
        title = ""
        for title_selector in ['h1', 'title', '.title', '.headline', '.post-title']:
            title_elem = soup.select_one(title_selector)
            if title_elem:
                title = title_elem.get_text().strip()
                if len(title) > 5:  # Ensure it's a meaningful title
                    break
        
        # Extract content
        if main_content:
            content = main_content.get_text(separator=' ', strip=True)
            content = self.clean_text(content)
            
            return {
                'content': content,
                'title': title,
                'author': '',
                'date': ''
            }
        
        return None
    
    def clean_text(self, text):
        """Advanced text cleaning for RAG"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common web artifacts
        artifacts = [
            r'Cookie Policy.*?(?=\.|\n|$)',
            r'Privacy Policy.*?(?=\.|\n|$)',
            r'Terms of Service.*?(?=\.|\n|$)',
            r'Click here.*?(?=\.|\n|$)',
            r'Read more.*?(?=\.|\n|$)',
            r'Share this.*?(?=\.|\n|$)',
            r'Subscribe.*?(?=\.|\n|$)',
            r'Sign up.*?(?=\.|\n|$)',
            r'Advertisement',
            r'Sponsored content',
            r'\[.*?\]',  # Remove content in brackets
            r'©\s*\d{4}.*?(?=\.|\n|$)',  # Copyright notices
            r'All rights reserved.*?(?=\.|\n|$)',
        ]
        
        for artifact in artifacts:
            text = re.sub(artifact, '', text, flags=re.IGNORECASE)
        
        # Fix common encoding issues
        replacements = {
            '\u00a0': ' ',  # Non-breaking space
            '\u2019': "'",  # Smart apostrophe
            '\u201c': '"',  # Left double quote
            '\u201d': '"',  # Right double quote
            '\u2013': '-',  # En dash
            '\u2014': '--', # Em dash
            '\u2026': '...', # Ellipsis
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Remove excessive punctuation
        text = re.sub(r'\.{3,}', '...', text)
        text = re.sub(r'-{3,}', '---', text)
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def quality_score(self, text):
        """Calculate quality score for extracted content"""
        if not text or len(text.strip()) < 50:
            return 0
        
        score = 0
        words = text.split()
        word_count = len(words)
        
        try:
            sentences = sent_tokenize(text)
        except:
            sentences = text.split('.')
        
        # Length scoring
        if 500 <= word_count <= 5000:
            score += 30
        elif 200 <= word_count < 500:
            score += 20
        elif 100 <= word_count < 200:
            score += 10
        else:
            score += 5
        
        # Sentence structure scoring
        if len(sentences) > 0:
            avg_sentence_length = word_count / len(sentences)
            if 10 <= avg_sentence_length <= 25:
                score += 20
            elif 5 <= avg_sentence_length < 10:
                score += 10
        
        # Language detection
        try:
            if detect(text) == 'en':
                score += 15
        except:
            score += 10
        
        # Content diversity
        if word_count > 0:
            unique_words = len(set(word.lower() for word in words if word.isalpha()))
            lexical_diversity = unique_words / word_count
            if lexical_diversity > 0.5:
                score += 15
            elif lexical_diversity > 0.3:
                score += 10
        
        return max(score, 0)
    
    def create_smart_chunks(self, text, chunk_size=500, overlap=50):
        """Create intelligent chunks preserving sentence boundaries"""
        try:
            sentences = sent_tokenize(text)
        except:
            sentences = [s.strip() + '.' for s in text.split('.') if s.strip()]
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sentence_words = sentence.split()
            sentence_length = len(sentence_words)
            
            if current_length + sentence_length <= chunk_size:
                current_chunk.append(sentence)
                current_length += sentence_length
            else:
                if current_chunk:
                    chunk_text = ' '.join(current_chunk)
                    if len(chunk_text.strip()) > 50:
                        chunks.append(chunk_text)
                    
                    # Create overlap
                    if overlap > 0 and len(current_chunk) > 1:
                        overlap_sentences = []
                        overlap_length = 0
                        for sent in reversed(current_chunk):
                            sent_length = len(sent.split())
                            if overlap_length + sent_length <= overlap:
                                overlap_sentences.insert(0, sent)
                                overlap_length += sent_length
                            else:
                                break
                        current_chunk = overlap_sentences
                        current_length = overlap_length
                    else:
                        current_chunk = []
                        current_length = 0
                
                current_chunk.append(sentence)
                current_length += sentence_length
        
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            if len(chunk_text.strip()) > 50:
                chunks.append(chunk_text)
        
        return chunks
    

    def save_results(self, data, chunk_size=800, overlap=100):
        """Save crawling results"""
        if not data:
            print("❌ No data to save!")
            return None

        # Create directories
        for subdir in ['documents', 'chunks', 'metadata']:
            os.makedirs(os.path.join(self.output_dir, subdir), exist_ok=True)

        all_chunks = []
        combined_text = ""  # To store all content for combined file

        print(f"\n💾 Saving {len(data)} documents...")

        for i, doc in enumerate(data):
            # Safe filename
            safe_title = re.sub(r'[^\w\s-]', '', doc['title'])[:50]
            if not safe_title:
                safe_title = f"document_{i}"
            
            filename = f"{i:03d}_{safe_title}_depth{doc.get('crawl_depth', 0)}_score{doc['score']}.txt"
            file_path = os.path.join(self.output_dir, 'documents', filename)

            document_text = (
                f"Title: {doc['title']}\n"
                f"URL: {doc['url']}\n"
                f"Crawl Depth: {doc.get('crawl_depth', 0)}\n"
                f"Quality Score: {doc['score']}\n"
                f"Method: {doc['method']}\n"
                f"Scraped: {doc['scraped_at']}\n"
                + "-" * 60 + "\n\n"
                + doc['content'] + "\n\n"
            )

            # Write individual file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(document_text)

            # Append to combined text
            combined_text += document_text + "\n" + "=" * 100 + "\n\n"

            # Create chunks
            chunks = self.create_smart_chunks(doc['content'], chunk_size, overlap)
            for j, chunk in enumerate(chunks):
                chunk_data = {
                    'text': chunk,
                    'source_title': doc['title'],
                    'source_url': doc['url'],
                    'crawl_depth': doc.get('crawl_depth', 0),
                    'quality_score': doc['score'],
                    'chunk_index': j,
                    'total_chunks': len(chunks),
                    'chunk_id': hashlib.md5(f"{doc['url']}_{j}".encode()).hexdigest()[:12],
                    'created_at': datetime.now().isoformat()
                }
                all_chunks.append(chunk_data)

        # ✅ Ensure 'output' folder exists
        output_dir = os.path.join(self.output_dir, 'output')
        os.makedirs(output_dir, exist_ok=True)

        # ✅ Save combined text file inside 'output' folder
        combined_path = os.path.join(output_dir, 'combined_documents.txt')
        with open(combined_path, 'w', encoding='utf-8') as f:
            f.write(combined_text)

        print(f"📄 Combined document saved to: {combined_path}")

        # Save chunks
        chunks_file = os.path.join(self.output_dir, 'chunks', 'all_chunks.jsonl')
        with open(chunks_file, 'w', encoding='utf-8') as f:
            for chunk in all_chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + '\n')

        # Save metadata
        metadata = {
            'total_documents': len(data),
            'total_chunks': len(all_chunks),
            'average_quality_score': sum(d['score'] for d in data) / len(data),
            'urls_scraped': len(self.scraped_urls),
            'urls_discovered': len(self.discovered_urls),
            'created_at': datetime.now().isoformat()
        }

        with open(os.path.join(self.output_dir, 'metadata', 'crawl_info.json'), 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"✅ Saved {len(data)} documents and {len(all_chunks)} chunks")
        return metadata



def main():
    """Main function to run the depth scraper"""
    print(" Depth RAG Data Scraper")
    print("=" * 50)
    
    # Configuration
    start_urls = [
        "https://aitglobalinc.com/"
    ]
    
    # Initialize depth scraper
    scraper = DepthRAGScraper(
        output_dir="depth_rag_dataset",
        max_depth=6,        
        max_pages=60        
    )
    
    # Start crawling
    scraped_data = scraper.crawl_website(start_urls, delay=3)
    
    if scraped_data:
        # Save results
        metadata = scraper.save_results(scraped_data)
        print(f"\nCrawling completed successfully!")
        print(f"Results saved in: {scraper.output_dir}")
    else:
        print("\nNo data was scraped.")

if __name__ == "__main__":
    main()
