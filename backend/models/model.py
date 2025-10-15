#!/usr/bin/env python
# coding: utf-8

# ## 0. Подключение нужных библиотек

# In[1]:


import pandas as pd
import numpy as np
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity
import json

import pickle
from pathlib import Path
from datetime import datetime

import warnings
warnings.filterwarnings('ignore')


# ## 1. Настройка клиента SciBox

# In[2]:


API_KEY = "sk-Hheb_7mljCgAWSIIyEYbnw"
BASE_URL = "https://llm.t1v.scibox.tech/v1"
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

class KnowledgeBase:
    def __init__(self, client):
        self.client = client
        self.knowledge_data = []
        self.embeddings = []
        
    def load_data_from_excel(self, file_path):
        """Загрузка данных из Excel файла"""
        df = pd.read_excel(file_path)
        
        # Создаем текстовые представления для эмбеддингов
        for _, row in df.iterrows():
            knowledge_item = {
                'main_category': row['Основная категория'],
                'subcategory': row['Подкатегория'],
                'question': row['Пример вопроса'],
                'priority': row['Приоритет'],
                'target_audience': row['Целевая аудитория'],
                'template_answer': row['Шаблонный ответ'],
                'combined_text': f"{row['Основная категория']} {row['Подкатегория']} {row['Пример вопроса']} {row['Шаблонный ответ']}"
            }
            self.knowledge_data.append(knowledge_item)
        
        print(f"Загружено {len(self.knowledge_data)} записей из базы знаний")
        return self.knowledge_data
    
    def generate_embeddings(self):
        """Генерация эмбеддингов для всей базы знаний"""
        texts = [item['combined_text'] for item in self.knowledge_data]
        
        # Разбиваем на батчи для избежания перегрузки API
        batch_size = 10
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            
            try:
                response = client.embeddings.create(
                    model="bge-m3",
                    input=batch_texts
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                print(f"Обработан батч {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")
                
            except Exception as e:
                print(f"Ошибка при генерации эмбеддингов: {e}")
                # Добавляем нулевые вектора для неудачных запросов
                all_embeddings.extend([np.zeros(1024)] * len(batch_texts))
        
        self.embeddings = np.array(all_embeddings)
        return self.embeddings
    
    def save_knowledge_base(self, file_path):
        """Сохранение базы знаний с эмбеддингами"""
        knowledge_dict = {
            'knowledge_data': self.knowledge_data,
            'embeddings': self.embeddings.tolist()
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(knowledge_dict, f, ensure_ascii=False, indent=2)
        
        print(f"База знаний сохранена в {file_path}")
    
    def load_knowledge_base(self, file_path):
        """Загрузка ранее сохраненной базы знаний"""
        with open(file_path, 'r', encoding='utf-8') as f:
            knowledge_dict = json.load(f)
        
        self.knowledge_data = knowledge_dict['knowledge_data']
        self.embeddings = np.array(knowledge_dict['embeddings'])
        print(f"Загружена база знаний из {file_path}")


# ## 2. Модуль классификации и поиска релевантных ответов

# In[3]:


class SupportClassifier:
    def __init__(self, knowledge_base):
        self.kb = knowledge_base
        self.client = knowledge_base.client
    
    def get_query_embedding(self, query):
        """Получение эмбеддинга для пользовательского запроса"""
        try:
            response = self.client.embeddings.create(
                model="bge-m3",
                input=query
            )
            return np.array(response.data[0].embedding)
        except Exception as e:
            print(f"Ошибка при получении эмбеддинга запроса: {e}")
            return np.zeros(1024)
    
    def find_similar_answers(self, query, top_k=5):
        """Поиск наиболее релевантных ответов"""
        query_embedding = self.get_query_embedding(query)
        
        # Вычисление косинусного сходства
        similarities = cosine_similarity(
            [query_embedding], 
            self.kb.embeddings)[0]
        
        # Получение топ-K наиболее похожих элементов
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            results.append({
                'knowledge_item': self.kb.knowledge_data[idx],
                'similarity_score': similarities[idx],
                'index': idx
            })
        
        return results
    
    def classify_query(self, query):
        """Классификация запроса и поиск релевантных ответов"""
        similar_items = self.find_similar_answers(query)
        
        # Определение основной категории на основе наиболее похожего элемента
        if similar_items and similar_items[0]['similarity_score'] > 0.7:
            main_category = similar_items[0]['knowledge_item']['main_category']
            subcategory = similar_items[0]['knowledge_item']['subcategory']
            confidence = similar_items[0]['similarity_score']
        else:
            main_category = "Неопределено"
            subcategory = "Общий вопрос"
            confidence = 0.0
        
        classification_result = {
            'main_category': main_category,
            'subcategory': subcategory,
            'confidence': confidence,
            'similar_items': similar_items
        }
        
        return classification_result


# ## 3. Модуль генерации персонализированных ответов

# In[4]:


class ResponseGenerator:
    def __init__(self, client):
        self.client = client
    
    def generate_response(self, user_query, similar_items, classification_result):
        """Генерация персонализированного ответа на основе найденных шаблонов"""
        
        # Подготовка контекста из похожих вопросов-ответов
        context = "Релевантные решения из базы знаний:\n"
        for i, item in enumerate(similar_items[:3]):  # Берем топ-3
            context += f"{i+1}. Вопрос: {item['knowledge_item']['question']}\n"
            context += f"   Ответ: {item['knowledge_item']['template_answer']}\n\n"
        
        system_prompt = """Ты - AI-ассистент службы поддержки банка. 
        Используй предоставленные шаблонные ответы из базы знаний для формирования точного и полезного ответа.
        Адаптируй ответ под конкретный запрос пользователя, сохраняя точность информации.
        Будь вежливым и профессиональным."""

        user_prompt = f"""
        Запрос пользователя: {user_query}
        
        {context}
        
        Категория запроса: {classification_result['main_category']} -> {classification_result['subcategory']}
        
        Сформируй четкий, полезный ответ на основе предоставленной информации. 
        Если необходимо, объедини информацию из нескольких релевантных источников.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="Qwen2.5-72B-Instruct-AWQ",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Низкая температура для большей консистентности
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Ошибка при генерации ответа: {e}")
            # Возвращаем самый релевантный шаблонный ответ в случае ошибки
            if similar_items:
                return similar_items[0]['knowledge_item']['template_answer']
            else:
                return "Извините, в настоящее время я не могу обработать ваш запрос. Пожалуйста, обратитесь в службу поддержки."


# ## 4. Механизм непрерывного обучения

# In[5]:


class ContinuousLearning:
    def __init__(self, support_system):
        self.system = support_system
        self.retraining_threshold = 50  # Количество новых данных для переобучения
    
    def analyze_feedback(self, feedback_file):
        """Анализ обратной связи для выявления проблемных областей"""
        try:
            feedback_df = pd.read_csv(feedback_file)
            
            # Анализ низко оцененных ответов
            low_rated = feedback_df[feedback_df['operator_rating'] <= 3]
            
            if len(low_rated) > 0:
                print(f"Найдено {len(low_rated)} низко оцененных ответов")
                
                # Группировка по категориям для выявления слабых мест
                category_issues = low_rated.groupby('classification_main_category').size()
                print("Проблемные категории:")
                for category, count in category_issues.items():
                    print(f"  {category}: {count} проблемных случаев")
            
            return low_rated
            
        except Exception as e:
            print(f"Ошибка при анализе обратной связи: {e}")
            return pd.DataFrame()
    
    def update_knowledge_base(self, new_data_file):
        """Обновление базы знаний новыми данными"""
        try:
            # Загрузка новых данных
            new_df = pd.read_excel(new_data_file)
            
            # Добавление в существующую базу знаний
            current_count = len(self.system.kb.knowledge_data)
            self.system.kb.load_data_from_excel(new_data_file)
            
            # Перегенерация эмбеддингов для новых данных
            new_embeddings = self.system.kb.generate_embeddings()
            
            print(f"База знаний обновлена. Добавлено {len(new_df)} новых записей.")
            
            # Сохранение обновленной базы
            self.system.kb.save_knowledge_base('knowledge_base_updated.json')
            
        except Exception as e:
            print(f"Ошибка при обновлении базы знаний: {e}")


# ## 5. Сохранение модели

# ### 5.1. Сохранение векторной базы знаний

# In[6]:


class ModelPersistor:
    def __init__(self, model_dir="models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
    
    def save_complete_model(self, support_system, model_name="support_model"):
        """Полное сохранение всей системы"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = self.model_dir / f"{model_name}_{timestamp}"
        model_path.mkdir(exist_ok=True)
        
        # 1. Сохраняем базу знаний
        self._save_knowledge_base(support_system.kb, model_path)
        
        # 2. Сохраняем конфигурацию модели
        self._save_model_config(support_system, model_path)
        
        # 3. Сохраняем историю обратной связи
        self._save_feedback_data(support_system, model_path)
        
        # 4. Сохраняем метрики производительности
        self._save_performance_metrics(support_system, model_path)
        
        print(f"Модель сохранена в: {model_path}")
        return model_path
    
    def _save_knowledge_base(self, knowledge_base, model_path):
        """Сохранение базы знаний с эмбеддингами"""
        kb_data = {
            'knowledge_data': knowledge_base.knowledge_data,
            'embeddings': knowledge_base.embeddings.tolist() if len(knowledge_base.embeddings) > 0 else [],
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'num_items': len(knowledge_base.knowledge_data),
                'embedding_dim': int(knowledge_base.embeddings.shape[1]) if len(knowledge_base.embeddings) > 0 else 0
            }
        }
        
        # Сохраняем в JSON
        with open(model_path / "knowledge_base.json", 'w', encoding='utf-8') as f:
            json.dump(kb_data, f, ensure_ascii=False, indent=2)
        
        # Дублируем в pickle для быстрой загрузки
        with open(model_path / "knowledge_base.pkl", 'wb') as f:
            pickle.dump(kb_data, f)
    
    def _save_model_config(self, support_system, model_path):
        """Сохранение конфигурации модели"""
        config = {
            'model_name': 'IntelligentSupportSystem',
            'version': '1.0',
            'embedding_model': 'bge-m3',
            'llm_model': 'Qwen2.5-72B-Instruct-AWQ',
            'parameters': {
                'similarity_threshold': 0.7,
                'top_k_results': 5,
                'temperature': 0.3,
                'max_tokens': 500
            },
            'save_timestamp': datetime.now().isoformat()
        }
        
        with open(model_path / "model_config.json", 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    
    def _save_feedback_data(self, support_system, model_path):
        """Сохранение данных обратной связи"""
        if hasattr(support_system, 'feedback_data') and support_system.feedback_data:
            # Преобразуем в стандартные Python типы перед сохранением
            feedback_data_serializable = []
            for item in support_system.feedback_data:
                serializable_item = {}
                for key, value in item.items():
                    if isinstance(value, (np.integer, np.int64)):
                        serializable_item[key] = int(value)
                    elif isinstance(value, (np.floating, np.float64)):
                        serializable_item[key] = float(value)
                    elif isinstance(value, np.ndarray):
                        serializable_item[key] = value.tolist()
                    else:
                        serializable_item[key] = value
                feedback_data_serializable.append(serializable_item)
            
            feedback_df = pd.DataFrame(feedback_data_serializable)
            feedback_df.to_csv(model_path / "feedback_data.csv", index=False, encoding='utf-8')
    
    def _save_performance_metrics(self, support_system, model_path):
        """Сохранение метрик производительности"""
        # Преобразуем NumPy типы в стандартные Python типы
        category_distribution = self._get_category_distribution(support_system)
        category_distribution_serializable = {}
        
        for key, value in category_distribution.items():
            if isinstance(value, (np.integer, np.int64)):
                category_distribution_serializable[key] = int(value)
            elif isinstance(value, (np.floating, np.float64)):
                category_distribution_serializable[key] = float(value)
            else:
                category_distribution_serializable[key] = value
        
        metrics = {
            'total_queries_processed': int(len(support_system.feedback_data)) if hasattr(support_system, 'feedback_data') else 0,
            'average_rating': float(self._calculate_average_rating(support_system)),
            'category_distribution': category_distribution_serializable
        }
        
        with open(model_path / "performance_metrics.json", 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
    
    def _calculate_average_rating(self, support_system):
        """Расчет средней оценки"""
        if hasattr(support_system, 'feedback_data') and support_system.feedback_data:
            ratings = [item.get('operator_rating', 0) for item in support_system.feedback_data]
            return sum(ratings) / len(ratings) if ratings else 0
        return 0
    
    def _get_category_distribution(self, support_system):
        """Распределение по категориям"""
        if hasattr(support_system, 'feedback_data') and support_system.feedback_data:
            categories = [item['classification']['main_category'] for item in support_system.feedback_data]
            return dict(pd.Series(categories).value_counts())
        return {}


# ### 5.2. Загрузка сохраненной модели

# In[7]:


class ModelLoader:
    def __init__(self, model_dir="models"):
        self.model_dir = Path(model_dir)
    
    def load_complete_model(self, model_path):
        """Загрузка полной модели"""
        model_path = Path(model_path)
        
        # Загружаем базу знаний
        knowledge_base = self._load_knowledge_base(model_path)
        
        # Загружаем конфигурацию
        config = self._load_model_config(model_path)
        
        # Создаем экземпляр системы
        support_system = IntelligentSupportSystem()
        support_system.kb = knowledge_base
        
        # Загружаем обратную связь
        self._load_feedback_data(support_system, model_path)
        
        print(f"Модель загружена из: {model_path}")
        return support_system, config
    
    def _load_knowledge_base(self, model_path):
        """Загрузка базы знаний"""
        kb = KnowledgeBase(client)  # client нужно инициализировать
        
        try:
            # Пробуем загрузить из pickle (быстрее)
            with open(model_path / "knowledge_base.pkl", 'rb') as f:
                kb_data = pickle.load(f)
        except:
            # Загружаем из JSON
            with open(model_path / "knowledge_base.json", 'r', encoding='utf-8') as f:
                kb_data = json.load(f)
        
        kb.knowledge_data = kb_data['knowledge_data']
        kb.embeddings = np.array(kb_data['embeddings'])
        
        print(f"Загружено {len(kb.knowledge_data)} записей из базы знаний")
        return kb
    
    def _load_model_config(self, model_path):
        """Загрузка конфигурации модели"""
        with open(model_path / "model_config.json", 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _load_feedback_data(self, support_system, model_path):
        """Загрузка данных обратной связи"""
        feedback_file = model_path / "feedback_data.csv"
        if feedback_file.exists():
            feedback_df = pd.read_csv(feedback_file, encoding='utf-8')
            support_system.feedback_data = feedback_df.to_dict('records')
            print(f"Загружено {len(support_system.feedback_data)} записей обратной связи")


# ## 6. Интеграция всех компонентов в единую систему

# In[8]:


class IntelligentSupportSystem:
    def __init__(self, knowledge_base_path=None):
        self.client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
        self.kb = KnowledgeBase(self.client)
        self.persistor = ModelPersistor()
        self.loader = ModelLoader()
        
        if knowledge_base_path:
            self.kb.load_knowledge_base(knowledge_base_path)
        else:
            # Инициализация пустой системы
            self.kb.knowledge_data = []
            self.kb.embeddings = np.array([])
        
        self.classifier = SupportClassifier(self.kb)
        self.generator = ResponseGenerator(self.client)
        self.feedback_data = []
    
    def train_from_excel(self, excel_file_path, save_model=True):
        """Обучение системы из Excel файла"""
        print("Начало обучения системы...")
        
        # Загрузка и обработка данных
        self.kb.load_data_from_excel(excel_file_path)
        self.kb.generate_embeddings()
        
        if save_model:
            # Сохранение обученной модели
            model_path = self.persistor.save_complete_model(self, "trained_support_model")
            print(f"Обученная модель сохранена в: {model_path}")
        
        print("Обучение завершено!")
        return self

    def process_query(self, user_query):
        """Основной метод обработки пользовательского запроса"""
        print(f"Обработка запроса: {user_query}")
        
        # Классификация и поиск релевантных ответов
        classification = self.classifier.classify_query(user_query)
        print(f"Категория: {classification['main_category']} (уверенность: {classification['confidence']:.2f})")
        
        # Генерация ответа
        response = self.generator.generate_response(
            user_query, 
            classification['similar_items'], 
            classification
        )
        
        result = {
            'user_query': user_query,
            'classification': classification,
            'response': response,
            'timestamp': pd.Timestamp.now().isoformat()
        }
        
        return result

    def collect_feedback(self, query_result, user_feedback, operator_rating):
        """Сбор обратной связи для улучшения системы"""
        feedback_entry = {
            **query_result,
            'user_feedback': user_feedback,
            'operator_rating': operator_rating,  # Оценка оператора (1-5)
            'feedback_timestamp': pd.Timestamp.now().isoformat()
        }
        
        self.feedback_data.append(feedback_entry)
        print("Обратная связь сохранена")
    
    def save_current_state(self, model_name="current_support_model"):
        """Сохранение текущего состояния системы"""
        return self.persistor.save_complete_model(self, model_name)
    
    def load_model(self, model_path):
        """Загрузка ранее сохраненной модели"""
        support_system, config = self.loader.load_complete_model(model_path)
        return support_system


# ## 7. Использование

# In[9]:


# Пример использования с сохранением
def main():
    # Инициализация системы
    support_system = IntelligentSupportSystem()
    
    # Вариант 1: Обучение с нуля и сохранение
    print("=== Обучение новой модели ===")
    support_system.train_from_excel('training_data.xlsx', save_model=True)

    """
    # Вариант 2: Загрузка существующей модели
    print("\n=== Загрузка существующей модели ===")
    try:
        loaded_system = support_system.load_model("models/trained_support_model_20231201_143022")
        
        # Тестирование загруженной модели
        test_query = "Как восстановить пароль?"
        result = loaded_system.process_query(test_query)
        print(f"Результат: {result['response']}")
        
        # Сохранение обновленного состояния после работы
        loaded_system.save_current_state("updated_support_model")
        
    except Exception as e:
        print(f"Ошибка при загрузке модели: {e}")
        print("Продолжаем с новой моделью...")
    
    # Работа с системой
    while True:
        user_query = input("\nВведите ваш вопрос (или 'quit' для выхода): ")
        if user_query.lower() == 'quit':
            break
        
        result = support_system.process_query(user_query)
        print(f"\nКатегория: {result['classification']['main_category']}")
        print(f"Ответ: {result['response']}")
        
        # Сбор обратной связи
        rating = input("Оцените ответ (1-5): ")
        if rating.isdigit():
            support_system.collect_feedback(result, "user_feedback", int(rating))

    """

    # Примеры запросов для тестирования
    test_queries = [
        "Как восстановить пароль от интернет-банка?",
        "Что делать если карта заблокирована?",
        "Как зарегистрироваться в вашем банке?",
        "Не могу войти в мобильное приложение"
    ]
    
    for query in test_queries:
        print(f"\n{'='*50}")
        result = support_system.process_query(query)
        
        print(f"Запрос: {result['user_query']}")
        print(f"Категория: {result['classification']['main_category']}")
        print(f"Ответ: {result['response']}")
        print(f"{'='*50}")
        
        # Имитация обратной связи
        support_system.collect_feedback(
            result, 
            user_feedback="helpful", 
            operator_rating=5
        )
    
    # Финальное сохранение
    support_system.save_current_state("final_support_model")
    print("Работа завершена. Модель сохранена.")

if __name__ == "__main__":
    main()


# In[ ]:





# In[ ]:




