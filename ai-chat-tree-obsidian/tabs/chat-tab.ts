import { ItemView, WorkspaceLeaf, Notice } from 'obsidian';
import AIChatTree from 'main';

export const VIEW_TYPE = 'chat-tree-chat';

const MODEL_OPTIONS = ['default', 'qwen2.5:32b', 'mistral-small3.2', 'hermes3:70b', 'claude-sonnet-4', 'gpt-4o'];

export interface ChatBranch {
    id: string;
    name: string;
    active: boolean;
}

export interface TurnData {
    id: string;
    branch_id: string;
    prompt: string;
    response: string;
    model: string;
    source: string;
    success_score: number;
    tags: string[];
    timestamp?: string;
}

export interface FruitData {
    id: string;
    turno_id: string;
    branch_id: string;
    content: string;
    fruit_type: string;
    notes: string;
    timestamp?: string;
}

export interface TreeItem {
    id: string;
    type: 'trunk' | 'branch' | 'turn';
    name: string;
    children?: TreeItem[];
}

export class ChatTreeTab extends ItemView {
    static readonly TYPE = VIEW_TYPE;
    private plugin: AIChatTree;
    private currentBranch: string;
    private messagesEl: Element;
    private modelSelector: HTMLSelectElement | null = null;

    constructor(leaf: WorkspaceLeaf, plugin: AIChatTree) {
        super(leaf);
        this.plugin = plugin;
        this.currentBranch = plugin.settings.defaultBranch;
    }

    getViewType(): string { return VIEW_TYPE; }
    getDisplayText(): string { return 'AI Chat Tree'; }
    getIcon(): string { return 'git-branch'; }

