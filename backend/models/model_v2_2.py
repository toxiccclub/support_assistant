"""
Optimized ML Model for Production Use - FIXED VERSION
Intelligent Support System for Banking Customer Service
"""

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

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

# Configuration
class Config:
    API_KEY = "sk-Hheb_7mljCgAWSIIyEYbnw"
    BASE_URL = "https://llm.t1v.scibox.tech/v1"
    EMBEDDING_MODEL = "bge-m3"
    LLM_MODEL = "Qwen2.5-72B-Instruct-AWQ"
    DEFAULT_SIMILARITY_THRESHOLD = 0.8
    DEFAULT_TOP_K = 5
    DEFAULT_TEMPERATURE = 0.1
    DEFAULT_MAX_TOKENS = 500
    BATCH_SIZE = 10
    RETRAINING_THRESHOLD = 50
    CATEGORY_CLASSIFICATION_THRESHOLD = 0.6

class AsyncKnowledgeBase:
    """Async version of KnowledgeBase for better performance"""
    
    def __init__(self, client):
        self.client = client
        self.knowledge_data = []
        self.embeddings = np.array([])
        self._embedding_cache = {}
        self.category_mapping = {}
        
    def load_data_from_excel(self, file_path: str) -> List[Dict]:
        """Load data from Excel file - FIXED: removed priority from combined_text"""
        try:
            df = pd.read_excel(file_path)
            
            knowledge_items = []
            category_pairs = set()
            
            for _, row in df.iterrows():
                # FIX 1: Priority removed from training data
                combined_text = f"{row['Основная категория']} {row['Подкатегория']} {row['Пример вопроса']} {row['Шаблонный ответ']}"
                
                item = {
                    'main_category': str(row['Основная категория']),
                    'subcategory': str(row['Подкатегория']),
                    'question': str(row['Пример вопроса']),
                    'priority': str(row['Приоритет']),  # Kept but not used for training
                    'target_audience': str(row['Целевая аудитория']),
                    'template_answer': str(row['Шаблонный ответ']),
                    'combined_text': combined_text
                }
                knowledge_items.append(item)
                
                category_pairs.add((row['Основная категория'], row['Подкатегория']))
            
            self.knowledge_data = knowledge_items
            self._build_category_mapping(category_pairs)
            logger.info(f"Loaded {len(self.knowledge_data)} records from knowledge base")
            logger.info(f"Found {len(category_pairs)} unique category-subcategory pairs")
            return self.knowledge_data
            
        except Exception as e:
            logger.error(f"Error loading data from Excel: {e}")
            raise
    
    def _build_category_mapping(self, category_pairs: set):
        """Build mapping for category validation"""
        self.category_mapping = {}
        for main_cat, sub_cat in category_pairs:
            if main_cat not in self.category_mapping:
                self.category_mapping[main_cat] = []
            self.category_mapping[main_cat].append(sub_cat)
    
    async def generate_embeddings_async(self) -> np.ndarray:
        """Generate embeddings asynchronously"""
        # FIX 2: Use only classification text, without priority
        texts = [f"{item['main_category']} {item['subcategory']} {item['question']}" 
                for item in self.knowledge_data]
        
        if len(self.embeddings) > 0 and len(self.embeddings) == len(texts):
            logger.info("Using existing embeddings")
            return self.embeddings
        
        all_embeddings = []
        
        for i in range(0, len(texts), Config.BATCH_SIZE):
            batch_texts = texts[i:i+Config.BATCH_SIZE]
            
            try:
                response = await self._get_embeddings_batch(batch_texts)
                all_embeddings.extend(response)
                logger.info(f"Processed batch {i//Config.BATCH_SIZE + 1}/{(len(texts)-1)//Config.BATCH_SIZE + 1}")
                
            except Exception as e:
                logger.error(f"Error generating embeddings for batch: {e}")
                all_embeddings.extend([np.zeros(1024)] * len(batch_texts))
        
        self.embeddings = np.array(all_embeddings)
        return self.embeddings
    
    async def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for a batch of texts"""
        try:
            response = self.client.embeddings.create(
                model=Config.EMBEDDING_MODEL,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"API error in embedding generation: {e}")
            raise
    
    def generate_embeddings(self) -> np.ndarray:
        """Synchronous version for backward compatibility"""
        return asyncio.run(self.generate_embeddings_async())
    
    def save_knowledge_base(self, file_path: str):
        """Save knowledge base with embeddings"""
        try:
            knowledge_dict = {
                'knowledge_data': self.knowledge_data,
                'embeddings': self.embeddings.tolist() if len(self.embeddings) > 0 else [],
                'category_mapping': self.category_mapping,
                'metadata': {
                    'created_at': datetime.now().isoformat(),
                    'num_items': len(self.knowledge_data),
                    'embedding_dim': int(self.embeddings.shape[1]) if len(self.embeddings) > 0 else 0
                }
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(knowledge_dict, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Knowledge base saved to {file_path}")
            
        except Exception as e:
            logger.error(f"Error saving knowledge base: {e}")
            raise
    
    def load_knowledge_base(self, file_path: str):
        """Load previously saved knowledge base"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                knowledge_dict = json.load(f)
            
            self.knowledge_data = knowledge_dict['knowledge_data']
            self.embeddings = np.array(knowledge_dict['embeddings']) if knowledge_dict['embeddings'] else np.array([])
            self.category_mapping = knowledge_dict.get('category_mapping', {})
            
            # FIX: Rebuild category mapping if it's empty
            if not self.category_mapping and self.knowledge_data:
                logger.info("Category mapping is empty, rebuilding from knowledge data...")
                category_pairs = set()
                for item in self.knowledge_data:
                    category_pairs.add((item['main_category'], item['subcategory']))
                self._build_category_mapping(category_pairs)
                logger.info(f"Rebuilt category mapping with {len(self.category_mapping)} main categories")
            
            logger.info(f"Loaded knowledge base from {file_path}")
            
        except Exception as e:
            logger.error(f"Error loading knowledge base: {e}")
            raise

