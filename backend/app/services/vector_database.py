"""
Vector Database for storing and searching embeddings
Supports hybrid search (vector similarity + keyword matching)
"""

import numpy as np
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
import pickle
import asyncio
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity
import re
from collections import defaultdict

logger = logging.getLogger(__name__)

class VectorDatabase:
    """Vector database for storing and searching embeddings"""
    
    def __init__(self, embedding_model: str = "bge-m3", dimension: int = 1024):
        self.embedding_model = embedding_model
        self.dimension = dimension
        self.documents: List[Dict[str, Any]] = []
        self.embeddings: np.ndarray = np.array([])
        self.keyword_index: Dict[str, List[int]] = defaultdict(list)
        self.client: Optional[OpenAI] = None
        self._embedding_cache: Dict[str, np.ndarray] = {}
    
    def initialize_client(self, api_key: str, base_url: str):
        """Initialize OpenAI client"""
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        logger.info("Vector database client initialized")
    
    async def add_documents(self, documents: List[Dict[str, Any]]) -> bool:
        """Add documents to vector database"""
        try:
            logger.info(f"Adding {len(documents)} documents to vector database")
            
            # Generate embeddings for new documents
            new_embeddings = await self._generate_embeddings_batch([doc['content'] for doc in documents])
            
            # Add to existing data
            self.documents.extend(documents)
            
            if len(self.embeddings) == 0:
                self.embeddings = new_embeddings
            else:
                self.embeddings = np.vstack([self.embeddings, new_embeddings])
            
            # Update keyword index
            self._update_keyword_index(documents)
            
            logger.info(f"Successfully added {len(documents)} documents. Total: {len(self.documents)}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding documents: {e}")
            return False
    
    async def _generate_embeddings_batch(self, texts: List[str], batch_size: int = 10) -> np.ndarray:
        """Generate embeddings for a batch of texts"""
        if not self.client:
            raise RuntimeError("Client not initialized")
        
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            
            try:
                response = self.client.embeddings.create(
                    model=self.embedding_model,
                    input=batch_texts
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
                logger.info(f"Generated embeddings for batch {i//batch_size + 1}")
                
            except Exception as e:
                logger.error(f"Error generating embeddings for batch: {e}")
                # Create zero embeddings as fallback
                batch_embeddings = [np.zeros(self.dimension) for _ in batch_texts]
                all_embeddings.extend(batch_embeddings)
        
        return np.array(all_embeddings)
    
    def _update_keyword_index(self, documents: List[Dict[str, Any]]):
        """Update keyword index for new documents"""
        start_index = len(self.documents) - len(documents)
        
        for i, doc in enumerate(documents):
            doc_index = start_index + i
            content = doc['content'].lower()
            
            # Extract keywords
            keywords = self._extract_keywords(content)
            
            for keyword in keywords:
                self.keyword_index[keyword].append(doc_index)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        # Remove punctuation and split into words
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Filter out common stop words
        stop_words = {
            'и', 'в', 'на', 'с', 'по', 'для', 'от', 'до', 'за', 'о', 'об', 'из', 'к', 'у', 'со',
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'
        }
        
        keywords = [word for word in words if len(word) > 2 and word not in stop_words]
        return keywords
    
    async def search(self, query: str, top_k: int = 5, use_hybrid: bool = True) -> List[Dict[str, Any]]:
        """Search for similar documents using hybrid approach"""
        try:
            if use_hybrid:
                return await self._hybrid_search(query, top_k)
            else:
                return await self._vector_search(query, top_k)
                
        except Exception as e:
            logger.error(f"Error in search: {e}")
            return []
    
    async def _vector_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Vector similarity search"""
        if not self.client or len(self.embeddings) == 0:
            return []
        
        try:
            # Get query embedding
            query_embedding = await self._get_query_embedding(query)
            
            # Calculate similarities
            similarities = cosine_similarity([query_embedding], self.embeddings)[0]
            
            # Get top results
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                results.append({
                    'document': self.documents[idx],
                    'similarity_score': float(similarities[idx]),
                    'index': int(idx),
                    'search_type': 'vector'
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return []
    
    async def _hybrid_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Hybrid search combining vector similarity and keyword matching"""
        try:
            # Get vector search results
            vector_results = await self._vector_search(query, top_k * 2)
            
            # Get keyword search results
            keyword_results = self._keyword_search(query, top_k * 2)
            
            # Combine and rank results
            combined_results = self._combine_search_results(vector_results, keyword_results, top_k)
            
            return combined_results
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            return []
    
    def _keyword_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Keyword-based search"""
        query_keywords = self._extract_keywords(query.lower())
        
        if not query_keywords:
            return []
        
        # Score documents based on keyword matches
        doc_scores = defaultdict(float)
        
        for keyword in query_keywords:
            if keyword in self.keyword_index:
                for doc_index in self.keyword_index[keyword]:
                    doc_scores[doc_index] += 1.0
        
        # Sort by score
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for doc_index, score in sorted_docs[:top_k]:
            if score > 0:
                results.append({
                    'document': self.documents[doc_index],
                    'similarity_score': score / len(query_keywords),  # Normalize
                    'index': doc_index,
                    'search_type': 'keyword'
                })
        
        return results
    
    def _combine_search_results(self, vector_results: List[Dict], keyword_results: List[Dict], top_k: int) -> List[Dict]:
        """Combine and rank search results"""
        # Create a combined score for each document
        combined_scores = {}
        
        # Add vector results
        for result in vector_results:
            doc_id = result['index']
            combined_scores[doc_id] = {
                'document': result['document'],
                'vector_score': result['similarity_score'],
                'keyword_score': 0.0,
                'combined_score': result['similarity_score'],
                'search_types': ['vector']
            }
        
        # Add keyword results
        for result in keyword_results:
            doc_id = result['index']
            if doc_id in combined_scores:
                combined_scores[doc_id]['keyword_score'] = result['similarity_score']
                combined_scores[doc_id]['search_types'].append('keyword')
                # Update combined score (weighted average)
                combined_scores[doc_id]['combined_score'] = (
                    0.7 * combined_scores[doc_id]['vector_score'] + 
                    0.3 * combined_scores[doc_id]['keyword_score']
                )
            else:
                combined_scores[doc_id] = {
                    'document': result['document'],
                    'vector_score': 0.0,
                    'keyword_score': result['similarity_score'],
                    'combined_score': result['similarity_score'],
                    'search_types': ['keyword']
                }
        
        # Sort by combined score
        sorted_results = sorted(combined_scores.values(), key=lambda x: x['combined_score'], reverse=True)
        
        # Format results
        results = []
        for result in sorted_results[:top_k]:
            results.append({
                'document': result['document'],
                'similarity_score': result['combined_score'],
                'index': result['document'].get('id', ''),
                'search_type': 'hybrid',
                'vector_score': result['vector_score'],
                'keyword_score': result['keyword_score'],
                'search_types': result['search_types']
            })
        
        return results
    
    async def _get_query_embedding(self, query: str) -> np.ndarray:
        """Get embedding for query"""
        if not self.client:
            raise RuntimeError("Client not initialized")
        
        # Check cache first
        query_hash = hash(query)
        if query_hash in self._embedding_cache:
            return self._embedding_cache[query_hash]
        
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=query
            )
            
            embedding = np.array(response.data[0].embedding)
            self._embedding_cache[query_hash] = embedding
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error getting query embedding: {e}")
            # Return random embedding as fallback
            return np.random.randn(self.dimension) * 0.1
    
    def save_database(self, file_path: str):
        """Save vector database to file"""
        try:
            data = {
                'documents': self.documents,
                'embeddings': self.embeddings.tolist() if len(self.embeddings) > 0 else [],
                'keyword_index': dict(self.keyword_index),
                'metadata': {
                    'embedding_model': self.embedding_model,
                    'dimension': self.dimension,
                    'total_documents': len(self.documents),
                    'saved_at': datetime.now().isoformat()
                }
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Vector database saved to {file_path}")
            
        except Exception as e:
            logger.error(f"Error saving vector database: {e}")
    
    def load_database(self, file_path: str):
        """Load vector database from file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.documents = data['documents']
            self.embeddings = np.array(data['embeddings']) if data['embeddings'] else np.array([])
            self.keyword_index = defaultdict(list, data.get('keyword_index', {}))
            
            logger.info(f"Vector database loaded from {file_path}")
            logger.info(f"Loaded {len(self.documents)} documents")
            
        except Exception as e:
            logger.error(f"Error loading vector database: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        return {
            'total_documents': len(self.documents),
            'embedding_dimension': self.dimension,
            'embedding_model': self.embedding_model,
            'total_keywords': len(self.keyword_index),
            'avg_embeddings_per_keyword': sum(len(indices) for indices in self.keyword_index.values()) / len(self.keyword_index) if self.keyword_index else 0
        }

class VectorKnowledgeBase:
    """Main knowledge base class that combines all data sources"""
    
    def __init__(self, api_key: str, base_url: str):
        self.vector_db = VectorDatabase()
        self.vector_db.initialize_client(api_key, base_url)
        self.is_initialized = False
    
    async def build_knowledge_base(self, excel_file: str, web_scraped_file: str = None) -> bool:
        """Build knowledge base from all sources"""
        try:
            logger.info("Building vector knowledge base...")
            
            all_documents = []
            
            # Process Excel data
            if Path(excel_file).exists():
                from .excel_processor import process_training_data
                excel_data = process_training_data(excel_file)
                all_documents.extend(excel_data)
                logger.info(f"Added {len(excel_data)} chunks from Excel data")
            
            # Process web scraped data
            if web_scraped_file and Path(web_scraped_file).exists():
                with open(web_scraped_file, 'r', encoding='utf-8') as f:
                    web_data = json.load(f)
                all_documents.extend(web_data.get('data', []))
                logger.info(f"Added {len(web_data.get('data', []))} chunks from web scraping")
            
            # Add to vector database
            if all_documents:
                success = await self.vector_db.add_documents(all_documents)
                if success:
                    self.is_initialized = True
                    logger.info(f"Knowledge base built successfully with {len(all_documents)} documents")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error building knowledge base: {e}")
            return False
    
    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search knowledge base"""
        if not self.is_initialized:
            logger.warning("Knowledge base not initialized")
            return []
        
        return await self.vector_db.search(query, top_k)
    
    def save_knowledge_base(self, file_path: str):
        """Save knowledge base"""
        self.vector_db.save_database(file_path)
    
    def load_knowledge_base(self, file_path: str):
        """Load knowledge base"""
        self.vector_db.load_database(file_path)
        self.is_initialized = True
