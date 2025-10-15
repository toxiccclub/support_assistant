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
            // Не сохраняем при повторных анализах того же текста
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
        
        // Убираем блокировку если она была
        this.unlockCurrentTicketUI();
        
        const cards = this.resultSection.querySelectorAll('.card');
        cards.forEach((card, index) => {
            card.style.animationDelay = `${index * 0.1}s`;
        });
    }

    // Разблокировка UI для нового анализа
    unlockCurrentTicketUI() {
        const lockedNote = document.getElementById('ticketLockedNote');
        if (lockedNote) {
            lockedNote.remove();
        }
        
        const operatorActions = document.querySelector('.operator-actions');
        if (operatorActions) {
            operatorActions.style.display = 'flex';
        }
        
        const clearBtn = document.getElementById('clearFormBtn');
        if (clearBtn) {
            clearBtn.remove();
        }
        
        // Показываем кнопку анализа
        this.analyzeBtn.style.display = 'block';
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
        
        container.innerHTML = `
            <div class="response-content">${cleanResponse}</div>
            <button onclick="copyToClipboard('${this.escapeForJavascript(cleanResponse)}')" 
                    class="copy-btn" title="Копировать ответ" style="margin-top: 10px;">
                📋 Копировать ответ
            </button>
        `;
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
        const updated = await this.updateTicketStatus('resolved', 5);
        if (updated) {
            this.showNotification('✅ Отмечено как решенное');
            if (document.getElementById('historyTab')?.classList.contains('active')) {
                loadHistory();
            }
            this.lockCurrentTicketUI();
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
        
        // Обновляем текущий ответ в ассистенте
        assistant.currentResponse = correctedResponse;
        assistant.currentCategory = correctedCategory || assistant.currentCategory;
        
        // Для статуса needs_correction рейтинг всегда 0 (не отображается)
        const updated = await this.updateTicketStatus('needs_correction', 0, correctedCategory || null);
        
        if (updated) {
            this.closeCorrectionModal();
            this.showNotification('📝 Заявка исправлена и сохранена');
            if (document.getElementById('historyTab')?.classList.contains('active')) {
                loadHistory();
            }
            this.lockCurrentTicketUI();
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
            operator_rating: status === 'resolved' ? rating : 0,
            operator_notes: notes,
            corrected_category: correctedCategory
        };

        const updatedTicket = TicketManager.saveOrUpdateTicket(ticketData);
        return !!updatedTicket;
    }

    static lockCurrentTicketUI() {
        // Скрываем действия оператора
        const operatorActions = document.querySelector('.operator-actions');
        if (operatorActions) {
            operatorActions.style.display = 'none';
        }
        
        // Скрываем кнопку анализа
        assistant.analyzeBtn.style.display = 'none';
        
        // Добавляем визуальное обозначение закрытой заявки
        const resultSection = document.getElementById('resultSection');
        if (resultSection && !document.getElementById('ticketLockedNote')) {
            const note = document.createElement('div');
            note.id = 'ticketLockedNote';
            note.style.cssText = `
                margin: 20px 0;
                padding: 20px;
                border: 1px solid #d4edda;
                border-radius: 8px;
                background: #f8fff9;
                color: #155724;
                text-align: center;
                font-weight: 500;
                border-left: 4px solid #28a745;
            `;
            note.innerHTML = `
                <div style="font-size: 24px; margin-bottom: 8px;">🔒</div>
                <div>Заявка сохранена в историю</div>
                <div style="font-size: 0.9em; margin-top: 5px; color: #6c757d;">
                    Вы можете начать новый анализ
                </div>
            `;
            resultSection.appendChild(note);
        }
        
        // Показываем кнопку для очистки формы
        this.addClearFormButton();
    }

    static addClearFormButton() {
        const inputSection = document.querySelector('.input-section');
        const existingClearBtn = document.getElementById('clearFormBtn');
        
        if (!existingClearBtn) {
            const clearBtn = document.createElement('button');
            clearBtn.id = 'clearFormBtn';
            clearBtn.textContent = '🧹 Начать новый анализ';
            clearBtn.style.cssText = `
                background: #003da6;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                cursor: pointer;
                margin-top: 15px;
                font-weight: 500;
                transition: 0.2s;
                width: 100%;
                font-size: 16px;
            `;
            clearBtn.onmouseover = () => clearBtn.style.backgroundColor = '#002a75';
            clearBtn.onmouseout = () => clearBtn.style.backgroundColor = '#003da6';
            clearBtn.onclick = () => {
                // Очищаем форму
                assistant.textArea.value = '';
                // Скрываем результаты
                assistant.resultSection.style.display = 'none';
                // Убираем блокировку
                const lockedNote = document.getElementById('ticketLockedNote');
                if (lockedNote) lockedNote.remove();
                // Показываем кнопки оператора снова
                const operatorActions = document.querySelector('.operator-actions');
                if (operatorActions) operatorActions.style.display = 'flex';
                // Показываем кнопку анализа
                assistant.analyzeBtn.style.display = 'block';
                // Убираем кнопку очистки
                clearBtn.remove();
                // Фокус на текстовое поле
                assistant.textArea.focus();
            };
            
            inputSection.appendChild(clearBtn);
        }
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
                predicted_category: ticketData.corrected_category || ticketData.predicted_category, // Обновляем категорию если исправлена
                system_response: ticketData.system_response, // Обновляем ответ
                status: ticketData.status,
                operator_rating: ticketData.operator_rating,
                operator_notes: ticketData.operator_notes || '',
                corrected_category: ticketData.corrected_category || null,
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
                corrected_category: ticketData.corrected_category || null
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
            historyHeader.innerHTML = `📋 История обращений <small style="font-size: 0.6em; color: #666;">(Всего: 0, Решено: 0)</small>`;
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
        // Определяем отображаемую категорию - исправленную или исходную
        const displayCategory = ticket.corrected_category || ticket.predicted_category;
        
        return `
        <div class="ticket-item">
            <div class="ticket-header">
                <div class="ticket-customer">
                    Запрос ${ticket.id}
                </div>
                <div class="ticket-meta">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span class="ticket-category">${escapeHtml(displayCategory)}</span>
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
                    <strong>Запрос:</strong> ${escapeHtml(ticket.original_text)}
                </div>
                ${ticket.system_response ? `
                <div class="ticket-response">
                    <strong>Ответ:</strong> ${cleanText(ticket.system_response)}
                </div>
                ` : ''}
                ${ticket.confidence ? `<div style="margin-top: 8px;"><strong>Уверенность:</strong> ${Math.round(ticket.confidence * 100)}%</div>` : ''}
                
                ${ticket.corrected_category ? `
                <div style="margin-top: 10px; padding: 10px; background: #fff3cd; border-radius: 6px; border-left: 4px solid #ffc107;">
                    <strong>📝 Исправления оператора:</strong><br>
                    <strong>Категория:</strong> ${escapeHtml(ticket.corrected_category)} (было: ${escapeHtml(ticket.predicted_category)})
                </div>
                ` : ''}
            </div>
            
            ${ticket.status === 'resolved' && ticket.operator_rating ? `
            <div class="ticket-feedback">
                <span><strong>Оценка:</strong> ${'⭐'.repeat(ticket.operator_rating)}</span>
            </div>
            ` : ''}
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
    link.download = `vtb_support_tickets_${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    
    alert(`Экспортировано ${tickets.length} заявок`);
}

// Очистка истории
function clearHistory() {
    if (confirm('Вы уверены что хотите очистить всю историю заявок? Счетчик номеров будет сброшен.')) {
        localStorage.removeItem('support_tickets');
        localStorage.removeItem('ticket_counter');
        updateHistoryDisplay();
        FeedbackSystem.showNotification('✅ История очищена, счетчик сброшен');
    }
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
        historyHeader.innerHTML = `📋 История обращений <small style="font-size: 0.6em; color: #666;">(Всего: 0, Решено: 0)</small>`;
    }
}

// Глобальная переменная для доступа к ассистенту
let assistant;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    assistant = new SupportAssistant();
    console.log('AI Assistant initialized');
});