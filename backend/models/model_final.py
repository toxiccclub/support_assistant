
"""
1) config.py
2) knowledge_base.py
3) entrity_extractor.py
4) classifier.py
5) response_generator.py
6) persistence.py
7) continious_learning.py
8) main_system.py
"""

import os
import pandas as pd
import numpy as np
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity
import json
import pickle
from pathlib import Path
from datetime import datetime
import warnings
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
import re

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

"""Configuration settings for the intelligent support system."""
class Config:
    # API Configuration
    API_KEY = os.getenv("SCIBOX_API_KEY", "sk-Hheb_7mljCgAWSIIyEYbnw")
    BASE_URL = "https://llm.t1v.scibox.tech/v1"
    
    # Model Configuration
    EMBEDDING_MODEL = "bge-m3"
    LLM_MODEL = "Qwen2.5-72B-Instruct-AWQ"
    
    # Classification Thresholds
    DEFAULT_SIMILARITY_THRESHOLD = 0.7 
    CATEGORY_CLASSIFICATION_THRESHOLD = 0.5 
    
    # Search Parameters
    DEFAULT_TOP_K = 5
    
    # LLM Generation Parameters
    DEFAULT_TEMPERATURE = 0.1
    DEFAULT_MAX_TOKENS = 500
    
    # Continuous Learning
    BATCH_SIZE = 10
    RETRAINING_THRESHOLD = 50
    
    # Feedback Collection
    FEEDBACK_BUFFER_SIZE = 100 
    
    # Paths for model persistence
    MODEL_SAVE_PATH = "models/"
    FEEDBACK_DATA_PATH = "data/feedback/"
    
    # Fuzzy matching settings
    FUZZY_MATCH_THRESHOLD = 0.6 
    USE_FUZZY_FALLBACK = True  

class KnowledgeBase:

    def __init__(self, client):
        self.client = client
        self.knowledge_data = []
        self.embeddings = np.array([])
        self._embedding_cache = {}
        self.category_mapping = {}
        self._text_normalization_cache = {}
        
    def _normalize_text(self, text: str) -> str:
        """Normalize text for better matching - handles case, transliteration, common variations."""
        if text in self._text_normalization_cache:
            return self._text_normalization_cache[text]
            
        # Приводим к нижнему регистру
        normalized = text.lower().strip()
        
        # Заменяем common transliterations and variations
        translit_map = {
            'c': 'с', 'a': 'а', 'e': 'е', 'o': 'о', 'p': 'р', 'x': 'х',
            'y': 'у', 'k': 'к', 'm': 'м', 't': 'т', 'h': 'н', 'b': 'в',
            'n': 'н', 'r': 'р', 'u': 'у', 'd': 'д', 'l': 'л', 'i': 'и',
            'g': 'г', 's': 'с', 'v': 'в', 'z': 'з', 'j': 'дж', 'f': 'ф',
            'q': 'к', 'w': 'в', 'ё': 'е'
        }
        
        for eng, rus in translit_map.items():
            normalized = normalized.replace(eng, rus)
        
        # Удаляем лишние пробелы и пунктуацию
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        self._text_normalization_cache[text] = normalized
        return normalized
        
    def load_data_from_excel(self, file_path: str) -> List[Dict]:
        """Load data from Excel file.

        we exclude `priority` from the combined text used for embeddings
        to avoid biasing semantic search with operational attributes.
        Returns the normalized list of knowledge items.
        """
        try:
            df = pd.read_excel(file_path)
            
            knowledge_items = []
            category_pairs = set()
            
            for _, row in df.iterrows():
                # Нормализуем текстовые поля для лучшего поиска
                main_category = self._normalize_text(str(row['Основная категория']))
                subcategory = self._normalize_text(str(row['Подкатегория']))
                question = self._normalize_text(str(row['Пример вопроса']))
                template_answer = str(row['Шаблонный ответ'])  # Ответ не нормализуем
                
                combined_text = f"{main_category} {subcategory} {question}"
                
                item = {
                    'main_category': main_category,
                    'subcategory': subcategory,
                    'question': question,
                    'original_question': str(row['Пример вопроса']),  # Сохраняем оригинал
                    'priority': str(row['Приоритет']),
                    'target_audience': str(row['Целевая аудитория']),
                    'template_answer': template_answer,
                    'combined_text': combined_text
                }
                knowledge_items.append(item)
                
                category_pairs.add((main_category, subcategory))
            
            self.knowledge_data = knowledge_items
            self._build_category_mapping(category_pairs)
            logger.info(f"Loaded {len(self.knowledge_data)} records from knowledge base")
            logger.info(f"Found {len(category_pairs)} unique category-subcategory pairs")
            return self.knowledge_data
            
        except Exception as e:
            logger.error(f"Error loading data from Excel: {e}")
            raise
    
    def _build_category_mapping(self, category_pairs: set):
        """Build mapping for category validation.

        Example structure:
            {
              'Карты': ['Блокировка', 'Доставка', ...],
              'Интернет-банк': ['Авторизация', 'Переводы', ...]
            }
        """
        self.category_mapping = {}
        for main_cat, sub_cat in category_pairs:
            if main_cat not in self.category_mapping:
                self.category_mapping[main_cat] = []
            self.category_mapping[main_cat].append(sub_cat)
    
    def generate_embeddings(self) -> np.ndarray:
        """Generate embeddings synchronously.

        Embeddings are generated in batches to optimize API throughput.
        If embeddings already exist and match the knowledge length, we reuse
        them to prevent unnecessary API calls.
        """
        texts = [f"{item['main_category']} {item['subcategory']} {item['question']}" 
                for item in self.knowledge_data]
        
        if len(self.embeddings) > 0 and len(self.embeddings) == len(texts):
            logger.info("Using existing embeddings")
            return self.embeddings
        
        all_embeddings = []
        
        for i in range(0, len(texts), Config.BATCH_SIZE):
            batch_texts = texts[i:i+Config.BATCH_SIZE]
            
            try:
                response = self._get_embeddings_batch(batch_texts)
                all_embeddings.extend(response)
                logger.info(f"Processed batch {i//Config.BATCH_SIZE + 1}/{(len(texts)-1)//Config.BATCH_SIZE + 1}")
                
            except Exception as e:
                logger.error(f"Error generating embeddings for batch: {e}")
                raise
        
        self.embeddings = np.array(all_embeddings)
        logger.info(f"Generated embeddings with shape {self.embeddings.shape}")
        return self.embeddings
    
    def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for a batch of texts."""
        try:
            response = self.client.embeddings.create(
                model=Config.EMBEDDING_MODEL,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"API error in embedding generation: {e}")
            raise
    
    def save_knowledge_base(self, file_path: str):
        """Save knowledge base with embeddings.

        The JSON includes data, embeddings, category mapping and metadata
        (timestamp, counts, embedding dimensionality) for reproducibility.
        """
        try:
            knowledge_dict = {
                'knowledge_data': self.knowledge_data,
                'embeddings': self.embeddings.tolist() if len(self.embeddings) > 0 else [],
                'category_mapping': self.category_mapping,
                'metadata': {
                    'created_at': datetime.now().isoformat(),
                    'num_items': len(self.knowledge_data),
                    'embedding_dim': self.embeddings.shape[1] if len(self.embeddings) > 0 else 0
                }
            }
            
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(knowledge_dict, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Knowledge base saved to {file_path}")
            
        except Exception as e:
            logger.error(f"Error saving knowledge base: {e}")
            raise
    
    def load_knowledge_base(self, file_path: str):
        """Load previously saved knowledge base.

        If a category mapping is missing, it is reconstructed from items to
        keep classification features functional across versions.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                knowledge_dict = json.load(f)
            
            self.knowledge_data = knowledge_dict['knowledge_data']
            self.embeddings = np.array(knowledge_dict['embeddings']) if knowledge_dict['embeddings'] else np.array([])
            self.category_mapping = knowledge_dict.get('category_mapping', {})
            
            if not self.category_mapping and self.knowledge_data:
                logger.info("Category mapping is empty, rebuilding from knowledge data...")
                category_pairs = set()
                for item in self.knowledge_data:
                    category_pairs.add((item['main_category'], item['subcategory']))
                self._build_category_mapping(category_pairs)
                logger.info(f"Rebuilt category mapping with {len(self.category_mapping)} main categories")
            
            logger.info(f"Loaded knowledge base from {file_path} with {len(self.knowledge_data)} items")
            
        except Exception as e:
            logger.error(f"Error loading knowledge base: {e}")
            raise

