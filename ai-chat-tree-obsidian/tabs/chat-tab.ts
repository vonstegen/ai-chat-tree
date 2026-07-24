import { ItemView, WorkspaceLeaf, Notice } from 'obsidian';
import AIChatTree from 'main';

export const VIEW_TYPE = 'chat-tree-chat';

export class ChatTreeTab extends ItemView {
    private plugin: AIChatTree;

    constructor(leaf: WorkspaceLeaf, plugin: AIChatTree) {
        super(leaf);
        this.plugin = plugin;
    }

    getViewType(): string { return VIEW_TYPE; }
    getDisplayText(): string { return 'AI Chat Tree'; }
    getIcon(): string { return 'git-branch'; }

    async onOpen(): Promise<void> {
        this.containerEl.addClass('chat-tree-plugin');
        this.containerEl.empty();

        // Header
        const header = this.containerEl.createDiv({ cls: 'chat-tree-header' });
        const branchSel = header.createDiv({ cls: 'branch-selector' });
        const label = branchSel.createEl('span', { text: 'Branch: ' });
        const select = branchSel.createEl('select', { attr: { id: 'chat-tree-branch-select' } });
        await this.loadBranches(select);

        // Body
        const body = this.containerEl.createDiv({ cls: 'chat-tree-body' });
        const messages = body.createDiv({ cls: 'chat-tree-messages' });

        // Input area
        const inputArea = this.containerEl.createDiv({ cls: 'chat-tree-input-area' });
        const textarea = inputArea.createEl('textarea', {
            cls: 'chat-tree-textarea',
            placeholder: 'Send a message...',
        });
        textarea.setAttribute('rows', '3');

        const sendBtn = inputArea.createEl('button', { text: 'Send' });
        sendBtn.addEventListener('click', () => this.sendMessage(textarea, messages));
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

        // User message
        messages.createDiv({ cls: 'chat-tree-message user', text });
        textarea.value = '';

        // Loading
        const loading = messages.createDiv({ cls: 'chat-tree-message assistant', text: 'Thinking...' });
        loading.scrollIntoView();

        try {
            const branchEl = (document.getElementById('chat-tree-branch-select') as HTMLSelectElement);
            const branch = branchEl ? branchEl.value : this.plugin.settings.defaultBranch;

            const res = await fetch(`${this.plugin.settings.engineUrl}/turnos`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ branch_id: branch, prompt: text, model: 'default' }),
            });

            loading.remove();

            if (!res.ok) throw new Error(`Server ${res.status}`);
            const data = await res.json();

            // Create response message
            const respText = data.response || `${data.prompt?.substring(0, 500)}...`;
            messages.createDiv({
                cls: 'chat-tree-message assistant',
                text: respText,
            });
            messages.lastElementChild?.scrollIntoView();

        } catch (err: any) {
            loading.textContent = `Error: ${err.message || err}`;
        }
    }

    private async loadBranches(el: HTMLSelectElement) {
        try {
            const res = await fetch(`${this.plugin.settings.engineUrl}/branches`);
            const branches = await res.json() as any[];
            for (const b of branches) {
                const opt = el.createEl('option', { text: b.name, value: b.id });
            }
        } catch (err: any) {
            console.warn('[ChatTree] loadBranches failed:', err);
        }
    }

    onClose(): void {}
}
