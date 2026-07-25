import { ItemView, WorkspaceLeaf, Notice } from 'obsidian';
import AIChatTree from 'main';

export const TREE_VIEW_TYPE = 'chat-tree-tree';

interface TreeNode {
    id: string;
    type: 'trunk' | 'branch' | 'turn';
    label: string;
    children: TreeNode[];
    turnCount?: number;
    active?: boolean;
}

export class ChatTreeTreeView extends ItemView {
    private plugin: AIChatTree;
    private currentTurnId: string | null = null;

    constructor(leaf: WorkspaceLeaf, plugin: AIChatTree) {
        super(leaf);
        this.plugin = plugin;
    }

    getViewType(): string { return TREE_VIEW_TYPE; }
    getDisplayText(): string { return 'Family Tree'; }
    getIcon(): string { return 'git-branch'; }

    async onOpen(): Promise<void> {
        this.containerEl.addClass('chat-tree-treeview');
        const container = this.containerEl.createEl('div');
        await this.renderTree(container);
    }

    private async renderTree(container: Element) {
        container.empty();
        
        // Create tree structure from API
        const trunks = await this.fetchTrunks();
        const branches = await this.fetchBranches();
        
        const tree: TreeNode[] = [];
        
        // Add trunks as root nodes
        for (const trunk of trunks) {
            const trunkBranches = branches.filter(b => {
                // Trunks whose children include this turn as parent
                // We check by looking at branch structure
                return true; // Show all branches under respective trunks
            });
            
            tree.push({
                id: trunk.id,
                type: 'trunk',
                label: `${trunk.icon || '🌳'} ${trunk.name}`,
                children: [],
            });
        }
        
        // Group branches by their parent structure
        const branchMap = new Map<string, TreeNode[]>();
        for (const branch of branches) {
            let parentId = 'root';
            // Try to find parent turn
            const children = await this.fetchChildren(branch.id);
            
            const parentKey = parentId === 'root' ? 'root' : `${parentId}-branches`;
            if (!branchMap.has(parentKey)) {
                branchMap.set(parentKey, []);
            }
            branchMap.get(parentKey)!.push({
                id: branch.id,
                type: 'branch',
                label: `${branch.icon || '🌿'} ${branch.name}`,
                children: children.map(c => ({
                    id: c.id,
                    type: 'turn' as const,
                    label: `${c.icon || '🎋'} ${c.prompt.substring(0, 40)}${c.prompt.length > 40 ? '...' : ''}`,
                    children: [],
                    turnCount: c.turnCount || 0,
                    active: this.currentTurnId === c.id,
                })),
            });
        }
        
        // Add branches to tree
        for (const [key, nodes] of branchMap.entries()) {
            for (const node of nodes) {
                const parentIdx = parseInt(key.replace('-branches', ''), 10);
                if (tree[parentIdx]) {
                    tree[parentIdx].children.push(node);
                } else {
                    tree.push(node);
                }
            }
        }
        
        // Render tree nodes
        for (const node of tree) {
            this.renderTreeNode(container, node, 0);
        }
        
        // Add search bar
        const searchEl = container.createEl('input', {
            type: 'text',
            placeholder: 'Search nodes...',
            cls: 'chat-tree-search-input',
        });
        searchEl.style.width = '100%';
        searchEl.style.marginTop = '12px';
        searchEl.style.padding = '6px 10px';
        searchEl.style.borderRadius = '4px';
        searchEl.style.border = '1px solid var(--background-modifier-border)';
        searchEl.addEventListener('input', async (e) => {
            const query = (e.target as HTMLInputElement).value.toLowerCase();
            if (query.length < 2) {
                await this.renderTree(container);
                return;
            }
            this.filterNodes(container, query);
        });
        
        // Add refresh button
        const refreshBtn = container.createEl('button', {
            text: '🔄 Refresh',
            cls: 'chat-tree-refresh-btn',
        });
        refreshBtn.style.marginTop = '8px';
        refreshBtn.style.width = '100%';
        refreshBtn.addEventListener('click', () => this.renderTree(container));
    }

    private renderTreeNode(container: Element, node: TreeNode, depth: number) {
        const nodeEl = container.createDiv({
            cls: `tree-node ${node.type === 'trunk' ? 'trunk-node' : ''} ${node.active ? 'active' : ''}`,
        });
        nodeEl.style.marginLeft = `${depth * 16}px`;
        nodeEl.createEl('span', { text: node.label });
        
        if (node.children.length > 0) {
            const childrenEl = container.createDiv({ cls: 'tree-children' });
            childrenEl.style.display = 'none';
            
            nodeEl.addEventListener('click', () => {
                const isHidden = childrenEl.style.display === 'none';
                childrenEl.style.display = isHidden ? 'block' : 'none';
                nodeEl.style.fontWeight = isHidden ? '600' : '';
            });
            
            for (const child of node.children) {
                this.renderTreeNode(childrenEl, child, depth + 1);
            }
        }
        
        // Click on turn node -> open in chat tab with that context
        if (node.type === 'turn') {
            nodeEl.addEventListener('click', () => {
                this.currentTurnId = node.id;
                // Highlight
                this.containerEl.querySelectorAll('.tree-node.active')
                    .forEach(el => el.classList.remove('active'));
                nodeEl.classList.add('active');
                // Open chat with context
                this.plugin.activateChatTab().catch(console.warn);
            });
        }
    }

    private async filterNodes(container: Element, query: string) {
        const nodes = container.querySelectorAll('.tree-node');
        nodes.forEach((node) => {
            const text = node.textContent?.toLowerCase() || '';
            node.display = text.includes(query) ? '' : 'none';
        });
    }

    private async fetchTrunks(): Promise<any[]> {
        try {
            const res = await fetch(`${this.plugin.settings.engineUrl}/trunks`);
            if (!res.ok) return [];
            return await res.json();
        } catch (err: any) {
            console.warn('[ChatTreeTreeView] fetchTrunks failed:', err);
            return [];
        }
    }

    private async fetchBranches(): Promise<any[]> {
        try {
            const res = await fetch(`${this.plugin.settings.engineUrl}/branches`);
            if (!res.ok) return [];
            return await res.json();
        } catch (err: any) {
            console.warn('[ChatTreeTreeView] fetchBranches failed:', err);
            return [];
        }
    }

    private async fetchChildren(branchId: string): Promise<any[]> {
        try {
            const res = await fetch(`${this.plugin.settings.engineUrl}/turnos/?branch=${branchId}&limit=200`);
            if (!res.ok) return [];
            const turns = await res.json();
            return turns.map((t: any) => ({
                ...t,
                icon: '🎋',
                turnCount: 1,
            }));
        } catch (err: any) {
            console.warn('[ChatTreeTreeView] fetchChildren failed:', err);
            return [];
        }
    }

    onClose(): void {}
}
