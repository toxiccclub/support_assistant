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
        this.isAnalyzing = false; // Флаг для предотвращения множественных запросов
        
        this.analyzeBtn.addEventListener('click', () => this.analyzeText());
        
        // Enter shortcut
        this.textArea.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                this.analyzeText();
            }
        });
    }

    async analyzeText() {
    // Защита от множественных кликов
    if (this.isAnalyzing) {
        return;
    }
    
    const text = this.textArea.value.trim();
    
    if (!text) {
        this.showError('Пожалуйста, введите текст запроса');
        return;
    }

    // СБРАСЫВАЕМ предыдущие результаты перед новым анализом
    this.resetToInitialState();
    
    this.isAnalyzing = true;
    this.setLoading(true);
    this.hideError();

    try {
        console.log('Отправка запроса на анализ:', text.substring(0, 50) + '...');
        
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
        console.log('Получен ответ от сервера:', data);
        
        // Сохраняем текущие данные
        this.currentText = text;
        this.currentCategory = data.category;
        this.currentResponse = data.recommendation || data.response || '';
        this.currentConfidence = data.category_score || 0;
        
        // Показываем результаты
        this.showResultsSection();
        
        // Сохраняем в историю ТОЛЬКО если это новый анализ
        if (!this.hasExistingTicket(text)) {
            FeedbackSystem.sendFeedback('analyzed', 0);
        }
        
        this.displayResults(data);
        
    } catch (error) {
        console.error('Analysis error:', error);
        this.showError(this.getErrorMessage(error));
    } finally {
        this.setLoading(false);
        this.isAnalyzing = false;
    }
}

    // Проверяем есть ли уже заявка с таким текстом
    hasExistingTicket(text) {
        const tickets = TicketManager.getAllTickets();
        return tickets.some(ticket => ticket.original_text === text);
    }

    showResultsSection() {
        this.resultSection.style.display = 'block';
        
        const operatorActions = document.querySelector('.operator-actions');
        if (operatorActions) {
            operatorActions.style.display = 'flex';
        }
        
        const cards = this.resultSection.querySelectorAll('.card');
        cards.forEach((card, index) => {
            card.style.animationDelay = `${index * 0.1}s`;
        });
    }

    // Сброс интерфейса в начальное состояние
    // Сброс интерфейса в начальное состояние
