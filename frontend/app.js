class SupportAssistant {
    constructor() {
        this.analyzeBtn = document.getElementById('analyze');
        this.textArea = document.getElementById('text');
        this.loading = document.getElementById('loading');
        this.resultSection = document.getElementById('resultSection');
        
        // Переменные для хранения текущих данных
        this.currentText = '';
        this.currentCategory = '';
        this.currentResponse = '';
        this.currentConfidence = 0;
        
        this.analyzeBtn.addEventListener('click', () => this.analyzeText());
        
        // Инициализируем систему обратной связи
        FeedbackSystem.init();
        
        // Enter shortcut
        this.textArea.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                this.analyzeText();
            }
        });
    }

    async analyzeText() {
        const text = this.textArea.value.trim();
        
        if (!text) {
            this.showError('Пожалуйста, введите текст запроса');
            return;
        }

        this.setLoading(true);
        this.hideError();

        try {
            const response = await fetch('http://127.0.0.1:8000/analyze', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({ 
                    text: text
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            // Сохраняем текущие данные
            this.currentText = text;
            this.currentCategory = data.category;
            this.currentResponse = data.recommendation || data.response || '';
            this.currentConfidence = data.category_score || 0;
            
            // Показываем результаты
            this.showResultsSection();
            
            // Сохраняем в историю
            FeedbackSystem.sendFeedback('analyzed', 0);
            
            this.displayResults(data);
            
        } catch (error) {
            console.error('Analysis error:', error);
            this.showError(this.getErrorMessage(error));
        } finally {
            this.setLoading(false);
        }
    }

    showResultsSection() {
        this.resultSection.classList.remove('initially-hidden');
        this.resultSection.style.display = 'block';
        
        const operatorActions = document.querySelector('.operator-actions');
        if (operatorActions) {
            operatorActions.classList.remove('initially-hidden');
            operatorActions.style.display = 'flex';
        }
        
        const cards = this.resultSection.querySelectorAll('.card');
        cards.forEach((card, index) => {
            card.style.animationDelay = `${index * 0.1}s`;
        });
    }

    displayResults(data) {
        this.displayCategory(data.category, data.category_score);
        this.displayResponse(data.recommendation || data.response);
        this.showResults();
    }

    displayCategory(category, confidence) {
        const container = document.getElementById('categoryResult');
        
        if (!category) {
            container.innerHTML = '<p style="color: #6c757d;">Категория не определена</p>';
            return;
        }

        const confidencePercent = Math.round((confidence || 0) * 100);
        
        container.innerHTML = `
            <div class="category-badge">${this.escapeHtml(category)}</div>
            <div class="confidence">Уверенность: ${confidencePercent}%</div>
        `;
    }

    displayResponse(response) {
        const container = document.getElementById('responseResult');
        
        if (!response) {
            container.innerHTML = '<p style="color: #6c757d;">Ответ не сгенерирован</p>';
            return;
        }

        // Правильно обрабатываем текст без экранирующих символов
        const cleanResponse = this.cleanText(response);
        
        container.innerHTML = `
            <div class="response-content">${cleanResponse}</div>
            <button onclick="copyToClipboard('${this.escapeForJavascript(cleanResponse)}')" 
                    class="copy-btn" title="Копировать ответ">
                📋 Копировать ответ
            </button>
        `;
    }

    // Методы для очистки текста
    cleanText(text) {
        if (!text) return '';
        
        // Убираем экранирующие символы и лишние пробелы
        let cleaned = text
            .replace(/\\n/g, '\n')           // Заменяем \n на настоящие переносы
            .replace(/\\t/g, '  ')           // Заменяем \t на пробелы
            .replace(/\\"/g, '"')            // Убираем экранирование кавычек
            .replace(/\\'/g, "'")            // Убираем экранирование апострофов
            .replace(/\\\\/g, '\\')          // Убираем двойные слеши
            .replace(/\s+/g, ' ')            // Убираем лишние пробелы
            .trim();
        
        // Форматируем абзацы
        cleaned = cleaned.replace(/\n\s*\n/g, '\n\n'); // Нормализуем переносы строк
        
        return cleaned;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    escapeForJavascript(text) {
        return text
            .replace(/\\/g, '\\\\')
            .replace(/'/g, "\\'")
            .replace(/"/g, '\\"')
            .replace(/\n/g, '\\n')
            .replace(/\r/g, '\\r')
            .replace(/\t/g, '\\t');
    }

    setLoading(loading) {
        this.analyzeBtn.disabled = loading;
        this.loading.style.display = loading ? 'block' : 'none';
        
        if (loading) {
            this.analyzeBtn.innerHTML = '⏳ Анализ...';
        } else {
            this.analyzeBtn.innerHTML = '🔍 Проанализировать запрос';
        }
    }

    showResults() {
        this.resultSection.scrollIntoView({ behavior: 'smooth' });
    }

    showError(message) {
        this.hideError();
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.innerHTML = `<strong>Ошибка:</strong> ${this.escapeHtml(message)}`;
        
        const inputSection = document.querySelector('.input-section');
        inputSection.appendChild(errorDiv);
    }

    hideError() {
        const existingError = document.querySelector('.error-message');
        if (existingError) {
            existingError.remove();
        }
    }

    getErrorMessage(error) {
        if (error.message.includes('Failed to fetch')) {
            return 'Не удалось подключиться к серверу. Убедитесь, что бэкенд запущен на порту 8000.';
        }
        return error.message || 'Произошла неизвестная ошибка';
    }
}

// Система обратной связи
class FeedbackSystem {
    static init() {
        // Создаем кнопки оператора в результатах
        const resultSection = document.getElementById('resultSection');
        if (resultSection && !document.querySelector('.operator-actions')) {
            resultSection.innerHTML += `
                <div class="operator-actions">
                    <button onclick="FeedbackSystem.markResolved()" class="btn btn-success">✅ Решено</button>
                    <button onclick="FeedbackSystem.needCorrection()" class="btn btn-warning">✏️ Требует правок</button>
                </div>
            `;
        }
    }

    static async markResolved() {
        // Обновляем статус в истории
        const updated = await this.updateTicketStatus('resolved', 5);
        if (updated) {
            this.showNotification('✅ Отмечено как решенное');
            if (document.getElementById('historyTab')?.classList.contains('active')) {
                loadHistory();
            }
        }
    }

    static async needCorrection() {
        const correctedCategory = prompt('Введите правильную категорию (или оставьте пустым):', assistant.currentCategory);
        const updated = await this.updateTicketStatus('needs_correction', 3, correctedCategory || null);
        if (updated) {
            this.showNotification('📝 Отмечено как требующее правок');
            if (document.getElementById('historyTab')?.classList.contains('active')) {
                loadHistory();
            }
        }
    }

    static async updateTicketStatus(status, rating, correctedCategory = null, notes = '') {
        if (!assistant.currentText) {
            alert('Нет данных для обновления');
            return false;
        }

        const ticketData = {
            original_text: assistant.currentText,
            predicted_category: assistant.currentCategory,
            system_response: assistant.currentResponse,
            confidence: assistant.currentConfidence,
            status: status,
            operator_rating: rating,
            operator_notes: notes,
            corrected_category: correctedCategory
        };

        const updatedTicket = TicketManager.saveOrUpdateTicket(ticketData);
        return !!updatedTicket;
    }

    static async sendFeedback(status, rating, correctedCategory = null, notes = '') {
    console.log('=== SEND FEEDBACK ===');
    console.log('Статус:', status);
    console.log('Текущий текст:', assistant.currentText);
    
    const ticketData = {
        original_text: assistant.currentText,
        predicted_category: assistant.currentCategory,
        system_response: assistant.currentResponse,
        confidence: assistant.currentConfidence,
        status: status,
        operator_rating: rating,
        operator_notes: notes,
        corrected_category: correctedCategory
    };

    const ticket = TicketManager.saveOrUpdateTicket(ticketData);
    this.showNotification('✅ Статус заявки обновлен');
    
    // Логируем результат
    console.log('Результат обновления:', ticket.id, ticket.status);
}

    static showNotification(message) {
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #28a745;
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 1000;
            font-weight: 500;
        `;
        notification.textContent = message;
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
}

// Система управления историей заявок
class TicketManager {
    static STORAGE_KEY = 'support_tickets';
    static COUNTER_KEY = 'ticket_counter';
    
    // Получаем следующий порядковый номер
    static getNextTicketNumber() {
        let counter = parseInt(localStorage.getItem(this.COUNTER_KEY) || '0');
        counter++;
        localStorage.setItem(this.COUNTER_KEY, counter.toString());
        return counter;
    }
    
    // Находим существующую заявку по тексту (более точный поиск)
    static findExistingTicket(ticketData) {
        const tickets = this.getAllTickets();
        
        // Ищем заявку с таким же текстом И статусом 'analyzed'
        return tickets.find(ticket => 
            ticket.original_text === ticketData.original_text && 
            ticket.status === 'analyzed'
        );
    }
    
    static saveOrUpdateTicket(ticketData) {
        const tickets = this.getAllTickets();
        const existingTicket = this.findExistingTicket(ticketData);
        
        console.log('=== SAVE/UPDATE TICKET ===');
        console.log('Текст запроса:', ticketData.original_text.substring(0, 50) + '...');
        console.log('Найдена существующая заявка:', !!existingTicket);
        
        if (existingTicket) {
            console.log('ОБНОВЛЯЕМ заявку ID:', existingTicket.id);
            // ОБНОВЛЯЕМ существующую заявку
            const ticketIndex = tickets.findIndex(t => t.id === existingTicket.id);
            tickets[ticketIndex] = {
                ...existingTicket, // сохраняем старый ID и номер
                status: ticketData.status,
                operator_rating: ticketData.operator_rating,
                operator_notes: ticketData.operator_notes || '',
                corrected_category: ticketData.corrected_category || null,
                timestamp: new Date().toISOString() // обновляем время
            };
            
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(tickets));
            console.log('Заявка обновлена');
            return tickets[ticketIndex];
        } else {
            console.log('СОЗДАЕМ новую заявку');
            // СОЗДАЕМ новую заявку
            const ticketNumber = this.getNextTicketNumber();
            const ticketId = `T${ticketNumber.toString().padStart(4, '0')}`;
            
            const ticket = {
                id: ticketId,
                number: ticketNumber,
                timestamp: new Date().toISOString(),
                original_text: ticketData.original_text,
                predicted_category: ticketData.predicted_category,
                system_response: ticketData.system_response,
                confidence: ticketData.confidence,
                status: ticketData.status || 'analyzed',
                operator_rating: ticketData.operator_rating || 0,
                operator_notes: ticketData.operator_notes || '',
                corrected_category: ticketData.corrected_category || null
            };
            
            tickets.unshift(ticket);
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(tickets));
            console.log('Новая заявка создана ID:', ticketId);
            return ticket;
        }
    }
    
    static getAllTickets() {
        const tickets = JSON.parse(localStorage.getItem(this.STORAGE_KEY) || '[]');
        // Сортируем по номеру в обратном порядке (новые сверху)
        return tickets.sort((a, b) => b.number - a.number);
    }
    
    static searchTickets(query) {
        const tickets = this.getAllTickets();
        if (!query) return tickets;
        
        const lowerQuery = query.toLowerCase();
        return tickets.filter(ticket => 
            ticket.predicted_category.toLowerCase().includes(lowerQuery) ||
            ticket.original_text.toLowerCase().includes(lowerQuery) ||
            ticket.id.toLowerCase().includes(lowerQuery)
        );
    }

    // Получить статистику
    static getStats() {
        const tickets = this.getAllTickets();
        return {
            total: tickets.length,
            resolved: tickets.filter(t => t.status === 'resolved').length,
            needs_correction: tickets.filter(t => t.status === 'needs_correction').length,
            lastNumber: parseInt(localStorage.getItem(this.COUNTER_KEY) || '0')
        };
    }
}

// Функция копирования в буфер обмена
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        const originalText = event.target.textContent;
        event.target.textContent = '✅ Скопировано!';
        event.target.style.background = '#28a745';
        
        setTimeout(() => {
            event.target.textContent = originalText;
            event.target.style.background = '';
        }, 2000);
    }).catch(err => {
        console.error('Copy failed:', err);
        alert('Не удалось скопировать текст');
    });
}

// Функции для работы с вкладками и историей
function showTab(tabName) {
    // Скрываем все вкладки
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Показываем выбранную вкладку
    document.getElementById(tabName + 'Tab').classList.add('active');
    event.target.classList.add('active');
    
    // Если открыли историю - загружаем данные
    if (tabName === 'history') {
        loadHistory();
    }
}

function loadHistory(searchQuery = '') {
    const historyList = document.getElementById('historyList');
    const historyHeader = document.querySelector('.history-header h2');
    
    // Явно проверяем наличие данных в localStorage
    const ticketsData = localStorage.getItem('support_tickets');
    const tickets = ticketsData ? JSON.parse(ticketsData) : [];
    
    console.log('loadHistory - tickets:', tickets.length);
    
    if (!ticketsData || tickets.length === 0) {
        // Явно показываем пустое состояние
        historyList.innerHTML = `
            <div style="text-align: center; padding: 40px; color: #6c757d;">
                <p>📭 История обращений пуста</p>
                <p style="margin-top: 10px;">Следующая заявка получит номер <strong>T0001</strong></p>
                <p style="margin-top: 5px; font-size: 0.9em;">Проанализируйте запрос чтобы начать новую историю</p>
            </div>
        `;
        
        // Обновляем заголовок
        if (historyHeader) {
            historyHeader.innerHTML = `📊 История обращений <small style="font-size: 0.6em; color: #666;">(Всего: 0, Решено: 0)</small>`;
        }
        return;
    }
    
    // Если есть заявки - фильтруем по поисковому запросу
    const filteredTickets = searchQuery ? 
        tickets.filter(ticket => 
            ticket.predicted_category.toLowerCase().includes(searchQuery.toLowerCase()) ||
            ticket.original_text.toLowerCase().includes(searchQuery.toLowerCase()) ||
            (ticket.id && ticket.id.toLowerCase().includes(searchQuery.toLowerCase()))
        ) : tickets;
    
    const stats = {
        total: tickets.length,
        resolved: tickets.filter(t => t.status === 'resolved').length
    };
    
    // Обновляем заголовок
    if (historyHeader) {
        historyHeader.innerHTML = `📊 История обращений <small style="font-size: 0.6em; color: #666;">(Всего: ${stats.total}, Решено: ${stats.resolved})</small>`;
    }
    
    // Показываем заявки
    historyList.innerHTML = filteredTickets.map(ticket => `
        <div class="ticket-item">
            <div class="ticket-header">
                <div class="ticket-customer">
                    Запрос ${ticket.id}
                </div>
                <div class="ticket-meta">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span class="ticket-category">${escapeHtml(ticket.predicted_category)}</span>
                        ${ticket.status !== 'analyzed' ? `
                        <span class="feedback-status status-${ticket.status}">
                            ${ticket.status === 'resolved' ? '✅ Решено' :
                              ticket.status === 'needs_correction' ? '✏️ Требует правок' :
                              '📊 Анализ'}
                        </span>
                        ` : ''}
                    </div>
                    <span>${new Date(ticket.timestamp).toLocaleString()}</span>
                </div>
            </div>
            
            <div class="ticket-content">
                <div class="ticket-text">
                    <strong>Запрос:</strong> ${escapeHtml(ticket.original_text)}
                </div>
                ${ticket.system_response ? `
                <div class="ticket-response">
                    <strong>Ответ:</strong> ${cleanText(ticket.system_response)}
                </div>
                ` : ''}
                ${ticket.confidence ? `<div style="margin-top: 10px;"><strong>Уверенность:</strong> ${Math.round(ticket.confidence * 100)}%</div>` : ''}
            </div>
            
            ${ticket.corrected_category ? `
            <div class="ticket-feedback">
                <span><strong>Исправленная категория:</strong> ${escapeHtml(ticket.corrected_category)}</span>
                ${ticket.operator_rating ? `<span><strong>Оценка:</strong> ${'⭐'.repeat(ticket.operator_rating)}</span>` : ''}
            </div>
            ` : ''}
        </div>
    `).join('');
}

// Вспомогательные функции для HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function cleanText(text) {
    if (!text) return '';
    
    let cleaned = text
        .replace(/\\n/g, '\n')
        .replace(/\\t/g, '  ')
        .replace(/\\"/g, '"')
        .replace(/\\'/g, "'")
        .replace(/\\\\/g, '\\')
        .replace(/\s+/g, ' ')
        .trim();
    
    cleaned = cleaned.replace(/\n\s*\n/g, '\n\n');
    return cleaned;
}

// Поиск в истории
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchHistory');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            loadHistory(this.value);
        });
    }
});

// Экспорт истории
function exportAllTickets() {
    const tickets = TicketManager.getAllTickets();
    if (tickets.length === 0) {
        alert('Нет данных для экспорта');
        return;
    }
    
    const dataStr = JSON.stringify(tickets, null, 2);
    const dataBlob = new Blob([dataStr], {type: 'application/json'});
    
    const link = document.createElement('a');
    link.href = URL.createObjectURL(dataBlob);
    link.download = `support_tickets_${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    
    alert(`Экспортировано ${tickets.length} заявок`);
}

// Очистка истории
function clearHistory() {
    if (confirm('Вы уверены что хотите очистить всю историю заявок? Счетчик номеров будет сброшен.')) {
        // Удаляем и заявки, и счетчик
        localStorage.removeItem('support_tickets');
        localStorage.removeItem('ticket_counter');
        
        // Принудительно обновляем интерфейс
        updateHistoryDisplay();
        
        // Показываем подтверждение
        FeedbackSystem.showNotification('✅ История очищена, счетчик сброшен');
    }
}

// Новая функция для обновления отображения истории
function updateHistoryDisplay() {
    const historyList = document.getElementById('historyList');
    const historyHeader = document.querySelector('.history-header h2');
    
    // Принудительно устанавливаем пустое состояние
    historyList.innerHTML = `
        <div style="text-align: center; padding: 40px; color: #6c757d;">
            <p>📭 История обращений пуста</p>
            <p style="margin-top: 10px;">Следующая заявка получит номер <strong>T0001</strong></p>
            <p style="margin-top: 5px; font-size: 0.9em;">Проанализируйте запрос чтобы начать новую историю</p>
        </div>
    `;
    
    // Обновляем заголовок
    if (historyHeader) {
        historyHeader.innerHTML = `📊 История обращений <small style="font-size: 0.6em; color: #666;">(Всего: 0, Решено: 0)</small>`;
    }
    
    console.log('История очищена - проверяем localStorage:');
    console.log('support_tickets:', localStorage.getItem('support_tickets'));
    console.log('ticket_counter:', localStorage.getItem('ticket_counter'));
}

// Функция для отладки - покажет все заявки в консоли
function debugTickets() {
    const tickets = TicketManager.getAllTickets();
    console.log('=== ДЕБАГ ЗАЯВОК ===');
    console.log('Счетчик:', localStorage.getItem('ticket_counter'));
    tickets.forEach(ticket => {
        console.log(`ID: ${ticket.id}, Номер: ${ticket.number}, Текст: "${ticket.original_text.substring(0, 30)}..."`);
    });
    console.log('====================');
}

// Вызови debugTickets() в консоли браузера чтобы посмотреть что хранится

// Глобальная переменная для доступа к ассистенту
let assistant;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    assistant = new SupportAssistant();
});