import * as MYCONFIG from "../../config/config.js";

class ChatHistoryManager {
    constructor() {
        this.histories = new Map(); // roomId/userId -> messages[]
    }

    addMessage(id, role, content, name = '') {
        if (!this.histories.has(id)) {
            this.histories.set(id, []);
        }

        const history = this.histories.get(id);
        const message = {
            role,
            content: name ? `${name}: ${content}` : content
        };

        history.push(message);

        // Keep only the last maxHistoryCount messages
        if (history.length > MYCONFIG.maxHistoryCount) {
            history.shift();
        }
    }

    getHistory(id) {
        return this.histories.get(id) || [];
    }

    clearHistory(id) {
        this.histories.delete(id);
    }
}

export const chatHistoryManager = new ChatHistoryManager();
