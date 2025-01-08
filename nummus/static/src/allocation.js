'use strict';
const allocation = {
    chart: null,
    /**
     * Create Allocation Chart
     *
     * @param {Object} raw Raw data from allocation controller
     */
    update: function(raw) {
        const tree = [];
        const categoryColors = {};
        const entries = Object.entries(raw);
        entries.forEach(([category, assets], i) => {
            const color = getChartColor(i, 360 / entries.length);
            categoryColors[category] = color;
            assets.forEach((asset) => {
                tree.push({
                    category: category,
                    name: asset.name,
                    value: asset.value,
                });
            });
        });

        {
            const canvas = document.getElementById('allocation-chart-canvas');
            const ctx = canvas.getContext('2d');
            const datasets = [{
                key: 'value',
                groups: ['category', 'name'],
                tree: tree,
                borderWidth: 0,
                spacing: 1,
                captions: {
                    align: 'center',
                },
                backgroundColor: function(context) {
                    if (context.type != 'data') {
                        return 'transparent';
                    }
                    const obj = context.raw._data;
                    if (obj.name) {
                        return categoryColors[obj.category] + 'D0';
                    }
                    return categoryColors[obj.category] + '40';
                },
                labels: {
                    display: true,
                    overflow: 'hidden',
                    formatter: function(context) {
                        const obj = context.raw._data;
                        return [
                            obj.name,
                            formatterF2.format(obj.value),
                        ]
                    },
                }
            }];
            if (this.chart && ctx == this.chart.ctx) {
                nummusChart.updateTree(this.chart, datasets);
            } else {
                this.chart = nummusChart.createTree(
                    ctx,
                    datasets,
                );
            }
        }
    },
}
