#!/bin/bash

# Support Assistant Launcher
# Frontend: frontend/ (index.html + app.js)
# Backend: backend/ (FastAPI)

echo "=== Support Assistant Launcher ==="

# Функция для проверки установки Python
check_python() {
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python3 не установлен. Пожалуйста, установите Python3."
        exit 1
    fi
    echo "✅ Python3 обнаружен"
}

# Функция для проверки портов
check_ports() {
    if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "❌ Порт 8000 уже используется"
        echo "   Попробуйте остановить процесс или изменить порт"
        exit 1
    fi
    
    if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "❌ Порт 3000 уже используется"
        echo "   Попробуйте остановить процесс или изменить порт"
        exit 1
    fi
    
    echo "✅ Порты 8000 и 3000 свободны"
}

# Функция для установки переменных окружения
setup_environment() {
    export PYTHONPATH="$PWD/backend"
    export ENVIRONMENT="development"
    export LOG_LEVEL="INFO"
    echo "✅ Переменные окружения настроены"
}

# Функция для запуска бекенда
start_backend() {
    echo "🚀 Запуск бекенда..."
    cd backend
    
    # Проверяем существование виртуального окружения
    if [ ! -d "venv" ]; then
        echo "📦 Создание виртуального окружения..."
        python3 -m venv venv
    fi
    
    # Активируем виртуальное окружение
    echo "🔧 Активация виртуального окружения..."
    if [ -f "venv/bin/activate" ]; then
        # Linux/Mac
        source venv/bin/activate
    else
        # Windows (в Git Bash)
        source venv/Scripts/activate
    fi
    
    # Устанавливаем зависимости
    echo "📚 Установка зависимостей..."
    pip install -r requirements.txt
    
    # Запускаем сервер
    echo "🌐 Запуск FastAPI сервера на http://localhost:8000"
    uvicorn app.main:app --reload --port 8000 &
    
    BACKEND_PID=$!
    cd ..
}

# Функция для запуска фронтенда
start_frontend() {
    echo "🖥️ Запуск фронтенда..."
    cd frontend
    
    # Ждем немного перед запуском фронтенда
    sleep 3
    
    echo "🌐 Запуск HTTP сервера для фронтенда на http://localhost:3000"
    echo "📂 Или откройте frontend/index.html напрямую в браузере"
    
    # Запускаем простой HTTP сервер
    python3 -m http.server 3000 --directory . &
    
    FRONTEND_PID=$!
    cd ..
}

# Функция для открытия в браузере
open_browser() {
    sleep 5
    echo "🔗 Открываю приложение в браузере..."
    
    if command -v xdg-open &> /dev/null; then
        # Linux
        xdg-open "http://localhost:3000"
    elif command -v open &> /dev/null; then
        # Mac
        open "http://localhost:3000"
    elif command -v start &> /dev/null; then
        # Windows
        start "http://localhost:3000"
    else
        echo "📍 Откройте вручную: http://localhost:3000"
    fi
}

# Основная функция
main() {
    check_python
    check_ports
    setup_environment
    
    # Запускаем бекенд
    start_backend
    
    # Запускаем фронтенд
    start_frontend
    
    # Открываем браузер
    open_browser &
    
    echo ""
    echo "✅ Приложение запущено!"
    echo "   Frontend: http://localhost:3000"
    echo "   Backend:  http://localhost:8000"
    echo "   Документация API: http://localhost:8000/docs"
    echo "   Health Check: http://localhost:8000/health"
    echo ""
    echo "⏹️  Для остановки нажмите Ctrl+C"
    
    # Обработка прерывания
    trap cleanup INT
    
    # Ждем завершения процессов
    wait
}

# Функция очистки при завершении
cleanup() {
    echo ""
    echo "🛑 Остановка приложения..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "✅ Приложение остановлено"
    exit 0
}

# Запуск основной функции
main