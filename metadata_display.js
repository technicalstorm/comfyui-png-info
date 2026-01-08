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

            // Re-enable the upload behavior manually on our empty widget
            const imageWidget = this.widgets.find(w => w.name === "image");
            imageWidget.type = "combo";
            imageWidget.options = { values: [], image_upload: true };

            const result = ComfyWidgets.STRING(
                this,
                "metadata",
                ["STRING", { multiline: true }],
                app
            ).widget;
            
            result.inputEl.readOnly = true;
            result.inputEl.style.height = "320px";
            result.inputEl.placeholder = "Drop image... it will be deleted immediately after reading.";

            this.widgets = this.widgets.filter(w => w !== result);
            this.widgets.push(result);

            imageWidget.callback = () => {
                if (!imageWidget.value) return;
                api.fetchApi("/pnginfo/fetch_metadata", {
                    method: "POST",
                    body: JSON.stringify({ image: imageWidget.value, node_id: this.id }),
                });
            };

            this.size = [500, 600];
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