resetToInitialState() {
    // Очищаем текстовое поле (НЕ очищаем, чтобы пользователь мог редактировать запрос)
    // this.textArea.value = ''; // УБИРАЕМ эту строку
    
    // Скрываем результаты
    this.resultSection.style.display = 'none';
    
    // Очищаем содержимое карточек результатов
    document.getElementById('categoryResult').innerHTML = '';
    document.getElementById('responseResult').innerHTML = '';
    
    // Сбрасываем текущие данные
    this.currentText = '';
    this.currentCategory = '';
    this.currentResponse = '';
    this.currentConfidence = 0;
    
    // Убираем блокировку
    const lockedNote = document.getElementById('ticketLockedNote');
    if (lockedNote) lockedNote.remove();
    
    // Показываем кнопки оператора
    const operatorActions = document.querySelector('.operator-actions');
    if (operatorActions) operatorActions.style.display = 'flex';
    
    // Показываем кнопку анализа
    this.analyzeBtn.style.display = 'block';
    
    // Разблокируем текстовое поле
    this.textArea.disabled = false;
    this.textArea.style.background = '';
    this.textArea.style.cursor = '';
    this.textArea.placeholder = 'Например: Не удаётся войти в мобильное приложение ВТБ...';
    
    // Фокус на текстовое поле (но НЕ очищаем его)
    this.textArea.focus();
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
            <div style="margin-top: 8px; color: #6c757d; font-size: 0.9em;">Уверенность: ${confidencePercent}%</div>
        `;
    }

 displayResponse(response) {
    const container = document.getElementById('responseResult');
    
    if (!response) {
        container.innerHTML = '<p style="color: #6c757d;">Ответ не сгенерирован</p>';
        return;
    }

    const cleanResponse = this.cleanText(response);
    
    // ВОЗВРАЩАЕМ кнопку копирования
    container.innerHTML = `
        <div class="response-content">${cleanResponse}</div>
        <button id="copyResponseBtn" class="copy-btn" title="Копировать ответ" style="margin-top: 10px;">
            📋 Копировать ответ
        </button>
    `;
    
    // Добавляем обработчик события
    const copyBtn = document.getElementById('copyResponseBtn');
    copyBtn.addEventListener('click', () => {
        this.copyToClipboard(cleanResponse, copyBtn);
    });
}

// Функция для копирования (должна быть в классе)
copyToClipboard(text, buttonElement) {
    navigator.clipboard.writeText(text).then(() => {
        const originalText = buttonElement.textContent;
        buttonElement.textContent = '✅ Скопировано!';
        buttonElement.style.background = '#28a745';
        
        setTimeout(() => {
            buttonElement.textContent = originalText;
            buttonElement.style.background = '';
        }, 2000);
    }).catch(err => {
        console.error('Copy failed:', err);
        
        // Fallback для старых браузеров
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            buttonElement.textContent = '✅ Скопировано!';
            buttonElement.style.background = '#28a745';
            setTimeout(() => {
                buttonElement.textContent = '📋 Копировать ответ';
                buttonElement.style.background = '';
            }, 2000);
        } catch (fallbackErr) {
            console.error('Fallback copy failed:', fallbackErr);
            alert('Не удалось скопировать текст. Скопируйте вручную.');
        }
        document.body.removeChild(textArea);
    });
}

    cleanText(text) {
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

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    setLoading(loading) {
        this.analyzeBtn.disabled = loading;
        this.loading.style.display = loading ? 'block' : 'none';
        
        if (loading) {
            this.analyzeBtn.innerHTML = '⏳ Анализ...';
        } else {
            this.analyzeBtn.innerHTML = '🔍 Проанализировать';
        }
    }

    showResults() {
        this.resultSection.scrollIntoView({ behavior: 'smooth' });
    }

    showError(message) {
        this.hideError();
        
        const errorDiv = document.createElement('div');
        errorDiv.style.cssText = `
            background: #ffebee;
            color: #c62828;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #f44336;
            margin-top: 15px;
        `;
        errorDiv.innerHTML = `<strong>Ошибка:</strong> ${this.escapeHtml(message)}`;
        
        const inputSection = document.querySelector('.input-section');
        inputSection.appendChild(errorDiv);
    }

    hideError() {
        const errorDivs = document.querySelectorAll('.error-message, [style*="background: #ffebee"]');
        errorDivs.forEach(div => div.remove());
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
        // Кнопки уже есть в HTML
    }

    static async markResolved() {
        const updated = await this.updateTicketStatus('resolved', 0);
        if (updated) {
            this.showNotification('✅ Отмечено как решенное');
            if (document.getElementById('historyTab')?.classList.contains('active')) {
                loadHistory();
            }
            // СРАЗУ возвращаем в начальное состояние
            assistant.resetToInitialState();
        }
    }

    static async needCorrection() {
        // Создаем модальное окно для редактирования
        const modalHtml = `
            <div id="correctionModal" style="
                position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
                background: rgba(0,0,0,0.5); display: flex; justify-content: center; 
                align-items: center; z-index: 10000; font-family: 'Segoe UI', Tahoma, sans-serif;
            ">
                <div style="
                    background: white; padding: 30px; border-radius: 12px; 
                    width: 90%; max-width: 700px; max-height: 80vh; overflow-y: auto;
                    border: 1px solid #dce3ed; box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                ">
                    <h3 style="margin-bottom: 20px; color: #1e2a3a; display: flex; align-items: center; gap: 10px;">
                        ✏️ Исправление заявки
                    </h3>
                    
                    <div style="margin-bottom: 20px;">
                        <label style="display: block; margin-bottom: 8px; font-weight: 600; color: #1e2a3a;">
                            Правильная категория:
                        </label>
                        <input type="text" id="correctedCategory" 
                               value="${assistant.currentCategory}" 
                               style="width: 100%; padding: 12px; border: 1px solid #cfd8e3; 
                                      border-radius: 6px; font-size: 14px; transition: 0.2s;"
                               onfocus="this.style.borderColor='#003da6'; this.style.boxShadow='0 0 0 3px rgba(0, 61, 166, 0.1)'"
                               onblur="this.style.borderColor='#cfd8e3'; this.style.boxShadow='none'">
                    </div>
                    
                    <div style="margin-bottom: 25px;">
                        <label style="display: block; margin-bottom: 8px; font-weight: 600; color: #1e2a3a;">
                            Текст ответа (можно редактировать):
                        </label>
                        <textarea id="correctedResponse" 
                                  style="width: 100%; min-height: 200px; padding: 15px; 
                                         border: 1px solid #cfd8e3; border-radius: 6px; 
                                         font-family: inherit; resize: vertical; font-size: 14px;
                                         transition: 0.2s; line-height: 1.5;"
                                  onfocus="this.style.borderColor='#003da6'; this.style.boxShadow='0 0 0 3px rgba(0, 61, 166, 0.1)'"
                                  onblur="this.style.borderColor='#cfd8e3'; this.style.boxShadow='none'">${assistant.currentResponse}</textarea>
                    </div>
                    
                    <div style="display: flex; gap: 12px; justify-content: flex-end;">
                        <button onclick="FeedbackSystem.closeCorrectionModal()" 
                                style="padding: 10px 20px; border: 1px solid #6c757d; 
                                       background: white; border-radius: 6px; cursor: pointer;
                                       color: #6c757d; font-weight: 500; transition: 0.2s;"
                                onmouseover="this.style.backgroundColor='#f8f9fa'"
                                onmouseout="this.style.backgroundColor='white'">
                            Отмена
                        </button>
                        <button onclick="FeedbackSystem.saveCorrection()" 
                                style="padding: 10px 24px; background: #28a745; color: white; 
                                       border: none; border-radius: 6px; cursor: pointer;
                                       font-weight: 500; transition: 0.2s;"
                                onmouseover="this.style.backgroundColor='#218838'"
                                onmouseout="this.style.backgroundColor='#28a745'">
                            ✅ Сохранить исправления
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }

    static closeCorrectionModal() {
        const modal = document.getElementById('correctionModal');
        if (modal) {
            modal.remove();
        }
    }

    static async saveCorrection() {
    const correctedCategory = document.getElementById('correctedCategory').value;
    const correctedResponse = document.getElementById('correctedResponse').value;
    
    const originalCategory = assistant.currentCategory;
    const originalResponse = assistant.currentResponse;
    
    // Сохраняем оригинальный ответ перед обновлением
    const originalResponseForHistory = originalResponse;
    
    // Обновляем текущий ответ в ассистенте
    assistant.currentResponse = correctedResponse;
    
    // Определяем, что было изменено
    const isCategoryChanged = correctedCategory && correctedCategory !== originalCategory;
    const isResponseChanged = correctedResponse !== originalResponse;
    
    let notificationMessage = '📝 Заявка сохранена';
    
    if (isCategoryChanged && isResponseChanged) {
        notificationMessage = '📝 Категория и ответ исправлены';
    } else if (isCategoryChanged) {
        notificationMessage = '📝 Категория исправлена';
    } else if (isResponseChanged) {
        notificationMessage = '📝 Ответ исправлен';
    } else {
        notificationMessage = '✅ Заявка сохранена (без изменений)';
    }
    
    const updated = await this.updateTicketStatus(
        'needs_correction', 
        0, 
        isCategoryChanged ? correctedCategory : null,
        '', 
        originalCategory,
        isResponseChanged ? originalResponseForHistory : null // Передаем оригинальный ответ если он изменился
    );
    
    if (updated) {
        this.closeCorrectionModal();
        this.showNotification(notificationMessage);
        if (document.getElementById('historyTab')?.classList.contains('active')) {
            loadHistory();
        }
        // СРАЗУ возвращаем в начальное состояние
        assistant.resetToInitialState();
    }
}

    static async updateTicketStatus(status, rating, correctedCategory = null, notes = '', originalCategory = null, originalResponse = null) {
    if (!assistant.currentText) {
        alert('Нет данных для обновления');
        return false;
    }
    
    const predictedCategory = originalCategory || assistant.currentCategory;
    
    const ticketData = {
        original_text: assistant.currentText,
        predicted_category: predictedCategory,
        system_response: assistant.currentResponse,
        confidence: assistant.currentConfidence,
        status: status,
        operator_rating: 0,
        operator_notes: notes,
        corrected_category: correctedCategory,
        original_response: originalResponse // Сохраняем оригинальный ответ
    };
    
    const updatedTicket = TicketManager.saveOrUpdateTicket(ticketData);
    return !!updatedTicket;
}

    static async sendFeedback(status, rating, correctedCategory = null, notes = '') {
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
        console.log('Заявка сохранена:', ticket.id, ticket.status);
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
    
    static getNextTicketNumber() {
        let counter = parseInt(localStorage.getItem(this.COUNTER_KEY) || '0');
        counter++;
        localStorage.setItem(this.COUNTER_KEY, counter.toString());
        return counter;
    }
    
    static findExistingTicket(ticketData) {
        const tickets = this.getAllTickets();
        return tickets.find(ticket => 
            ticket.original_text === ticketData.original_text && 
            ticket.status === 'analyzed'
        );
    }
    
    static saveOrUpdateTicket(ticketData) {
    const tickets = this.getAllTickets();
    const existingTicket = this.findExistingTicket(ticketData);
    
    if (existingTicket) {
        console.log('Обновляем существующую заявку:', existingTicket.id);
        const ticketIndex = tickets.findIndex(t => t.id === existingTicket.id);
        
        tickets[ticketIndex] = {
            ...existingTicket,
            predicted_category: ticketData.predicted_category,
            system_response: ticketData.system_response,
            status: ticketData.status,
            operator_rating: ticketData.operator_rating,
            operator_notes: ticketData.operator_notes || '',
            corrected_category: ticketData.corrected_category || null,
            // Сохраняем оригинальный ответ если он передан
            original_response: ticketData.original_response || existingTicket.original_response,
            timestamp: new Date().toISOString()
        };
        
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(tickets));
        return tickets[ticketIndex];
    } else {
        console.log('Создаем новую заявку');
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
            corrected_category: ticketData.corrected_category || null,
            original_response: ticketData.original_response || null // Сохраняем оригинальный ответ
        };
        
        tickets.unshift(ticket);
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(tickets));
        return ticket;
    }
}
    
    static getAllTickets() {
        const tickets = JSON.parse(localStorage.getItem(this.STORAGE_KEY) || '[]');
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

// Функции для работы с вкладками и истории
function showTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    document.getElementById(tabName + 'Tab').classList.add('active');
    event.target.classList.add('active');
    
    if (tabName === 'history') {
        loadHistory();
    }
}