class EntityExtractor:
        
    def __init__(self):
        self.financial_entities = {
            'карта': ['карта', 'карточка', 'банковская карта', 'кредитная карта', 'дебетовая карта', 'card', 'karta'],
            'счет': ['счет', 'банковский счет', 'текущий счет', 'расчетный счет', 'schet', 'account'],
            'вход': ['вход', 'войти', 'авторизация', 'логин', 'пароль', 'login', 'password', 'avtorizaciya'],
            'регистрация': ['регистрация', 'зарегистрироваться', 'онбординг', 'стать клиентом', 'registraciya'],
            'перевод': ['перевод', 'перевести', 'отправка денег', 'денежный перевод', 'perevod', 'transfer'],
            'платеж': ['платеж', 'оплата', 'заплатить', 'оплатить', 'platezh', 'payment'],
            'блокировка': ['блокировка', 'заблокирован', 'разблокировка', 'блокировать', 'blokirovka', 'block'],
            'мобильное': ['мобильное приложение', 'приложение', 'мобильный банк', 'mbank', 'mobile', 'app'],
            'интернет-банк': ['интернет-банк', 'online банк', 'веб-банк', 'internet bank', 'online bank'],
            'поддержка': ['поддержка', 'помощь', 'консультация', 'оператор', 'support', 'help']
        }
        
        # Создаем нормализованные версии ключевых слов
        self._normalized_entities = {}
        for entity_type, keywords in self.financial_entities.items():
            normalized_keywords = []
            for keyword in keywords:
                normalized = self._normalize_text(keyword)
                normalized_keywords.append(normalized)
            self._normalized_entities[entity_type] = normalized_keywords
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for fuzzy matching."""
        # Приводим к нижнему регистру и удаляем пунктуацию
        text = text.lower().strip()
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract key entities from text using keyword matching with fuzzy support."""
        text_normalized = self._normalize_text(text)
        found_entities = {}
        
        for entity_type, keywords in self._normalized_entities.items():
            matches = []
            for keyword in keywords:
                # Простое частичное совпадение
                if keyword in text_normalized:
                    matches.append(keyword)
                # Проверяем совпадение отдельных слов
                elif any(word in text_normalized.split() for word in keyword.split()):
                    matches.append(keyword)
            if matches:
                found_entities[entity_type] = list(set(matches))  # Убираем дубликаты
        
        return found_entities
    
