import { ItemView, WorkspaceLeaf } from 'obsidian';
import AIChatTree from 'main';

export const TREE_VIEW_TYPE = 'chat-tree-tree';

export class ChatTreeTreeView extends ItemView {
    private plugin: AIChatTree;

    constructor(leaf: WorkspaceLeaf, plugin: AIChatTree) {
        super(leaf);
        this.plugin = plugin;
    }

    getViewType(): string { return TREE_VIEW_TYPE; }
    getDisplayText(): string { return 'Chat Tree'; }
    getIcon(): string { return 'git-branch'; }

    async onOpen(): Promise<void> {
        const container = this.containerEl.createEl('div', { cls: 'chat-tree-treeview' });
        await this.loadTree(container);
    }

    private async loadTree(container: Element) {
        try {
            // Load branches
            const res = await fetch(`${this.plugin.settings.engineUrl}/branches`);
            const branches = await res.json() as any[];

            if (branches.length === 0) {
                container.createEl('p', { text: 'No branches yet. Create one via the Chat Tree tab.' });
                return;
            }

            for (const branch of branches) {
                const branchEl = container.createEl('div', { cls: 'tree-node' });
                branchEl.createEl('span', { text: '🌿 ' + branch.name });
                branchEl.onclick = async () => {
                    // Clear existing and show turns for this branch
                    container.empty();
                    container.createEl('h3', { text: 'Branch: ' + branch.name });
                    const turnsRes = await fetch(`${this.plugin.settings.engineUrl}/turnos/?branch=${branch.id}`);
                    const turns = await turnsRes.json() as any[];
                    if (turns.length === 0) {
                        container.createEl('p', { text: 'No turns yet.' });
                        return;
                    }
                    const list = container.createEl('ul');
                    for (const turn of turns) {
                        const li = list.createEl('li', { cls: 'tree-node', text: turn.prompt?.substring(0, 60) });
                        li.onclick = () => {
                            window.open(`${this.plugin.settings.engineUrl}/turnos/${turn.id}`);
                        };
                    }
                };
            }
        } catch (err: any) {
            container.createEl('p', { text: `Failed to load tree: ${err.message}` });
        }
    }

    onClose(): void {}
}
