"""
Web Scraper for VTB Bank Belarus website
Extracts relevant information for knowledge base
"""

import asyncio
import aiohttp
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Any, Set
import re
from datetime import datetime
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class VTBWebScraper:
    """Web scraper for VTB Bank Belarus website"""
    
    def __init__(self, base_url: str = "https://www.vtb.by", max_pages: int = 50):
        self.base_url = base_url
        self.max_pages = max_pages
        self.visited_urls: Set[str] = set()
        self.scraped_data: List[Dict[str, Any]] = []
        self.session = None
        
        # Keywords to identify relevant content
        self.relevant_keywords = [
            'карта', 'счет', 'кредит', 'депозит', 'перевод', 'платеж',
            'интернет-банк', 'мобильное приложение', 'услуги', 'тарифы',
            'поддержка', 'помощь', 'вопросы', 'ответы', 'faq', 'инструкция',
            'регистрация', 'вход', 'безопасность', 'блокировка', 'разблокировка'
        ]
        
        # URLs to prioritize
        self.priority_paths = [
            '/services/', '/cards/', '/deposits/', '/credits/', '/support/',
            '/help/', '/faq/', '/tariffs/', '/mobile/', '/internet-bank/'
        ]
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def scrape_website(self) -> List[Dict[str, Any]]:
        """Main scraping method"""
        logger.info(f"Starting web scraping of {self.base_url}")
        
        try:
            # Start with main page
            await self._scrape_page(self.base_url, priority=1)
            
            # Find and scrape additional pages
            await self._discover_and_scrape_pages()
            
            # Process and clean scraped data
            processed_data = self._process_scraped_data()
            
            logger.info(f"Scraping completed. Found {len(processed_data)} relevant pages")
            return processed_data
            
        except Exception as e:
            logger.error(f"Error during web scraping: {e}")
            return []
    
    async def _scrape_page(self, url: str, priority: int = 0) -> Dict[str, Any]:
        """Scrape a single page"""
        if url in self.visited_urls:
            return {}
        
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return {}
                
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Extract page data
                page_data = {
                    'url': url,
                    'title': self._extract_title(soup),
                    'content': self._extract_content(soup),
                    'links': self._extract_links(soup, url),
                    'priority': priority,
                    'scraped_at': datetime.now().isoformat(),
                    'relevance_score': self._calculate_relevance_score(soup)
                }
                
                # Only store if relevant
                if page_data['relevance_score'] > 0.3:
                    self.scraped_data.append(page_data)
                    self.visited_urls.add(url)
                    logger.info(f"Scraped: {url} (relevance: {page_data['relevance_score']:.2f})")
                
                return page_data
                
        except Exception as e:
            logger.warning(f"Error scraping {url}: {e}")
            return {}
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title"""
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text().strip()
        return ""
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Extract main content from page"""
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Extract text from main content areas
        content_selectors = [
            'main', 'article', '.content', '.main-content', 
            '.page-content', '.text-content', 'body'
        ]
        
        content_text = ""
        for selector in content_selectors:
            elements = soup.select(selector)
            for element in elements:
                content_text += element.get_text() + " "
        
        # Clean up text
        content_text = re.sub(r'\s+', ' ', content_text).strip()
        return content_text
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract relevant links from page"""
        links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(base_url, href)
            
            # Only include internal links
            if self._is_internal_link(full_url):
                links.append(full_url)
        
        return list(set(links))  # Remove duplicates
    
    def _is_internal_link(self, url: str) -> bool:
        """Check if link is internal to VTB website"""
        try:
            parsed_url = urlparse(url)
            base_domain = urlparse(self.base_url).netloc
            return parsed_url.netloc == base_domain or parsed_url.netloc == ""
        except:
            return False
    
    def _calculate_relevance_score(self, soup: BeautifulSoup) -> float:
        """Calculate relevance score for page content"""
        text_content = soup.get_text().lower()
        score = 0.0
        
        # Check for relevant keywords
        keyword_matches = sum(1 for keyword in self.relevant_keywords if keyword in text_content)
        score += keyword_matches * 0.1
        
        # Check for FAQ or help content
        if any(word in text_content for word in ['вопрос', 'ответ', 'faq', 'помощь', 'поддержка']):
            score += 0.3
        
        # Check for banking services content
        if any(word in text_content for word in ['услуги', 'карта', 'счет', 'кредит', 'депозит']):
            score += 0.2
        
        # Normalize score
        return min(score, 1.0)
    
    async def _discover_and_scrape_pages(self):
        """Discover and scrape additional pages"""
        # Get all discovered links
        all_links = []
        for page_data in self.scraped_data:
            all_links.extend(page_data.get('links', []))
        
        # Remove duplicates and already visited
        unique_links = list(set(all_links) - self.visited_urls)
        
        # Prioritize links
        prioritized_links = self._prioritize_links(unique_links)
        
        # Scrape up to max_pages
        pages_to_scrape = prioritized_links[:self.max_pages - len(self.visited_urls)]
        
        # Scrape pages concurrently
        tasks = []
        for i, url in enumerate(pages_to_scrape):
            priority = 2 if any(path in url for path in self.priority_paths) else 3
            tasks.append(self._scrape_page(url, priority))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def _prioritize_links(self, links: List[str]) -> List[str]:
        """Prioritize links based on relevance"""
        prioritized = []
        
        # High priority: specific service pages
        for link in links:
            if any(path in link for path in self.priority_paths):
                prioritized.append(link)
        
        # Medium priority: other internal pages
        for link in links:
            if link not in prioritized and self._is_internal_link(link):
                prioritized.append(link)
        
        return prioritized
    
    def _process_scraped_data(self) -> List[Dict[str, Any]]:
        """Process and clean scraped data"""
        processed_data = []
        
        for page_data in self.scraped_data:
            if not page_data.get('content'):
                continue
            
            # Split content into chunks
            chunks = self._split_into_chunks(page_data['content'])
            
            for i, chunk in enumerate(chunks):
                if len(chunk.strip()) < 50:  # Skip very short chunks
                    continue
                
                processed_chunk = {
                    'id': f"{page_data['url']}_chunk_{i}",
                    'source_url': page_data['url'],
                    'title': page_data['title'],
                    'content': chunk,
                    'chunk_index': i,
                    'relevance_score': page_data['relevance_score'],
                    'scraped_at': page_data['scraped_at'],
                    'source_type': 'web_scraping'
                }
                
                processed_data.append(processed_chunk)
        
        return processed_data
    
    def _split_into_chunks(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks"""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings
                for i in range(end, max(start + chunk_size - 100, start), -1):
                    if text[i] in '.!?':
                        end = i + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap
        
        return chunks
    
    def save_scraped_data(self, file_path: str):
        """Save scraped data to file"""
        try:
            data = {
                'scraped_at': datetime.now().isoformat(),
                'base_url': self.base_url,
                'total_pages': len(self.scraped_data),
                'data': self._process_scraped_data()
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Scraped data saved to {file_path}")
            
        except Exception as e:
            logger.error(f"Error saving scraped data: {e}")

async def scrape_vtb_website(output_file: str = "vtb_scraped_data.json") -> List[Dict[str, Any]]:
    """Main function to scrape VTB website"""
    async with VTBWebScraper() as scraper:
        scraped_data = await scraper.scrape_website()
        scraper.save_scraped_data(output_file)
        return scraped_data

if __name__ == "__main__":
    # Example usage
    async def main():
        data = await scrape_vtb_website()
        print(f"Scraped {len(data)} content chunks from VTB website")
    
    asyncio.run(main())
