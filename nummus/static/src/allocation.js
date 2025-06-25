"use strict";
const allocation = {
  chartCategory: null,
  chartSector: null,
  /**
   * Create Allocation Chart
   *
   * @param {Object} raw Raw data from allocation controller
   */
  update: function (raw) {
    const categories = raw.categories;
    const sectors = raw.sectors;

    const categoryTree = {};
    const categoryEntries = Object.entries(categories);
    categoryEntries.forEach(([category, assets], i) => {
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
    const sectorEntries = Object.entries(sectors);
    sectorEntries.forEach(([sector, assets], i) => {
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

    {
      const canvas = htmx.find("#category-chart-canvas");
      const ctx = canvas.getContext("2d");
      const datasets = [
        {
          key: "value",
          groups: [0, "name"],
          tree: categoryTree,
          treeLeafKey: "name",
          borderWidth: 2,
          spacing: 2,
          borderRadius: function (context) {
            if (!context.raw) {
              return 0;
            }
            const zoom = context.chart.getZoomLevel();
            const size = Math.min(context.raw.w, context.raw.h) * zoom;
            return Math.min(8, size * 0.2);
          },
        },
      ];
      if (this.chartCategory) {
        this.chartCategory.destroy();
      }
      this.chartCategory = nummusChart.createTree(ctx, datasets);
    }

    {
      const canvas = htmx.find("#sector-chart-canvas");
      const ctx = canvas.getContext("2d");
      const datasets = [
        {
          key: "value",
          groups: [0, "name"],
          tree: sectorTree,
          treeLeafKey: "name",
          borderWidth: 2,
          spacing: 2,
          borderRadius: function (context) {
            if (!context.raw) {
              return 0;
            }
            const zoom = context.chart.getZoomLevel();
            const size = Math.min(context.raw.w, context.raw.h) * zoom;
            return Math.min(8, size * 0.2);
          },
        },
      ];
      if (this.chartSector) {
        this.chartSector.destroy();
      }
      const callbacks = {
        label: function (context) {
          const obj = context.raw._data;
          const sector = obj[0];
          const label = obj.name || sector;
          const value = formatterF2.format(obj.value);
          if (obj.name) {
            const weight = sectorTree[sector][obj.name].weight;
            return `${label} (${weight.toFixed(2)}%): ${value}`;
          }
          return `${label}: ${value}`;
        },
      };
      this.chartSector = nummusChart.createTree(ctx, datasets, null, {
        plugins: { tooltip: { callbacks: callbacks } },
      });
    }
  },
};
