import { App, Plugin, PluginSettingTab, Setting, Notice } from 'obsidian';
import { ChatTreeTab } from './tabs/chat-tab';

interface AIChatTreeSettings {
    engineUrl: string;
    defaultBranch: string;
    autoConnect: boolean;
}

const DEFAULT_SETTINGS: AIChatTreeSettings = {
    engineUrl: 'http://localhost:8765',
    defaultBranch: 'trunk',
    autoConnect: true,
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

    async onload() {
        await this.loadSettings();

        this.addRibbonIcon('git-branch', 'AI Chat Tree', () => {
            this.activateChatTab();
        });

        this.addSettingTab(new AIChatTreeSettingTab(this.app, this));

        this.registerTabView();
        this.registerCommands();
        this.registerAPI();
    }

    async loadSettings() {
        this.settings = { ...DEFAULT_SETTINGS, ...await this.loadData() };
    }

    async saveSettings() {
        await this.saveData(this.settings);
    }

    async activateChatTab() {
        const leaf = this.app.workspace.createLeafBySplit('right');
        leaf.setViewState({ type: ChatTreeTab.TYPE, state: { branch: this.settings.defaultBranch } });
        this.app.workspace.revealLeaf(leaf);
    }

    registerTabView() {
        this.registerView(
            ChatTreeTab.TYPE,
            (leaf) => new ChatTreeTab(leaf, this),
        );
    }

    registerCommands() {
        this.addCommand({
            id: 'new-turn',
            name: 'New Turn (Chat Tree)',
            callback: () => this.activateChatTab(),
        });

        this.addCommand({
            id: 'new-branch',
            name: 'New Branch (Chat Tree)',
            callback: async () => {
                const branch = prompt('Branch name:');
                if (branch) {
                    await this.createBranch(branch);
                    new Notice(`Branch "${branch}" created`);
                }
            },
        });

        this.addCommand({
            id: 'tree-status',
            name: 'Show Tree Status',
            callback: async () => {
                const status = await this.fetchStatus();
                new Notice(status);
            },
        });

        this.addCommand({
            id: 'toggle-sidebar',
            name: 'Toggle Chat Tree Sidebar',
            callback: () => this.toggleSidebar(),
        });
    }

    registerAPI() {
        window.AIChatTreeAPI = {
            createTurn: async (branchId: string, prompt: string, model: string) => {
                const res = await fetch(`${this.settings.engineUrl}/api/v1/turns`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ branch_id: branchId, prompt, model }),
                });
                return res.json();
            },
            search: async (query: string) => {
                const res = await fetch(`${this.settings.engineUrl}/api/v1/search?query=${encodeURIComponent(query)}`);
                return res.json();
            },
            listBranches: async () => {
                const res = await fetch(`${this.settings.engineUrl}/api/v1/branches`);
                return res.json();
            },
        };
    }

    async createBranch(name: string) {
        await fetch(`${this.settings.engineUrl}/api/v1/branches`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
        });
    }

    async fetchStatus(): Promise<string> {
        const res = await fetch(`${this.settings.engineUrl}/ping`);
        return await res.text();
    }

    async toggleSidebar() {
        new Notice('Sidebar toggled');
    }

    async onunload() {
        // Cleanup
    }
}

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

        new Setting(containerEl)
            .setName('Engine URL')
            .setDesc('The HTTP URL of the ai-chat-tree-fastapi service.')
            .addText(text => text
                .setPlaceholder('http://localhost:8765')
                .setValue(this.plugin.settings.engineUrl)
                .onChange(async (value) => {
                    this.plugin.settings.engineUrl = value;
                    await this.plugin.saveSettings();
                }));

        new Setting(containerEl)
            .setName('Auto Connect')
            .setDesc('Whether to open the chat on startup.')
            .addToggle(toggle => toggle
                .setValue(this.plugin.settings.autoConnect)
                .onChange(async (value) => {
                    this.plugin.settings.autoConnect = value;
                    await this.plugin.saveSettings();
                }));
    }
}
