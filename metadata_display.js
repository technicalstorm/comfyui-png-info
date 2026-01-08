import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { ComfyWidgets } from "../../scripts/widgets.js";

app.registerExtension({
    name: "pnginfo",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "pnginfo") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);

            const imageWidget = this.widgets.find(w => w.name === "image");

            const result = ComfyWidgets.STRING(
                this,
                "metadata",
                ["STRING", { multiline: true }],
                app
            );
            
            const textWidget = result.widget;
            textWidget.inputEl.readOnly = true;
            textWidget.inputEl.style.height = "320px";
            textWidget.inputEl.style.fontSize = "12px";
            textWidget.inputEl.placeholder = "Awaiting image...";

            // Place text widget at the bottom
            this.widgets = this.widgets.filter(w => w !== textWidget);
            this.widgets.push(textWidget);

            const triggerFetch = () => {
                if (!imageWidget.value) return;
                api.fetchApi("/pnginfo/fetch_metadata", {
                    method: "POST",
                    body: JSON.stringify({ 
                        image: imageWidget.value,
                        node_id: this.id 
                    }),
                });
            };

            const cb = imageWidget.callback;
            imageWidget.callback = function () {
                cb?.apply(this, arguments);
                triggerFetch();
            };

            this.size = [500, 600];
            setTimeout(triggerFetch, 200);
        };

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
        api.addEventListener("pnginfo-metadata-update", (event) => {
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