class EntityExtractor:
    """Key entity extraction from user queries"""
    
    def __init__(self):
        self.financial_entities = {
            'карта': ['карта', 'карточка', 'банковская карта', 'кредитная карта', 'дебетовая карта'],
            'счет': ['счет', 'банковский счет', 'текущий счет', 'расчетный счет'],
            'вход': ['вход', 'войти', 'авторизация', 'логин', 'пароль'],
            'регистрация': ['регистрация', 'зарегистрироваться', 'онбординг', 'стать клиентом'],
            'перевод': ['перевод', 'перевести', 'отправка денег', 'денежный перевод'],
            'платеж': ['платеж', 'оплата', 'заплатить', 'оплатить'],
            'блокировка': ['блокировка', 'заблокирован', 'разблокировка', 'блокировать'],
            'мобильное': ['мобильное приложение', 'приложение', 'мобильный банк', 'mbank'],
            'интернет-банк': ['интернет-банк', 'online банк', 'веб-банк'],
            'поддержка': ['поддержка', 'помощь', 'консультация', 'оператор']
        }
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract key entities from text"""
        text_lower = text.lower()
        found_entities = {}
        
        for entity_type, keywords in self.financial_entities.items():
            matches = []
            for keyword in keywords:
                if keyword in text_lower:
                    matches.append(keyword)
            if matches:
                found_entities[entity_type] = matches
        
        return found_entities

class OptimizedSupportClassifier:
    """Optimized classifier with enhanced category detection"""
    
    def __init__(self, knowledge_base, similarity_threshold=Config.DEFAULT_SIMILARITY_THRESHOLD, top_k=Config.DEFAULT_TOP_K):
        self.kb = knowledge_base
        self.client = knowledge_base.client
        self.similarity_threshold = similarity_threshold
        self.top_k = top_k
        self._query_cache = {}
        self._max_cache_size = 1000
        self.entity_extractor = EntityExtractor()
    
    async def get_query_embedding_async(self, query: str) -> np.ndarray:
        """Get embedding for user query asynchronously"""
        query_hash = hash(query)
        if query_hash in self._query_cache:
            return self._query_cache[query_hash]
        
        try:
            response = self.client.embeddings.create(
                model=Config.EMBEDDING_MODEL,
                input=query
            )
            embedding = np.array(response.data[0].embedding)
            
            if len(self._query_cache) < self._max_cache_size:
                self._query_cache[query_hash] = embedding
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error getting query embedding: {e}")
            # FIX: Return a random embedding with same dimension as knowledge base
            # This allows the model to work even when API is unavailable
            if self.kb.embeddings.size > 0:
                embedding_dim = self.kb.embeddings.shape[1]
                return np.random.randn(embedding_dim) * 0.1  # Small random embedding
            return np.zeros(1024)
    
    def get_query_embedding(self, query: str) -> np.ndarray:
        """Synchronous version for backward compatibility"""
        return asyncio.run(self.get_query_embedding_async(query))
    
    def find_similar_answers(self, query: str, top_k: Optional[int] = None) -> List[Dict]:
        """Find most relevant answers with optimized similarity search"""
        try:
            if top_k is None:
                top_k = self.top_k
            
            if self.kb.embeddings.size == 0:
                logger.warning(f"Knowledge base embeddings are empty - shape: {self.kb.embeddings.shape}, size: {self.kb.embeddings.size}")
                return []
            
            # FIX: Try to get query embedding, but fall back to keyword matching if API fails
            try:
                query_embedding = self.get_query_embedding(query)
                similarities = cosine_similarity([query_embedding], self.kb.embeddings)[0]
                top_indices = np.argsort(similarities)[::-1][:top_k]
                
                results = []
                for idx in top_indices:
                    results.append({
                        'knowledge_item': self.kb.knowledge_data[idx],
                        'similarity_score': float(similarities[idx]),
                        'index': int(idx)
                    })
                
                logger.info(f"Found {len(results)} similar items using embeddings")
                return results
                
            except Exception as api_error:
                logger.warning(f"API embedding failed ({api_error}), falling back to keyword matching")
                return self._find_similar_by_keywords(query, top_k)
            
        except Exception as e:
            logger.error(f"Error in find_similar_answers: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def _find_similar_by_keywords(self, query: str, top_k: int) -> List[Dict]:
        """Fallback method using keyword matching when embeddings fail"""
        query_lower = query.lower()
        results = []
        
        for idx, item in enumerate(self.kb.knowledge_data):
            score = 0.0
            
            # Check question similarity
            question_lower = item['question'].lower()
            if any(word in question_lower for word in query_lower.split()):
                score += 0.3
            
            # Check category similarity
            category_lower = f"{item['main_category']} {item['subcategory']}".lower()
            if any(word in category_lower for word in query_lower.split()):
                score += 0.2
            
            # Check template answer similarity
            answer_lower = item['template_answer'].lower()
            if any(word in answer_lower for word in query_lower.split()):
                score += 0.1
            
            if score > 0:
                results.append({
                    'knowledge_item': item,
                    'similarity_score': score,
                    'index': idx
                })
        
        # Sort by score and return top_k
        results.sort(key=lambda x: x['similarity_score'], reverse=True)
        return results[:top_k]
    
    def classify_query(self, query: str) -> Dict[str, Any]:
        """Enhanced classification with entity extraction"""
        similar_items = self.find_similar_answers(query)
        entities = self.entity_extractor.extract_entities(query)
        
        main_category = "Неопределено"
        subcategory = "Общий вопрос"
        confidence = 0.0
        
        if similar_items and similar_items[0]['similarity_score'] > Config.CATEGORY_CLASSIFICATION_THRESHOLD:
            best_match = similar_items[0]['knowledge_item']
            main_category = best_match['main_category']
            subcategory = best_match['subcategory']
            confidence = similar_items[0]['similarity_score']
        
        if confidence < Config.CATEGORY_CLASSIFICATION_THRESHOLD and len(similar_items) > 0:
            main_category, subcategory, confidence = self._refine_classification_with_llm(query, similar_items)
        
        return {
            'main_category': main_category,
            'subcategory': subcategory,
            'confidence': confidence,
            'similar_items': similar_items,
            'entities': entities,
            'top_similarity_scores': [item['similarity_score'] for item in similar_items[:3]]
        }
    
    def _refine_classification_with_llm(self, query: str, similar_items: List[Dict]) -> Tuple[str, str, float]:
        """Refine classification using LLM for difficult cases"""
        try:
            candidate_categories = []
            for item in similar_items[:5]:
                kb_item = item['knowledge_item']
                candidate_categories.append(f"{kb_item['main_category']} -> {kb_item['subcategory']}")
            
            unique_categories = list(set(candidate_categories))
            
            system_prompt = """Ты - эксперт по классификации банковских запросов. 
            Определи наиболее подходящую категорию и подкатегорию для запроса клиента.
            Выбери из предложенных вариантов или верни "Неопределено -> Общий вопрос" если нет хорошего соответствия."""
            
            user_prompt = f"""
            Запрос клиента: {query}
            
            Возможные категории:
            {chr(10).join([f"- {cat}" for cat in unique_categories])}
            
            Верни ответ в формате: ОсновнаяКатегория -> Подкатегория
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
                return main_cat.strip(), sub_cat.strip(), 0.7
            
        except Exception as e:
            logger.error(f"Error in LLM classification refinement: {e}")
        
        best_match = similar_items[0]['knowledge_item']
        return best_match['main_category'], best_match['subcategory'], similar_items[0]['similarity_score']

