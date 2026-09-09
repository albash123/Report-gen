/* Workbook data is JSON-serialized by Jinja's tojson filter, never executable source. */
(function () {
  'use strict';
  const dataElement = document.getElementById('chart-data');
  if (dataElement && typeof Chart !== 'undefined') {
    const data = JSON.parse(dataElement.textContent);
    Chart.defaults.font.family = 'Arial, Helvetica, sans-serif';
    Chart.defaults.color = '#53616c';
    const weekly = document.getElementById('weekly-chart');
    const mix = document.getElementById('status-chart');
    if (weekly) new Chart(weekly, {
      type: 'bar',
      data: {labels: data.projects.labels, datasets: [{label: 'Weekly completion %', data: data.projects.values, backgroundColor: '#245c73', barThickness: 11}]},
      options: {indexAxis: 'y', animation: false, responsive: true, maintainAspectRatio: false,
        plugins: {legend: {display: false}},
        scales: {x: {min: 0, max: 100, ticks: {callback: value => value + '%'}, grid: {color: '#edf0f2'}}, y: {grid: {display: false}, ticks: {font: {size: 10}, autoSkip: false}}}}
    });
    if (mix) new Chart(mix, {
      type: 'doughnut',
      data: {labels: data.status.labels, datasets: [{data: data.status.values, backgroundColor: data.status.colors, borderWidth: 2, borderColor: '#fff'}]},
      options: {animation: false, responsive: true, maintainAspectRatio: false, cutout: '65%', plugins: {legend: {position: 'bottom', labels: {boxWidth: 10, font: {size: 11}}}}}
    });
  }
  let originalDetails = [];
  const beforePrint = () => {
    if (originalDetails.length) return;
    originalDetails = Array.from(document.querySelectorAll('details'), element => [element, element.open]);
    originalDetails.forEach(([element]) => {element.open = true;});
    if (typeof Chart !== 'undefined') Object.values(Chart.instances).forEach(chart => chart.resize());
  };
  const afterPrint = () => {
    originalDetails.forEach(([element, open]) => {element.open = open;});
    originalDetails = [];
    if (typeof Chart !== 'undefined') Object.values(Chart.instances).forEach(chart => chart.resize());
  };
  window.addEventListener('beforeprint', beforePrint);
  window.addEventListener('afterprint', afterPrint);
  document.getElementById('print-report')?.addEventListener('click', () => {beforePrint(); window.print();});
  document.getElementById('expand-tasks')?.addEventListener('click', () => {
    const sections = Array.from(document.querySelectorAll('details.tasks'));
    const expand = sections.some(element => !element.open);
    sections.forEach(element => {element.open = expand;});
    document.getElementById('expand-tasks').textContent = expand ? 'Collapse task log' : 'Expand task log';
  });
}());
