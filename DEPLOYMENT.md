# 🚀 AI Support Assistant - Руководство по развертыванию

## 📋 **Обзор развертывания**

Это руководство предоставляет комплексные инструкции по развертыванию системы AI Support Assistant с использованием Docker контейнеров. Система поддерживает как разработку, так и продакшен окружения с опциональными сервисами мониторинга и кэширования.

---

## 🐳 **Docker конфигурация**

### **Архитектура контейнеров**
```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Stack                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │  Frontend   │  │  Backend    │  │   Redis     │            │
│  │  (Nginx)    │  │  (FastAPI)  │  │  (Cache)    │            │
│  │  Port: 3000 │  │  Port: 8000 │  │  Port: 6379 │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
├─────────────────────────────────────────────────────────────────┤
│  Optional Monitoring Stack                                      │
│  ┌─────────────┐  ┌─────────────┐                              │
│  │ Prometheus  │  │   Grafana   │                              │
│  │  Port: 9090 │  │  Port: 3001 │                              │
│  └─────────────┘  └─────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 **Быстрое развертывание**

### **Использование скрипта развертывания (Рекомендуется)**

```bash
# Сделать скрипт исполняемым
chmod +x deploy.sh

# Развернуть окружение разработки
./deploy.sh dev

# Развернуть продакшен окружение
./deploy.sh prod

# Развернуть с мониторингом
./deploy.sh monitoring

# Проверить здоровье
./deploy.sh health

# Просмотреть логи
./deploy.sh logs
```

### **Ручное развертывание через Docker Compose**

#### **Окружение разработки**
```bash
# Базовое развертывание
docker-compose up -d

# С кэшированием
docker-compose --profile cache up -d

# С мониторингом
docker-compose --profile monitoring up -d

# Полный стек
docker-compose --profile cache --profile monitoring up -d
```

#### **Продакшен окружение**
```bash
# Продакшен развертывание
docker-compose -f docker-compose.prod.yml up -d

# С SSL сертификатами
cp your-cert.pem ./ssl/cert.pem
cp your-key.pem ./ssl/key.pem
docker-compose -f docker-compose.prod.yml up -d
```

---

## ⚙️ **Конфигурация**

### **Переменные окружения**

Создайте файл `.env` на основе `env.example`:

```bash
# Окружение приложения
ENVIRONMENT=production
LOG_LEVEL=INFO

# Безопасность
ADMIN_API_KEY=your-secure-admin-key-here
CORS_ORIGINS=https://yourdomain.com

# Конфигурация API
API_TIMEOUT=30
MAX_REQUEST_SIZE=1048576

# Конфигурация модели
KNOWLEDGE_BASE_PATH=app/data/knowledge_base.json
MODEL_TIMEOUT=60
MAX_ERRORS=5
ENABLE_FALLBACK=true

# Мониторинг (опционально)
GRAFANA_PASSWORD=admin
GRAFANA_SECRET_KEY=your-grafana-secret-key
```

### **SSL сертификаты (Продакшен)**

Для продакшен развертывания разместите ваши SSL сертификаты в директории `ssl/`:

```bash
mkdir -p ssl
cp your-certificate.pem ssl/cert.pem
cp your-private-key.pem ssl/key.pem
```

---

## 🌐 **Точки доступа**

### **Окружение разработки**
| Сервис | URL | Описание |
|--------|-----|----------|
| Frontend | http://localhost:3000 | Пользовательский интерфейс |
| Backend API | http://localhost:8000 | REST API |
| Документация API | http://localhost:8000/docs | Интерактивная документация |
| Проверка здоровья | http://localhost:8000/health | Здоровье системы |
| Метрики | http://localhost:8000/metrics | Метрики производительности |

### **Продакшен окружение**
| Сервис | URL | Описание |
|--------|-----|----------|
| Frontend | https://yourdomain.com | Пользовательский интерфейс (HTTPS) |
| Backend API | https://yourdomain.com/api | REST API (HTTPS) |
| Документация API | https://yourdomain.com/api/docs | Интерактивная документация |
| Проверка здоровья | https://yourdomain.com/health | Здоровье системы |

### **Стек мониторинга**
| Сервис | URL | Учетные данные |
|--------|-----|----------------|
| Prometheus | http://localhost:9090 | Без аутентификации |
| Grafana | http://localhost:3001 | admin / (из GRAFANA_PASSWORD) |

---

## 📊 **Мониторинг и наблюдаемость**

### **Мониторинг здоровья**

```bash
# Проверить здоровье системы
curl http://localhost:8000/health

