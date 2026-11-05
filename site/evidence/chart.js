// chart.js: hover readout for the simplicity chart on evidence/index.html and the home page.
// Pointing at a stage draws a crosshair and shows that stage's two values; Escape or leaving the
// chart hides them. The home page carries a wide and a compact copy of the chart and CSS shows one,
// so each copy gets its own crosshair. The table under the chart carries the same numbers, so the
// page reads fully without this file.
(function () {
  var plot = document.querySelector('.chart-plot');
  if (!plot) return;
  var tip = plot.querySelector('.chart-tip');
  var svgs = plot.querySelectorAll('svg');

  function show(svg, hit) {
    var cross = svg.querySelector('.cross');
    var x = hit.getAttribute('data-x');
    cross.setAttribute('x1', x);
    cross.setAttribute('x2', x);
    cross.classList.add('on');
    tip.innerHTML =
      '<b>Stage ' + hit.getAttribute('data-stage') + '</b>' +
      '<span><span class="key consult"></span>With Consult ' + hit.getAttribute('data-consult') + '</span>' +
      '<span><span class="key bare"></span>Without ' + hit.getAttribute('data-bare') + '</span>';
    var left = (Number(x) / svg.viewBox.baseVal.width) * svg.getBoundingClientRect().width;
    var flip = left > plot.clientWidth / 2;
    tip.style.left = flip ? '' : left + 12 + 'px';
    tip.style.right = flip ? plot.clientWidth - left + 12 + 'px' : '';
    tip.classList.add('on');
  }

  function hide() {
    Array.prototype.forEach.call(svgs, function (svg) {
      svg.querySelector('.cross').classList.remove('on');
    });
    tip.classList.remove('on');
  }

  Array.prototype.forEach.call(svgs, function (svg) {
    Array.prototype.forEach.call(svg.querySelectorAll('.hit'), function (hit) {
      hit.addEventListener('pointerenter', function () { show(svg, hit); });
    });
    svg.addEventListener('pointerleave', hide);
  });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') hide();
  });
})();
