import { App, Plugin, PluginSettingTab, Setting, Notice, ItemView, WorkspaceLeaf, statusbarItemEl } from 'obsidian';
import { ChatTreeTab, VIEW_TYPE } from './tabs/chat-tab';
import { ChatTreeTreeView, TREE_VIEW_TYPE } from './tabs/tree-tab';

interface AIChatTreeSettings {
    engineUrl: string;
    defaultBranch: string;
    autoConnect: boolean;
    vaultPath: string;
    embeddings: string;
    apiKey: string;
    modelPerBranch: Record<string, string>;
    statusUpdateInterval: number;
}

const DEFAULT_SETTINGS: AIChatTreeSettings = {
    engineUrl: 'http://localhost:8765',
    defaultBranch: 'trunk',
    autoConnect: true,
    vaultPath: '',
    embeddings: 'default',
    apiKey: '',
    modelPerBranch: {},
    statusUpdateInterval: 30000,
};

declare global {
    interface Window {
        AIChatTreeAPI?: {
            createTurn: (branchId: string, prompt: string, model: string) => Promise<any>;
            search: (query: string) => Promise<any>;
            listBranches: () => Promise<any[]>;
        };
    }
}

export default class AIChatTree extends Plugin {
    settings: AIChatTreeSettings = { ...DEFAULT_SETTINGS };
    private statusBarItem: HTMLElement | null = null;
    private statusRefreshInterval: number | null = null;

    async onload() {
        await this.loadSettings();

        // Ribbon icon — open chat tab
        this.addRibbonIcon('git-branch', 'AI Chat Tree', () => {
            this.activateChatTab();
        });

        // Settings tab
        this.addSettingTab(new AIChatTreeSettingTab(this.app, this));

        // Register both views
        this.registerTabView();

        // Command palette
        this.registerCommands();

        // Public API
        this.registerAPI();

        // Status bar
        this.initStatusBar();

        // Auto-connect
        if (this.settings.autoConnect) {
            this.activateChatTab().catch(console.warn);
        }
    }

    async loadSettings() {
        this.settings = { ...DEFAULT_SETTINGS, ...await this.loadData() };
    }

    async saveSettings() {
        await this.saveData(this.settings);
    }

    async activateChatTab() {
        const leaf = this.app.workspace.createLeafBySplit('right');
        leaf.setViewState({ type: VIEW_TYPE, state: { branch: this.settings.defaultBranch } });
        this.app.workspace.revealLeaf(leaf);
    }

    async activateTreeView() {
        const leaf = this.app.workspace.createLeafBySplit('right');
        leaf.setViewState({ type: TREE_VIEW_TYPE });
        this.app.workspace.revealLeaf(leaf);
    }

    registerTabView() {
        this.registerView(VIEW_TYPE, (leaf) => new ChatTreeTab(leaf, this));
        this.registerView(TREE_VIEW_TYPE, (leaf) => new ChatTreeTreeView(leaf, this));
    }

    registerCommands() {
        // View commands
        this.addCommand({
            id: 'new-turn',
            name: 'New Turn (Chat Tree)',
            callback: () => this.activateChatTab(),
        });

        this.addCommand({
            id: 'show-tree',
            name: 'Show Family Tree (Chat Tree)',
            callback: () => this.activateTreeView(),
        });

        // New branch
        this.addCommand({
            id: 'new-branch',
            name: 'New Branch (Chat Tree)',
            callback: async () => {
                const branchName = prompt('Branch name:');
                if (!branchName) return;
                const parent = prompt('Parent turn ID (or enter for trunk-001):', 'trunk-001') || 'trunk-001';
                await this.createBranch(branchName, parent);
                new Notice(`Branch "${branchName}" created`);
            },
        });

        // RLM command — regenerate a turn
        this.addCommand({
            id: 'rlm-regenerate',
            name: 'Generate Rotation (RLM)',
            callback: async () => {
                const turnId = prompt('Turn ID to rotate:');
                if (!turnId) return;
                const reason = prompt('Change reason:') || 'manual RLM';
                const changeStr = prompt('New prompt/response details:', '');
                const body = JSON.stringify({ turn_id: turnId, change_reason: reason, new_content: changeStr });
                try {
                    const res = await fetch(`${this.settings.engineUrl}/turnos/${turnId}/rotate`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body,
                    });
                    if (!res.ok) throw new Error(`Server ${res.status}`);
                    const data = await res.json();
                    new Notice(`Rotation created: ${data.id}`);
                } catch (err: any) {
                    new Notice(`RLM failed: ${err.message}`);
                }
            },
        });

