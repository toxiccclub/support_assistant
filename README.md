# AI Support Assistant

An intelligent support system for VTB bank that helps operators analyze customer inquiries using AI-powered classification and response generation.

## 🚀 Features

- **AI-Powered Classification**: Automatically categorizes customer inquiries using advanced ML models
- **Template-Based Responses**: Generates appropriate responses based on knowledge base templates
- **Fuzzy Matching**: Handles typos, transliterations, and variations in customer queries
- **Continuous Learning**: Improves over time through operator feedback
- **Modern Web Interface**: Clean, responsive UI built with vanilla JavaScript
- **Real-time Analytics**: Track system performance and operator feedback

## 🏗️ Architecture

```
support_assistant/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── main.py         # FastAPI application
│   │   └── data/           # Knowledge base data
│   ├── models/
│   │   └── model_final.py  # AI model implementation
│   └── requirements.txt    # Python dependencies
├── frontend/               # Web interface
│   ├── index.html         # Main application page
│   └── app.js            # JavaScript application logic
└── logs/                  # Application logs
```

## 🐳 Docker Deployment (Recommended)

### Quick Start with Docker

1. **Clone and navigate to the project:**
   ```bash
   git clone <repository-url>
   cd support_assistant
   ```

2. **Build and run with Docker Compose:**
   ```bash
   docker-compose up --build
   ```

3. **Access the application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Docker Services

- **Backend**: FastAPI application with AI model
- **Frontend**: Nginx serving static files
- **Database**: Optional PostgreSQL for persistent storage

## 🛠️ Manual Setup

### Prerequisites

- Python 3.8+
- Node.js (for development server)
- OpenAI API key (configured in environment)

### Backend Setup

1. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Configure environment variables:**
   ```bash
   export SCIBOX_API_KEY="your-api-key-here"
   ```

4. **Run the backend:**
   ```bash
   cd backend
   uvicorn app.main:app --reload --port 8000
   ```

### Frontend Setup

1. **Option 1 - Direct file access:**
   - Open `frontend/index.html` in your browser

2. **Option 2 - Development server:**
   ```bash
   cd frontend
   python3 -m http.server 3000
   ```

## 📊 API Endpoints

### Core Endpoints

- `POST /analyze` - Analyze customer inquiry
- `POST /feedback` - Submit operator feedback
- `GET /health` - Health check
- `GET /stats` - System statistics

### Example Usage

```bash
# Analyze a customer inquiry
curl -X POST "http://localhost:8000/analyze" \
     -H "Content-Type: application/json" \
     -d '{"text": "Не могу войти в мобильное приложение"}'

# Submit feedback
curl -X POST "http://localhost:8000/feedback" \
     -H "Content-Type: application/json" \
     -d '{"query": "test", "response": "test response", "rating": 5}'
```

## 🔧 Configuration

### Environment Variables

- `SCIBOX_API_KEY`: API key for AI services
- `SCIBOX_BASE_URL`: Base URL for AI API (default: https://llm.t1v.scibox.tech/v1)
- `LOG_LEVEL`: Logging level (default: INFO)

### Model Configuration

The AI model can be configured in `backend/models/model_final.py`:

- `EMBEDDING_MODEL`: Model for text embeddings
- `LLM_MODEL`: Language model for classification
- `SIMILARITY_THRESHOLD`: Minimum similarity for matches
- `CLASSIFICATION_THRESHOLD`: Confidence threshold for classification

## 📈 Monitoring and Analytics

### System Metrics

- Query processing statistics
- Classification accuracy
- Operator feedback ratings
- Model performance metrics

### Continuous Learning

The system automatically:
- Collects operator feedback
- Identifies misclassifications
- Suggests model improvements
- Triggers retraining when needed

## 🧪 Testing

### Run Tests

```bash
# Backend tests
cd backend
python -m pytest tests/

# Integration tests
docker-compose -f docker-compose.test.yml up --build
```

### Test Data

The system includes sample knowledge base data in `backend/app/data/knowledge_base.json`.

## 🚀 Production Deployment

### Docker Production

```bash
# Build production images
docker-compose -f docker-compose.prod.yml build

# Deploy with production settings
docker-compose -f docker-compose.prod.yml up -d
```

### Environment Setup

1. Configure environment variables
2. Set up SSL certificates
3. Configure reverse proxy
4. Set up monitoring and logging

## 📝 Development

### Adding New Features

1. Update the AI model in `backend/models/model_final.py`
2. Modify API endpoints in `backend/app/main.py`
3. Update frontend in `frontend/app.js`
4. Test with Docker Compose

### Knowledge Base Updates

1. Update `backend/app/data/knowledge_base.json`
2. Restart the backend service
3. Test with sample queries

## 🐛 Troubleshooting

### Common Issues

1. **API Connection Errors**: Check API key configuration
2. **Model Loading Issues**: Verify knowledge base file exists
3. **Frontend Not Loading**: Check nginx configuration
4. **Docker Build Failures**: Check Dockerfile and dependencies

### Logs

```bash
# View application logs
docker-compose logs -f backend

# View nginx logs
docker-compose logs -f frontend
```

## 📄 License

This project is proprietary software developed for VTB Bank.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📞 Support

For technical support or questions, please contact the development team.