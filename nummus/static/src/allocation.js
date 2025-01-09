'use strict';
const allocation = {
    chart: null,
    chartSector: null,
    /**
     * Create Allocation Chart
     *
     * @param {Object} rawCategories Raw category data from allocation
     *     controller
     * @param {Object} rawSectors Raw sector data from allocation controller
     */
    update: function(rawCategories, rawSectors) {
        const categoryTree = {};
        const categoryColors = {};
        const categoryEntries = Object.entries(rawCategories);
        categoryEntries.forEach(([category, assets], i) => {
            const color = getChartColor(i, 360 / categoryEntries.length);
            categoryColors[category] =
                [color, tinycolor(color).isDark() ? 'white' : 'black'];

            categoryTree[category] = {};
            assets.forEach((asset) => {
                categoryTree[category][asset.name] = {
                    category: category,
                    name: asset.name,
                    ticker: asset.ticker,
                    value: Number(asset.value),
                };
            });
        });

        const sectorTree = {};
        const sectorColors = {};
        const sectorEntries = Object.entries(rawSectors);
        sectorEntries.forEach(([sector, assets], i) => {
            const color = getChartColor(i, 360 / sectorEntries.length);
            sectorColors[sector] =
                [color, tinycolor(color).isDark() ? 'white' : 'black'];

            sectorTree[sector] = {};
            assets.forEach((asset) => {
                sectorTree[sector][asset.name] = {
                    sector: sector,
                    name: asset.name,
                    ticker: asset.ticker,
                    weight: Number(asset.weight) * 100,
                    value: Number(asset.value),
                };
            });
        });

        const labelPadding = 2;

        function word_wrap(rawLines, maxWidth, maxLines, ctx) {
            if (maxLines < 1) {
                return [];
            }
            const lines = [];
            for (const rawLine of rawLines) {
                if (!rawLine) {
                    continue;
                }
                const words = rawLine.split(' ');
                let currentLine = null;
                for (const word of words) {
                    const newLine =
                        currentLine ? currentLine + ' ' + word : word;
                    const width = ctx.measureText(newLine).width;
                    if (width < maxWidth) {
                        currentLine = newLine;
                    } else if (currentLine) {
                        const wordWidth = ctx.measureText(word).width;
                        if (wordWidth >= maxWidth) {
                            return lines;
                        }
                        lines.push(currentLine);
                        if (lines.length == maxLines) {
                            return lines;
                        }
                        currentLine = word;
                    } else {
                        // word alone doesn't fit
                        return lines;
                    }
                }
                if (currentLine) {
                    lines.push(currentLine);
                    if (lines.length == maxLines) {
                        return lines;
                    }
                }
            }
            return lines;
        }

        {
            const canvas = document.getElementById('allocation-chart-canvas');
            const ctx = canvas.getContext('2d');
            const datasets = [{
                key: 'value',
                groups: [0, 'name'],
                tree: categoryTree,
                treeLeafKey: 'name',
                borderWidth: 0,
                spacing: 1,
                backgroundColor: function(context) {
                    if (context.type != 'data') {
                        return 'transparent';
                    }
                    const obj = context.raw._data;
                    const category = obj[0];
                    if (obj.name) {
                        return categoryColors[category][0] + 'D0';
                    }
                    return categoryColors[category][0] + '40';
                },
                labels: {
                    display: true,
                    padding: labelPadding,
                    formatter: function(context) {
                        const rawObj = context.raw._data;
                        const obj = categoryTree[rawObj[0]][rawObj.name];
                        const ctx = context.chart.ctx;
                        const zoom = context.chart.getZoomLevel();

                        const maxWidth =
                            context.raw.w * zoom - labelPadding * 2;
                        const font = Chart.helpers.toFont(ctx.font);
                        const maxLines = Math.floor(
                            (context.raw.h * zoom - labelPadding * 2) /
                            font.lineHeight);

                        let lines = [
                            obj.ticker, obj.name, formatterF2.format(obj.value)
                        ];
                        return word_wrap(lines, maxWidth, maxLines, ctx);
                    },
                    color: function(context) {
                        const obj = context.raw._data;
                        if (obj.name) {
                            const category = obj[0];
                            return categoryColors[category][1];
                        }
                        return 'black';
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

        {
            const canvas = document.getElementById('sector-chart-canvas');
            const ctx = canvas.getContext('2d');
            const datasets = [{
                key: 'value',
                groups: [0, 'name'],
                tree: sectorTree,
                treeLeafKey: 'name',
                borderWidth: 0,
                spacing: 1,
                backgroundColor: function(context) {
                    if (context.type != 'data') {
                        return 'transparent';
                    }
                    const obj = context.raw._data;
                    const sector = obj[0];
                    if (obj.name) {
                        return sectorColors[sector][0] + 'D0';
                    }
                    return sectorColors[sector][0] + '40';
                },
                labels: {
                    display: true,
                    padding: labelPadding,
                    formatter: function(context) {
                        const rawObj = context.raw._data;
                        const obj = sectorTree[rawObj[0]][rawObj.name];
                        const ctx = context.chart.ctx;
                        const zoom = context.chart.getZoomLevel();

                        const maxWidth =
                            context.raw.w * zoom - labelPadding * 2;
                        const font = Chart.helpers.toFont(ctx.font);
                        const maxLines = Math.floor(
                            (context.raw.h * zoom - labelPadding * 2) /
                            font.lineHeight);

                        let lines = [
                            obj.ticker,
                            obj.name,
                            (obj.weight == 100) ? null :
                                                  obj.weight.toFixed(2) + '%',
                            formatterF2.format(obj.value),
                        ];
                        return word_wrap(lines, maxWidth, maxLines, ctx);
                    },
                    color: function(context) {
                        const obj = context.raw._data;
                        if (obj.name) {
                            const sector = obj[0];
                            return sectorColors[sector][1];
                        }
                        return 'black';
                    },
                }
            }];
            if (this.chartSector && ctx == this.chartSector.ctx) {
                nummusChart.updateTree(this.chartSector, datasets);
            } else {
                const callbacks = {
                    label: function(context) {
                        const obj = context.raw._data;
                        const sector = obj[0];
                        const label = obj.name || sector;
                        const value = formatterF2.format(obj.value);
                        if (obj.name) {
                            const weight = sectorTree[sector][obj.name].weight;
                            return `${label} (${weight.toFixed(2)}%): ${value}`;
                        }
                        return `${label}: ${value}`;
                    }
                };
                this.chartSector = nummusChart.createTree(
                    ctx,
                    datasets,
                    null,
                    {plugins: {tooltip: {callbacks: callbacks}}},
                );
            }
        }
    },
}