class OptimizedSupportClassifier:

    def __init__(self, knowledge_base, similarity_threshold=Config.DEFAULT_SIMILARITY_THRESHOLD, top_k=Config.DEFAULT_TOP_K):
        self.kb = knowledge_base
        self.client = knowledge_base.client
        self.similarity_threshold = similarity_threshold
        self.top_k = top_k
        self._query_cache = {}
        self._max_cache_size = 1000
        self.entity_extractor = EntityExtractor()
    
    def _normalize_query(self, query: str) -> str:
        """Normalize user query for better matching."""
        # Используем ту же нормализацию, что и в KnowledgeBase
        return self.kb._normalize_text(query)
    
    def get_query_embedding(self, query: str) -> np.ndarray:
        """Get embedding for user query with caching.

        A small LRU-like cache avoids repeated API calls for identical queries.
        """
        normalized_query = self._normalize_query(query)
        query_hash = hash(normalized_query)
        
        if query_hash in self._query_cache:
            return self._query_cache[query_hash]
        
        try:
            response = self.client.embeddings.create(
                model=Config.EMBEDDING_MODEL,
                input=normalized_query
            )
            embedding = np.array(response.data[0].embedding)
            
            # Простое кэширование
            if len(self._query_cache) >= self._max_cache_size:
                # Удаляем первый элемент (простейший LRU)
                first_key = next(iter(self._query_cache))
                del self._query_cache[first_key]
            
            self._query_cache[query_hash] = embedding
            return embedding
            
        except Exception as e:
            logger.error(f"Error getting query embedding: {e}")
            # Возвращаем случайный вектор той же размерности, что и в базе знаний
            if self.kb.embeddings.size > 0:
                embedding_dim = self.kb.embeddings.shape[1]
                return np.random.randn(embedding_dim) * 0.1
            return np.zeros(1024)  # fallback dimension
    
    def find_similar_answers(self, query: str, top_k: Optional[int] = None) -> List[Dict]:
        """Find most relevant answers with optimized similarity search.

        Primary path uses cosine similarity of embeddings; on API failure we
        fall back to heuristic keyword overlap scoring.
        """
        try:
            if top_k is None:
                top_k = self.top_k
            
            if self.kb.embeddings.size == 0 or len(self.kb.knowledge_data) == 0:
                logger.warning("Knowledge base is empty - using keyword fallback")
                return self._find_similar_by_keywords(query, top_k)
            
            try:
                query_embedding = self.get_query_embedding(query)
                
                # Проверяем совместимость размерностей
                if query_embedding.shape[0] != self.kb.embeddings.shape[1]:
                    logger.warning(f"Dimension mismatch: query {query_embedding.shape[0]} vs KB {self.kb.embeddings.shape[1]}")
                    return self._find_similar_by_keywords(query, top_k)
                
                similarities = cosine_similarity([query_embedding], self.kb.embeddings)[0]
                top_indices = np.argsort(similarities)[::-1][:top_k]
                
                results = []
                for idx in top_indices:
                    if similarities[idx] > 0:  # Фильтруем отрицательные similarity
                        results.append({
                            'knowledge_item': self.kb.knowledge_data[idx],
                            'similarity_score': float(similarities[idx]),
                            'index': int(idx)
                        })
                
                logger.info(f"Found {len(results)} similar items using embeddings")
                
                # Если результаты с низкой схожестью, добавляем keyword-based результаты
                if not results or results[0]['similarity_score'] < Config.FUZZY_MATCH_THRESHOLD:
                    logger.info("Low similarity with embeddings, adding keyword-based results")
                    keyword_results = self._find_similar_by_keywords(query, top_k)
                    # Объединяем и убираем дубликаты
                    combined_results = self._merge_results(results, keyword_results)
                    return combined_results[:top_k]
                
                return results
                
            except Exception as api_error:
                logger.warning(f"Embedding failed ({api_error}), falling back to keyword matching")
                return self._find_similar_by_keywords(query, top_k)
            
        except Exception as e:
            logger.error(f"Error in find_similar_answers: {e}")
            return []
    
    def _merge_results(self, embedding_results: List[Dict], keyword_results: List[Dict]) -> List[Dict]:
        """Merge embedding and keyword results, removing duplicates."""
        merged = []
        seen_indices = set()
        
        # Сначала добавляем embedding результаты
        for result in embedding_results:
            idx = result['index']
            if idx not in seen_indices:
                merged.append(result)
                seen_indices.add(idx)
        
        # Затем добавляем keyword результаты
        for result in keyword_results:
            idx = result['index']
            if idx not in seen_indices:
                merged.append(result)
                seen_indices.add(idx)
        
        # Сортируем по убыванию similarity_score
        merged.sort(key=lambda x: x['similarity_score'], reverse=True)
        return merged
    
    def _find_similar_by_keywords(self, query: str, top_k: int) -> List[Dict]:
        """Enhanced keyword matching with fuzzy support.

        Heuristic scoring considers overlaps with question, category and
        template answer fields. This is a safety net, not a replacement for
        embeddings.
        """
        normalized_query = self._normalize_query(query)
        query_words = set(normalized_query.split())
        results = []
        
        for idx, item in enumerate(self.kb.knowledge_data):
            score = 0.0
            
            # Check question similarity
            question_words = set(item['question'].split())
            common_words = query_words & question_words
            if common_words:
                score += len(common_words) * 0.15
            
            # Check category similarity
            category_text = f"{item['main_category']} {item['subcategory']}"
            category_words = set(category_text.split())
            common_category = query_words & category_words
            if common_category:
                score += len(common_category) * 0.3
            
            # Check partial word matches
            for q_word in query_words:
                for kb_word in question_words | category_words:
                    if len(q_word) > 3 and len(kb_word) > 3:
                        # Простая проверка на схожесть слов
                        if q_word in kb_word or kb_word in q_word:
                            score += 0.1
            
            # Bonus for exact phrase matches in original question
            original_question_lower = item['original_question'].lower()
            if any(word in original_question_lower for word in normalized_query.split()):
                score += 0.2
            
            if score > 0:
                results.append({
                    'knowledge_item': item,
                    'similarity_score': min(score, 1.0),  # Нормализуем до 1.0
                    'index': idx
                })
        
        # Sort by score and return top_k
        results.sort(key=lambda x: x['similarity_score'], reverse=True)
        return results[:top_k]
    
    def classify_query(self, query: str) -> Dict[str, Any]:
        """Enhanced classification with entity extraction and fallback.

        Returns a dict including category, confidence, top similar items,
        detected entities, and a few top similarity scores for diagnostics.
        """
        similar_items = self.find_similar_answers(query)
        entities = self.entity_extractor.extract_entities(query)
        
        # Значения по умолчанию для неопределенных запросов
        main_category = "Неопределено"
        subcategory = "Общий вопрос"
        confidence = 0.0
        
        if similar_items:
            best_match = similar_items[0]
            confidence = best_match['similarity_score']
            
            if confidence >= Config.CATEGORY_CLASSIFICATION_THRESHOLD:
                main_category = best_match['knowledge_item']['main_category']
                subcategory = best_match['knowledge_item']['subcategory']
                logger.info(f"High confidence classification: {main_category} -> {subcategory} ({confidence:.3f})")
            else:
                # Низкая уверенность - используем LLM для уточнения
                main_category, subcategory, confidence = self._refine_classification_with_llm(query, similar_items)
                logger.info(f"LLM-refined classification: {main_category} -> {subcategory} ({confidence:.3f})")
        else:
            logger.warning("No similar items found for classification")
        
        return {
            'main_category': main_category,
            'subcategory': subcategory,
            'confidence': confidence,
            'similar_items': similar_items[:3],  # Возвращаем только топ-3
            'entities': entities,
            'top_similarity_scores': [item['similarity_score'] for item in similar_items[:3]] if similar_items else []
        }
    
    def _refine_classification_with_llm(self, query: str, similar_items: List[Dict]) -> Tuple[str, str, float]:
        """Refine classification using LLM for difficult cases.

        The LLM is asked to choose among a short list of plausible categories
        produced by the similarity search, reducing hallucination risk and cost.
        """
        try:
            # Собираем уникальные категории из топ результатов
            candidate_categories = []
            for item in similar_items[:5]:  # Берем только топ-5 для экономии
                kb_item = item['knowledge_item']
                candidate_categories.append(f"{kb_item['main_category']} -> {kb_item['subcategory']}")
            
            unique_categories = list(set(candidate_categories))
            
            if not unique_categories:
                best_match = similar_items[0]['knowledge_item']
                return best_match['main_category'], best_match['subcategory'], similar_items[0]['similarity_score']
            
            system_prompt = """Ты - эксперт по классификации банковских запросов. 
            Определи наиболее подходящую категорию и подкатегорию для запроса клиента.
            Выбери ТОЛЬКО из предложенных вариантов или верни "Неопределено -> Общий вопрос" если нет хорошего соответствия."""

            user_prompt = f"""
            Запрос клиента: "{query}"
            
            Доступные категории (выбери одну):
            {chr(10).join([f"- {cat}" for cat in unique_categories])}
            
            Формат ответа: ОсновнаяКатегория -> Подкатегория
            """

            response = self.client.chat.completions.create(
                model=Config.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=100
            )
            
            result = response.choices[0].message.content.strip()
            if "->" in result:
                main_cat, sub_cat = result.split("->", 1)
                main_cat = main_cat.strip()
                sub_cat = sub_cat.strip()
                
                # Проверяем, что выбранная категория была в кандидатах
                selected = f"{main_cat} -> {sub_cat}"
                if selected in unique_categories:
                    return main_cat, sub_cat, 0.7  # Средняя уверенность для LLM
            
        except Exception as e:
            logger.error(f"Error in LLM classification refinement: {e}")
        
        # Fallback: возвращаем лучший результат из similarity search
        best_match = similar_items[0]['knowledge_item']
        return best_match['main_category'], best_match['subcategory'], similar_items[0]['similarity_score']
    