        // Re-embed all turns
        this.addCommand({
            id: 're-embed-all',
            name: 'Re-embed All Turns',
            callback: async () => {
                new Notice('Re-embedding all turns...');
                try {
                    const res = await fetch(`${this.settings.engineUrl}/re-embed-all`, {
                        method: 'POST',
                    });
                    if (!res.ok) throw new Error(`Server ${res.status}`);
                    const data = await res.json();
                    new Notice(`Re-embedded ${data.embedded} turns`);
                    this.updateStatusBar();
                } catch (err: any) {
                    new Notice(`Re-embed failed: ${err.message}`);
                }
            },
        });

        // Import from ChatGPT/Claude JSON
        this.addCommand({
            id: 'import-gpt',
            name: 'Import ChatGPT JSON',
            callback: async () => {
                const path = (prompt('Path to conversations.json:') || '').trim();
                if (!path) return;
                new Notice(`Importing from ${path}...`);
                try {
                    const res = await fetch(`${this.settings.engineUrl}/import/chatgpt`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ json_path: path }),
                    });
                    if (!res.ok) throw new Error(`Server ${res.status}`);
                    const data = await res.json();
                    new Notice(`Imported ${data.imports} turns`);
                } catch (err: any) {
                    new Notice(`Import failed: ${err.message}`);
                }
            },
        });

        this.addCommand({
            id: 'import-claude',
            name: 'Import Claude JSON',
            callback: async () => {
                const path = (prompt('Path to Claude export JSON:') || '').trim();
                if (!path) return;
                new Notice(`Importing from ${path}...`);
                try {
                    const res = await fetch(`${this.settings.engineUrl}/import/claude`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ json_path: path }),
                    });
                    if (!res.ok) throw new Error(`Server ${res.status}`);
                    const data = await res.json();
                    new Notice(`Imported ${data.imports} turns`);
                } catch (err: any) {
                    new Notice(`Import failed: ${err.message}`);
                }
            },
        });

        // Health status
        this.addCommand({
            id: 'tree-status',
            name: 'Show Tree Status',
            callback: async () => {
                const status = await this.fetchStatus();
                new Notice(status);
            },
        });

        // Toggle sidebar
        this.addCommand({
            id: 'toggle-sidebar',
            name: 'Toggle Chat Tree Sidebar',
            callback: () => this.toggleSidebar(),
        });
    }

    registerAPI() {
        window.AIChatTreeAPI = {
            createTurn: async (branchId: string, prompt: string, model: string) => {
                const res = await fetch(`${this.settings.engineUrl}/turnos`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ branch_id: branchId, prompt, model }),
                });
                return res.json();
            },
            search: async (query: string) => {
                const res = await fetch(`${this.settings.engineUrl}/search?query=${encodeURIComponent(query)}`);
                return res.json();
            },
            listBranches: async () => {
                const res = await fetch(`${this.settings.engineUrl}/branches`);
                return res.json();
            },
        };
    }

    async createBranch(name: string, parentTurn: string = 'trunk-001') {
        const res = await fetch(`${this.settings.engineUrl}/branches`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, parent_turn: parentTurn }),
        });
        if (!res.ok) throw new Error(`Branch creation failed: ${res.status}`);
        return res.json();
    }

    async fetchStatus(): Promise<string> {
        const res = await fetch(`${this.settings.engineUrl}/healthz`);
        const data = await res.json() as any;
        return `Status: ${data.status} | Vault: ${data.vault_root || 'N/A'}`;
    }

    toggleSidebar() {
        new Notice('Sidebar toggled');
    }

    async onunload() {
        if (this.statusRefreshInterval) {
            clearInterval(this.statusRefreshInterval);
        }
    }

    // ─── Status Bar ───

    initStatusBar() {
        this.statusBarItem = this.addStatusBarItem();
        if (!this.statusBarItem) return;
        this.statusBarItem.addClass('status-chat-tree');
        this.updateStatusBar();
        this.statusRefreshInterval = window.setInterval(() => this.updateStatusBar(), this.settings.statusUpdateInterval);
    }

    async updateStatusBar() {
        if (!this.statusBarItem) return;
        try {
            const res = await fetch(`${this.settings.engineUrl}/healthz`);
            const data = await res.json() as any;
            this.statusBarItem.innerHTML = `
                <span class="chat-tree-icon">🌲</span>
                <span class="chat-tree-status">${data.status || 'unknown'}</span>
                <span class="chat-tree-branch">🌿 ${this.settings.defaultBranch}</span>
            `;
            this.statusBarItem.onclick = () => this.activateChatTab();
        } catch (err: any) {
            this.statusBarItem.innerHTML = `<span class="chat-tree-icon">🌲</span><span class="chat-tree-status">⚠ offline</span>`;
        }
    }
}