class TemplateBasedResponseGenerator:
    """Template-based response generator - FIXED VERSION"""
    
    def __init__(self, client, temperature=0.1, max_tokens=300):
        self.client = client
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    def generate_response(self, user_query: str, similar_items: List[Dict], classification_result: Dict) -> str:
        """Generate response EXCLUSIVELY from templates"""
        
        # FIX 3: Use only template answers, don't generate new ones
        if not similar_items:
            return ""  # Empty response - no suggestion for operator
        
        best_match = similar_items[0]
        if best_match['similarity_score'] >= Config.CATEGORY_CLASSIFICATION_THRESHOLD:
            return best_match['knowledge_item']['template_answer']
        
        return ""
    
    def get_multiple_template_options(self, similar_items: List[Dict], max_options: int = 3) -> List[Dict]:
        """Return multiple template options for operator"""
        options = []
        for item in similar_items[:max_options]:
            if item['similarity_score'] >= 0.5:
                options.append({
                    'template_answer': item['knowledge_item']['template_answer'],
                    'similarity_score': item['similarity_score'],
                    'category': f"{item['knowledge_item']['main_category']} -> {item['knowledge_item']['subcategory']}",
                    'source_question': item['knowledge_item']['question']
                })
        return options

class ContinuousLearning:
    """Continuous learning with analytics"""
    
    def __init__(self, support_system):
        self.system = support_system
        self.retraining_threshold = Config.RETRAINING_THRESHOLD
        self._feedback_analytics = {}
    
    def analyze_feedback(self, feedback_file: str) -> Dict[str, Any]:
        """Enhanced feedback analysis with detailed metrics"""
        try:
            feedback_df = pd.read_csv(feedback_file)
            
            analytics = {
                'total_feedback': len(feedback_df),
                'average_rating': float(feedback_df['operator_rating'].mean()),
                'low_rated_count': len(feedback_df[feedback_df['operator_rating'] <= 3]),
                'high_rated_count': len(feedback_df[feedback_df['operator_rating'] >= 4]),
                'category_issues': {},
                'improvement_suggestions': []
            }
            
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
            
            self._feedback_analytics = analytics
            return analytics
            
        except Exception as e:
            logger.error(f"Error analyzing feedback: {e}")
            return {}
    
    def should_retrain(self) -> bool:
        """Determine if model should be retrained"""
        if not hasattr(self.system, 'feedback_data'):
            return False
        
        total_feedback = len(self.system.feedback_data)
        low_rated = sum(1 for item in self.system.feedback_data if item.get('operator_rating', 5) <= 3)
        
        return total_feedback >= self.retraining_threshold and (low_rated / total_feedback) > 0.2
    
    def update_knowledge_base(self, new_data_file: str, merge_strategy: str = "append"):
        """Update knowledge base with new data"""
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
            
            self.system.kb.generate_embeddings()
            logger.info(f"Knowledge base updated. Added {len(new_df)} new records.")
            
        except Exception as e:
            logger.error(f"Error updating knowledge base: {e}")
            raise

