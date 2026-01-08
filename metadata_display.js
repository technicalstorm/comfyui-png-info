import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { ComfyWidgets } from "../../scripts/widgets.js";

app.registerExtension({
    name: "WLSH.MetadataDisplay",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "MetadataDisplay") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);

            // The 'image' widget is already created by Comfy because it's in INPUT_TYPES
            const imageWidget = this.widgets.find(w => w.name === "image");

            // Create the metadata widget
            const result = ComfyWidgets.STRING(
                this,
                "metadata",
                ["STRING", { multiline: true }],
                app
            );
            
            const textWidget = result.widget;
            textWidget.inputEl.readOnly = true;
            textWidget.inputEl.placeholder = "Metadata will appear here...";

            // RE-ORDER: Ensure the text widget is at the very bottom of the widget list
            // This places the image preview and image dropdown above it.
            this.widgets = this.widgets.filter(w => w !== textWidget);
            this.widgets.push(textWidget);

            const triggerFetch = () => {
                if (!imageWidget.value) return;
                api.fetchApi("/wlsh/fetch_metadata", {
                    method: "POST",
                    body: JSON.stringify({ 
                        image: imageWidget.value,
                        node_id: this.id 
                    }),
                });
            };

            // Auto-fetch on change
            const cb = imageWidget.callback;
            imageWidget.callback = function () {
                cb?.apply(this, arguments);
                triggerFetch();
            };

            this.size = [450, 450];
            setTimeout(triggerFetch, 100);
        };

        // Standard execution update
        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            onExecuted?.apply(this, arguments);
            const widget = this.widgets.find(w => w.name === "metadata");
            if (widget && message?.text) {
                widget.value = message.text[0];
                if (widget.inputEl) widget.inputEl.value = message.text[0];
            }
        };
    },

    async setup() {
        api.addEventListener("wlsh-metadata-update", (event) => {
            const { node_id, text } = event.detail;
            const node = app.graph.getNodeById(node_id);
            if (node) {
                const widget = node.widgets.find(w => w.name === "metadata");
                if (widget) {
                    widget.value = text;
                    if (widget.inputEl) widget.inputEl.value = text;
                }
            }
        });
    }
});