function loadHistory(searchQuery = '') {
    const historyList = document.getElementById('historyList');
    const historyHeader = document.querySelector('.history-header h2');
    
    const ticketsData = localStorage.getItem('support_tickets');
    const tickets = ticketsData ? JSON.parse(ticketsData) : [];
    
    if (!ticketsData || tickets.length === 0) {
        historyList.innerHTML = `
            <div style="text-align: center; padding: 40px; color: #6c757d;">
                <p>📭 История обращений пуста</p>
                <p style="margin-top: 10px;">Следующая заявка получит номер <strong>T0001</strong></p>
            </div>
        `;
        
        if (historyHeader) {
            historyHeader.innerHTML = `📋 История обращений <small style="font-size: 0.6em; color: #666;">(Всего: 0, Решено: 0, Исправлено: 0)</small>`;
        }
        return;
    }
    
    const filteredTickets = searchQuery ? 
        tickets.filter(ticket => 
            ticket.predicted_category.toLowerCase().includes(searchQuery.toLowerCase()) ||
            ticket.original_text.toLowerCase().includes(searchQuery.toLowerCase()) ||
            (ticket.id && ticket.id.toLowerCase().includes(searchQuery.toLowerCase()))
        ) : tickets;
    
    const stats = {
        total: tickets.length,
        resolved: tickets.filter(t => t.status === 'resolved').length,
        needs_correction: tickets.filter(t => t.status === 'needs_correction').length
    };
    
    if (historyHeader) {
        historyHeader.innerHTML = `📋 История обращений <small style="font-size: 0.6em; color: #666;">(Всего: ${stats.total}, Решено: ${stats.resolved}, Исправлено: ${stats.needs_correction})</small>`;
    }
    
    historyList.innerHTML = filteredTickets.map(ticket => {
    const displayCategory = ticket.corrected_category || ticket.predicted_category;
    const isCorrected = ticket.status === 'needs_correction';
    
    return `
    <div class="ticket-item" 
         style="${isCorrected ? 'border-left: 4px solid #ffc107;' : ''}; cursor: pointer;" 
         onclick="ModalSystem.showTicketDetails(${JSON.stringify(ticket).replace(/"/g, '&quot;')})">
        <div class="ticket-header">
            <div class="ticket-customer">
                ${isCorrected ? '<span style="margin-right: 6px; color: #ffc107; font-size: 0.9em;">✏️</span>' : ''}
                Запрос ${ticket.id}
            </div>
            <div class="ticket-meta">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span class="ticket-category" style="${ticket.corrected_category ? 'background: #28a745;' : ''}">
                        ${escapeHtml(displayCategory)}
                    </span>
                    ${ticket.status !== 'analyzed' ? `
                    <span class="status-${ticket.status}">
                        ${ticket.status === 'resolved' ? '✅ Решено' :
                          ticket.status === 'needs_correction' ? '✏️ Исправлено' :
                          '📊 Анализ'}
                    </span>
                    ` : ''}
                </div>
                <span>${new Date(ticket.timestamp).toLocaleString()}</span>
            </div>
        </div>
        
        <div class="ticket-content">
            <div style="background: #f8f9fa; padding: 12px; border-radius: 6px; margin-bottom: 10px;">
                <strong>Запрос:</strong> ${escapeHtml(ticket.original_text.substring(0, 100))}${ticket.original_text.length > 100 ? '...' : ''}
            </div>
            ${ticket.system_response ? `
            <div class="ticket-response" style="${ticket.original_response ? 'border-left-color: #007bff;' : ''}">
                <strong>Ответ:</strong> ${cleanText(ticket.system_response.substring(0, 150))}${ticket.system_response.length > 150 ? '...' : ''}
            </div>
            ` : ''}
            ${ticket.confidence ? `<div style="margin-top: 8px;"><strong>Уверенность:</strong> ${Math.round(ticket.confidence * 100)}%</div>` : ''}
            
            ${isCorrected ? `
            <div style="margin-top: 10px; color: #6c757d; font-size: 0.9em;">
                🔍 Нажмите для просмотра деталей исправлений
            </div>
            ` : ''}
        </div>
    </div>
    `;
}).join('');
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


// Очистка истории
function clearHistory() {
    ModalSystem.showClearHistoryModal();
}

function updateHistoryDisplay() {
    const historyList = document.getElementById('historyList');
    const historyHeader = document.querySelector('.history-header h2');
    
    historyList.innerHTML = `
        <div style="text-align: center; padding: 40px; color: #6c757d;">
            <p>📭 История обращений пуста</p>
            <p style="margin-top: 10px;">Следующая заявка получит номер <strong>T0001</strong></p>
        </div>
    `;
    
    if (historyHeader) {
        historyHeader.innerHTML = `📋 История обращений <small style="font-size: 0.6em; color: #666;">(Всего: 0, Решено: 0, Исправлено: 0)</small>`;
    }
}

// Система управления модальными окнами
class ModalSystem {
    static showClearHistoryModal() {
        const modal = document.getElementById('clearHistoryModal');
        if (modal) {
            modal.style.display = 'flex';
        }
    }
    
    static closeClearHistoryModal() {
        const modal = document.getElementById('clearHistoryModal');
        if (modal) {
            modal.style.display = 'none';
        }
    }
    
    static confirmClearHistory() {
        this.closeClearHistoryModal();
        this.performClearHistory();
    }
    
    static performClearHistory() {
        localStorage.removeItem('support_tickets');
        localStorage.removeItem('ticket_counter');
        updateHistoryDisplay();
        FeedbackSystem.showNotification('✅ История очищена, счетчик сброшен');
    }
    // В класс ModalSystem добавь эти методы:

static showTicketDetails(ticket) {
    const modal = document.getElementById('ticketDetailsModal');
    const content = document.getElementById('ticketDetailsContent');
    
    if (modal && content) {
        content.innerHTML = this.generateTicketDetailsHTML(ticket);
        modal.style.display = 'flex';
    }
}

static closeTicketDetails() {
    const modal = document.getElementById('ticketDetailsModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

static generateTicketDetailsHTML(ticket) {
    const displayCategory = ticket.corrected_category || ticket.predicted_category;
    const hasCorrections = ticket.corrected_category || ticket.original_response;
    
    return `
        <div style="margin-bottom: 25px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <div>
                    <strong style="font-size: 1.1em;">Запрос ${ticket.id}</strong>
                    <span style="margin-left: 10px; color: #6c757d; font-size: 0.9em;">
                        ${new Date(ticket.timestamp).toLocaleString()}
                    </span>
                </div>
                <span class="status-${ticket.status}" style="font-size: 0.9em;">
                    ${ticket.status === 'resolved' ? '✅ Решено' :
                      ticket.status === 'needs_correction' ? '✏️ Исправлено' :
                      '📊 Анализ'}
                </span>
            </div>
            
            <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                <span class="ticket-category" style="${ticket.corrected_category ? 'background: #28a745;' : ''}">
                    ${escapeHtml(displayCategory)}
                </span>
                ${ticket.confidence ? `
                <span style="background: #e9ecef; color: #6c757d; padding: 4px 10px; border-radius: 20px; font-size: 0.8em;">
                    Уверенность: ${Math.round(ticket.confidence * 100)}%
                </span>
                ` : ''}
            </div>
        </div>
        
        <div style="margin-bottom: 20px;">
            <h4 style="margin-bottom: 10px; color: var(--vtb-dark);">📝 Запрос клиента</h4>
            <div style="background: #f8f9fa; padding: 15px; border-radius: 6px; border-left: 4px solid var(--vtb-blue);">
                ${escapeHtml(ticket.original_text)}
            </div>
        </div>
        
        ${ticket.system_response ? `
        <div style="margin-bottom: 20px;">
            <h4 style="margin-bottom: 10px; color: var(--vtb-dark);">💡 Ответ системы</h4>
            <div style="background: #eef4ff; padding: 15px; border-radius: 6px; border-left: 4px solid var(--vtb-light-blue); white-space: pre-wrap;">
                ${cleanText(ticket.system_response)}
            </div>
        </div>
        ` : ''}
        
        ${hasCorrections ? `
        <div style="margin-bottom: 20px;">
            <h4 style="margin-bottom: 15px; color: var(--vtb-dark); display: flex; align-items: center; gap: 8px;">
                ✏️ Исправления оператора
            </h4>
            
            ${ticket.corrected_category && ticket.corrected_category !== ticket.predicted_category ? `
            <div style="margin-bottom: 15px;">
                <h5 style="margin-bottom: 8px; color: #6c757d;">Категория</h5>
                <div style="display: flex; gap: 15px; align-items: center;">
                    <div style="flex: 1; background: #ffebee; padding: 12px; border-radius: 6px; border-left: 4px solid #dc3545;">
                        <div style="font-size: 0.9em; color: #6c757d; margin-bottom: 4px;">Было:</div>
                        <div>${escapeHtml(ticket.predicted_category)}</div>
                    </div>
                    <div style="font-size: 20px; color: #6c757d;">→</div>
                    <div style="flex: 1; background: #d4edda; padding: 12px; border-radius: 6px; border-left: 4px solid #28a745;">
                        <div style="font-size: 0.9em; color: #6c757d; margin-bottom: 4px;">Стало:</div>
                        <div>${escapeHtml(ticket.corrected_category)}</div>
                    </div>
                </div>
            </div>
            ` : ''}
            
            ${ticket.original_response ? `
            <div style="margin-bottom: 15px;">
                <h5 style="margin-bottom: 8px; color: #6c757d;">Текст ответа</h5>
                <div style="display: flex; flex-direction: column; gap: 10px;">
                    <div style="background: #fff3cd; padding: 12px; border-radius: 6px; border-left: 4px solid #ffc107;">
                        <div style="font-size: 0.9em; color: #6c757d; margin-bottom: 4px;">Было:</div>
                        <div style="white-space: pre-wrap;">${cleanText(ticket.original_response)}</div>
                    </div>
                    <div style="background: #e7f3ff; padding: 12px; border-radius: 6px; border-left: 4px solid #007bff;">
                        <div style="font-size: 0.9em; color: #6c757d; margin-bottom: 4px;">Стало:</div>
                        <div style="white-space: pre-wrap;">${cleanText(ticket.system_response)}</div>
                    </div>
                </div>
            </div>
            ` : ''}
        </div>
        ` : ''}
        
        ${!hasCorrections ? `
        <div style="text-align: center; padding: 20px; color: #6c757d;">
            <p>Оператор не вносил изменений в эту заявку</p>
        </div>
        ` : ''}
    `;
}
}

// Глобальная переменная для доступа к ассистенту
let assistant;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    assistant = new SupportAssistant();
    console.log('AI Assistant initialized');
});
