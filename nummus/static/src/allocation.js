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
        const categoryTree = [];
        const categoryColors = {};
        const categoryEntries = Object.entries(rawCategories);
        categoryEntries.forEach(([category, assets], i) => {
            const color = getChartColor(i, 360 / categoryEntries.length);
            categoryColors[category] =
                [color, tinycolor(color).isDark() ? 'white' : 'black'];
            assets.forEach((asset) => {
                categoryTree.push({
                    category: category,
                    name: asset.name,
                    value: Number(asset.value),
                });
            });
        });

        const sectorTree = [];
        const sectorColors = {};
        const sectorWeights = {};
        const sectorEntries = Object.entries(rawSectors);
        sectorEntries.forEach(([sector, assets], i) => {
            const color = getChartColor(i, 360 / sectorEntries.length);
            sectorColors[sector] =
                [color, tinycolor(color).isDark() ? 'white' : 'black'];
            sectorWeights[sector] = {};
            assets.forEach((asset) => {
                const weight = Number(asset.weight);
                sectorWeights[sector][asset.name] = weight;
                sectorTree.push({
                    sector: sector,
                    name: asset.name,
                    weight: weight,
                    value: Number(asset.value),
                });
            });
        });

        const labelPadding = 2;

        function word_wrap(label, maxWidth, ctx) {
            const words = label.split(' ');
            const lines = [];
            let currentLine = null;
            for (const word of words) {
                const newLine = currentLine ? currentLine + ' ' + word : word;
                const width = ctx.chart.ctx.measureText(newLine).width;
                if (width < maxWidth) {
                    currentLine = newLine;
                } else if (currentLine) {
                    const wordWidth = ctx.chart.ctx.measureText(word).width;
                    if (wordWidth >= maxWidth) {
                        return lines;
                    }

                    lines.push(currentLine);
                    currentLine = word;
                } else {
                    // word alone doesn't fit
                    return lines;
                }
            }
            if (currentLine) {
                lines.push(currentLine);
            }
            return lines;
        }

        {
            const canvas = document.getElementById('allocation-chart-canvas');
            const ctx = canvas.getContext('2d');
            const datasets = [{
                key: 'value',
                groups: ['category', 'name'],
                tree: categoryTree,
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
                        return categoryColors[obj.category][0] + 'D0';
                    }
                    return categoryColors[obj.category][0] + '40';
                },
                labels: {
                    display: true,
                    padding: labelPadding,
                    formatter: function(context) {
                        const obj = context.raw._data;
                        const maxWidth = context.raw.w - labelPadding * 2;
                        const font =
                            Chart.helpers.toFont(context.chart.ctx.font);
                        const maxLines = Math.floor(
                            (context.raw.h - labelPadding * 2) /
                            font.lineHeight);
                        let lines = word_wrap(obj.name, maxWidth, context);
                        const strValue = formatterF2.format(obj.value);
                        if (context.chart.ctx.measureText(strValue).width <
                            maxWidth) {
                            lines.push(strValue);
                        }
                        return lines.slice(0, maxLines);
                    },
                    color: function(context) {
                        const obj = context.raw._data;
                        if (obj.name) {
                            return categoryColors[obj.category][1];
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
                groups: ['sector', 'name'],
                tree: sectorTree,
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
                        return sectorColors[obj.sector][0] + 'D0';
                    }
                    return sectorColors[obj.sector][0] + '40';
                },
                labels: {
                    display: true,
                    padding: labelPadding,
                    formatter: function(context) {
                        const obj = context.raw._data;
                        const weight =
                            sectorWeights[obj.sector][obj.name] * 100;
                        const maxWidth = context.raw.w - labelPadding * 2;
                        const font =
                            Chart.helpers.toFont(context.chart.ctx.font);
                        const maxLines = Math.floor(
                            (context.raw.h - labelPadding * 2) /
                            font.lineHeight);
                        let lines = word_wrap(obj.name, maxWidth, context);
                        const strValue = formatterF2.format(obj.value);
                        if (lines.length > 0 && lines.length < maxLines &&
                            context.chart.ctx.measureText(strValue).width <
                                maxWidth) {
                            lines.push(strValue);
                        }
                        return lines.slice(0, maxLines);
                    },
                    color: function(context) {
                        const obj = context.raw._data;
                        if (obj.name) {
                            return sectorColors[obj.sector][1];
                        }
                        return 'black';
                    },
                }
            }];
            if (this.chartSector && ctx == this.chartSector.ctx) {
                nummusChart.updateTree(this.chartSector, datasets);
            } else {
                this.chartSector = nummusChart.createTree(
                    ctx,
                    datasets,
                    null,
                    {
                        plugins: {
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const obj = context.raw._data;
                                        const label = obj.name || obj.sector;
                                        const value =
                                            formatterF2.format(obj.value);
                                        if (obj.name) {
                                            const weight =
                                                sectorWeights[obj.sector][obj.name] *
                                                100;
                                            return `${label} (${
                                                weight.toFixed(2)}%): ${value}`;
                                        }
                                        return `${label}: ${value}`;
                                    }
                                },
                            }
                        }
                    },
                );
            }
        }
    },
}