// ─── Settings Tab ───

class AIChatTreeSettingTab extends PluginSettingTab {
    plugin: AIChatTree;

    constructor(app: App, plugin: AIChatTree) {
        super(app, plugin);
        this.plugin = plugin;
    }

    display(): void {
        const { containerEl } = this;
        containerEl.empty();
        containerEl.createEl('h2', { text: 'AI Chat Tree Configuration' });

        // Engine URL
        new Setting(containerEl)
            .setName('Engine URL')
            .setDesc('The HTTP URL of the local FastAPI engine.')
            .addText(text => text
                .setPlaceholder('http://localhost:8765')
                .setValue(this.plugin.settings.engineUrl)
                .onChange(async (value) => {
                    this.plugin.settings.engineUrl = value;
                    await this.plugin.saveSettings();
                }));

        // Default branch
        new Setting(containerEl)
            .setName('Default Branch')
            .setDesc('Branch to use for new turns.')
            .addText(text => text
                .setPlaceholder('trunk')
                .setValue(this.plugin.settings.defaultBranch)
                .onChange(async (value) => {
                    this.plugin.settings.defaultBranch = value;
                    await this.plugin.saveSettings();
                }));

        // Vault path
        new Setting(containerEl)
            .setName('Vault Root Path')
            .setDesc('Local path to the AI Chat Tree vault directory.')
            .addText(text => text
                .setPlaceholder('~/.local/share/ai-chat-tree/vault')
                .setValue(this.plugin.settings.vaultPath)
                .onChange(async (value) => {
                    this.plugin.settings.vaultPath = value;
                    await this.plugin.saveSettings();
                }));

        // Embedding model
        const embedSetting = new Setting(containerEl)
            .setName('Embedding Model')
            .setDesc('Model used for text embeddings.');
        embedSetting.addDropdown(dropdown => {
            dropdown.addOptions({
                'default': 'default (local)',
                'sentence-transformers': 'sentence-transformers (local)',
                'openai': 'OpenAI text-embedding-3-small',
                'custom': 'Custom endpoint',
            });
            dropdown.setValue(this.plugin.settings.embeddings || 'default');
            dropdown.onChange(async (value) => {
                this.plugin.settings.embeddings = value;
                await this.plugin.saveSettings();
            });
        });

        // API key (for OpenAI or other providers)
        new Setting(containerEl)
            .setName('API Key')
            .setDesc('API key for embedding provider (if needed).')
            .addText(text => text
                .setPlaceholder('sk-...')
                .setValue(this.plugin.settings.apiKey)
                .setDynamicType('password')
                .onChange(async (value) => {
                    this.plugin.settings.apiKey = value;
                    await this.plugin.saveSettings();
                }));

        // Auto connect
        new Setting(containerEl)
            .setName('Auto Connect')
            .setDesc('Open chat tab on plugin load.')
            .addToggle(toggle => toggle
                .setValue(this.plugin.settings.autoConnect)
                .onChange(async (value) => {
                    this.plugin.settings.autoConnect = value;
                    await this.plugin.saveSettings();
                }));

        // Status update interval
        new Setting(containerEl)
            .setName('Status Update Interval (ms)')
            .setDesc('How often to refresh status bar.')
            .addText(text => text
                .setPlaceholder('30000')
                .setValue(String(this.plugin.settings.statusUpdateInterval))
                .onChange(async (value) => {
                    const interval = parseInt(value, 10);
                    if (interval > 0) {
                        this.plugin.settings.statusUpdateInterval = interval;
                        if (this.plugin.statusRefreshInterval) clearInterval(this.plugin.statusRefreshInterval);
                        this.plugin.statusRefreshInterval = window.setInterval(() => this.plugin.updateStatusBar(), interval);
                        await this.plugin.saveSettings();
                    }
                }));
    }
}
