"""
Excel Data Processor for Training Data
Processes training_data.xlsx and splits into chunks for vector database
"""

import pandas as pd
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class ExcelDataProcessor:
    """Processes Excel training data and splits into chunks"""
    
    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.processed_data: List[Dict[str, Any]] = []
    
    def process_excel_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Process Excel file and return chunked data"""
        try:
            logger.info(f"Processing Excel file: {file_path}")
            
            # Read Excel file
            df = pd.read_excel(file_path)
            logger.info(f"Loaded {len(df)} rows from Excel file")
            
            # Process each row
            for index, row in df.iterrows():
                row_data = self._process_row(row, index)
                if row_data:
                    self.processed_data.extend(row_data)
            
            logger.info(f"Processed {len(self.processed_data)} chunks from Excel data")
            return self.processed_data
            
        except Exception as e:
            logger.error(f"Error processing Excel file: {e}")
            return []
    
    def _process_row(self, row: pd.Series, row_index: int) -> List[Dict[str, Any]]:
        """Process a single row from Excel"""
        try:
            # Extract data from row
            main_category = str(row.get('Основная категория', ''))
            subcategory = str(row.get('Подкатегория', ''))
            question = str(row.get('Пример вопроса', ''))
            template_answer = str(row.get('Шаблонный ответ', ''))
            priority = str(row.get('Приоритет', ''))
            target_audience = str(row.get('Целевая аудитория', ''))
            
            # Skip empty rows
            if not any([main_category, subcategory, question, template_answer]):
                return []
            
            # Create combined text for processing
            combined_text = f"{main_category} {subcategory} {question} {template_answer}"
            
            # Split into chunks
            chunks = self._split_text_into_chunks(combined_text)
            
            processed_chunks = []
            for i, chunk in enumerate(chunks):
                if len(chunk.strip()) < 30:  # Skip very short chunks
                    continue
                
                chunk_data = {
                    'id': f"excel_row_{row_index}_chunk_{i}",
                    'source_type': 'excel_training',
                    'row_index': row_index,
                    'chunk_index': i,
                    'main_category': main_category,
                    'subcategory': subcategory,
                    'question': question,
                    'template_answer': template_answer,
                    'priority': priority,
                    'target_audience': target_audience,
                    'content': chunk,
                    'processed_at': datetime.now().isoformat(),
                    'metadata': {
                        'original_row': row_index,
                        'chunk_size': len(chunk),
                        'has_question': bool(question.strip()),
                        'has_answer': bool(template_answer.strip())
                    }
                }
                
                processed_chunks.append(chunk_data)
            
            return processed_chunks
            
        except Exception as e:
            logger.warning(f"Error processing row {row_index}: {e}")
            return []
    
    def _split_text_into_chunks(self, text: str) -> List[str]:
        """Split text into overlapping chunks"""
        if len(text) <= self.chunk_size:
            return [text]
        
        # Clean text
        text = re.sub(r'\s+', ' ', text).strip()
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings
                for i in range(end, max(start + self.chunk_size - 100, start), -1):
                    if text[i] in '.!?':
                        end = i + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - self.overlap
        
        return chunks
    
    def save_processed_data(self, file_path: str):
        """Save processed data to file"""
        try:
            data = {
                'processed_at': datetime.now().isoformat(),
                'chunk_size': self.chunk_size,
                'overlap': self.overlap,
                'total_chunks': len(self.processed_data),
                'data': self.processed_data
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Processed data saved to {file_path}")
            
        except Exception as e:
            logger.error(f"Error saving processed data: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics"""
        if not self.processed_data:
            return {}
        
        categories = {}
        total_chunks = len(self.processed_data)
        
        for chunk in self.processed_data:
            category = chunk.get('main_category', 'Unknown')
            categories[category] = categories.get(category, 0) + 1
        
        return {
            'total_chunks': total_chunks,
            'categories': categories,
            'avg_chunk_size': sum(len(chunk['content']) for chunk in self.processed_data) / total_chunks if total_chunks > 0 else 0,
            'chunk_size': self.chunk_size,
            'overlap': self.overlap
        }

def process_training_data(excel_file_path: str, output_file: str = "processed_training_data.json") -> List[Dict[str, Any]]:
    """Main function to process training data"""
    processor = ExcelDataProcessor()
    processed_data = processor.process_excel_file(excel_file_path)
    processor.save_processed_data(output_file)
    
    # Print statistics
    stats = processor.get_statistics()
    logger.info(f"Processing completed: {stats}")
    
    return processed_data

if __name__ == "__main__":
    # Example usage
    data = process_training_data("training_data.xlsx")
    print(f"Processed {len(data)} chunks from training data")