    async onOpen(): Promise<void> {
        this.containerEl.addClass('chat-tree-plugin');
        this.containerEl.empty();

        // Header — branch selector + model switcher
        const header = this.containerEl.createDiv({ cls: 'chat-tree-header' });
        
        const leftSection = header.createDiv({ cls: 'branch-selector' });
        leftSection.createEl('span', { text: 'Branch: ' });
        const select = leftSection.createEl('select', { attr: { id: 'chat-tree-branch-select' } });
        await this.loadBranches(select);

        this.currentBranch = select.value || this.currentBranch;
        select.addEventListener('change', async () => {
            this.currentBranch = select.value;
            this.plugin.settings.defaultBranch = this.currentBranch;
            await this.plugin.saveSettings();
            await this.refreshMessages();
        });
        this.currentBranch = select.value;

        // Model switcher
        const modelSection = header.createDiv({ cls: 'model-selector' });
        modelSection.createEl('span', { text: 'Model: ' });
        this.modelSelector = modelSection.createEl('select', { attr: { id: 'chat-tree-model-select' } });
        this.modelSelector.addEventListener('change', () => {
            const modelPerBranch = { ...this.plugin.settings.modelPerBranch };
            modelPerBranch[this.currentBranch] = this.modelSelector.value;
            this.plugin.settings.modelPerBranch = modelPerBranch;
        });
        // Set option for current branch
        const currentModel = this.plugin.settings.modelPerBranch[this.currentBranch] || 'default';
        for (const m of MODEL_OPTIONS) {
            const opt = this.modelSelector.createEl('option', { value: m, text: m });
            if (m === currentModel) opt.selected = true;
        }

        // Sidebar toggle button
        const sidebarBtn = header.createEl('button', {
            text: '🌿 Tree',
            cls: 'chat-tree-tree-toggle'
        });
        sidebarBtn.addEventListener('click', () => this.plugin.activateTreeView());

        // Body
        const body = this.containerEl.createDiv({ cls: 'chat-tree-body' });
        this.messagesEl = body.createDiv({ cls: 'chat-tree-messages', attr: { id: 'chat-tree-messages' } });
        await this.refreshMessages();

        // Input area
        const inputArea = this.containerEl.createDiv({ cls: 'chat-tree-input-area' });
        const textarea = inputArea.createEl('textarea', {
            attr: { id: 'chat-tree-textarea' },
            placeholder: 'Send a message...',
        });
        textarea.setAttribute('rows', '3');

        const sendBtn = inputArea.createEl('button', { text: 'Send' });
        sendBtn.addEventListener('click', () => this.sendMessage(textarea, this.messagesEl));
        sendBtn.addEventListener('click', () => textarea.focus());
        textarea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                sendBtn.click();
            }
        });
    }

    private async sendMessage(textarea: HTMLTextAreaElement, messages: Element) {
        const text = textarea.value.trim();
        if (!text) return;

        // Show user message
        const userMsg = this.createMessageEl('user', text);
        messages.appendChild(userMsg);
        textarea.value = '';
        userMsg.scrollIntoView();

        // Loading indicator
        const loading = this.createMessageEl('assistant', 'Thinking...', { loading: true });
        messages.appendChild(loading);
        loading.scrollIntoView();

        const branchEl = (document.getElementById('chat-tree-branch-select') as HTMLSelectElement);
        const branch = branchEl ? branchEl.value : this.currentBranch;
        this.currentBranch = branch;
        const model = this.modelSelector ? this.modelSelector.value : 'default';

        try {
            const res = await fetch(`${this.plugin.settings.engineUrl}/turnos`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    branch_id: branch, 
                    prompt: text, 
                    model,
                    source: this.model ? 'obsidian-plugin' : 'manual'
                }),
            });

            loading.remove();

            if (!res.ok) throw new Error(`Server ${res.status}`);
            const data = await res.json() as TurnData;

            // Show assistant response
            const respMsg = this.createMessageEl('assistant', data.response || text, {
                turnId: data.id,
                model: data.model,
                timestamp: new Date().toISOString(),
                branchId: data.id,
            });
            this.addTurnActions(respMsg, data, model);
            messages.appendChild(respMsg);
            respMsg.scrollIntoView();

            // Fetch and show fruits for this turn
            await this.loadFruitsForTurn(respMsg, data.id);

        } catch (err: any) {
            loading.textContent = `Error: ${err.message || err}`;
            loading.classList.add('chat-tree-message-error');
        }
    }

    private createMessageEl(role: string, text: string, opts: { loading?: boolean; turnId?: string; model?: string; timestamp?: string; branchId?: string } = {}): HTMLDivElement {
        const el = document.createElement('div');
        el.className = `chat-tree-message ${role}`;
        if (opts.loading) el.classList.add('loading');
        
        let html = `<div class="role">${role}</div>`;
        html += `<div class="content">${this.escapeHtml(text)}</div>`;
        
        if (opts.turnId || opts.model || opts.timestamp) {
            html += '<div class="meta">';
            if (opts.model) html += `<span class="meta-model">model: ${opts.model}</span>`;
            if (opts.timestamp) html += `<span class="meta-timestamp">` + new Date(opts.timestamp).toLocaleTimeString() + `</span>`;
            html += '</div>';
        }
        
        el.innerHTML = html;
        return el;
    }

    private escapeHtml(str: string): string {
        return str.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    private async addTurnActions(msgEl: HTMLDivElement, turn: TurnData, model: string) {
        const actionsEl = msgEl.createDiv({ cls: 'turn-actions' });

        // Thumbs up / down (feedback capture)
        const feedbackEl = actionsEl.createDiv({ cls: 'feedback' });
        feedbackEl.innerHTML += '<button class="feedback-btn" data-score="1" title="Good">👍</button>';
        feedbackEl.innerHTML += '<button class="feedback-btn" data-score="0.5" title="Needs improvement">🤔</button>';
        feedbackEl.innerHTML += '<button class="feedback-btn" data-score="0" title="Bad">👎</button>';
        
        feedbackEl.querySelectorAll('.feedback-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.preventDefault();
                const score = (e.target as HTMLButtonElement).getAttribute('data-score');
                if (score === null) return;
                try {
                    const res = await fetch(`${this.plugin.settings.engineUrl}/turnos/${turn.id}/score`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ score: parseFloat(score) }),
                    });
                    if (res.ok) {
                        btn.style.transform = 'scale(1.3)';
                        setTimeout(() => btn.style.transform = '', 300);
                    }
                } catch (err) {
                    console.warn('Score update failed:', err);
                }
            });
        });

        // One-click branch
        const branchBtn = actionsEl.createEl('button', { text: '🌿 Branch', cls: 'action-btn branch-btn' });
        branchBtn.addEventListener('click', async () => {
            const name = prompt('Branch name:');
            if (!name) return;
            try {
                const res = await fetch(`${this.plugin.settings.engineUrl}/branches`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, parent_turn: turn.id }),
                });
                if (!res.ok) throw new Error(`Server ${res.status}`);
                new Notice(`Branch "${name}" created from ${turn.id}`);
            } catch (err: any) {
                new Notice(`Branch failed: ${err.message}`);
            }
        });

        // Revise prompt (RLM)
        const reviseBtn = actionsEl.createEl('button', { text: '↻ Revise', cls: 'action-btn revise-btn' });
        reviseBtn.addEventListener('click', () => {
            const revPrompt = prompt('Revision prompt:', turn.prompt);
            if (!revPrompt) return;
            try {
                fetch(`${this.plugin.settings.engineUrl}/turnos/rotate`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        turno_id: turn.id, 
                        new_prompt: revPrompt, 
                        model,
                    }),
                }).then(() => new Notice(`Revise requested for ${turn.id}`));
            } catch (err: any) {
                new Notice(`Revise failed: ${err.message}`);
            }
        });

        // Export as fruit
        const fruitBtn = actionsEl.createEl('button', { text: '🍎 Fruit', cls: 'action-btn fruit-btn' });
        fruitBtn.addEventListener('click', async () => {
            const type = prompt('Fruit type (text/script/config/visual/plan):', 'text');
            const notes = prompt('Notes:', `Fruit extracted from ${turn.id} on ${new Date().toISOString()}`);
            if (!type) return;
            try {
                const res = await fetch(`${this.plugin.settings.engineUrl}/fruits`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        turno_id: turn.id, 
                        branch_id: turn.branch_id, 
                        content: turn.response || turn.prompt,
                        fruit_type: type,
                        notes: notes || '',
                    }),
                });
                if (!res.ok) throw new Error(`Server ${res.status}`);
                new Notice('Fruit created');
            } catch (err: any) {
                new Notice(`Fruit creation failed: ${err.message}`);
            }
        });
    }

    private async loadFruitsForTurn(msgEl: Element, turnId: string) {
        try {
            const res = await fetch(`${this.plugin.settings.engineUrl}/fruits?turno_id=${turnId}`);
            const fruits = await res.json() as FruitData[];
            if (fruits.length === 0) return;

            const fruitsEl = msgEl.createDiv({ cls: 'fruits-container', attr: { id: `fruits-${turnId}` } });
            fruitsEl.createEl('span', { text: '🍎 Fruits:', cls: 'fruits-header' });
            
            for (const fruit of fruits) {
                const fruitEl = fruitsEl.createDiv({ cls: 'fruit-item' });
                fruitEl.innerHTML = `<div class="fruit-type">[${fruit.fruit_type}]</div><div class="fruit-content">${this.escapeHtml(fruit.content.substring(0, 200))}${fruit.content.length > 200 ? '...' : ''}</div>`;
                if (fruit.notes) {
                    fruitEl.createEl('div', { text: fruit.notes, cls: 'fruit-notes' });
                }
            }
        } catch (err) {
            console.warn('[ChatTree] Fruit load failed:', err);
        }
    }

    private async refreshMessages() {
        if (!this.messagesEl) return;
        this.messagesEl.empty();
        try {
            const res = await fetch(`${this.plugin.settings.engineUrl}/turnos/?branch=${this.currentBranch}&limit=100`);
            const turns = await res.json() as TurnData[];
            for (const turn of turns) {
                const msgEl = this.createMessageEl(turn.source === 'obsidian-plugin' || turn.source === 'chatgpt' ? 'user' : 'assistant', turn.prompt, {
                    turnId: turn.id,
                    model: turn.model,
                    timestamp: turn.timestamp,
                });
                this.messagesEl.appendChild(msgEl);
            }
            // Scroll to bottom
            this.messagesEl.parentElement?.scrollIntoView({ behavior: 'smooth' });
        } catch (err: any) {
            console.warn('[ChatTree] refreshMessages failed:', err);
        }
    }

    private async loadBranches(el: HTMLSelectElement) {
        try {
            const res = await fetch(`${this.plugin.settings.engineUrl}/branches`);
            const branches = await res.json() as ChatBranch[];
            for (const b of branches) {
                const opt = el.createEl('option', { value: b.id, text: `${b.name}${b.active ? '' : ' (inactive)'}` });
            }
        } catch (err: any) {
            console.warn('[ChatTree] loadBranches failed:', err);
        }
    }

    onClose(): void {}
}