class TemplateBasedResponseGenerator:

    def __init__(self, client, temperature=0.1, max_tokens=300):
        self.client = client
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    def generate_response(self, user_query: str, similar_items: List[Dict], classification_result: Dict) -> str:
        """Generate response EXCLUSIVELY from templates.

        Returns an empty string when confidence is low or category is undefined; 
        the UI can then show multiple template options for the operator to choose.
        """
        if not similar_items:
            return ""
        
        # Не генерируем ответ для неопределенных категорий
        if classification_result['main_category'] == 'Неопределено':
            return ""
        
        best_match = similar_items[0]
        if best_match['similarity_score'] >= Config.CATEGORY_CLASSIFICATION_THRESHOLD:
            return best_match['knowledge_item']['template_answer']
        
        return ""
    
    def get_multiple_template_options(self, similar_items: List[Dict], max_options: int = 3) -> List[Dict]:
        """Return multiple template options for operator.

        The options include the source question and category to help a human
        quickly judge applicability.
        """
        options = []
        for item in similar_items[:max_options]:
            if item['similarity_score'] >= 0.3:  # Снизим порог для показа больше вариантов
                options.append({
                    'template_answer': item['knowledge_item']['template_answer'],
                    'similarity_score': item['similarity_score'],
                    'category': f"{item['knowledge_item']['main_category']} -> {item['knowledge_item']['subcategory']}",
                    'source_question': item['knowledge_item']['original_question']
                })
        return options
    