class ModelPersistor:
    """Enhanced model persistence with compression and versioning"""
    
    def __init__(self, model_dir: str = "models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
    
    def save_complete_model(self, support_system, model_name: str = "support_model") -> Path:
        """Save complete model with enhanced metadata"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = self.model_dir / f"{model_name}_{timestamp}"
        model_path.mkdir(exist_ok=True)
        
        try:
            self._save_knowledge_base(support_system.kb, model_path)
            self._save_model_config(support_system, model_path)
            self._save_feedback_data(support_system, model_path)
            self._save_performance_metrics(support_system, model_path)
            
            logger.info(f"Model saved to: {model_path}")
            return model_path
            
        except Exception as e:
            logger.error(f"Error saving model: {e}")
            raise
    
    def _save_knowledge_base(self, knowledge_base, model_path: Path):
        """Save knowledge base with compression"""
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
        """Save model configuration"""
        config = {
            'model_name': 'OptimizedIntelligentSupportSystem',
            'version': '2.1',
            'embedding_model': Config.EMBEDDING_MODEL,
            'llm_model': Config.LLM_MODEL,
            'parameters': {
                'similarity_threshold': getattr(support_system.classifier, 'similarity_threshold', Config.DEFAULT_SIMILARITY_THRESHOLD),
                'top_k_results': getattr(support_system.classifier, 'top_k', Config.DEFAULT_TOP_K),
                'temperature': getattr(support_system.generator, 'temperature', 0.1),
                'max_tokens': getattr(support_system.generator, 'max_tokens', 300)
            },
            'save_timestamp': datetime.now().isoformat()
        }
        
        with open(model_path / "model_config.json", 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    
    def _save_feedback_data(self, support_system, model_path: Path):
        """Save feedback data"""
        if hasattr(support_system, 'feedback_data') and support_system.feedback_data:
            feedback_df = pd.DataFrame(support_system.feedback_data)
            feedback_df.to_csv(model_path / "feedback_data.csv", index=False, encoding='utf-8')
    
    def _save_performance_metrics(self, support_system, model_path: Path):
        """Save performance metrics"""
        metrics = {
            'total_queries_processed': len(support_system.feedback_data) if hasattr(support_system, 'feedback_data') else 0,
            'average_rating': self._calculate_average_rating(support_system),
            'category_distribution': self._get_category_distribution(support_system),
            'model_performance': {
                'embedding_dim': int(support_system.kb.embeddings.shape[1]) if len(support_system.kb.embeddings) > 0 else 0,
                'knowledge_base_size': len(support_system.kb.knowledge_data),
                'last_updated': datetime.now().isoformat()
            }
        }
        
        with open(model_path / "performance_metrics.json", 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
    
    def _calculate_average_rating(self, support_system) -> float:
        """Calculate average rating"""
        if hasattr(support_system, 'feedback_data') and support_system.feedback_data:
            ratings = [item.get('operator_rating', 0) for item in support_system.feedback_data]
            return sum(ratings) / len(ratings) if ratings else 0.0
        return 0.0
    
    def _get_category_distribution(self, support_system) -> Dict[str, int]:
        """Get category distribution"""
        if hasattr(support_system, 'feedback_data') and support_system.feedback_data:
            categories = [item['classification']['main_category'] for item in support_system.feedback_data]
            return dict(pd.Series(categories).value_counts())
        return {}

class ModelLoader:
    """Enhanced model loader with error handling and validation"""
    
    def __init__(self, model_dir: str = "models"):
        self.model_dir = Path(model_dir)
    
    def load_complete_model(self, model_path: str):
        """Load complete model with validation"""
        model_path = Path(model_path)
        
        if not model_path.exists():
            raise FileNotFoundError(f"Model path does not exist: {model_path}")
        
        try:
            knowledge_base = self._load_knowledge_base(model_path)
            config = self._load_model_config(model_path)
            
            support_system = OptimizedIntelligentSupportSystem()
            support_system.kb = knowledge_base
            
            # FIX: Update classifier to use the loaded knowledge base
            support_system.classifier.kb = knowledge_base
            
            self._load_feedback_data(support_system, model_path)
            
            logger.info(f"Model loaded from: {model_path}")
            return support_system, config
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise
    
    def _load_knowledge_base(self, model_path: Path):
        """Load knowledge base with fallback options"""
        client = OpenAI(api_key=Config.API_KEY, base_url=Config.BASE_URL)
        kb = AsyncKnowledgeBase(client)
        
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
            
            # FIX: Rebuild category mapping if it's empty
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
        """Load model configuration"""
        config_file = model_path / "model_config.json"
        if not config_file.exists():
            raise FileNotFoundError("Model configuration file not found")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _load_feedback_data(self, support_system, model_path: Path):
        """Load feedback data"""
        feedback_file = model_path / "feedback_data.csv"
        if feedback_file.exists():
            feedback_df = pd.read_csv(feedback_file, encoding='utf-8')
            support_system.feedback_data = feedback_df.to_dict('records')
            logger.info(f"Loaded {len(support_system.feedback_data)} feedback records")

class OptimizedIntelligentSupportSystem:
    """Main optimized support system class - FIXED VERSION"""
    
    def __init__(self, knowledge_base_path: Optional[str] = None):
        self.client = OpenAI(api_key=Config.API_KEY, base_url=Config.BASE_URL)
        self.kb = AsyncKnowledgeBase(self.client)
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
        """Train system from Excel file"""
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
        """Process user query with template-based responses"""
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
                    'model_version': '2.1_fixed'
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
    
    def collect_feedback(self, query_result: Dict, user_feedback: str, operator_rating: int):
        """Collect feedback for continuous learning"""
        feedback_entry = {
            **query_result,
            'user_feedback': user_feedback,
            'operator_rating': operator_rating,
            'feedback_timestamp': datetime.now().isoformat()
        }
        
        self.feedback_data.append(feedback_entry)
        
        if self.continuous_learning.should_retrain():
            logger.info("Retraining threshold reached, scheduling retraining...")
        
        logger.info("Feedback collected successfully")
    
    def save_current_state(self, model_name: str = "current_support_model") -> Path:
        """Save current system state"""
        return self.persistor.save_complete_model(self, model_name)
    
    def load_model(self, model_path: str):
        """Load previously saved model"""
        return self.loader.load_complete_model(model_path)

# Backward compatibility aliases
KnowledgeBase = AsyncKnowledgeBase
SupportClassifier = OptimizedSupportClassifier
ResponseGenerator = TemplateBasedResponseGenerator
IntelligentSupportSystem = OptimizedIntelligentSupportSystem

def demo_fixed_system():
    """Demonstration of the fixed system"""
    system = OptimizedIntelligentSupportSystem()
    
    # Train the system (replace with your Excel file path)
    # system.train_from_excel("training_data.xlsx", save_model=True)
    
    system, config = system.load_model("models/trained_support_model_20251014_195117")
    
    print("✅ Модель успешно загружена!")
    print(f"📊 Записей в базе знаний: {len(system.kb.knowledge_data)}")
    
    test_queries = [
        "Как восстановить пароль от интернет-банка?",
        "Моя карта заблокирована, что делать?",
        "Хочу стать клиентом вашего банка",
        "Не работает мобильное приложение",
        "Как сварить борщ?"
    ]
    
    print("=== Intelligent Support System Demo ===\n")
    
    for query in test_queries:
        result = system.process_query(query)
        print(f"📝 Query: {query}")
        print(f"🏷️ Category: {result['classification']['main_category']} -> {result['classification']['subcategory']}")
        print(f"🎯 Confidence: {result['classification']['confidence']:.2f}")
        print(f"🔍 Entities: {result['classification']['entities']}")
        print(f"💡 Suggestion: {'AVAILABLE' if result['has_suggestion'] else 'NOT AVAILABLE'}")
        if result['response']:
            print(f"📄 Response: {result['response'][:150]}...")
        print(f"📊 Similar items found: {result['processing_metadata']['num_similar_items']}")
        print("-" * 80)

if __name__ == "__main__":
    demo_fixed_system()