# Пример ответа:
{
  "status": "healthy",
  "timestamp": "2025-10-15T16:30:00.000Z",
  "metrics": {
    "requests_total": 150,
    "requests_success": 148,
    "requests_failed": 2,
    "success_rate": 98.67,
    "uptime_seconds": 3600
  }
}
```

### **Сбор метрик**

Система автоматически собирает метрики:
- Количество запросов и время ответа
- Частота и типы ошибок
- Время работы системы и производительность
- Время обработки модели

### **Grafana дашборды**

Доступ к Grafana по http://localhost:3001 для просмотра:
- Графики частоты запросов и времени ответа
- Мониторинг частоты ошибок
- Использование системных ресурсов
- Пользовательские бизнес-метрики

---

## 🔧 **Команды управления**

### **Управление контейнерами**

```bash
# Просмотр запущенных контейнеров
docker-compose ps

# Просмотр логов
docker-compose logs -f

# Перезапуск сервисов
docker-compose restart

# Остановка всех сервисов
docker-compose down

# Обновление и перезапуск
docker-compose pull
docker-compose up -d
```

### **Управление бекендом**

```bash
# Сброс счетчиков ошибок
curl -X POST http://localhost:8000/admin/reset-errors \
  -H "Authorization: Bearer your-admin-key"

# Сброс метрик
curl -X POST http://localhost:8000/admin/reset-metrics \
  -H "Authorization: Bearer your-admin-key"

# Получение статуса системы
curl http://localhost:8000/metrics
```

---

## 🔒 **Конфигурация безопасности**

### **Чеклист безопасности для продакшена**

- [ ] **Изменить стандартный ключ администратора**: Обновить `ADMIN_API_KEY` в `.env`
- [ ] **Настроить CORS**: Установить `CORS_ORIGINS` для вашего домена
- [ ] **SSL сертификаты**: Установить валидные SSL сертификаты
- [ ] **Правила фаервола**: Настроить соответствующие правила фаервола
- [ ] **Ограничение запросов**: Настроить лимиты для вашего трафика
- [ ] **Мониторинг**: Настроить алертинг для критических метрик
- [ ] **Стратегия бэкапов**: Реализовать регулярные бэкапы
- [ ] **Ротация логов**: Настроить политики ротации логов

### **Security Headers**

Система автоматически включает security headers:
```http
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'
```

---

## 📈 **Масштабирование и производительность**

### **Горизонтальное масштабирование**

```bash
# Масштабирование инстансов бекенда
docker-compose up -d --scale backend=3

# Использование балансировщика нагрузки
# Настроить nginx или внешний балансировщик нагрузки
```

### **Лимиты ресурсов**

Продакшен конфигурация включает лимиты ресурсов:
- **Backend**: 1GB RAM, 0.5 CPU
- **Frontend**: 256MB RAM, 0.25 CPU
- **Redis**: 512MB RAM, 0.25 CPU

### **Тюнинг производительности**

```bash
# Увеличить количество worker процессов
# Редактировать docker-compose.prod.yml
command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# Включить кэширование Redis
docker-compose --profile cache up -d
```

---

## 🛠️ **Решение проблем**

### **Распространенные проблемы**

#### **Контейнер не запускается**
```bash
# Проверить логи
docker-compose logs backend

# Проверить переменные окружения
docker-compose config

# Пересобрать контейнеры
docker-compose build --no-cache
```

#### **Проверка здоровья не проходит**
```bash
# Проверить логи бекенда
docker-compose logs backend

# Протестировать health endpoint напрямую
curl -v http://localhost:8000/health

# Проверить статус контейнеров
docker-compose ps
```

#### **Проблемы с SSL сертификатами**
```bash
# Проверить файлы сертификатов
ls -la ssl/

# Проверить валидность сертификата
openssl x509 -in ssl/cert.pem -text -noout

# Сгенерировать новый self-signed сертификат
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/key.pem -out ssl/cert.pem
```

### **Анализ логов**

```bash
# Просмотреть все логи
docker-compose logs

# Просмотреть логи конкретного сервиса
docker-compose logs backend
docker-compose logs frontend

# Следить за логами в реальном времени
docker-compose logs -f backend
```

---

## 🔄 **Бэкапы и восстановление**

### **Бэкап данных**

```bash
# Создать бэкап
./deploy.sh backup

# Ручной бэкап
mkdir -p backups/$(date +%Y%m%d)
cp -r logs backups/$(date +%Y%m%d)/
cp -r backend/app/data backups/$(date +%Y%m%d)/
```

### **Восстановление**

```bash
# Восстановить из бэкапа
cp -r backups/20251015/logs ./
cp -r backups/20251015/data backend/app/data/

# Перезапустить сервисы
docker-compose restart
```

---

## 📚 **Дополнительные ресурсы**

- [Документация архитектуры](ARCHITECTURE.md) - Детальная архитектура системы
- [Отчет безопасности](SECURITY_TEST_REPORT.md) - Результаты аудита безопасности
- [Документация API](http://localhost:8000/docs) - Интерактивная документация API
- [README](README.md) - Обзор проекта и быстрый старт

---

Это руководство по развертыванию обеспечивает плавное и безопасное развертывание вашей системы AI Support Assistant в любом окружении! 🚀