class ModelPersistor:
    """Enhanced model persistence with compression and versioning.

    Saves a versioned snapshot containing KB, config, feedback data
    and training data for continuous learning.
    """  
    def __init__(self, model_dir: str = "models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
    
    def save_complete_model(self, support_system, model_name: str = "support_model") -> Path:
        """Save complete model with enhanced metadata.

        Creates a timestamped directory inside `models/` to avoid overwrites.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = self.model_dir / f"{model_name}_{timestamp}"
        model_path.mkdir(exist_ok=True)
        
        try:
            self._save_knowledge_base(support_system.kb, model_path)
            self._save_model_config(support_system, model_path)
            self._save_feedback_data(support_system, model_path)
            self._save_training_data(support_system, model_path)
            self._save_performance_metrics(support_system, model_path)
            
            logger.info(f"Model saved to: {model_path}")
            return model_path
            
        except Exception as e:
            logger.error(f"Error saving model: {e}")
            raise
    
    def _save_knowledge_base(self, knowledge_base, model_path: Path):
        """Save knowledge base with compression."""
        kb_data = {
            'knowledge_data': knowledge_base.knowledge_data,
            'embeddings': knowledge_base.embeddings.tolist() if len(knowledge_base.embeddings) > 0 else [],
            'category_mapping': knowledge_base.category_mapping,
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'num_items': len(knowledge_base.knowledge_data),
                'embedding_dim': int(knowledge_base.embeddings.shape[1]) if len(knowledge_base.embeddings) > 0 else 0,
                'version': '2.1'
            }
        }
        
        with open(model_path / "knowledge_base.json", 'w', encoding='utf-8') as f:
            json.dump(kb_data, f, ensure_ascii=False, indent=2)
    
    def _save_model_config(self, support_system, model_path: Path):
        """Save model configuration with key runtime parameters."""
        config = {
            'model_name': 'OptimizedIntelligentSupportSystem',
            'version': '2.1',
            'embedding_model': Config.EMBEDDING_MODEL,
            'llm_model': Config.LLM_MODEL,
            'parameters': {
                'similarity_threshold': getattr(support_system.classifier, 'similarity_threshold', Config.DEFAULT_SIMILARITY_THRESHOLD),
                'top_k_results': getattr(support_system.classifier, 'top_k', Config.DEFAULT_TOP_K),
                'classification_threshold': Config.CATEGORY_CLASSIFICATION_THRESHOLD,
            },
            'save_timestamp': datetime.now().isoformat()
        }
        
        with open(model_path / "model_config.json", 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    
    def _save_feedback_data(self, support_system, model_path: Path):
        """Save feedback data for continuous learning."""
        if hasattr(support_system, 'feedback_data') and support_system.feedback_data:
            feedback_df = pd.DataFrame(support_system.feedback_data)
            feedback_df.to_csv(model_path / "feedback_data.csv", index=False, encoding='utf-8')
            logger.info(f"Saved {len(feedback_df)} feedback records")
    
    def _save_training_data(self, support_system, model_path: Path):
        """Save training data for model retraining."""
        training_data = []
        if hasattr(support_system, 'feedback_data') and support_system.feedback_data:
            for feedback in support_system.feedback_data:
                if feedback.get('operator_corrected_category'):
                    training_data.append({
                        'query': feedback['user_query'],
                        'main_category': feedback['operator_corrected_category']['main_category'],
                        'subcategory': feedback['operator_corrected_category']['subcategory'],
                        'timestamp': feedback.get('timestamp', datetime.now().isoformat())
                    })
        
        if training_data:
            training_df = pd.DataFrame(training_data)
            training_df.to_csv(model_path / "training_data.csv", index=False, encoding='utf-8')
            logger.info(f"Saved {len(training_df)} training examples")
    
    def _save_performance_metrics(self, support_system, model_path: Path):
        """Save performance metrics for monitoring."""
        metrics = {
            'total_queries_processed': len(support_system.feedback_data) if hasattr(support_system, 'feedback_data') else 0,
            'average_rating': self._calculate_average_rating(support_system),
            'category_distribution': self._get_category_distribution(support_system),
            'training_data_size': self._get_training_data_size(support_system),
            'model_performance': {
                'embedding_dim': int(support_system.kb.embeddings.shape[1]) if len(support_system.kb.embeddings) > 0 else 0,
                'knowledge_base_size': len(support_system.kb.knowledge_data),
                'last_updated': datetime.now().isoformat()
            }
        }
        
        with open(model_path / "performance_metrics.json", 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
    
    def _calculate_average_rating(self, support_system) -> float:
        """Calculate average operator rating across stored feedback."""
        if hasattr(support_system, 'feedback_data') and support_system.feedback_data:
            ratings = [item.get('operator_rating', 0) for item in support_system.feedback_data if item.get('operator_rating')]
            return sum(ratings) / len(ratings) if ratings else 0.0
        return 0.0
    
    def _get_category_distribution(self, support_system) -> Dict[str, int]:
        """Get category distribution from collected feedback."""
        if hasattr(support_system, 'feedback_data') and support_system.feedback_data:
            categories = [item.get('classification', {}).get('main_category', 'Unknown') 
                         for item in support_system.feedback_data]
            return dict(pd.Series(categories).value_counts())
        return {}
    
    def _get_training_data_size(self, support_system) -> int:
        """Get number of training examples for continuous learning."""
        if hasattr(support_system, 'feedback_data') and support_system.feedback_data:
            return sum(1 for item in support_system.feedback_data 
                      if item.get('operator_corrected_category'))
        return 0

class ModelLoader:
    """Enhanced model loader with error handling and validation."""
     
    def __init__(self, model_dir: str = "models"):
        self.model_dir = Path(model_dir)
    
    def load_complete_model(self, model_path: str):
        """Load complete model with validation and wire dependencies."""
        model_path = Path(model_path)
        
        if not model_path.exists():
            raise FileNotFoundError(f"Model path does not exist: {model_path}")
        
        try:
            knowledge_base = self._load_knowledge_base(model_path)
            config = self._load_model_config(model_path)
            
            support_system = OptimizedIntelligentSupportSystem()
            support_system.kb = knowledge_base
            
            # Важно: обновляем ссылку на KB в классификаторе
            support_system.classifier.kb = knowledge_base
            
            self._load_feedback_data(support_system, model_path)
            self._load_training_data(support_system, model_path) 
            
            logger.info(f"Model loaded from: {model_path}")
            return support_system, config
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise
    
    def _load_knowledge_base(self, model_path: Path):
        """Load knowledge base with fallback options."""
        client = OpenAI(api_key=Config.API_KEY, base_url=Config.BASE_URL)
        kb = KnowledgeBase(client)
        
        try:
            json_file = model_path / "knowledge_base.json"
            if json_file.exists():
                with open(json_file, 'r', encoding='utf-8') as f:
                    kb_data = json.load(f)
            else:
                raise FileNotFoundError("No knowledge base file found")
            
            kb.knowledge_data = kb_data['knowledge_data']
            kb.embeddings = np.array(kb_data['embeddings']) if kb_data['embeddings'] else np.array([])
            kb.category_mapping = kb_data.get('category_mapping', {})
            
            if not kb.category_mapping and kb.knowledge_data:
                logger.info("Category mapping is empty, rebuilding from knowledge data...")
                category_pairs = set()
                for item in kb.knowledge_data:
                    category_pairs.add((item['main_category'], item['subcategory']))
                kb._build_category_mapping(category_pairs)
                logger.info(f"Rebuilt category mapping with {len(kb.category_mapping)} main categories")
            
            logger.info(f"Loaded {len(kb.knowledge_data)} records from knowledge base")
            return kb
            
        except Exception as e:
            logger.error(f"Error loading knowledge base: {e}")
            raise
    
    def _load_model_config(self, model_path: Path) -> Dict:
        """Load model configuration from JSON."""
        config_file = model_path / "model_config.json"
        if not config_file.exists():
            raise FileNotFoundError("Model configuration file not found")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _load_feedback_data(self, support_system, model_path: Path):
        """Load feedback data if present to restore history."""
        feedback_file = model_path / "feedback_data.csv"
        if feedback_file.exists():
            feedback_df = pd.read_csv(feedback_file, encoding='utf-8')
            support_system.feedback_data = feedback_df.to_dict('records')
            logger.info(f"Loaded {len(support_system.feedback_data)} feedback records")
    
    def _load_training_data(self, support_system, model_path: Path):
        """Load training data for continuous learning."""
        training_file = model_path / "training_data.csv"
        if training_file.exists():
            training_df = pd.read_csv(training_file, encoding='utf-8')
            if not hasattr(support_system, 'training_data'):
                support_system.training_data = []
            support_system.training_data.extend(training_df.to_dict('records'))
            logger.info(f"Loaded {len(training_df)} training examples")
            
class ContinuousLearning:
    
    def __init__(self, support_system):
        self.system = support_system
        self.retraining_threshold = Config.RETRAINING_THRESHOLD
        self._feedback_analytics = {}
        self._training_buffer = []
    
    def add_feedback_to_training_buffer(self, feedback_data: Dict[str, Any]):
        """Add operator feedback to training buffer for retraining.
        
        Collects corrected classifications from operators to improve
        the category classification model.
        """
        if feedback_data.get('operator_corrected_category'):
            training_example = {
                'query': feedback_data['user_query'],
                'main_category': feedback_data['operator_corrected_category']['main_category'],
                'subcategory': feedback_data['operator_corrected_category']['subcategory'],
                'original_category': feedback_data['classification']['main_category'],
                'original_subcategory': feedback_data['classification']['subcategory'],
                'timestamp': datetime.now().isoformat(),
                'operator_rating': feedback_data.get('operator_rating', 0)
            }
            self._training_buffer.append(training_example)
            logger.info(f"Added training example to buffer. Total: {len(self._training_buffer)}")
    
    def analyze_feedback(self, feedback_data: List[Dict]) -> Dict[str, Any]:
        """Enhanced feedback analysis with detailed metrics.

        Returns aggregate stats plus a list of suggested improvement actions
        when issues are concentrated in specific categories.
        """
        try:
            if not feedback_data:
                return {'total_feedback': 0, 'improvement_suggestions': []}
            
            feedback_df = pd.DataFrame(feedback_data)
            
            analytics = {
                'total_feedback': len(feedback_df),
                'average_rating': float(feedback_df['operator_rating'].mean()) if 'operator_rating' in feedback_df.columns else 0,
                'low_rated_count': len(feedback_df[feedback_df['operator_rating'] <= 3]) if 'operator_rating' in feedback_df.columns else 0,
                'high_rated_count': len(feedback_df[feedback_df['operator_rating'] >= 4]) if 'operator_rating' in feedback_df.columns else 0,
                'misclassification_rate': self._calculate_misclassification_rate(feedback_data),
                'category_issues': {},
                'improvement_suggestions': []
            }
            
            # Анализ низких оценок по категориям
            if 'operator_rating' in feedback_df.columns:
                low_rated = feedback_df[feedback_df['operator_rating'] <= 3]
                if len(low_rated) > 0:
                    category_issues = low_rated.groupby('classification_main_category').size().to_dict()
                    analytics['category_issues'] = category_issues
                    
                    for category, count in category_issues.items():
                        if count > 5:
                            analytics['improvement_suggestions'].append({
                                'category': category,
                                'issue': f"High number of low ratings ({count})",
                                'suggestion': f"Review and improve knowledge base entries for {category}"
                            })
            
            # Анализ исправлений категорий операторами
            corrections = [f for f in feedback_data if f.get('operator_corrected_category')]
            if corrections:
                correction_analysis = {}
                for correction in corrections:
                    original_cat = correction['classification']['main_category']
                    corrected_cat = correction['operator_corrected_category']['main_category']
                    key = f"{original_cat} -> {corrected_cat}"
                    correction_analysis[key] = correction_analysis.get(key, 0) + 1
                
                analytics['category_corrections'] = correction_analysis
                
                for correction, count in correction_analysis.items():
                    if count >= 3:
                        analytics['improvement_suggestions'].append({
                            'category': correction,
                            'issue': f"Frequent misclassification ({count} times)",
                            'suggestion': f"Improve distinction between {correction}"
                        })
            
            self._feedback_analytics = analytics
            return analytics
            
        except Exception as e:
            logger.error(f"Error analyzing feedback: {e}")
            return {}
    
    def _calculate_misclassification_rate(self, feedback_data: List[Dict]) -> float:
        """Calculate how often operators correct classifications."""
        corrections = [f for f in feedback_data if f.get('operator_corrected_category')]
        return len(corrections) / len(feedback_data) if feedback_data else 0.0
    
    def should_retrain(self) -> bool:
        """Determine if model should be retrained based on feedback density."""
        if not hasattr(self.system, 'feedback_data') or not self.system.feedback_data:
            return False
        
        total_feedback = len(self.system.feedback_data)
        corrections = sum(1 for item in self.system.feedback_data 
                         if item.get('operator_corrected_category'))
        
        # Условия для переобучения:
        # 1. Достаточно фидбека ИЛИ много исправлений
        # 2. Значительный процент исправлений
        has_enough_feedback = total_feedback >= self.retraining_threshold
        has_significant_corrections = corrections >= (self.retraining_threshold * 0.3)
        high_correction_rate = (corrections / total_feedback) > 0.2 if total_feedback > 0 else False
        
        should_retrain = (has_enough_feedback or has_significant_corrections) and high_correction_rate
        
        if should_retrain:
            logger.info(f"Retraining triggered: {total_feedback} total feedback, {corrections} corrections")
        
        return should_retrain
    
    def get_training_data(self) -> List[Dict]:
        """Get collected training data for model retraining."""
        return self._training_buffer.copy()
    
    def clear_training_buffer(self):
        """Clear training buffer after successful retraining."""
        cleared_count = len(self._training_buffer)
        self._training_buffer.clear()
        logger.info(f"Cleared training buffer with {cleared_count} examples")
    
    def update_knowledge_base(self, new_data_file: str, merge_strategy: str = "append"):
        """Update knowledge base with new data.

        When merging, new items are appended and embeddings are regenerated
        to keep search space current.
        """
        try:
            new_df = pd.read_excel(new_data_file)
            
            if merge_strategy == "replace":
                self.system.kb.load_data_from_excel(new_data_file)
            else:
                new_knowledge_items = []
                for _, row in new_df.iterrows():
                    combined_text = f"{row['Основная категория']} {row['Подкатегория']} {row['Пример вопроса']} {row['Шаблонный ответ']}"
                    
                    item = {
                        'main_category': str(row['Основная категория']),
                        'subcategory': str(row['Подкатегория']),
                        'question': str(row['Пример вопроса']),
                        'priority': str(row['Приоритет']),
                        'target_audience': str(row['Целевая аудитория']),
                        'template_answer': str(row['Шаблонный ответ']),
                        'combined_text': combined_text
                    }
                    new_knowledge_items.append(item)
                
                self.system.kb.knowledge_data.extend(new_knowledge_items)
            
            # Обновляем эмбеддинги для новых данных
            self.system.kb.generate_embeddings()
            logger.info(f"Knowledge base updated. Added {len(new_df)} new records.")
            
        except Exception as e:
            logger.error(f"Error updating knowledge base: {e}")
            raise
    
    def generate_retraining_report(self) -> Dict[str, Any]:
        """Generate comprehensive report for retraining decision."""
        training_data = self.get_training_data()
        
        report = {
            'training_examples_count': len(training_data),
            'feedback_analytics': self._feedback_analytics,
            'should_retrain': self.should_retrain(),
            'retraining_threshold': self.retraining_threshold,
            'recommendation': 'RETRAIN' if self.should_retrain() else 'CONTINUE_MONITORING',
            'timestamp': datetime.now().isoformat()
        }
        
        if training_data:
            categories = [item['main_category'] for item in training_data]
            report['category_distribution'] = dict(pd.Series(categories).value_counts())
        
        return report
    
    def prepare_retraining_data(self) -> str:
        """Prepare training data and return path to temp file."""
        training_data = self.get_training_data()
        
        retraining_data = []
        for training_example in training_data:
            retraining_data.append({
                'Основная категория': training_example['main_category'],
                'Подкатегория': training_example['subcategory'],
                'Пример вопроса': training_example['query'],
                'Шаблонный ответ': 'Ответ будет дополнен оператором',
                'Приоритет': 'Средний',
                'Целевая аудитория': 'Все клиенты'
            })
        
        retraining_df = pd.DataFrame(retraining_data)
        temp_file = "temp_retraining_data.xlsx"
        retraining_df.to_excel(temp_file, index=False)
        
        return temp_file
    
    def get_retraining_plan(self) -> Dict[str, Any]:
        """Generate detailed retraining plan with analytics."""
        training_data = self.get_training_data()
        
        return {
            'training_examples_count': len(training_data),
            'affected_categories': self._get_affected_categories(training_data),
            'expected_improvements': self._calculate_expected_improvements(),
            'risk_assessment': self._assess_retraining_risk(),
            'recommendation': 'PROCEED' if self.should_retrain() else 'DELAY'
        }
        

class OptimizedIntelligentSupportSystem:
    """Main optimized support system class.

    Orchestrates the components: knowledge base, classifier, response
    generator, persistence, loader, and continuous learning.
    """    
    def __init__(self, knowledge_base_path: Optional[str] = None):
        self.client = OpenAI(api_key=Config.API_KEY, base_url=Config.BASE_URL)
        self.kb = KnowledgeBase(self.client)
        self.persistor = ModelPersistor()
        self.loader = ModelLoader()
        
        if knowledge_base_path:
            self.kb.load_knowledge_base(knowledge_base_path)
        else:
            self.kb.knowledge_data = []
            self.kb.embeddings = np.array([])
        
        self.classifier = OptimizedSupportClassifier(self.kb)
        self.generator = TemplateBasedResponseGenerator(self.client)
        self.continuous_learning = ContinuousLearning(self)
        self.feedback_data = []
    
    def train_from_excel(self, excel_file_path: str, save_model: bool = True):
        """Train system from Excel file."""
        logger.info("Starting system training...")
        
        try:
            self.kb.load_data_from_excel(excel_file_path)
            self.kb.generate_embeddings()
            
            if save_model:
                model_path = self.persistor.save_complete_model(self, "trained_support_model")
                logger.info(f"Trained model saved to: {model_path}")
            
            logger.info("Training completed successfully!")
            return self
            
        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise
    
    def process_query(self, user_query: str) -> Dict[str, Any]:
        """Process user query with template-based responses.

        Returns a structured result including classification, selected
        template (if confident), alternative options, and diagnostics.
        """
        logger.info(f"Processing query: {user_query[:100]}...")
        
        try:
            classification = self.classifier.classify_query(user_query)
            
            response = self.generator.generate_response(
                user_query,
                classification['similar_items'],
                classification
            )
            
            template_options = self.generator.get_multiple_template_options(classification['similar_items'])
            
            result = {
                'user_query': user_query,
                'classification': classification,
                'response': response,
                'template_options': template_options,
                'has_suggestion': bool(response),
                'timestamp': datetime.now().isoformat(),
                'processing_metadata': {
                    'num_similar_items': len(classification['similar_items']),
                    'confidence': classification['confidence'],
                    'entities_detected': classification['entities'],
                    'model_version': '2.2_enhanced_fuzzy_matching'
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {
                'user_query': user_query,
                'classification': {
                    'main_category': 'Ошибка',
                    'subcategory': 'Системная ошибка',
                    'confidence': 0.0,
                    'similar_items': [],
                    'entities': {}
                },
                'response': "",
                'template_options': [],
                'has_suggestion': False,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def collect_feedback(self, query_result: Dict, operator_rating: int, 
                        operator_corrected_category: Optional[Dict] = None,
                        user_feedback: str = ""):
        """Collect feedback for continuous learning and analytics.
        
        This is CRITICAL for the continuous learning mechanism.
        """
        feedback_entry = {
            **query_result,
            'user_feedback': user_feedback,
            'operator_rating': operator_rating,
            'operator_corrected_category': operator_corrected_category,
            'feedback_timestamp': datetime.now().isoformat()
        }
        
        self.feedback_data.append(feedback_entry)
        
        # Добавляем данные для continuous learning
        self.continuous_learning.add_feedback_to_training_buffer(feedback_entry)
        
        # Проверяем, не пора ли переобучать модель
        if self.continuous_learning.should_retrain():
            logger.info("Retraining threshold reached! Ready for model retraining.")
            self.retrain_model()
        
        logger.info(f"Feedback collected. Total feedback: {len(self.feedback_data)}")
        return feedback_entry
    
    def get_continuous_learning_report(self) -> Dict[str, Any]:
        """Get comprehensive report on system performance and learning needs."""
        analytics = self.continuous_learning.analyze_feedback(self.feedback_data)
        retraining_report = self.continuous_learning.generate_retraining_report()
        
        return {
            'feedback_analytics': analytics,
            'retraining_report': retraining_report,
            'system_metrics': {
                'total_queries_processed': len(self.feedback_data),
                'knowledge_base_size': len(self.kb.knowledge_data),
                'training_examples_available': len(self.continuous_learning.get_training_data()),
                'fuzzy_matching_enabled': Config.USE_FUZZY_FALLBACK
            }
        }
        
    def retrain_model(self) -> bool:
        """Orchestrate model retraining using continuous learning component."""
        
        # 1. Проверяем, нужно ли переобучаться
        if not self.continuous_learning.should_retrain():
            logger.info("Retraining not needed at this time")
            return False
        
        # 2. Получаем план переобучения
        retraining_plan = self.continuous_learning.get_retraining_plan()
        logger.info(f"Retraining plan: {retraining_plan}")
        
        # 3. Continuous Learning готовит данные
        temp_training_file = self.continuous_learning.prepare_retraining_data()
        
        try:
            # 4. Main System выполняет переобучение
            self._execute_retraining(temp_training_file)
            
            # 5. Continuous Learning анализирует результаты
            success = self.continuous_learning.analyze_retraining_results()
            
            if success:
                self.continuous_learning.clear_training_buffer()
                logger.info("Model retraining completed successfully")
            else:
                logger.warning("Retraining completed with warnings")
            
            return success
            
        except Exception as e:
            logger.error(f"Retraining failed: {e}")
            return False
        finally:
            # Очистка временных файлов
            Path(temp_training_file).unlink(missing_ok=True)

    def _execute_retraining(self, training_file: str):
        """Execute the actual retraining - separated for clarity."""
        # Обновляем базу знаний
        self.kb.load_data_from_excel(training_file)
        
        # Перестраиваем эмбеддинги
        self.kb.generate_embeddings()
        
        # Обновляем категории
        category_pairs = set()
        for item in self.kb.knowledge_data:
            category_pairs.add((item['main_category'], item['subcategory']))
        self.kb._build_category_mapping(category_pairs)
        
        # Обновляем классификатор
        self.classifier.kb = self.kb
        self.classifier._query_cache.clear()
        
        # Очищаем кэш нормализации
        self.kb._text_normalization_cache.clear()
    
    def save_current_state(self, model_name: str = "current_support_model") -> Path:
        """Save current system state as a versioned snapshot."""
        return self.persistor.save_complete_model(self, model_name)
    
    def load_model(self, model_path: str):
        """Load previously saved model using the loader."""
        loaded_system, config = self.loader.load_complete_model(model_path)
        
        # Обновляем текущий экземпляр
        self.kb = loaded_system.kb
        self.classifier.kb = loaded_system.kb
        self.feedback_data = getattr(loaded_system, 'feedback_data', [])
        
        logger.info(f"Model loaded successfully from {model_path}")
        return self

    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information."""
        return {
            'system_version': '2.2_enhanced_fuzzy_matching',
            'knowledge_base': {
                'total_items': len(self.kb.knowledge_data),
                'categories_count': len(self.kb.category_mapping),
                'embedding_dimensions': self.kb.embeddings.shape[1] if self.kb.embeddings.size > 0 else 0,
                'normalization_cache_size': len(self.kb._text_normalization_cache)
            },
            'classifier': {
                'similarity_threshold': self.classifier.similarity_threshold,
                'cache_size': len(self.classifier._query_cache),
                'fuzzy_matching_enabled': Config.USE_FUZZY_FALLBACK
            },
            'continuous_learning': {
                'feedback_count': len(self.feedback_data),
                'training_examples': len(self.continuous_learning.get_training_data()),
                'retraining_threshold': Config.RETRAINING_THRESHOLD
            },
            'config': {
                'classification_threshold': Config.CATEGORY_CLASSIFICATION_THRESHOLD,
                'fuzzy_match_threshold': Config.FUZZY_MATCH_THRESHOLD,
                'embedding_model': Config.EMBEDDING_MODEL,
                'llm_model': Config.LLM_MODEL
            }
        }

# Backward compatibility aliases
SupportClassifier = OptimizedSupportClassifier
ResponseGenerator = TemplateBasedResponseGenerator
IntelligentSupportSystem = OptimizedIntelligentSupportSystem

def demo_enhanced_system():
    """Demonstration entrypoint for manual testing.

    Trains the system on `training_data.xlsx` (if present) and processes a
    few example queries, printing diagnostics to stdout.
    """
    system = OptimizedIntelligentSupportSystem()
    
    try:
        # Train the system (replace with your Excel file path)
        system.train_from_excel("training_data.xlsx", save_model=True)
        
        test_queries = [
            "Депозит условия мои где открыть можно? хочу деньги положить под проценты",
            "ну вот карту кстати где можно сделать? для рассрочки типа...",
            "здравствуйте! я хочу на все про все"
        ]
        
        print("=== Enhanced Intelligent Support System Demo ===\n")
        print("System features:")
        print("   - Fuzzy matching for typos and variations")
        print("   - Transliteration support (english -> russian)")
        print("   - Case insensitive processing")
        print("   - Combined embedding + keyword search")
        print("   - Undefined category handling")
        print()
        
        for query in test_queries:
            result = system.process_query(query)
            print(f"Query: {query}")
            print(f"Category: {result['classification']['main_category']} -> {result['classification']['subcategory']}")
            print(f"Confidence: {result['classification']['confidence']:.2f}")
            print(f"Entities: {result['classification']['entities']}")
            print(f"Suggestion: {'AVAILABLE' if result['has_suggestion'] else 'NOT AVAILABLE'}")
            if result['response']:
                print(f"Response: {result['response'][:150]}...")
            print(f"Similar items found: {result['processing_metadata']['num_similar_items']}")
            
            # Показываем топ похожие варианты
            if result['template_options']:
                print(f"Template options: {len(result['template_options'])}")
                for i, option in enumerate(result['template_options'][:2], 1):
                    print(f"     {i}. [{option['similarity_score']:.2f}] {option['category']}")
            
            print("-" * 80)
        
        # Демонстрация continuous learning
        print("\n=== Continuous Learning Demo ===")
        report = system.get_continuous_learning_report()
        print(f"Total feedback: {report['system_metrics']['total_queries_processed']}")
        print(f"Training examples: {report['system_metrics']['training_examples_available']}")
        print(f"Should retrain: {report['retraining_report']['should_retrain']}")
        
        # Информация о системе
        print("\n=== System Information ===")
        system_info = system.get_system_info()
        print(f"System version: {system_info['system_version']}")
        print(f"KB items: {system_info['knowledge_base']['total_items']}")
        print(f"Categories: {system_info['knowledge_base']['categories_count']}")
        print(f"Fuzzy matching: {system_info['classifier']['fuzzy_matching_enabled']}")
        
    except FileNotFoundError:
        print("training_data.xlsx not found. Please provide your training data file.")
    except Exception as e:
        print(f"Demo failed: {e}")

if __name__ == "__main__":
    demo_enhanced_system()